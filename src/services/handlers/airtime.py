# src/services/handlers/airtime.py
import re
from decimal import Decimal
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.transaction import TransactionStatus, TransactionType
from src.services.bigisub import bigisub_client
from src.services.handlers.base import BaseVendingHandler
from src.services.nlu_engine import extract_airtime_slots
from src.services.transaction_service import TransactionService
from src.utils.ledger_guard import initialize_local_ledger
from src.utils.network_detector import detect_network
from src.utils.responses import TRANSACTION_RESPONSES


def normalize_network_name(net_str: Optional[str]) -> str:
    """Safely normalizes any network variant or object string into standard shortcodes."""
    if not net_str:
        return "mtn"
    val = str(net_str).lower()
    if "glo" in val:
        return "glo"
    if "airtel" in val:
        return "airtel"
    if "9mobile" in val or "mobile" in val or "etisalat" in val:
        return "9mobile"
    return "mtn"


class AirtimeHandler(BaseVendingHandler):
    intent_name = "airtime"
    required_slots = ["amount", "network", "phone_number"]

    async def extract_slots(self, text: str, current_slots: Dict[str, Any]) -> Dict[str, Any]:
        merged = current_slots.copy() if current_slots else {}
        clean_text = text.strip()

        # 1. Fallback Regex Parsing for Standalone Inputs
        phone_match = re.search(r"\b(0\d{9,10}|234\d{10})\b", clean_text)
        if phone_match:
            merged["phone_number"] = phone_match.group(1)

        if re.match(r"^\d{1,6}$", clean_text):
            val = int(clean_text)
            if val >= 10:
                merged["amount"] = val

        amount_match = re.search(r"\b(\d+)\s*(?:naira|ngn)?\b", clean_text, re.IGNORECASE)
        if amount_match and not merged.get("amount"):
            potential_amt = int(amount_match.group(1))
            if potential_amt < 1000000:
                merged["amount"] = potential_amt

        # 2. LLM / NLU Extraction
        try:
            extracted = await extract_airtime_slots(clean_text)
            if extracted:
                if getattr(extracted, "amount", None):
                    merged["amount"] = int(extracted.amount)
                if getattr(extracted, "network", None):
                    merged["network"] = normalize_network_name(extracted.network)
                if getattr(extracted, "phone_number", None):
                    merged["phone_number"] = str(extracted.phone_number)
        except Exception:
            pass

        # 3. Auto-detect network from phone prefix if missing or unnormalized
        target_phone = merged.get("phone_number")
        if target_phone:
            detected_net = detect_network(target_phone)
            if detected_net:
                merged["network"] = detected_net

        if merged.get("network"):
            merged["network"] = normalize_network_name(merged["network"])

        return merged

    async def execute(self, db: AsyncSession, profile: Any, slots: Dict[str, Any]) -> Dict[str, Any]:
        user_lang = profile.lang or "english"
        tx_copy = TRANSACTION_RESPONSES.get(user_lang, TRANSACTION_RESPONSES["english"])

        target_phone = slots.get("phone_number") or profile.phone_num
        req_amount = Decimal(str(slots.get("amount", 0)))
        req_network = normalize_network_name(slots.get("network"))

        # Check balance and register ledger entry atomically with Decimal precision
        cleared, local_tx = await initialize_local_ledger(
            db=db,
            profile=profile,
            amount=req_amount,
            recipient=target_phone,
            tx_type=TransactionType.AIRTIME,
            provider=req_network,
        )

        if not cleared or not local_tx:
            insufficient_msg = tx_copy["insufficient_funds"].format(
                balance=profile.user_wallet or Decimal("0.00")
            )
            return {"status": "error", "message": insufficient_msg}

        # Dispatch API Call to Bigisub
        vending_res = await bigisub_client.vend_airtime(
            phone=target_phone, amount=int(req_amount), network=req_network
        )

        if vending_res.get("success") is True:
            vendor_tx_id = vending_res.get("transaction_id")
            local_tx.status = TransactionStatus.SUCCESSFUL
            if not local_tx.reference:
                local_tx.reference = TransactionService.generate_reference("MP-AIR")
            local_tx.balance_after = profile.user_wallet
            local_tx.token_or_details = (
                f"{req_network.upper()} Airtime • Vendor: {vendor_tx_id}"
                if vendor_tx_id
                else f"{req_network.upper()} Airtime"
            )
            await db.commit()

            # Formatted digital text receipt
            receipt_msg = TransactionService.format_receipt(
                txn=local_tx,
                service_label=f"{req_network.upper()} Airtime",
            )

            # High-resolution image receipt action button
            receipt_markup = {
                "inline_keyboard": [
                    [
                        {
                            "text": "🖼️ Download Image Receipt",
                            "callback_data": f"rx_img:{local_tx.reference}",
                        }
                    ]
                ]
            }

            # Real-time alert to Admin Telegram
            alert_details = {
                "User": profile.user_tag,
                "Amount": f"₦{req_amount:,.2f}",
                "Recipient": target_phone,
                "Network": req_network.upper(),
                "Ref": local_tx.reference,
            }
            if vendor_tx_id:
                alert_details["Vendor Ref"] = vendor_tx_id

            await TransactionService.dispatch_admin_alert(
                event_title="Airtime Vended",
                details=alert_details,
                level="INFO",
            )

            return {
                "status": "success",
                "message": receipt_msg,
                "reply_markup": receipt_markup,
            }
        else:
            # Atomic refund using Decimal arithmetic
            profile.user_wallet = (profile.user_wallet or Decimal("0.00")) + req_amount
            local_tx.status = TransactionStatus.FAILED
            local_tx.balance_after = profile.user_wallet
            await db.commit()

            failed_reason = vending_res.get("error", tx_copy.get("vending_failed", "Gateway error"))

            await TransactionService.dispatch_admin_alert(
                event_title="Airtime Vending Failed",
                details={
                    "User": profile.user_tag,
                    "Amount": f"₦{req_amount:,.2f}",
                    "Recipient": target_phone,
                    "Network": req_network.upper(),
                    "Ref": local_tx.reference,
                    "Error": failed_reason,
                },
                level="ERROR",
            )

            return {
                "status": "error",
                "message": f"❌ Transaction Failed: {failed_reason}\n• Reference: `{local_tx.reference}`\n\nYour wallet has been refunded.",
            }