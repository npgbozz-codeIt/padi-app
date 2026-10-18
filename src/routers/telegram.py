# src/routers/telegram.py
import re
from typing import Annotated
import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

# Internal imports
from src.database.db_conn import get_db
from src.models.data_plan import DataPlan
from src.models.identity import UserIdentity
from src.models.profile import Profile
from src.services.data_ux_handler import (
    format_data_size,
    generate_plan_selection_buttons,
    process_data_ux_routing,
)
from src.services.onboarding_handler import OnboardingHandler
from src.services.pipeline import handle_incoming_user_message
from src.services.session_manager import SessionManager
from src.services.state_manager import state_manager
from src.services.telegram import logger, telegram_client
from src.services.financial.paystack import PaystackFinancialProvider
from src.schemas.telegram import TelegramWebhookInput
from src.utils.responses import TRANSACTION_RESPONSES
from src.utils.tag_generator import tag_generator

router = APIRouter()
paystack_provider = PaystackFinancialProvider()

redis_pool = aioredis.ConnectionPool(
    host="localhost", port=6379, db=0, decode_responses=True, protocol=2
)
redis_client = aioredis.Redis(connection_pool=redis_pool)


def is_valid_phone(phone_str: str) -> bool:
    """Strictly checks for 11-digit or 234-prefixed Nigerian phone numbers."""
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
    from_user_meta = callback_dict.get("from", {})

    if not click_data:
        return {"status": "ignored"}

    if callback_query_id:
        try:
            await telegram_client.answer_callback_query(
                {"callback_query_id": callback_query_id}
            )
        except Exception:
            pass

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

    # 1. Handle Onboarding Inline Callbacks
    if (
        click_data.startswith("lang_")
        or click_data.startswith("name_confirm_")
        or click_data == "skip_referral"
        or click_data == "verify_later"
    ):
        if profile:
            class MockChat:
                def __init__(self, cid):
                    self.id = cid

            class MockMessage:
                def __init__(self, cid, mid):
                    self.chat = MockChat(cid)
                    self.message_id = mid
                    self.contact = None

            mock_msg = MockMessage(chat_id, message_id)
            
            class MockUserMeta:
                def __init__(self, data):
                    self.first_name = data.get("first_name", "")
                    self.last_name = data.get("last_name", "")

            await OnboardingHandler.process_onboarding(
                db=db,
                profile=profile,
                text=None,
                message_obj=mock_msg,
                callback_data=click_data,
                telegram_user_data=MockUserMeta(from_user_meta)
            )
            return {"status": "ok"}

    user_lang = profile.lang.lower() if profile and profile.lang else "english"
    tx_copy = TRANSACTION_RESPONSES.get(user_lang, TRANSACTION_RESPONSES["english"])

    # Handle preset funding amount buttons (e.g. fund_preset:1000)
    if click_data.startswith("fund_preset:"):
        if not profile:
            return {"status": "error"}
        try:
            amount_naira = int(click_data.split(":")[1])
            amount_in_kobo = amount_naira * 100

            tx_res = await paystack_provider.initialize_transaction(
                email=profile.email or f"{profile.id}@mypadi.app",
                amount_in_kobo=amount_in_kobo
            )
            if tx_res.get("status"):
                auth_url = tx_res.get("authorization_url")
                await telegram_client.send_message({
                    "chat_id": chat_id,
                    "text": (
                        f"💳 **Fund Your MyPadi Wallet (₦{amount_naira:,})**\n\n"
                        f"Tap the secure button below to complete your payment via Paystack Checkout:"
                    ),
                    "reply_markup": {
                        "inline_keyboard": [
                            [{"text": f"🔗 Pay ₦{amount_naira:,} via Paystack", "url": auth_url}],
                            [{"text": "❌ Close", "callback_data": "action_cancel"}]
                        ]
                    },
                    "parse_mode": "Markdown",
                })
            else:
                await telegram_client.send_message({
                    "chat_id": chat_id,
                    "text": f"❌ Could not generate payment link: {tx_res.get('message', 'Please try again.')}"
                })
        except Exception as e:
            logger.error(f"Error processing fund preset callback: {e}")
        return {"status": "ok"}

    # Handle custom funding amount trigger
    if click_data == "fund_custom":
        if not profile:
            return {"status": "error"}
        profile.user_state = "awaiting_custom_fund_amount"
        await db.commit()

        await telegram_client.send_message({
            "chat_id": chat_id,
            "text": "✏️ Please type the amount you want to add to your wallet (e.g., `5000`):",
            "parse_mode": "Markdown",
            "reply_markup": {"remove_keyboard": True}
        })
        return {"status": "ok"}

    if click_data == "trigger_fund_wallet":
        if not profile:
            return {"status": "error"}
        
        await telegram_client.send_message({
            "chat_id": chat_id,
            "text": (
                "💳 **Fund Your MyPadi Wallet**\n\n"
                "Select a quick funding amount or choose custom:"
            ),
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "₦500", "callback_data": "fund_preset:500"},
                        {"text": "₦1,000", "callback_data": "fund_preset:1000"},
                        {"text": "₦2,000", "callback_data": "fund_preset:2000"}
                    ],
                    [
                        {"text": "₦5,000", "callback_data": "fund_preset:5000"},
                        {"text": "₦10,000", "callback_data": "fund_preset:10000"}
                    ],
                    [
                        {"text": "✏️ Type Custom Amount", "callback_data": "fund_custom"}
                    ]
                ]
            },
            "parse_mode": "Markdown",
        })
        return {"status": "ok"}

    if click_data.startswith("net_override:"):
        parts = click_data.split(":")
        chosen_network = parts[1]
        phone_num = parts[2]

        ux_res = await process_data_ux_routing(
            db=db,
            user_lang=user_lang,
            phone_number=phone_num,
            extracted_network=chosen_network,
            extracted_size=None,
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
                    {
                        "text": "☀️ Daily Plans",
                        "callback_data": f"data_net_view:{network}:daily:{phone_num}",
                    },
                    {
                        "text": "⏳ Weekly Plans",
                        "callback_data": f"data_net_view:{network}:weekly:{phone_num}",
                    },
                ],
                [
                    {
                        "text": "📅 Monthly Plans",
                        "callback_data": f"data_net_view:{network}:monthly:{phone_num}",
                    },
                    {
                        "text": "💼 Corporate Plans",
                        "callback_data": f"data_net_view:{network}:corporate:{phone_num}",
                    },
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
            await telegram_client.edit_message_text(
                {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": "❌ Selected plan is no longer available.",
                }
            )
            return {"status": "error"}

        target_phone = (
            phone_num
            if (phone_num != "PROMPT_PHONE" and is_valid_phone(phone_num))
            else (
                profile.phone_num
                if (profile and profile.phone_num and is_valid_phone(profile.phone_num))
                else None
            )
        )

        if not target_phone or not is_valid_phone(target_phone):
            await state_manager.set_session(
                user_id=str(telegramuser_id),
                state="AWAITING_SLOT",
                intent="data",
                payload={
                    "slots": {
                        "vendor_plan_id": vendor_plan_id,
                        "network": plan_obj.network_name.lower(),
                        "amount": float(plan_obj.retail_amount),
                    },
                    "missing_slots": ["phone_number"],
                },
            )
            formatted_size = format_data_size(plan_obj.size)
            await telegram_client.edit_message_text(
                {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": f"📱 Please enter the recipient phone number for **{plan_obj.network_name.upper()} {formatted_size}** (₦{int(plan_obj.retail_amount)}):",
                    "parse_mode": "Markdown",
                }
            )
            return {"status": "ok"}

        await state_manager.set_session(
            user_id=str(telegramuser_id),
            state="PENDING_CONFIRMATION",
            intent="data",
            payload={
                "slots": {
                    "vendor_plan_id": vendor_plan_id,
                    "phone_number": target_phone,
                    "network": plan_obj.network_name.lower(),
                    "amount": float(plan_obj.retail_amount),
                }
            },
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

        await telegram_client.edit_message_text(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": confirm_text,
                "parse_mode": "Markdown",
            }
        )
        return {"status": "ok"}

    elif click_data in ["menu_data", "buy_data"]:
        markup = {
            "inline_keyboard": [
                [
                    {
                        "text": "MTN",
                        "callback_data": "data_net_view:mtn:monthly:PROMPT_PHONE",
                    },
                    {
                        "text": "GLO",
                        "callback_data": "data_net_view:glo:monthly:PROMPT_PHONE",
                    },
                ],
                [
                    {
                        "text": "Airtel",
                        "callback_data": "data_net_view:airtel:monthly:PROMPT_PHONE",
                    },
                    {
                        "text": "9mobile",
                        "callback_data": "data_net_view:9mobile:monthly:PROMPT_PHONE",
                    },
                ],
                [{"text": "❌ Cancel", "callback_data": "action_cancel"}],
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
        await SessionManager.update_session(chat_id, "airtime", {})
        await telegram_client.edit_message_text(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": tx_copy["airtime_prompt"],
                "parse_mode": "Markdown",
            }
        )
        return {"status": "ok"}

    elif click_data in ["menu_electricity", "menu_cable", "menu_betting"]:
        key_target = (
            "electricity_prompt"
            if click_data == "menu_electricity"
            else ("cable_prompt" if click_data == "menu_cable" else "betting_prompt")
        )
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
        await state_manager.clear_session(str(chat_id))
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

    user_message = (payload.message.text or "").strip()

    if existing_user:
        profile = existing_user.profile

        # 1. PRIORITY INTERCEPT: Handle Custom Funding Amount Input State
        if profile.user_state == "awaiting_custom_fund_amount":
            clean_input = re.sub(r"\D", "", user_message)
            if not clean_input.isdigit() or int(clean_input) <= 0:
                await telegram_client.send_message({
                    "chat_id": chat_id,
                    "text": "❌ Invalid amount. Please enter a valid number (e.g., `5000`):",
                    "parse_mode": "Markdown"
                })
                return {"success": 200, "result": "invalid_amount"}

            amount_naira = int(clean_input)
            amount_in_kobo = amount_naira * 100

            # Reset state back to active
            profile.user_state = "active"
            await db.commit()

            tx_res = await paystack_provider.initialize_transaction(
                email=profile.email or f"{profile.id}@mypadi.app",
                amount_in_kobo=amount_in_kobo
            )
            if tx_res.get("status"):
                auth_url = tx_res.get("authorization_url")
                await telegram_client.send_message({
                    "chat_id": chat_id,
                    "text": (
                        f"💳 **Fund Your MyPadi Wallet (₦{amount_naira:,})**\n\n"
                        f"Tap the secure button below to complete your payment via Paystack Checkout:"
                    ),
                    "reply_markup": {
                        "inline_keyboard": [
                            [{"text": f"🔗 Pay ₦{amount_naira:,} via Paystack", "url": auth_url}]
                        ]
                    },
                    "parse_mode": "Markdown",
                })
            else:
                await telegram_client.send_message({
                    "chat_id": chat_id,
                    "text": f"❌ Could not generate payment link: {tx_res.get('message', 'Please try again.')}"
                })
            return {"success": 200, "result": "custom_fund_initialized"}

        # 2. Gatekeeping: Delegate actual onboarding states straight to OnboardingHandler
        onboarding_states = [
            "awaiting_language",
            "awaiting_phone",
            "awaiting_name_confirm",
            "awaiting_name_input",
            "awaiting_bvn",
            "awaiting_pin_setup",
            "awaiting_referral"
        ]
        db_state = (
            profile.user_state.lower() if profile.user_state else "awaiting_language"
        )
        if db_state in onboarding_states:
            res = await OnboardingHandler.process_onboarding(
                db=db,
                profile=profile,
                text=user_message,
                message_obj=payload.message,
                telegram_user_data=payload.message.message_from,
            )
            return {"success": 200, "result": res}

        # 3. Active User Commands & Conversation Pipeline
        user_lang = profile.lang or "english"
        tx_copy = TRANSACTION_RESPONSES.get(user_lang, TRANSACTION_RESPONSES["english"])

        # Handle explicit /fund command or text
        if user_message.lower() in ["/fund", "fund", "fund wallet", "topup"]:
            await telegram_client.send_message({
                "chat_id": chat_id,
                "text": (
                    "💳 **Fund Your MyPadi Wallet**\n\n"
                    "Select a quick funding amount or choose custom:"
                ),
                "reply_markup": {
                    "inline_keyboard": [
                        [
                            {"text": "₦500", "callback_data": "fund_preset:500"},
                            {"text": "₦1,000", "callback_data": "fund_preset:1000"},
                            {"text": "₦2,000", "callback_data": "fund_preset:2000"}
                        ],
                        [
                            {"text": "₦5,000", "callback_data": "fund_preset:5000"},
                            {"text": "₦10,000", "callback_data": "fund_preset:10000"}
                        ],
                        [
                            {"text": "✏️ Type Custom Amount", "callback_data": "fund_custom"}
                        ]
                    ]
                },
                "parse_mode": "Markdown",
            })
            return {"success": 200, "message": "fund_menu"}

        if user_message.lower() in [
            "hi",
            "hello",
            "hey",
            "yo",
            "sup",
            "barka",
            "sannu",
            "menu",
        ]:
            await state_manager.clear_session(str(telegramuser_id))
            greeting_text = tx_copy["greeting"]
            greeting_markup = tx_copy.get("greeting_markup")

            payload_data = {
                "chat_id": chat_id,
                "text": greeting_text,
                "parse_mode": "Markdown",
            }
            if greeting_markup:
                payload_data["reply_markup"] = greeting_markup

            await telegram_client.send_message(payload_data)
            return {"success": 200, "message": greeting_text}

        # Route through NLU and Vending Handler Pipeline
        pipeline_res = await handle_incoming_user_message(
            user_id=str(telegramuser_id),
            message_text=user_message,
            db=db,
            profile=profile,
        )
        bot_reply = pipeline_res.get("message", "Processing request...")
        reply_markup = pipeline_res.get("reply_markup")

        # If transaction failed due to insufficient balance, attach a quick fund button
        if "balance is running low" in bot_reply.lower():
            if not reply_markup:
                reply_markup = {"inline_keyboard": []}
            if "inline_keyboard" in reply_markup:
                reply_markup["inline_keyboard"].append([{"text": "💳 Fund Wallet via Paystack", "callback_data": "trigger_fund_wallet"}])

        msg_payload = {
            "chat_id": chart_id if 'chart_id' in locals() else chat_id,
            "text": bot_reply,
            "parse_mode": "Markdown",
        }
        if reply_markup:
            msg_payload["reply_markup"] = reply_markup

        await telegram_client.send_message(msg_payload)
        return {"success": 200, "message": pipeline_res.get("status")}

    else:
        # 3. Brand New User Creation & Referral Deep Link Extraction
        referred_by_code = None
        if user_message.startswith("/start ref_"):
            referred_by_code = user_message.replace("/start ref_", "").strip()

        firstName = payload.message.message_from.first_name
        lastName = payload.message.message_from.username or "Padi"
        new_tag = tag_generator(firstname=firstName, lastname=lastName)

        new_profile = Profile(
            user_tag=new_tag,
            first_name=firstName,
            last_name=lastName,
            email=f"{new_tag.replace('@', '')}@mypadi.com.ng",
            user_state="awaiting_language",
            referred_by=referred_by_code,
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

        # Initiate Onboarding
        res = await OnboardingHandler.process_onboarding(
            db=db,
            profile=new_profile,
            text=user_message,
            message_obj=payload.message,
            telegram_user_data=payload.message.message_from,
        )
        return {"success": 201, "result": res}