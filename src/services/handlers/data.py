# src/services/handlers/data.py
import re
from decimal import Decimal
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.services.handlers.base import BaseVendingHandler
from src.utils.network_detector import detect_network
from src.utils.ledger_guard import initialize_local_ledger
from src.models.transaction import TransactionType, TransactionStatus
from src.models.data_plan import DataPlan
from src.services.bigisub import bigisub_client
from src.services.transaction_service import TransactionService
from src.utils.responses import TRANSACTION_RESPONSES


def normalize_network_name(net_str: Optional[str]) -> str:
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


class DataHandler(BaseVendingHandler):
    intent_name = "data"
    required_slots = ["network", "phone_number"]

    def get_missing_slot_prompt(self, missing_slot: str, user_lang: str) -> str:
        prompts = {
            "network": {
                "english": "Which network is this data bundle for? (MTN, Glo, Airtel, 9mobile)",
                "pidgin": "Which network be dis data? (MTN, Glo, Airtel, 9mobile)",
                "hausa": "Wace hanyar sadarwa ce? (MTN, Glo, Airtel, 9mobile)",
            },
            "phone_number": {
                "english": "Please provide the recipient phone number for the data bundle.",
                "pidgin": "Abeg drop the phone number wey go collect the data.",
                "hausa": "Da fatan za a bayar da lambar wayar.",
            }
        }
        slot_dict = prompts.get(missing_slot, {})
        return slot_dict.get(user_lang, slot_dict.get("english", f"Please provide the {missing_slot}."))

    async def extract_slots(self, text: str, current_slots: Dict[str, Any]) -> Dict[str, Any]:
        merged = current_slots.copy() if current_slots else {}
        clean_text = text.strip()

        phone_match = re.search(r"\b(0\d{9,10}|234\d{10})\b", clean_text)
        if phone_match:
            merged["phone_number"] = phone_match.group(1)

        for net in ["mtn", "glo", "airtel", "9mobile", "etisalat"]:
            if net in clean_text.lower():
                merged["network"] = normalize_network_name(net)
                break

        target_phone = merged.get("phone_number")
        if target_phone and not merged.get("network"):
            detected = detect_network(target_phone)
            if detected:
                merged["network"] = detected

        return merged

    async def execute(self, db: AsyncSession, profile: Any, slots: Dict[str, Any]) -> Dict[str, Any]:
        user_lang = profile.lang or "english"
        tx_copy = TRANSACTION_RESPONSES.get(user_lang, TRANSACTION_RESPONSES["english"])

        target_phone = slots.get("phone_number") or profile.phone_num
        vendor_plan_id = int(slots.get("vendor_plan_id") or slots.get("plan_id", 0))
        network = normalize_network_name(slots.get("network", "mtn"))

        stmt = select(DataPlan).where(DataPlan.vendor_plan_id == vendor_plan_id)
        res = await db.execute(stmt)
        plan_obj = res.scalars().first()

        if not plan_obj:
            return {"status": "error", "message": "❌ Selected data plan not found or expired."}

        req_amount = Decimal(str(plan_obj.retail_amount))

        cleared, local_tx = await initialize_local_ledger(
            db=db,
            profile=profile,
            amount=req_amount,
            recipient=target_phone,
            tx_type=TransactionType.DATA,
            provider=network,
        )

        if not cleared or not local_tx:
            return {"status": "error", "message": tx_copy.get("insufficient_funds", "Insufficient wallet balance.")}

        vending_res = await bigisub_client.vend_data(
            phone=target_phone, plan_id=vendor_plan_id, network=network
        )

        if vending_res.get("success") is True:
            local_tx.status = TransactionStatus.SUCCESSFUL
            local_tx.reference = vending_res.get("transaction_id") or TransactionService.generate_reference("MP-DAT")
            local_tx.balance_after = profile.user_wallet
            local_tx.token_or_details = f"{plan_obj.network_name.upper()} {plan_obj.size} ({plan_obj.validity})"
            await db.commit()

            receipt_msg = TransactionService.format_receipt(
                txn=local_tx,
                service_label=f"{network.upper()} Data ({plan_obj.size})",
                detail_label="Validity & Bundle"
            )

            receipt_markup = {
                "inline_keyboard": [
                    [
                        {
                            "text": "🖼️ Download Image Receipt",
                            "callback_data": f"rx_img:{local_tx.reference}"
                        }
                    ]
                ]
            }

            await TransactionService.dispatch_admin_alert(
                event_title="Data Bundle Vended",
                details={
                    "User": profile.user_tag,
                    "Bundle": f"{network.upper()} {plan_obj.size}",
                    "Amount": f"₦{req_amount:,.2f}",
                    "Recipient": target_phone,
                    "Ref": local_tx.reference
                },
                level="INFO"
            )

            return {
                "status": "success",
                "message": receipt_msg,
                "reply_markup": receipt_markup
            }
        else:
            profile.user_wallet = (profile.user_wallet or Decimal("0.00")) + req_amount
            local_tx.status = TransactionStatus.FAILED
            local_tx.balance_after = profile.user_wallet
            await db.commit()

            failed_reason = vending_res.get("error", "Gateway error")

            await TransactionService.dispatch_admin_alert(
                event_title="Data Vending Failed",
                details={
                    "User": profile.user_tag,
                    "Bundle": f"{network.upper()} {plan_obj.size}",
                    "Amount": f"₦{req_amount:,.2f}",
                    "Recipient": target_phone,
                    "Error": failed_reason
                },
                level="ERROR"
            )

            return {"status": "error", "message": f"❌ Data Purchase Failed: {failed_reason}\n\nYour wallet has been refunded."}