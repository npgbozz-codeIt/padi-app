# src/routers/telegram.py
from fastapi import APIRouter, Depends, status
from src.schemas.telegram import TelegramWebhookInput
from src.schemas.enums import OnboardingState, UserLang
from typing import Annotated
import re
import redis.asyncio as aioredis

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

# internal imports
from src.services.data_ux_handler import (
    process_data_ux_routing,
    generate_plan_selection_buttons,
)
from src.database.db_conn import get_db
from src.models.identity import UserIdentity
from src.models.profile import Profile
from src.utils.tag_generator import tag_generator
from src.utils.responses import (
    ONBOARDING_RESPONSES,
    TRANSACTION_RESPONSES,
    DATA_RESPONSES,
)
from src.services.nlu_engine import (
    classify_intent,
    extract_airtime_slots,
    extract_datapurchase_slots,
    extract_betting_slots,
    extract_cabletv_slots,
    extract_electricity_slots,
    extract_education_slots,
    extract_isp_slots,
)
from src.services.telegram import telegram_client, logger

router = APIRouter()
# setting up redis connection for caching
redis_pool = aioredis.ConnectionPool(
    host="localhost", port=6379, db=0, decode_responses=True, protocol=2
)
redis_client = aioredis.Redis(connection_pool=redis_pool)


async def handle_inline_callbacks(update: dict, db: AsyncSession):
    """Internal processor for inline keyword button clicks."""
    callback_dict = update.get("callback_query", {})
    click_data = callback_dict.get("data", "")
    chat_id = callback_dict.get("message", {}).get("chat", {}).get("id")
    message_id = callback_dict.get("message", {}).get("message_id")
    telegramuser_id = callback_dict.get("from", {}).get("id")

    if not click_data:
        return {"status": "ignored"}

    # Dynamic user profile language lookup layer
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

    # Load matching translation copy
    tx_copy = TRANSACTION_RESPONSES.get(user_lang, TRANSACTION_RESPONSES["english"])

    if click_data.startswith("data_net_view:"):
        _, network, category = click_data.split(":")
        menu_res = await generate_plan_selection_buttons(
            db, user_lang, network, category
        )
        await telegram_client.edit_message_text(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": menu_res["text"],
                "parse_mode": "Markdown",
                "reply_markup": menu_res["reply_markup"],
            }
        )
        return {"status": "ok"}

    elif click_data.startswith("data_back_to_net:"):
        _, network = click_data.split(":")
        menu_res = await process_data_ux_routing(db, user_lang, None, network, None)
        await telegram_client.edit_message_text(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": menu_res["text"],
                "parse_mode": "Markdown",
                "reply_markup": menu_res["reply_markup"],
            }
        )
        return {"status": "ok"}

    # Dynamic localized menu routes setup
    elif click_data == "menu_airtime":
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
            logger.info(
                f"🛡️ [Idempotency Guard] Dropped duplicate update_id: {update_id}"
            )
            return {"status": "duplicated_and_dropped"}
        # processing lock with a 5-minute self-cleansing timeout
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
    # 🛠️ Sending immediate interactive feedback to mask network or NLU delays
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
            db_state = (
                profile.user_state.lower()
                if profile.user_state
                else "awaiting_language"
            )
            profile_state = OnboardingState(db_state)
        except ValueError:
            profile_state = OnboardingState.AWAITING_LANGUAGE

        user_message = (payload.message.text or "").strip()
        user_lang = profile.lang or "english"
        copy_text = ONBOARDING_RESPONSES.get(user_lang, ONBOARDING_RESPONSES["english"])

        if not user_message and not payload.message.contact:
            return {"success": 200, "status": "ignored"}

        # ========================================================
        # STEP 1: ACTIVE STATE PROGRESSION GATEKEEPER
        # ========================================================
        if profile_state == OnboardingState.AWAITING_LANGUAGE:
            cleaned_input = user_message.lower()
            if cleaned_input not in ["english", "pidgin", "hausa"]:
                await telegram_client.send_message(
                    {"chat_id": chat_id, "text": copy_text["invalid_lang"]}
                )
                return {"success": 200, "message": copy_text["invalid_lang"]}

            profile.lang = cleaned_input
            profile.user_state = OnboardingState.AWAITING_PHONE.value
            await db.commit()

            new_copy = ONBOARDING_RESPONSES[cleaned_input]
            await telegram_client.send_message(
                {"chat_id": chat_id, "text": new_copy["ask_phone"]}
            )
            return {"success": 200, "message": new_copy["ask_phone"]}

        elif profile_state == OnboardingState.AWAITING_PHONE:
            if payload.message.contact and payload.message.contact.phone_number:
                phone = payload.message.contact.phone_number
            else:
                phone = re.sub(r"\s+", "", user_message)

            profile.phone_num = phone
            profile.user_state = OnboardingState.AWAITING_BVN.value
            await db.commit()

            await telegram_client.send_message(
                {"chat_id": chat_id, "text": copy_text["ask_bvn"]}
            )
            return {"success": 200, "message": copy_text["ask_bvn"]}

        elif profile_state == OnboardingState.AWAITING_BVN:
            clean_bvn = re.sub(r"\D", "", user_message)
            if len(clean_bvn) != 11:
                await telegram_client.send_message(
                    {"chat_id": chat_id, "text": copy_text["invalid_bvn"]}
                )
                return {"success": 200, "message": copy_text["invalid_bvn"]}

            profile.bnv = clean_bvn
            profile.user_state = OnboardingState.AWAITING_PIN.value
            await db.commit()

            await telegram_client.send_message(
                {"chat_id": chat_id, "text": copy_text["ask_pin"]}
            )
            return {"success": 200, "message": copy_text["ask_pin"]}

        elif profile_state == OnboardingState.AWAITING_PIN:
            clean_pin = re.sub(r"\D", "", user_message)
            if len(clean_pin) != 4:
                await telegram_client.send_message(
                    {"chat_id": chat_id, "text": copy_text["invalid_pin"]}
                )
                return {"success": 200, "message": copy_text["invalid_pin"]}

            profile.hash_pin = clean_pin
            profile.user_state = OnboardingState.AWAITING_PIN_CONFIRMATION.value
            await db.commit()

            await telegram_client.send_message(
                {"chat_id": chat_id, "text": copy_text["confirm_pin"]}
            )
            return {"success": 200, "message": copy_text["confirm_pin"]}

        elif profile_state == OnboardingState.AWAITING_PIN_CONFIRMATION:
            clean_pin = re.sub(r"\D", "", user_message)
            if clean_pin != profile.hash_pin:
                profile.user_state = OnboardingState.AWAITING_PIN.value
                profile.hash_pin = None
                await db.commit()
                await telegram_client.send_message(
                    {"chat_id": chat_id, "text": copy_text["mismatch_pin"]}
                )
                return {"success": 200, "message": copy_text["mismatch_pin"]}

            profile.user_state = OnboardingState.COMPLETED.value
            await db.commit()

            await telegram_client.send_message(
                {"chat_id": chat_id, "text": copy_text["completed"]}
            )
            return {"success": 200, "message": copy_text["completed"]}

        # ========================================================
        # STEP 2: FULL TRANSACTION ENGINE (Only hits if COMPLETED)
        # ========================================================
        elif profile_state == OnboardingState.COMPLETED:
            nlu_analysis = await classify_intent(user_message)
            logger.info(
                f"🧠 [NLU Intent Engine] Action Classified: '{nlu_analysis.action}' | Raw Text: '{user_message}'"
            )

            tx_copy = TRANSACTION_RESPONSES.get(
                user_lang, TRANSACTION_RESPONSES["english"]
            )
            action_str = str(nlu_analysis.action).lower()

            # 🛠️ GREETING GATEWAY: Catch common greetings or greeting intent labels instantly
            if action_str in [
                "greeting",
                "general_greeting",
                "intentenum.greeting",
            ] or user_message.lower() in [
                "hi",
                "hello",
                "hey",
                "yo",
                "sup",
                "barka",
                "sannu",
            ]:

                greeting_text = tx_copy["greeting"]
                greeting_markup = tx_copy.get(
                    "greeting_markup"
                )  # Fetch the button layout safely

                payload_data = {
                    "chat_id": chat_id,
                    "text": greeting_text,
                    "parse_mode": "Markdown",
                }
                if greeting_markup:
                    payload_data["reply_markup"] = greeting_markup
                await telegram_client.send_message(payload_data)
                return {"success": 200, "message": greeting_text}

            elif "airtime" in action_str:
                extracted_slots = await extract_airtime_slots(user_message)
                if (
                    not extracted_slots
                    or not extracted_slots.amount
                    or not extracted_slots.network
                ):
                    await telegram_client.send_message(
                        {"chat_id": chat_id, "text": tx_copy["missing_slots"]}
                    )
                    return {"success": 200, "message": tx_copy["missing_slots"]}

                target_phone = extracted_slots.phone_number or profile.phone_num
                req_amount = int(extracted_slots.amount)
                req_network = extracted_slots.network

                from src.utils.ledger_guard import initialize_local_ledger
                from src.models.transaction import TransactionType, TransactionStatus

                cleared, local_tx = await initialize_local_ledger(
                    db=db,
                    profile=profile,
                    amount=req_amount,
                    recipient=target_phone,
                    tx_type=TransactionType.AIRTIME,
                    provider=req_network,
                )

                if not cleared:
                    insufficient_msg = tx_copy["insufficient_funds"].format(
                        balance=profile.user_wallet or 0.0
                    )
                    await telegram_client.send_message(
                        {"chat_id": chat_id, "text": insufficient_msg}
                    )
                    return {"success": 200, "message": insufficient_msg}

                from src.services.bigisub import bigisub_client

                vending_res = await bigisub_client.vend_airtime(
                    phone=target_phone, amount=req_amount, network=req_network
                )
                # current_lock = f"tg_lock:{payload.update_id}"

                if vending_res.get("success") is True:
                    local_tx.status = TransactionStatus.SUCCESSFUL
                    local_tx.reference = vending_res.get("transaction_id")
                    await db.commit()
                    # mark the lock as sucess to avoid reprocessing
                    await redis_client.set(lock_key, "success", ex=300)

                    success_msg = tx_copy["vending_success"].format(
                        amount=req_amount, provider=req_network, recipient=target_phone
                    )
                    await telegram_client.send_message(
                        {"chat_id": chat_id, "text": success_msg}
                    )
                    return {"success": 200, "message": success_msg}
                else:
                    profile.user_wallet = float(profile.user_wallet) + req_amount
                    local_tx.status = TransactionStatus.FAILED
                    await db.commit()
                    # mark the lock as failed to avoid reprocessing
                    await redis_client.set(lock_key, "failed", ex=300)

                    failed_msg = tx_copy["vending_failed"]
                    await telegram_client.send_message(
                        {"chat_id": chat_id, "text": failed_msg}
                    )
                    return {"success": 200, "message": failed_msg}

            elif "data" in action_str:
                extracted_slots = await extract_datapurchase_slots(user_message)
                extracted_net = (
                    extracted_slots.network.value
                    if extracted_slots and extracted_slots.network
                    else None
                )
                extracted_size = extracted_slots.size if extracted_slots else None
                extracted_amt = extracted_slots.amount if extracted_slots else None
                target_phone = (
                    extracted_slots.phone_number
                    if extracted_slots and extracted_slots.phone_number
                    else profile.phone_num
                )

                ux_response = await process_data_ux_routing(
                    db=db,
                    user_lang=user_lang,
                    phone_number=target_phone,
                    extracted_network=extracted_net,
                    extracted_size=extracted_size,
                    extracted_amount=float(extracted_amt) if extracted_amt else None,
                )

                payload_data = {
                    "chat_id": chat_id,
                    "text": ux_response["text"],
                    "parse_mode": "Markdown",
                }
                if ux_response.get("reply_markup"):
                    payload_data["reply_markup"] = ux_response["reply_markup"]

                await telegram_client.send_message(payload_data)
                return {"status": "ok"}

            elif "betting" in action_str:
                extracted_slots = await extract_betting_slots(user_message)
                await telegram_client.send_message(
                    {"chat_id": chat_id, "text": tx_copy["coming_soon"]}
                )
                return {"success": 200, "message": tx_copy["coming_soon"]}

            elif "cabletv" in action_str or "cable" in action_str:
                extracted_slots = await extract_cabletv_slots(user_message)
                await telegram_client.send_message(
                    {"chat_id": chat_id, "text": tx_copy["coming_soon"]}
                )
                return {"success": 200, "message": tx_copy["coming_soon"]}

            elif "electricity" in action_str:
                extracted_slots = await extract_electricity_slots(user_message)
                await telegram_client.send_message(
                    {"chat_id": chat_id, "text": tx_copy["coming_soon"]}
                )
                return {"success": 200, "message": tx_copy["coming_soon"]}

            elif "education" in action_str:
                extracted_slots = await extract_education_slots(user_message)
                await telegram_client.send_message(
                    {"chat_id": chat_id, "text": tx_copy["coming_soon"]}
                )
                return {"success": 200, "message": tx_copy["coming_soon"]}

            elif "isp" in action_str:
                extracted_slots = await extract_isp_slots(user_message)
                await telegram_client.send_message(
                    {"chat_id": chat_id, "text": tx_copy["coming_soon"]}
                )
                return {"success": 200, "message": tx_copy["coming_soon"]}

            else:
                fallback_msg = tx_copy["fallback_safety"]
                await telegram_client.send_message(
                    {"chat_id": chat_id, "text": fallback_msg, "parse_mode": "Markdown"}
                )
                return {"success": 200, "message": fallback_msg}

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
