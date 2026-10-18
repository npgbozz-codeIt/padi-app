# src/services/pipeline.py
import re
import logging
from typing import Any, Dict
from sqlalchemy import select

from src.services.nlu_router import handle_user_text_request
from src.services.state_manager import state_manager
from src.services.handlers.registry import get_vending_handler
from src.services.data_ux_handler import process_data_ux_routing, format_data_size
from src.models.data_plan import DataPlan
from src.utils.network_detector import detect_network, normalize_network_name
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

redis_pool = aioredis.ConnectionPool(
    host="localhost", port=6379, db=0, decode_responses=True, protocol=2
)
redis_client = aioredis.Redis(connection_pool=redis_pool)

CONFIRMATION_YES_WORDS = {"yes", "yep", "confirm", "proceed", "send", "pay", "ok", "okay", "go ahead"}
CONFIRMATION_NO_WORDS = {"no", "cancel", "stop", "abort", "don't", "dont"}


def is_valid_phone(phone_str: str) -> bool:
    """Strictly validates Nigerian phone numbers to prevent conversational strings like 'Okay'."""
    clean = re.sub(r"\D", "", str(phone_str))
    if len(clean) == 11 and clean.startswith("0"):
        return True
    if len(clean) == 13 and clean.startswith("234"):
        return True
    return False


async def handle_incoming_user_message(user_id: str, message_text: str, db: Any = None, profile: Any = None) -> Dict[str, Any]:
    clean_text = message_text.strip().lower()
    session = await state_manager.get_session(user_id)

    user_lang = profile.lang if profile and profile.lang else "english"

    # =========================================================================
    # STATE 1: PENDING_CONFIRMATION -> PIN / PREFERENCE CHECK
    # =========================================================================
    if session and session.get("state") == "PENDING_CONFIRMATION":
        intent = session.get("intent")
        payload = session.get("payload", {})
        slots = payload.get("slots", {})

        if clean_text in CONFIRMATION_YES_WORDS:
            # 1. Check if user has an active 5-minute authorized session in Redis
            auth_token = await redis_client.get(f"pin_auth:{user_id}")
            if auth_token:
                await state_manager.clear_session(user_id)
                handler = get_vending_handler(intent)
                if not handler or not db or not profile:
                    return {"status": "error", "message": "Transaction handler or profile context missing."}
                result = await handler.execute(db=db, profile=profile, slots=slots)
                return {"status": result.get("status"), "message": result.get("message")}

            # 2. First-time preference check: Prompt for 5min vs Always if unset
            if profile.pin_mode is None:
                await state_manager.set_session(
                    user_id=user_id,
                    state="AWAITING_PIN_PREFERENCE",
                    intent=intent,
                    payload={"slots": slots}
                )
                preference_markup = {
                    "inline_keyboard": [
                        [{"text": "⏱️ Remember for 5 Mins", "callback_data": "pin_mode:5min"}],
                        [{"text": "🔐 Always Require PIN", "callback_data": "pin_mode:always"}],
                        [{"text": "❌ Cancel", "callback_data": "action_cancel"}]
                    ]
                }
                return {
                    "status": "awaiting_pin_preference",
                    "message": (
                        "🛡️ **Security Preference Setup**\n\n"
                        "How would you like MyPadi to authorize your transactions?"
                    ),
                    "reply_markup": preference_markup
                }

            # 3. Preference already configured: Request 4-digit PIN directly
            await state_manager.set_session(
                user_id=user_id,
                state="AWAITING_PIN",
                intent=intent,
                payload={"slots": slots}
            )
            return {
                "status": "awaiting_pin",
                "message": "🔐 Please enter your **4-digit transaction PIN** to authorize this payment:"
            }

        elif clean_text in CONFIRMATION_NO_WORDS:
            await state_manager.clear_session(user_id)
            return {"status": "cancelled", "message": "🚫 Transaction cancelled. Let me know when you're ready!"}

    # =========================================================================
    # STATE 2: AWAITING_SLOT
    # =========================================================================
    if session and session.get("state") == "AWAITING_SLOT":
        intent = session.get("intent")
        payload = session.get("payload", {})
        current_slots = payload.get("slots", {})

        handler = get_vending_handler(intent)
        if handler:
            updated_slots = await handler.extract_slots(message_text, current_slots)

            extracted_phone = updated_slots.get("phone_number")
            if extracted_phone and not is_valid_phone(extracted_phone):
                updated_slots["phone_number"] = None

            still_missing = [s for s in handler.required_slots if not updated_slots.get(s)]

            selected_net = updated_slots.get("network") or current_slots.get("network")
            phone_num = updated_slots.get("phone_number")
            vendor_plan_id = current_slots.get("vendor_plan_id") or updated_slots.get("vendor_plan_id")

            # Network mismatch guard
            if intent in ["data", "buy_data"] and selected_net and phone_num and is_valid_phone(phone_num):
                detected_raw = detect_network(phone_num)
                if detected_raw:
                    detected_net = normalize_network_name(detected_raw)
                    normalized_selected = normalize_network_name(selected_net)

                    if detected_net != normalized_selected:
                        conflict_markup = {
                            "inline_keyboard": [
                                [
                                    {
                                        "text": f"✅ Proceed with {selected_net.upper()}",
                                        "callback_data": f"net_override:{selected_net}:{phone_num}"
                                    },
                                    {
                                        "text": f"🔄 Switch to {detected_net.upper()}",
                                        "callback_data": f"net_override:{detected_net}:{phone_num}"
                                    }
                                ],
                                [{"text": "❌ Cancel", "callback_data": "action_cancel"}]
                            ]
                        }
                        warning_msg = (
                            f"⚠️ **Network Mismatch Notice**\n\n"
                            f"The number `{phone_num}` appears to be a **{detected_net.upper()}** line, "
                            f"but you selected **{selected_net.upper()}**.\n\n"
                            f"Is this number ported to {selected_net.upper()}, or would you like to switch?"
                        )
                        await state_manager.clear_session(user_id)
                        return {
                            "status": "network_conflict",
                            "message": warning_msg,
                            "reply_markup": conflict_markup
                        }

            if intent in ["data", "buy_data"] and vendor_plan_id and updated_slots.get("phone_number") and db:
                target_phone = updated_slots["phone_number"]
                
                stmt = select(DataPlan).where(DataPlan.vendor_plan_id == int(vendor_plan_id))
                res = await db.execute(stmt)
                plan_obj = res.scalars().first()

                if plan_obj:
                    await state_manager.set_session(
                        user_id=user_id,
                        state="PENDING_CONFIRMATION",
                        intent="data",
                        payload={
                            "slots": {
                                "vendor_plan_id": int(vendor_plan_id),
                                "phone_number": target_phone,
                                "network": plan_obj.network_name.lower(),
                                "amount": float(plan_obj.retail_amount)
                            }
                        }
                    )

                    formatted_size = format_data_size(plan_obj.size)
                    confirm_text = (
                        f"📦 **Data Bundle Order Summary**\n"
                        f"• Network: {plan_obj.network_name.upper()}\n"
                        f"• Bundle: {formatted_size} ({plan_obj.validity})\n"
                        f"• Recipient: {target_phone}\n"
                        f"• Price: ₦{int(plan_obj.retail_amount)}\n\n"
                        f"Reply *YES* to confirm or *NO* to cancel."
                    )
                    return {"status": "awaiting_confirmation", "message": confirm_text}

            if intent in ["data", "buy_data"] and updated_slots.get("network") and updated_slots.get("phone_number") and db and not vendor_plan_id:
                await state_manager.clear_session(user_id)
                net = updated_slots.get("network")
                phone = updated_slots.get("phone_number")

                ux_res = await process_data_ux_routing(
                    db=db, user_lang=user_lang, phone_number=phone,
                    extracted_network=net, extracted_size=None
                )
                return {
                    "status": "interactive_menu",
                    "message": ux_res["text"],
                    "reply_markup": ux_res.get("reply_markup")
                }

            if still_missing:
                next_missing = still_missing[0]
                prompt_msg = handler.get_missing_slot_prompt(next_missing, user_lang)

                await state_manager.set_session(
                    user_id=user_id, state="AWAITING_SLOT", intent=intent,
                    payload={"slots": updated_slots, "missing_slots": still_missing}
                )
                return {"status": "missing_param", "message": prompt_msg}
            else:
                await state_manager.set_session(
                    user_id=user_id, state="PENDING_CONFIRMATION", intent=intent,
                    payload={"slots": updated_slots}
                )
                recipient = updated_slots.get('phone_number') or updated_slots.get('meter_number')
                amount = float(updated_slots.get('amount', 0))
                network = str(updated_slots.get('network', '')).upper()

                return {
                    "status": "awaiting_confirmation",
                    "message": f"Airtime: ₦{amount:,.2f} to {recipient} ({network})\n\nReply *YES* to confirm or *NO* to cancel."
                }

    # =========================================================================
    # STATE 3: IDLE
    # =========================================================================
    nlu_res = await handle_user_text_request(user_id=user_id, user_text=message_text, execute=False)
    intent = nlu_res.get("action")
    handler = get_vending_handler(intent)

    if intent in ["data", "buy_data"] and db:
        extracted_slots = await handler.extract_slots(message_text, {}) if handler else {}
        network = extracted_slots.get("network")

        phone = extracted_slots.get("phone_number")
        if phone and not is_valid_phone(phone):
            phone = None

        # Do NOT auto-bind to onboarding profile phone; require explicit recipient phone
        target_phone = phone

        if network and target_phone and is_valid_phone(target_phone):
            detected_raw = detect_network(target_phone)
            if detected_raw:
                detected_net = normalize_network_name(detected_raw)
                normalized_selected = normalize_network_name(network)

                if detected_net != normalized_selected:
                    conflict_markup = {
                        "inline_keyboard": [
                            [
                                {
                                    "text": f"✅ Proceed with {network.upper()}",
                                    "callback_data": f"net_override:{network}:{target_phone}"
                                },
                                {
                                    "text": f"🔄 Switch to {detected_net.upper()}",
                                    "callback_data": f"net_override:{detected_net}:{target_phone}"
                                }
                            ],
                            [{"text": "❌ Cancel", "callback_data": "action_cancel"}]
                        ]
                    }
                    warning_msg = (
                        f"⚠️ **Network Mismatch Notice**\n\n"
                        f"The number `{target_phone}` appears to be a **{detected_net.upper()}** line, "
                        f"but you selected **{network.upper()}**.\n\n"
                        f"Is this number ported to {network.upper()}, or would you like to switch?"
                    )
                    await state_manager.clear_session(user_id)
                    return {
                        "status": "network_conflict",
                        "message": warning_msg,
                        "reply_markup": conflict_markup
                    }

        if network and target_phone:
            await state_manager.clear_session(user_id)
            ux_res = await process_data_ux_routing(
                db=db, user_lang=user_lang, phone_number=target_phone,
                extracted_network=network, extracted_size=None
            )
            return {
                "status": "interactive_menu",
                "message": ux_res["text"],
                "reply_markup": ux_res.get("reply_markup")
            }
        else:
            missing = []
            if not network:
                missing.append("network")
            if not target_phone:
                missing.append("phone_number")

            await state_manager.set_session(
                user_id=user_id, state="AWAITING_SLOT", intent="data",
                payload={"slots": {"network": network, "phone_number": target_phone}, "missing_slots": missing}
            )
            next_prompt = "Which network is this data bundle for? (MTN, Glo, Airtel, 9mobile)" if "network" in missing else "Please provide the recipient phone number for the data bundle."
            return {"status": "missing_param", "message": next_prompt}

    if handler:
        extracted_slots = await handler.extract_slots(message_text, {})
        
        if extracted_slots.get("phone_number") and not is_valid_phone(extracted_slots["phone_number"]):
            extracted_slots["phone_number"] = None

        missing_slots = [s for s in handler.required_slots if not extracted_slots.get(s)]

        if missing_slots:
            next_missing = missing_slots[0]
            prompt_msg = handler.get_missing_slot_prompt(next_missing, user_lang)

            await state_manager.set_session(
                user_id=user_id, state="AWAITING_SLOT", intent=intent or "airtime",
                payload={"slots": extracted_slots, "missing_slots": missing_slots}
            )
            return {"status": "missing_param", "message": prompt_msg}
        else:
            await state_manager.set_session(
                user_id=user_id, state="PENDING_CONFIRMATION", intent=intent or "airtime",
                payload={"slots": extracted_slots}
            )
            recipient = extracted_slots.get('phone_number') or extracted_slots.get('meter_number')
            amount = float(extracted_slots.get('amount', 0))
            network = str(extracted_slots.get('network', '')).upper()

            return {
                "status": "awaiting_confirmation",
                "message": f"Airtime: ₦{amount:,.2f} to {recipient} ({network})\n\nReply *YES* to confirm or *NO* to cancel."
            }

    return {"status": "unknown", "message": "I didn't quite catch that. Type 'menu' to see available options."}