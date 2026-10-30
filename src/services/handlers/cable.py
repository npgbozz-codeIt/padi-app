# src/services/handlers/cable.py
import re
import json
import logging
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.cable_pricing import cable_pricing_config
from src.database.redis import redis_client
from src.models.transaction import TransactionStatus, TransactionType
from src.services.bigisub import bigisub_client, resolve_cable_provider
from src.services.handlers.base import BaseVendingHandler
from src.services.nlu_engine import extract_cabletv_slots
from src.services.transaction_service import TransactionService
from src.utils.ledger_guard import initialize_local_ledger
from src.utils.responses import TRANSACTION_RESPONSES

logger = logging.getLogger(__name__)

SMARTCARD_CANDIDATE = re.compile(r"\b(\d{8,14})\b")
PHONE_PATTERN = re.compile(r"^(0[789][01]\d{8}|234[789][01]\d{8})$")
AMOUNT_PATTERN = re.compile(r"(?:₦|ngn|n)?\s?\b(\d{3,6})\b", re.IGNORECASE)

CABLE_LABELS = {
    "dstv": "DStv",
    "gotv": "GOtv",
    "startimes": "StarTimes",
    "showmax": "Showmax",
}

BOUQUET_KEYWORDS = [
    "compact plus", "compact", "confam", "yanga", "padi", "premium", "asia", "great wall",
    "supa plus", "supa", "max", "jolli", "jinja", "smallie",
    "super", "classic", "smart", "basic", "nova",
]

FALLBACK_CABLE_PLANS: Dict[str, List[Dict[str, Any]]] = {
    "dstv": [
        {"product_name": "DStv Padi", "variation_code": "dstv-padi", "amount": 4400},
        {"product_name": "DStv Yanga", "variation_code": "dstv-yanga", "amount": 6000},
        {"product_name": "DStv Confam", "variation_code": "dstv-confam", "amount": 11000},
        {"product_name": "DStv Compact", "variation_code": "dstv-compact", "amount": 19000},
        {"product_name": "DStv Compact Plus", "variation_code": "dstv-compact-plus", "amount": 30000},
        {"product_name": "DStv Premium", "variation_code": "dstv-premium", "amount": 44500},
    ],
    "gotv": [
        {"product_name": "GOtv Smallie", "variation_code": "gotv-smallie", "amount": 1575},
        {"product_name": "GOtv Jinja", "variation_code": "gotv-jinja", "amount": 3300},
        {"product_name": "GOtv Jolli", "variation_code": "gotv-jolli", "amount": 4850},
        {"product_name": "GOtv Max", "variation_code": "gotv-max", "amount": 7200},
        {"product_name": "GOtv Supa", "variation_code": "gotv-supa", "amount": 9600},
        {"product_name": "GOtv Supa Plus", "variation_code": "gotv-supa-plus", "amount": 15700},
    ],
    "startimes": [
        {"product_name": "StarTimes Nova", "variation_code": "nova", "amount": 1900},
        {"product_name": "StarTimes Basic", "variation_code": "basic", "amount": 3700},
        {"product_name": "StarTimes Smart", "variation_code": "smart", "amount": 4700},
        {"product_name": "StarTimes Classic", "variation_code": "classic", "amount": 5500},
        {"product_name": "StarTimes Super", "variation_code": "super", "amount": 9000},
    ],
}


def _md_escape(text: Any) -> str:
    """Escapes Telegram legacy-Markdown control chars in vendor-supplied text."""
    return re.sub(r"([_*`\[])", r"\\\1", str(text or ""))


def calculate_cable_fee(amount: Decimal) -> Decimal:
    """Decimal-safe convenience fee for Cable TV subscriptions via cable_pricing_config."""
    fee_type = cable_pricing_config.FEE_TYPE.lower()
    fee_value = Decimal(str(cable_pricing_config.FEE_VALUE))
    if fee_type == "fixed":
        return fee_value.quantize(Decimal("0.01"))
    return (amount * fee_value).quantize(Decimal("1"), rounding=ROUND_CEILING)


async def get_provider_plans(provider: str) -> List[Dict[str, Any]]:
    """Fetches cable plans for a provider with 12-hour Redis caching and static fallback."""
    cache_key = f"cable_plans:{provider}"
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            parsed = json.loads(cached)
            if isinstance(parsed, list) and parsed:
                return parsed
    except Exception:
        pass

    res = await bigisub_client.fetch_cable_plans(provider)
    plans = res.get("plans") or []
    if plans:
        try:
            await redis_client.set(cache_key, json.dumps(plans), ex=43200)
        except Exception:
            pass
        return plans

    return FALLBACK_CABLE_PLANS.get(provider, [])


def match_cable_plan(
    plans: List[Dict[str, Any]],
    bouquet_query: Optional[str],
    amount_query: Optional[Any],
    current_bouquet: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Matches a user's bouquet name, variation_code, or amount to a specific BigiSub plan."""
    if not plans:
        return None

    # 1. Explicit amount match
    if amount_query:
        try:
            target_amt = int(Decimal(str(amount_query)))
            for p in plans:
                if int(Decimal(str(p.get("amount", 0)))) == target_amt:
                    return p
        except Exception:
            pass

    # 2. Bouquet name / variation_code match
    query = (bouquet_query or "").strip().lower()
    if query in ("renew", "renewal", "same", "current") and current_bouquet:
        query = current_bouquet.strip().lower()

    if query:
        for p in plans:
            v_code = str(p.get("variation_code", "")).lower()
            p_name = str(p.get("product_name", "")).lower()
            if query == v_code or query == p_name:
                return p
        candidates = []
        for p in plans:
            v_code = str(p.get("variation_code", "")).lower()
            p_name = str(p.get("product_name", "")).lower()
            if query in v_code or query in p_name:
                candidates.append(p)
        if candidates:
            candidates.sort(key=lambda x: len(str(x.get("product_name", ""))))
            return candidates[0]

    return None


def format_plan_choices(provider: str, plans: List[Dict[str, Any]], limit: int = 8) -> str:
    """Formats a concise list of popular bouquets and prices for user selection."""
    label = CABLE_LABELS.get(provider, provider.upper())
    lines = [f"📺 *Available {label} Bouquets:*"]
    for p in plans[:limit]:
        name = _md_escape(p.get("product_name") or p.get("variation_code"))
        amt = Decimal(str(p.get("amount", 0)))
        lines.append(f"• *{name}* — ₦{amt:,.2f}")
    lines.append("\nReply with the *bouquet name* (e.g. _DStv Yanga_, _GOtv Jolli_) or *amount*:")
    return "\n".join(lines)


class CableHandler(BaseVendingHandler):
    intent_name = "cable"
    required_slots = ["provider", "smartcard_number"]
    requires_pre_verification = True

    def get_missing_slot_prompt(self, missing_slot: str, user_lang: str) -> str:
        prompts = {
            "provider": {
                "english": "📺 Which Cable TV provider would you like to pay for?\n_Reply with DStv, GOtv, or StarTimes._",
                "pidgin": "📺 Which Cable TV you wan pay for, boss?\n_Reply with DStv, GOtv, or StarTimes._",
                "hausa": "📺 Wane kamfanin Cable TV kuke son biya?\n_Zaɓi DStv, GOtv, ko StarTimes._",
            },
            "smartcard_number": {
                "english": "🔢 Please enter your *Smartcard / IUC number* (minimum 8 digits).",
                "pidgin": "🔢 Abeg drop your *Smartcard / IUC number* (at least 8 digits).",
                "hausa": "🔢 Da fatan za a shigar da lambar *Smartcard / IUC* ɗinku.",
            },
            "bouquet": {
                "english": "📦 Which bouquet/package or amount would you like to subscribe to? (e.g. _DStv Yanga_, _GOtv Jolli_, or _renew_)",
                "pidgin": "📦 Which package or amount you wan subscribe? (e.g. _DStv Yanga_, _GOtv Jolli_, or _renew_)",
                "hausa": "📦 Wane fakiti ko nawa kuke son biya? (misali _DStv Yanga_, _GOtv Jolli_)",
            },
        }
        slot_dict = prompts.get(missing_slot, {})
        return slot_dict.get(user_lang, slot_dict.get("english", f"Please provide the {missing_slot}."))

    async def extract_slots(self, text: str, current_slots: Dict[str, Any]) -> Dict[str, Any]:
        merged = current_slots.copy() if current_slots else {}
        clean_text = text.strip()
        lower_text = clean_text.lower()
        residual = clean_text

        # 1. Deterministic regex parsing (smartcard vs phone disambiguation)
        for candidate in SMARTCARD_CANDIDATE.findall(clean_text):
            residual = residual.replace(candidate, " ")
            if PHONE_PATTERN.match(candidate) and len(candidate) == 11:
                merged.setdefault("phone_number", candidate)
                continue
            merged["smartcard_number"] = candidate

        provider = resolve_cable_provider(lower_text)
        if provider:
            merged["provider"] = provider

        for kw in BOUQUET_KEYWORDS:
            if re.search(rf"\b{re.escape(kw)}\b", lower_text):
                merged["bouquet"] = kw
                break

        if not merged.get("bouquet") and any(w in lower_text for w in ("renew", "renewal", "same plan")):
            merged["bouquet"] = "renew"

        amount_match = AMOUNT_PATTERN.search(residual)
        if amount_match:
            val = int(amount_match.group(1))
            if val >= 500:
                merged["amount"] = val

        # 2. LLM extraction fills anything regex missed
        try:
            extracted = await extract_cabletv_slots(clean_text)
            if extracted:
                if getattr(extracted, "provider", None) and not merged.get("provider"):
                    llm_prov = resolve_cable_provider(extracted.provider)
                    if llm_prov:
                        merged["provider"] = llm_prov
                card = re.sub(r"\D", "", str(getattr(extracted, "smartcard_number", "") or ""))
                if (
                    card
                    and len(card) >= 8
                    and not (len(card) == 11 and PHONE_PATTERN.match(card))
                    and not merged.get("smartcard_number")
                ):
                    merged["smartcard_number"] = card
                if getattr(extracted, "bouquet", None) and not merged.get("bouquet"):
                    merged["bouquet"] = str(extracted.bouquet).strip()
                if getattr(extracted, "amount", None) and not merged.get("amount"):
                    merged["amount"] = int(extracted.amount)
                if getattr(extracted, "types", None) == "renewal" and not merged.get("bouquet"):
                    merged["bouquet"] = "renew"
        except Exception as exc:
            logger.warning(f"Cable NLU extraction skipped: {exc}")

        return merged

    async def execute(self, db: AsyncSession, profile: Any, slots: Dict[str, Any]) -> Dict[str, Any]:
        user_lang = profile.lang or "english"
        tx_copy = TRANSACTION_RESPONSES.get(user_lang, TRANSACTION_RESPONSES["english"])

        provider = resolve_cable_provider(slots.get("provider"))
        smartcard_number = re.sub(r"\D", "", str(slots.get("smartcard_number") or ""))

        if not provider:
            return {
                "status": "retry_slot",
                "missing_slot": "provider",
                "slots": {**slots, "provider": None},
                "message": self.get_missing_slot_prompt("provider", user_lang),
            }

        if len(smartcard_number) < 8:
            return {
                "status": "retry_slot",
                "missing_slot": "smartcard_number",
                "slots": {**slots, "smartcard_number": None},
                "message": "❌ That smartcard/IUC number looks invalid (minimum 8 digits).\n\n"
                + self.get_missing_slot_prompt("smartcard_number", user_lang),
            }

        provider_label = CABLE_LABELS.get(provider, provider.upper())

        # ---------------- PHASE A: Verify smartcard & resolve plan before confirmation ----------------
        if not slots.get("smartcard_verified"):
            customer_name = slots.get("customer_name")
            current_bouquet = slots.get("current_bouquet")
            if not customer_name:
                verify_res = await bigisub_client.verify_smartcard(smartcard_number, provider)
                if not verify_res.get("success"):
                    return {
                        "status": "retry_slot",
                        "missing_slot": "smartcard_number",
                        "slots": {**slots, "smartcard_number": None},
                        "message": f"❌ *Smartcard verification failed:* {_md_escape(verify_res.get('error'))}\n\n"
                        + self.get_missing_slot_prompt("smartcard_number", user_lang),
                    }
                customer_name = verify_res["customer_name"]
                current_bouquet = verify_res.get("current_bouquet")

            plans = await get_provider_plans(provider)
            matched_plan = match_cable_plan(
                plans=plans,
                bouquet_query=slots.get("bouquet"),
                amount_query=slots.get("amount"),
                current_bouquet=current_bouquet,
            )

            if not matched_plan:
                partial_slots = {
                    **slots,
                    "provider": provider,
                    "smartcard_number": smartcard_number,
                    "customer_name": customer_name,
                    "current_bouquet": current_bouquet,
                    "bouquet": None,
                    "amount": None,
                }
                header = (
                    f"✅ *Smartcard Verified*\n"
                    f"• *Customer:* {_md_escape(customer_name)}\n"
                    f"• *Current Bouquet:* {_md_escape(current_bouquet or 'N/A')}\n\n"
                )
                return {
                    "status": "retry_slot",
                    "missing_slot": "bouquet",
                    "slots": partial_slots,
                    "message": header + format_plan_choices(provider, plans),
                }

            plan_name = matched_plan.get("product_name") or matched_plan.get("variation_code")
            plan_code = matched_plan.get("variation_code") or str(matched_plan.get("id") or plan_name)
            plan_amount = Decimal(str(matched_plan.get("amount"))).quantize(Decimal("0.01"))
            fee = calculate_cable_fee(plan_amount)
            total_debit = plan_amount + fee

            verified_slots = {
                **slots,
                "provider": provider,
                "smartcard_number": smartcard_number,
                "customer_name": customer_name,
                "current_bouquet": current_bouquet,
                "plan_id": plan_code,
                "plan_name": plan_name,
                "amount": str(plan_amount),
                "smartcard_verified": True,
            }

            lines = [
                f"📺 *Confirm {provider_label} Subscription*",
                "──────────────────────────",
                f"• *Customer:* {_md_escape(customer_name)}",
                f"• *Smartcard / IUC:* `{smartcard_number}`",
            ]
            if current_bouquet:
                lines.append(f"• *Current Bouquet:* {_md_escape(current_bouquet)}")
            lines.extend([
                f"• *Selected Package:* {_md_escape(plan_name)}",
                f"• *Package Price:* ₦{plan_amount:,.2f}",
            ])
            if fee > Decimal("0.00"):
                lines.append(f"• *Convenience Fee:* ₦{fee:,.2f}")
            lines.extend([
                f"• *Total Debit:* *₦{total_debit:,.2f}*",
                "──────────────────────────",
                "⚠️ Make sure the customer name matches your decoder.",
                "Reply *YES* to confirm or *NO* to cancel.",
            ])
            return {"status": "awaiting_confirmation", "message": "\n".join(lines), "slots": verified_slots}

        # ---------------- PHASE B: Atomic ledger stage -> vend_cable -> commit ----------------
        customer_name = slots.get("customer_name")
        plan_id = slots.get("plan_id")
        plan_name = slots.get("plan_name") or str(plan_id)
        phone_number = slots.get("phone_number") or profile.phone_num or "08000000000"

        if not customer_name or not plan_id:
            return {"status": "error", "message": "❌ Smartcard verification expired. Please start again."}

        plan_amount = Decimal(str(slots.get("amount") or "0")).quantize(Decimal("0.01"))
        fee = calculate_cable_fee(plan_amount)
        total_debit = plan_amount + fee

        cleared, local_tx = await initialize_local_ledger(
            db=db,
            profile=profile,
            amount=total_debit,
            recipient=smartcard_number,
            tx_type=TransactionType.CABLETV,
            provider=provider_label,
        )
        if not cleared or not local_tx:
            return {
                "status": "error",
                "message": tx_copy["insufficient_funds"].format(
                    balance=f"{(profile.user_wallet or Decimal('0.00')):,.2f}"
                ),
            }

        try:
            vend_res = await bigisub_client.vend_cable(
                smartcard_number=smartcard_number,
                plan_id=plan_id,
                provider=provider,
                amount=plan_amount,
                customer_name=customer_name,
                phone_number=phone_number,
            )
        except Exception as exc:
            logger.error(f"🚨 Unexpected cable vend exception: {exc}")
            vend_res = {"success": False, "error": "Unexpected gateway error.", "timeout": True}

        # ---------------- SUCCESS ----------------
        if vend_res.get("success") is True:
            vendor_tx_id = vend_res.get("transaction_id")
            resolved_plan_name = vend_res.get("plan_name") or plan_name

            local_tx.status = TransactionStatus.SUCCESSFUL
            local_tx.balance_after = profile.user_wallet
            local_tx.token_or_details = str(resolved_plan_name)
            await db.commit()

            receipt_msg = TransactionService.format_receipt(
                txn=local_tx,
                service_label=f"{provider_label} Subscription",
                detail_label="Package",
            )
            receipt_msg += f"\n\n👤 *Customer:* {_md_escape(customer_name)}"

            receipt_markup = {
                "inline_keyboard": [
                    [{"text": "🖼️ Download Image Receipt", "callback_data": f"rx_img:{local_tx.reference}"}]
                ]
            }

            alert_details = {
                "User": profile.user_tag,
                "Provider": provider_label,
                "Smartcard": smartcard_number,
                "Customer": customer_name,
                "Package": resolved_plan_name,
                "Amount": f"₦{plan_amount:,.2f}",
                "Fee": f"₦{fee:,.2f}",
                "Ref": local_tx.reference,
            }
            if vendor_tx_id:
                alert_details["Vendor Ref"] = vendor_tx_id

            await TransactionService.dispatch_admin_alert(
                event_title="Cable TV Subscribed", details=alert_details, level="INFO"
            )
            return {"status": "success", "message": receipt_msg, "reply_markup": receipt_markup}

        failed_reason = vend_res.get("error", tx_copy.get("vending_failed", "Gateway error"))

        # ---------------- AMBIGUOUS (timeout) -> keep PENDING, no auto-refund ----------------
        if vend_res.get("timeout"):
            local_tx.status = TransactionStatus.PENDING
            local_tx.token_or_details = f"{plan_name} (AWAITING CONFIRMATION)"
            await db.commit()

            await TransactionService.dispatch_admin_alert(
                event_title="Cable TV Vend Pending — Manual Requery Required",
                details={
                    "User": profile.user_tag,
                    "Provider": provider_label,
                    "Smartcard": smartcard_number,
                    "Customer": customer_name,
                    "Package": plan_name,
                    "Debited": f"₦{total_debit:,.2f}",
                    "Ref": local_tx.reference,
                    "Error": failed_reason,
                },
                level="WARNING",
            )
            return {
                "status": "pending",
                "message": (
                    "⏳ *Cable Subscription Processing*\n\n"
                    "The provider gateway is responding slowly, so we're confirming your subscription manually.\n"
                    f"• Reference: `{local_tx.reference}`\n"
                    f"• Amount Held: ₦{total_debit:,.2f}\n\n"
                    "Your decoder will be activated once confirmed. If it fails, your wallet will be fully refunded."
                ),
            }

        # ---------------- DEFINITE FAILURE -> atomic Decimal refund ----------------
        profile.user_wallet = (profile.user_wallet or Decimal("0.00")) + total_debit
        local_tx.status = TransactionStatus.FAILED
        local_tx.balance_after = profile.user_wallet
        await db.commit()

        await TransactionService.dispatch_admin_alert(
            event_title="Cable TV Subscription Failed",
            details={
                "User": profile.user_tag,
                "Provider": provider_label,
                "Smartcard": smartcard_number,
                "Package": plan_name,
                "Amount": f"₦{total_debit:,.2f}",
                "Ref": local_tx.reference,
                "Error": failed_reason,
            },
            level="ERROR",
        )
        return {
            "status": "error",
            "message": f"❌ Cable Subscription Failed: {_md_escape(failed_reason)}\n"
            f"• Reference: `{local_tx.reference}`\n\nYour wallet has been refunded.",
        }
