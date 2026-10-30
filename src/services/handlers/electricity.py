# src/services/handlers/electricity.py
import re
import logging
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.electricity_pricing import electricity_pricing_config
from src.models.transaction import TransactionStatus, TransactionType
from src.services.bigisub import (
    DISCO_SHORT_NAMES,
    bigisub_client,
    get_disco_min_amount,
    resolve_disco_code,
)
from src.services.handlers.base import BaseVendingHandler
from src.services.nlu_engine import extract_electricity_slots
from src.services.transaction_service import TransactionService
from src.utils.ledger_guard import initialize_local_ledger
from src.utils.responses import TRANSACTION_RESPONSES

logger = logging.getLogger(__name__)

METER_CANDIDATE = re.compile(r"\b(\d{10,15})\b")
PHONE_PATTERN = re.compile(r"^(0[789][01]\d{8}|234[789][01]\d{8})$")
AMOUNT_PATTERN = re.compile(r"(?:₦|ngn|n)?\s?\b(\d{3,7})\b", re.IGNORECASE)


def _md_escape(text: Any) -> str:
    """Escapes Telegram legacy-Markdown control chars in vendor-supplied text."""
    return re.sub(r"([_*`\[])", r"\\\1", str(text or ""))


def calculate_convenience_fee(amount: Decimal) -> Decimal:
    """Decimal-safe convenience fee (covers BigiSub's per-vend service charge)."""
    fee_type = electricity_pricing_config.FEE_TYPE.lower()
    fee_value = Decimal(str(electricity_pricing_config.FEE_VALUE))
    if fee_type == "fixed":
        return fee_value.quantize(Decimal("0.01"))
    return (amount * fee_value).quantize(Decimal("1"), rounding=ROUND_CEILING)


class ElectricityHandler(BaseVendingHandler):
    intent_name = "electricity"
    required_slots = ["disco", "meter_number", "amount"]
    # Pipeline calls execute() once BEFORE the YES/PIN step to verify the meter.
    requires_pre_verification = True

    def get_missing_slot_prompt(self, missing_slot: str, user_lang: str) -> str:
        prompts = {
            "disco": {
                "english": "⚡ Which electricity company (DisCo) is this for?\n_e.g. IKEDC, EKEDC, AEDC, IBEDC, PHED, KEDCO, EEDC_",
                "pidgin": "⚡ Which light company be dis, boss?\n_e.g. IKEDC, EKEDC, AEDC, IBEDC, PHED, KEDCO, EEDC_",
                "hausa": "⚡ Wane kamfanin wutar lantarki ne?\n_misali IKEDC, EKEDC, AEDC, KEDCO, KAEDCO, JED_",
            },
            "meter_number": {
                "english": "🔢 Please enter your meter number (10–15 digits).",
                "pidgin": "🔢 Abeg drop your meter number (10–15 digits).",
                "hausa": "🔢 Da fatan za a shigar da lambar mita (lambobi 10–15).",
            },
            "amount": {
                "english": "💰 How much electricity would you like to buy? (e.g. 5000)",
                "pidgin": "💰 How much light you wan buy? (e.g. 5000)",
                "hausa": "💰 Nawa kuke son saya na wutar lantarki? (misali 5000)",
            },
        }
        slot_dict = prompts.get(missing_slot, {})
        return slot_dict.get(user_lang, slot_dict.get("english", f"Please provide the {missing_slot}."))

    async def extract_slots(self, text: str, current_slots: Dict[str, Any]) -> Dict[str, Any]:
        merged = current_slots.copy() if current_slots else {}
        clean_text = text.strip()
        lower_text = clean_text.lower()
        residual = clean_text

        # 1. Deterministic regex parsing (meter vs phone disambiguation)
        for candidate in METER_CANDIDATE.findall(clean_text):
            residual = residual.replace(candidate, " ")
            if PHONE_PATTERN.match(candidate):
                merged.setdefault("phone_number", candidate)
                continue
            merged["meter_number"] = candidate

        disco_code = resolve_disco_code(lower_text)
        if disco_code:
            merged["disco"] = disco_code

        if "postpaid" in lower_text:
            merged["meter_type"] = "postpaid"
        elif "prepaid" in lower_text:
            merged["meter_type"] = "prepaid"

        amount_match = AMOUNT_PATTERN.search(residual)
        if amount_match:
            merged["amount"] = int(amount_match.group(1))

        # 2. LLM extraction fills anything regex missed
        try:
            extracted = await extract_electricity_slots(clean_text)
            if extracted:
                if getattr(extracted, "amount", None) and not merged.get("amount"):
                    merged["amount"] = int(extracted.amount)
                if getattr(extracted, "company", None) and not merged.get("disco"):
                    llm_code = resolve_disco_code(extracted.company)
                    if llm_code:
                        merged["disco"] = llm_code
                meter_no = re.sub(r"\D", "", str(getattr(extracted, "meter_no", "") or ""))
                if (
                    meter_no
                    and 10 <= len(meter_no) <= 15
                    and not PHONE_PATTERN.match(meter_no)
                    and not merged.get("meter_number")
                ):
                    merged["meter_number"] = meter_no
                if getattr(extracted, "phone_number", None) and not merged.get("phone_number"):
                    merged["phone_number"] = str(extracted.phone_number)
        except Exception as exc:
            logger.warning(f"Electricity NLU extraction skipped: {exc}")

        merged.setdefault("meter_type", "prepaid")
        return merged

    async def execute(self, db: AsyncSession, profile: Any, slots: Dict[str, Any]) -> Dict[str, Any]:
        user_lang = profile.lang or "english"
        tx_copy = TRANSACTION_RESPONSES.get(user_lang, TRANSACTION_RESPONSES["english"])

        disco_code = resolve_disco_code(slots.get("disco"))
        meter_number = re.sub(r"\D", "", str(slots.get("meter_number") or ""))
        meter_type = str(slots.get("meter_type") or "prepaid").lower()
        if meter_type not in ("prepaid", "postpaid"):
            meter_type = "prepaid"

        try:
            vend_amount = Decimal(str(slots.get("amount") or "0")).quantize(Decimal("1"))
        except InvalidOperation:
            vend_amount = Decimal("0")

        if not disco_code:
            return {
                "status": "retry_slot",
                "missing_slot": "disco",
                "slots": {**slots, "disco": None},
                "message": self.get_missing_slot_prompt("disco", user_lang),
            }
        if not (10 <= len(meter_number) <= 15):
            return {
                "status": "retry_slot",
                "missing_slot": "meter_number",
                "slots": {**slots, "meter_number": None},
                "message": "❌ That meter number looks invalid.\n\n"
                + self.get_missing_slot_prompt("meter_number", user_lang),
            }

        disco_label = DISCO_SHORT_NAMES.get(disco_code, disco_code.upper())
        min_amount = get_disco_min_amount(disco_code, meter_type)
        if vend_amount < min_amount:
            return {
                "status": "retry_slot",
                "missing_slot": "amount",
                "slots": {**slots, "amount": None},
                "message": f"⚠️ Minimum {meter_type} purchase for *{disco_label}* is *₦{min_amount:,.2f}*.\n\n"
                + self.get_missing_slot_prompt("amount", user_lang),
            }

        fee = calculate_convenience_fee(vend_amount)
        total_debit = vend_amount + fee

        # ---------------- PHASE A: verify meter, suspend for confirmation ----------------
        if not slots.get("meter_verified"):
            verify_res = await bigisub_client.verify_meter(meter_number, disco_code, meter_type)
            if not verify_res.get("success"):
                return {
                    "status": "retry_slot",
                    "missing_slot": "meter_number",
                    "slots": {**slots, "meter_number": None},
                    "message": f"❌ *Meter verification failed:* {_md_escape(verify_res.get('error'))}\n\n"
                    + self.get_missing_slot_prompt("meter_number", user_lang),
                }

            customer_name = verify_res["customer_name"]
            customer_address = verify_res.get("customer_address")
            verified_slots = {
                **slots,
                "disco": disco_code,
                "meter_number": meter_number,
                "meter_type": meter_type,
                "amount": str(vend_amount),
                "customer_name": customer_name,
                "customer_address": customer_address,
                "meter_verified": True,
            }
            lines = [
                "⚡ *Confirm Electricity Payment*",
                "──────────────────────────",
                f"• *Customer:* {_md_escape(customer_name)}",
            ]
            if customer_address:
                lines.append(f"• *Address:* {_md_escape(customer_address)}")
            lines.extend([
                f"• *DisCo:* {disco_label}",
                f"• *Meter:* `{meter_number}` ({meter_type.title()})",
                f"• *Amount:* ₦{vend_amount:,.2f}",
                f"• *Convenience Fee:* ₦{fee:,.2f}",
                f"• *Total Debit:* *₦{total_debit:,.2f}*",
                "──────────────────────────",
                "⚠️ Make sure the customer name matches your meter.",
                "Reply *YES* to confirm or *NO* to cancel.",
            ])
            return {"status": "awaiting_confirmation", "message": "\n".join(lines), "slots": verified_slots}

        # ---------------- PHASE B: atomic ledger stage → vend → commit ----------------
        customer_name = slots.get("customer_name")
        phone_number = slots.get("phone_number") or profile.phone_num
        if not customer_name:
            return {"status": "error", "message": "❌ Meter verification expired. Please start the payment again."}
        if not phone_number:
            return {"status": "error", "message": "❌ A phone number is required on your profile to buy electricity."}

        cleared, local_tx = await initialize_local_ledger(
            db=db,
            profile=profile,
            amount=total_debit,
            recipient=meter_number,
            tx_type=TransactionType.ELECTRICITY,
            provider=disco_label,
        )
        if not cleared or not local_tx:
            return {
                "status": "error",
                "message": tx_copy["insufficient_funds"].format(
                    balance=f"{(profile.user_wallet or Decimal('0.00')):,.2f}"
                ),
            }

        try:
            vend_res = await bigisub_client.vend_electricity(
                meter_number=meter_number,
                amount=vend_amount,
                disco_id=disco_code,
                meter_type=meter_type,
                customer_name=customer_name,
                phone_number=phone_number,
                customer_address=slots.get("customer_address"),
            )
        except Exception as exc:
            # Outcome unknown at the vendor → treat as ambiguous (no auto-refund)
            logger.error(f"🚨 Unexpected electricity vend exception: {exc}")
            vend_res = {"success": False, "error": "Unexpected gateway error.", "timeout": True}

        # ---------------- SUCCESS ----------------
        if vend_res.get("success") is True:
            vendor_tx_id = vend_res.get("transaction_id")
            token = vend_res.get("token")
            units = vend_res.get("units")

            local_tx.status = TransactionStatus.SUCCESSFUL
            local_tx.balance_after = profile.user_wallet
            local_tx.token_or_details = str(token) if token else f"{meter_type.upper()} BILL SETTLED"
            await db.commit()

            receipt_msg = TransactionService.format_receipt(
                txn=local_tx,
                service_label=f"{disco_label} {meter_type.title()} Electricity",
                detail_label="Token" if token else "Details",
            )
            receipt_msg += f"\n\n👤 *Customer:* {_md_escape(customer_name)}"
            if units:
                receipt_msg += f"\n⚡ *Units:* {_md_escape(units)}"
            if token:
                receipt_msg += "\n\n🔑 _Enter the token above on your meter. Keep it safe — it cannot be re-issued._"

            receipt_markup = {
                "inline_keyboard": [
                    [{"text": "🖼️ Download Image Receipt", "callback_data": f"rx_img:{local_tx.reference}"}]
                ]
            }

            alert_details = {
                "User": profile.user_tag,
                "DisCo": disco_label,
                "Meter": f"{meter_number} ({meter_type})",
                "Customer": customer_name,
                "Amount": f"₦{vend_amount:,.2f}",
                "Fee": f"₦{fee:,.2f}",
                "Ref": local_tx.reference,
            }
            if vendor_tx_id:
                alert_details["Vendor Ref"] = vendor_tx_id
            if token:
                alert_details["Token"] = token
            await TransactionService.dispatch_admin_alert(
                event_title="Electricity Vended", details=alert_details, level="INFO"
            )
            return {"status": "success", "message": receipt_msg, "reply_markup": receipt_markup}

        failed_reason = vend_res.get("error", tx_copy.get("vending_failed", "Gateway error"))

        # ---------------- AMBIGUOUS (timeout) → keep PENDING, NO refund ----------------
        if vend_res.get("timeout"):
            local_tx.status = TransactionStatus.PENDING
            local_tx.token_or_details = "AWAITING VENDOR CONFIRMATION"
            await db.commit()

            await TransactionService.dispatch_admin_alert(
                event_title="Electricity Vend Pending — Manual Requery Required",
                details={
                    "User": profile.user_tag,
                    "DisCo": disco_label,
                    "Meter": f"{meter_number} ({meter_type})",
                    "Customer": customer_name,
                    "Debited": f"₦{total_debit:,.2f}",
                    "Ref": local_tx.reference,
                    "Error": failed_reason,
                    "Action": "Check BigiSub dashboard, then mark SUCCESSFUL (send token) or FAILED (refund).",
                },
                level="WARNING",
            )
            return {
                "status": "pending",
                "message": (
                    "⏳ *Electricity Payment Processing*\n\n"
                    "The DisCo gateway is responding slowly, so we're confirming your payment manually.\n"
                    f"• Reference: `{local_tx.reference}`\n"
                    f"• Amount Held: ₦{total_debit:,.2f}\n\n"
                    "You'll receive your token once confirmed. If it fails, your wallet will be fully refunded.\n"
                    "_Please do not retry this payment to avoid a double charge._"
                ),
            }

        # ---------------- DEFINITE FAILURE → atomic Decimal refund ----------------
        profile.user_wallet = (profile.user_wallet or Decimal("0.00")) + total_debit
        local_tx.status = TransactionStatus.FAILED
        local_tx.balance_after = profile.user_wallet
        await db.commit()

        await TransactionService.dispatch_admin_alert(
            event_title="Electricity Vending Failed",
            details={
                "User": profile.user_tag,
                "DisCo": disco_label,
                "Meter": meter_number,
                "Amount": f"₦{total_debit:,.2f}",
                "Ref": local_tx.reference,
                "Error": failed_reason,
            },
            level="ERROR",
        )
        return {
            "status": "error",
            "message": f"❌ Electricity Purchase Failed: {_md_escape(failed_reason)}\n"
            f"• Reference: `{local_tx.reference}`\n\nYour wallet has been refunded.",
        }
