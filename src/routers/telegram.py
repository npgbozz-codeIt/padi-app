# src/routers/telegram.py
from fastapi import APIRouter, Depends, status
from src.schemas.telegram import TelegramWebhookInput
from src.schemas.enums import OnboardingState
from typing import Annotated
import re
import redis.asyncio as aioredis

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

# Internal imports
from src.services.data_ux_handler import (
    process_data_ux_routing,
    generate_plan_selection_buttons,
    format_data_size,
)
from src.database.db_conn import get_db
from src.models.identity import UserIdentity
from src.models.profile import Profile
from src.models.data_plan import DataPlan
from src.utils.tag_generator import tag_generator
from src.utils.responses import (
    ONBOARDING_RESPONSES,
    TRANSACTION_RESPONSES,
)
from src.services.telegram import telegram_client, logger
from src.services.session_manager import SessionManager

router = APIRouter()

redis_pool = aioredis.ConnectionPool(
    host="localhost", port=6379, db=0, decode_responses=True, protocol=2
)
redis_client = aioredis.Redis(connection_pool=redis_pool)


def is_valid_phone(phone_str: str) -> bool:
    clean = re.sub(r"\D", "", str(phone_str))
    if len(clean) == 11 and clean.startswith("0"):
        return True
    if len(clean) == 13 and clean.startswith("234"):
        return True
    return False


async def handle_inline_callbacks(update: dict, db: AsyncSession):
    callback_dict = update.get("callback_query", {})
    callback_query_id = callback_dict.get("id")
    click_data = callback_dict.get("data", "")
    chat_id = callback_dict.get("message", {}).get("chat", {}).get("id")
    message_id = callback_dict.get("message", {}).get("message_id")
    telegramuser_id = callback_dict.get("from", {}).get("id")

    if not click_data:
        return {"status": "ignored"}

    if callback_query_id:
        try:
            await telegram_client.answer_callback_query({"callback_query_id": callback_query_id})
        except Exception:
            pass

    user_lang = "english"
    stmt = (
        select(Profile)
        .join(UserIdentity)
        .where(
            UserIdentity.platform_id == str(telegramuser_id),
            UserIdentity.platform == "Telegram",
        )
    )
    res = await db.execute(stmt)
    profile = res.scalars().first()
    if profile and profile.lang:
        user_lang = profile.lang.lower()

    tx_copy = TRANSACTION_RESPONSES.get(user_lang, TRANSACTION_RESPONSES["english"])

    if click_data.startswith("net_override:"):
        parts = click_data.split(":")
        chosen_network = parts[1]
        phone_num = parts[2]

        ux_res = await process_data_ux_routing(
            db=db,
            user_lang=user_lang,
            phone_number=phone_num,
            extracted_network=chosen_network,
            extracted_size=None
        )
        markup = ux_res.get("reply_markup")

        await telegram_client.edit_message_text(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": f"⚡ Network set to **{chosen_network.upper()}** for `{phone_num}`.\n\n{ux_res['text']}",
                "parse_mode": "Markdown",
                "reply_markup": markup,
            }
        )
        return {"status": "ok"}

    elif click_data.startswith("data_net_view:"):
        parts = click_data.split(":")
        network = parts[1]
        category = parts[2]
        phone_num = parts[3] if len(parts) > 3 else "PROMPT_PHONE"

        menu_res = await generate_plan_selection_buttons(
            db, user_lang, network, category, phone_number=phone_num
        )
        markup = menu_res.get("reply_markup")

        await telegram_client.edit_message_text(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": menu_res["text"],
                "parse_mode": "Markdown",
                "reply_markup": markup,
            }
        )
        return {"status": "ok"}

    elif click_data.startswith("data_back_to_net:"):
        parts = click_data.split(":")
        network = parts[1]
        phone_num = parts[2] if len(parts) > 2 else "PROMPT_PHONE"
        net_display = network.upper() if network != "9mobile" else "9mobile"

        markup = {
            "inline_keyboard": [
                [
                    {"text": "☀️ Daily Plans", "callback_data": f"data_net_view:{network}:daily:{phone_num}"},
                    {"text": "⏳ Weekly Plans", "callback_data": f"data_net_view:{network}:weekly:{phone_num}"},
                ],
                [
                    {"text": "📅 Monthly Plans", "callback_data": f"data_net_view:{network}:monthly:{phone_num}"},
                    {"text": "💼 Corporate Plans", "callback_data": f"data_net_view:{network}:corporate:{phone_num}"},
                ],
                [{"text": "❌ Cancel Operations", "callback_data": "action_cancel"}],
            ]
        }
        await telegram_client.edit_message_text(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": f"⚡ Choose your preferred {net_display} data lifespan category below:",
                "parse_mode": "Markdown",
                "reply_markup": markup,
            }
        )
        return {"status": "ok"}

    elif click_data.startswith("data_pay:"):
        parts = click_data.split(":")
        vendor_plan_id = int(parts[1])
        phone_num = parts[2] if len(parts) > 2 else "PROMPT_PHONE"

        stmt = select(DataPlan).where(DataPlan.vendor_plan_id == vendor_plan_id)
        res = await db.execute(stmt)
        plan_obj = res.scalars().first()

        if not plan_obj:
            await telegram_client.edit_message_text({
                "chat_id": chat_id, "message_id": message_id,
                "text": "❌ Selected plan is no longer available."
            })
            return {"status": "error"}

        target_phone = phone_num if (phone_num != "PROMPT_PHONE" and is_valid_phone(phone_num)) else (profile.phone_num if (profile and profile.phone_num and is_valid_phone(profile.phone_num)) else None)

        if not target_phone or not is_valid_phone(target_phone):
            from src.services.state_manager import state_manager
            await state_manager.set_session(
                user_id=str(telegramuser_id),
                state="AWAITING_SLOT",
                intent="data",
                payload={
                    "slots": {
                        "vendor_plan_id": vendor_plan_id,
                        "network": plan_obj.network_name.lower(),
                        "amount": float(plan_obj.retail_amount)
                    },
                    "missing_slots": ["phone_number"]
                }
            )
            formatted_size = format_data_size(plan_obj.size)
            await telegram_client.edit_message_text({
                "chat_id": chat_id,
                "message_id": message_id,
                "text": f"📱 Please enter the recipient phone number for **{plan_obj.network_name.upper()} {formatted_size}** (₦{int(plan_obj.retail_amount)}):",
                "parse_mode": "Markdown"
            })
            return {"status": "ok"}

        from src.services.state_manager import state_manager
        await state_manager.set_session(
            user_id=str(telegramuser_id),
            state="PENDING_CONFIRMATION",
            intent="data",
            payload={
                "slots": {
                    "vendor_plan_id": vendor_plan_id,
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

        await telegram_client.edit_message_text({
            "chat_id": chat_id,
            "message_id": message_id,
            "text": confirm_text,
            "parse_mode": "Markdown"
        })
        return {"status": "ok"}

    elif click_data in ["menu_data", "buy_data"]:
        markup = {
            "inline_keyboard": [
                [
                    {"text": "MTN", "callback_data": "data_net_view:mtn:monthly:PROMPT_PHONE"},
                    {"text": "GLO", "callback_data": "data_net_view:glo:monthly:PROMPT_PHONE"}
                ],
                [
                    {"text": "Airtel", "callback_data": "data_net_view:airtel:monthly:PROMPT_PHONE"},
                    {"text": "9mobile", "callback_data": "data_net_view:9mobile:monthly:PROMPT_PHONE"}
                ],
                [{"text": "❌ Cancel", "callback_data": "action_cancel"}]
            ]
        }
        await telegram_client.edit_message_text(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": "Please select your data network provider:",
                "parse_mode": "Markdown",
                "reply_markup": markup,
            }
        )
        return {"status": "ok"}

    elif click_data == "menu_airtime":
        from src.services.state_manager import state_manager
        await state_manager.update_session(chat_id, "airtime", {})
        await telegram_client.edit_message_text(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": tx_copy["airtime_prompt"],
                "parse_mode": "Markdown",
            }
        )
        return {"status": "ok"}

    elif click_data == "menu_electricity":
        await telegram_client.edit_message_text(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": tx_copy["electricity_prompt"],
                "parse_mode": "Markdown",
            }
        )
        return {"status": "ok"}

    elif click_data in ["menu_cable", "menu_betting"]:
        key_target = "cable_prompt" if click_data == "menu_cable" else "betting_prompt"
        await telegram_client.edit_message_text(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": tx_copy[key_target],
                "parse_mode": "Markdown",
            }
        )
        return {"status": "ok"}

    elif click_data == "action_cancel":
        from src.services.state_manager import state_manager
        await state_manager.clear_session(chat_id)
        cancel_msg = "❌ Operation closed cleanly. Let me know whenever you're ready to run another trade, boss!"
        await telegram_client.edit_message_text(
            {"chat_id": chat_id, "message_id": message_id, "text": cancel_msg}
        )
        return {"status": "ok"}

    return {"status": "unhandled_callback"}


@router.post("", status_code=status.HTTP_200_OK)
async def telegram_webhook(update: dict, db: Annotated[AsyncSession, Depends(get_db)]):
    update_id = update.get("update_id")
    if update_id:
        lock_key = f"tg_lock:{update_id}"
        is_duplicate = await redis_client.get(lock_key)
        if is_duplicate:
            logger.info(f"🛡️ [Idempotency Guard] Dropped duplicate update_id: {update_id}")
            return {"status": "duplicated_and_dropped"}
        await redis_client.set(lock_key, "processing", ex=300)

    if "callback_query" in update:
        return await handle_inline_callbacks(update, db)

    if "message" not in update:
        return {"status": "ignored", "reason": "non-message event"}

    try:
        payload = TelegramWebhookInput.model_validate(update)
    except Exception as e:
        return {"status": "error", "detail": f"Schema parsing error: {e}"}

    telegramuser_id = payload.message.message_from.id
    chat_id = payload.message.chat.id

    try:
        await telegram_client.send_chat_action(chat_id=chat_id, action="typing")
    except Exception as e:
        logger.warning(f"Failed to trigger typing indicator packet: {e}")

    stmt = (
        select(UserIdentity)
        .options(joinedload(UserIdentity.profile))
        .where(
            UserIdentity.platform_id == str(telegramuser_id),
            UserIdentity.platform == "Telegram",
        )
    )
    result = await db.execute(stmt)
    existing_user = result.scalars().first()

    if existing_user:
        profile = existing_user.profile

        try:
            db_state = profile.user_state.lower() if profile.user_state else "awaiting_language"
            profile_state = OnboardingState(db_state)
        except ValueError:
            profile_state = OnboardingState.AWAITING_LANGUAGE

        user_message = (payload.message.text or "").strip()
        user_lang = profile.lang or "english"
        copy_text = ONBOARDING_RESPONSES.get(user_lang, ONBOARDING_RESPONSES["english"])

        if not user_message and not payload.message.contact:
            return {"success": 200, "status": "ignored"}

        if profile_state == OnboardingState.AWAITING_LANGUAGE:
            cleaned_input = user_message.lower()
            if cleaned_input not in ["english", "pidgin", "hausa"]:
                await telegram_client.send_message({"chat_id": chat_id, "text": copy_text["invalid_lang"]})
                return {"success": 200, "message": copy_text["invalid_lang"]}

            profile.lang = cleaned_input
            profile.user_state = OnboardingState.AWAITING_PHONE.value
            await db.commit()

            new_copy = ONBOARDING_RESPONSES[cleaned_input]
            await telegram_client.send_message({"chat_id": chat_id, "text": new_copy["ask_phone"]})
            return {"success": 200, "message": new_copy["ask_phone"]}

        elif profile_state == OnboardingState.AWAITING_PHONE:
            phone = payload.message.contact.phone_number if (payload.message.contact and payload.message.contact.phone_number) else re.sub(r"\s+", "", user_message)
            profile.phone_num = phone
            profile.user_state = OnboardingState.AWAITING_BVN.value
            await db.commit()
            await telegram_client.send_message({"chat_id": chat_id, "text": copy_text["ask_bvn"]})
            return {"success": 200, "message": copy_text["ask_bvn"]}

        elif profile_state == OnboardingState.AWAITING_BVN:
            clean_bvn = re.sub(r"\D", "", user_message)
            if len(clean_bvn) != 11:
                await telegram_client.send_message({"chat_id": chat_id, "text": copy_text["invalid_bvn"]})
                return {"success": 200, "message": copy_text["invalid_bvn"]}
            profile.bnv = clean_bvn
            profile.user_state = OnboardingState.AWAITING_PIN.value
            await db.commit()
            await telegram_client.send_message({"chat_id": chat_id, "text": copy_text["ask_pin"]})
            return {"success": 200, "message": copy_text["ask_pin"]}

        elif profile_state == OnboardingState.AWAITING_PIN:
            clean_pin = re.sub(r"\D", "", user_message)
            if len(clean_pin) != 4:
                await telegram_client.send_message({"chat_id": chat_id, "text": copy_text["invalid_pin"]})
                return {"success": 200, "message": copy_text["invalid_pin"]}
            profile.hash_pin = clean_pin
            profile.user_state = OnboardingState.AWAITING_PIN_CONFIRMATION.value
            await db.commit()
            await telegram_client.send_message({"chat_id": chat_id, "text": copy_text["confirm_pin"]})
            return {"success": 200, "message": copy_text["confirm_pin"]}

        elif profile_state == OnboardingState.AWAITING_PIN_CONFIRMATION:
            clean_pin = re.sub(r"\D", "", user_message)
            if clean_pin != profile.hash_pin:
                profile.user_state = OnboardingState.AWAITING_PIN.value
                profile.hash_pin = None
                await db.commit()
                await telegram_client.send_message({"chat_id": chat_id, "text": copy_text["mismatch_pin"]})
                return {"success": 200, "message": copy_text["mismatch_pin"]}
            profile.user_state = OnboardingState.COMPLETED.value
            await db.commit()
            await telegram_client.send_message({"chat_id": chat_id, "text": copy_text["completed"]})
            return {"success": 200, "message": copy_text["completed"]}

        elif profile_state == OnboardingState.COMPLETED:
            from src.services.pipeline import handle_incoming_user_message
            from src.services.state_manager import state_manager

            tx_copy = TRANSACTION_RESPONSES.get(user_lang, TRANSACTION_RESPONSES["english"])

            if user_message.lower() in ["hi", "hello", "hey", "yo", "sup", "barka", "sannu", "menu"]:
                await state_manager.clear_session(str(telegramuser_id))
                greeting_text = tx_copy["greeting"]
                greeting_markup = tx_copy.get("greeting_markup")

                payload_data = {"chat_id": chat_id, "text": greeting_text, "parse_mode": "Markdown"}
                if greeting_markup:
                    payload_data["reply_markup"] = greeting_markup

                await telegram_client.send_message(payload_data)
                return {"success": 200, "message": greeting_text}

            pipeline_res = await handle_incoming_user_message(
                user_id=str(telegramuser_id), message_text=user_message, db=db, profile=profile
            )
            bot_reply = pipeline_res.get("message", "Processing request...")
            reply_markup = pipeline_res.get("reply_markup")

            msg_payload = {"chat_id": chat_id, "text": bot_reply, "parse_mode": "Markdown"}
            if reply_markup:
                msg_payload["reply_markup"] = reply_markup

            # If pipeline returned network conflict markup, send it appropriately
            if pipeline_res.get("status") == "network_conflict":
                msg_payload["reply_markup"] = pipeline_res.get("reply_markup")

            await telegram_client.send_message(msg_payload)
            return {"success": 200, "message": pipeline_res.get("status")}
    else:
        firstName = payload.message.message_from.first_name
        lastName = payload.message.message_from.username or "Padi"
        new_tag = tag_generator(firstname=firstName, lastname=lastName)

        new_profile = Profile(
            user_tag=new_tag,
            first_name=firstName,
            last_name=lastName,
            email=f"{new_tag.replace('@', '')}@mypadi.com.ng",
            user_state=OnboardingState.AWAITING_LANGUAGE.value,
        )
        db.add(new_profile)
        await db.flush()

        new_identity = UserIdentity(
            platform="Telegram",
            platform_id=str(telegramuser_id),
            profile_id=new_profile.id,
        )
        db.add(new_identity)
        await db.commit()

        init_copy = ONBOARDING_RESPONSES["english"]["ask_lang"]
        await telegram_client.send_message({"chat_id": chat_id, "text": init_copy})
        return {"success": 201, "message": init_copy}