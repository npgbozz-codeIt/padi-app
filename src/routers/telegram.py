# src/routers/telegram.py
import re
from decimal import Decimal
import bcrypt
import httpx
from typing import Annotated
from src.database.redis import redis_client
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

# Internal imports
from src.database.db_conn import get_db
from src.models.data_plan import DataPlan
from src.models.identity import UserIdentity
from src.models.profile import Profile
from src.models.transaction import Transaction, TransactionStatus
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
from src.services.handlers.registry import get_vending_handler
from src.services.transaction_service import TransactionService
from src.schemas.telegram import TelegramWebhookInput
from src.utils.responses import TRANSACTION_RESPONSES
from src.utils.tag_generator import tag_generator

router = APIRouter()
paystack_provider = PaystackFinancialProvider()



def is_balance_inquiry(text: str) -> bool:
    """Detects /balance command and conversational balance query phrases."""
    clean = text.strip().lower()
    exact_matches = {
        "/balance", "balance", "check balance", "wallet balance",
        "my balance", "view balance", "show balance", "check my balance",
        "how much dey my wallet", "kudin asusu"
    }
    if clean in exact_matches or clean.startswith("/balance"):
        return True
    if "check balance" in clean or "wallet balance" in clean or "my balance" in clean:
        return True
    return False


def is_valid_phone(phone_str: str) -> bool:
    clean = re.sub(r"\D", "", str(phone_str))
    if len(clean) == 11 and clean.startswith("0"):
        return True
    if len(clean) == 13 and clean.startswith("234"):
        return True
    return False


def normalize_phone(phone_str: str) -> str:
    """Normalizes phone numbers to 234XXXXXXXXXX format for safe comparison."""
    clean = re.sub(r"\D", "", str(phone_str))
    if clean.startswith("0") and len(clean) == 11:
        return "234" + clean[1:]
    return clean


async def delete_telegram_message(chat_id: int, message_id: int):
    """Deletes sensitive messages (like transaction PINs) from Telegram chat."""
    try:
        url_delete = f"{telegram_client.base_url}/deleteMessage"
        async with httpx.AsyncClient() as client:
            await client.post(url_delete, json={"chat_id": chat_id, "message_id": message_id})
    except Exception as e:
        logger.warning(f"Failed to delete sensitive message: {e}")


def get_labels_for_txn(txn: Transaction) -> tuple[str, str]:
    """Computes human-friendly service and detail labels for any transaction type."""
    tx_type = txn.tx_type.value if hasattr(txn.tx_type, "value") else str(txn.tx_type)
    provider = (txn.provider or "").upper()
    if tx_type == "airtime":
        return f"{provider} Airtime".strip() or "Airtime", "Details"
    elif tx_type == "data":
        return f"{provider} Data".strip() or "Data", "Bundle"
    elif tx_type == "electricity":
        return f"{provider} Electricity".strip() or "Electricity", "Token"
    elif tx_type == "deposit":
        return "Wallet Top-up", "Details"
    elif tx_type == "cabletv":
        return f"{provider} Cable TV".strip() or "Cable TV", "Package"
    elif tx_type == "betting":
        return f"{provider} Betting".strip() or "Betting", "Account"
    return tx_type.replace("_", " ").title(), "Details"


async def render_history_page(db: AsyncSession, profile: Profile, page: int = 1) -> tuple[str, dict]:
    """Renders a 5-item compact transaction history summary page with interactive buttons."""
    page = max(1, page)
    limit = 5
    offset = (page - 1) * limit

    stmt = (
        select(Transaction)
        .where(Transaction.profile_id == profile.id)
        .order_by(Transaction.date_created.desc())
        .offset(offset)
        .limit(limit + 1)
    )
    res = await db.execute(stmt)
    txns = res.scalars().all()

    has_more = len(txns) > limit
    page_txns = txns[:limit]

    if not page_txns:
        text = (
            "📜 *Transaction History*\n\n"
            "You don't have any transactions recorded yet, Boss!\n"
            "When you recharge airtime, purchase data, or pay bills, your history will appear here."
        )
        markup = {"inline_keyboard": [[{"text": "❌ Close", "callback_data": "action_cancel"}]]}
        return text, markup

    lines = [f"📜 *Transaction History (Page {page})*", "──────────────────────────"]
    num_buttons = []

    for idx, txn in enumerate(page_txns, start=1):
        # Auto-heal legacy or failed transactions missing a reference
        if not txn.reference:
            prefix_map = {
                "airtime": "MP-AIR",
                "data": "MP-DAT",
                "electricity": "MP-ELC",
                "cabletv": "MP-CAB",
                "betting": "MP-BET",
                "deposit": "MP-DEP",
            }
            tx_key = txn.tx_type.value if hasattr(txn.tx_type, "value") else str(txn.tx_type)
            ref_prefix = prefix_map.get(tx_key, "MP-TXN")
            txn.reference = TransactionService.generate_reference(ref_prefix)
            await db.commit()

        date_str = txn.date_created.strftime("%d %b")
        service_label, _ = get_labels_for_txn(txn)
        amount_str = f"₦{int(txn.amount):,}" if txn.amount % 1 == 0 else f"₦{txn.amount:,.2f}"

        status_emoji = "✅"
        if txn.status == TransactionStatus.PENDING:
            status_emoji = "⏳"
        elif txn.status == TransactionStatus.FAILED:
            status_emoji = "❌"

        lines.append(f"{idx}. {date_str} • {service_label} • {amount_str} {status_emoji}")
        num_buttons.append({"text": f"[ {idx} ]", "callback_data": f"hist_view:{txn.reference}"})

    lines.append("──────────────────────────")
    lines.append("_Tap a number below to view the receipt and details:_")

    keyboard = [num_buttons]
    nav_row = []
    if page > 1:
        nav_row.append({"text": "⬅️ Newer", "callback_data": f"hist_page:{page - 1}"})
    if has_more:
        nav_row.append({"text": "➡️ Older", "callback_data": f"hist_page:{page + 1}"})

    if nav_row:
        keyboard.append(nav_row)
    keyboard.append([{"text": "❌ Close", "callback_data": "action_cancel"}])

    return "\n".join(lines), {"inline_keyboard": keyboard}


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

    # -----------------------------------------------------------------
    # Handle Image Receipt Generation Callback
    # -----------------------------------------------------------------
    if click_data.startswith("rx_img:"):
        reference = click_data.split(":", 1)[1]

        stmt = select(Transaction).where(Transaction.reference == reference)
        res = await db.execute(stmt)
        txn = res.scalars().first()

        if not txn and reference == "None" and profile:
            stmt_fallback = (
                select(Transaction)
                .where(Transaction.profile_id == profile.id, Transaction.reference.is_(None))
                .order_by(Transaction.date_created.desc())
            )
            res_fallback = await db.execute(stmt_fallback)
            txn = res_fallback.scalars().first()
            if txn and not txn.reference:
                txn.reference = TransactionService.generate_reference("MP-TXN")
                await db.commit()

        if not txn:
            if callback_query_id:
                try:
                    await telegram_client.answer_callback_query({
                        "callback_query_id": callback_query_id,
                        "text": "❌ Transaction record not found."
                    })
                except Exception:
                    pass
            return {"status": "error"}

        if callback_query_id:
            try:
                await telegram_client.answer_callback_query({
                    "callback_query_id": callback_query_id,
                    "text": "🎨 Rendering your high-res receipt..."
                })
            except Exception:
                pass

        try:
            png_bytes = TransactionService.generate_image_receipt_bytes(txn=txn)

            url_photo = f"{telegram_client.base_url}/sendPhoto"
            async with httpx.AsyncClient() as client:
                files = {"photo": ("mypadi_receipt.png", png_bytes.getvalue(), "image/png")}
                data = {
                    "chat_id": chat_id,
                    "caption": f"🧾 *MyPadi Verified Receipt*\nReference: `{txn.reference}`\n_Tap to save to gallery or share!_",
                    "parse_mode": "Markdown",
                }
                await client.post(url_photo, data=data, files=files)
        except Exception as e:
            logger.error(f"Failed to generate receipt image: {e}")
            await telegram_client.send_message({
                "chat_id": chat_id,
                "text": f"❌ Could not render image receipt: {e}"
            })

        return {"status": "ok"}
    # -----------------------------------------------------------------
    # Handle Transaction History Pagination & Drill-Down
    # -----------------------------------------------------------------
    if click_data.startswith("hist_page:"):
        if not profile:
            return {"status": "error"}
        raw_page = click_data.split(":", 1)[1]
        page = int(raw_page) if raw_page.isdigit() else 1
        text, markup = await render_history_page(db=db, profile=profile, page=page)
        await telegram_client.edit_message_text({
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "reply_markup": markup,
            "parse_mode": "Markdown",
        })
        return {"status": "ok"}

    if click_data.startswith("hist_view:"):
        if not profile:
            return {"status": "error"}
        target_ref = click_data.split(":", 1)[1]

        # Defensive lookup: by reference, or by UUID if passed or literal 'None'
        stmt = select(Transaction).where(Transaction.reference == target_ref)
        res = await db.execute(stmt)
        txn = res.scalars().first()

        if not txn and target_ref == "None":
            # Find the most recent transaction for this profile without a reference
            stmt_fallback = (
                select(Transaction)
                .where(Transaction.profile_id == profile.id, Transaction.reference.is_(None))
                .order_by(Transaction.date_created.desc())
            )
            res_fallback = await db.execute(stmt_fallback)
            txn = res_fallback.scalars().first()

        if txn and not txn.reference:
            txn.reference = TransactionService.generate_reference("MP-TXN")
            await db.commit()

        if not txn:
            if callback_query_id:
                try:
                    await telegram_client.answer_callback_query({
                        "callback_query_id": callback_query_id,
                        "text": "❌ Transaction record not found."
                    })
                except Exception:
                    pass
            return {"status": "error"}

        service_label, detail_label = get_labels_for_txn(txn)
        receipt_text = TransactionService.format_receipt(txn, service_label=service_label, detail_label=detail_label)
        drilldown_markup = {
            "inline_keyboard": [
                [{"text": "🖼️ Download Image Receipt", "callback_data": f"rx_img:{txn.reference}"}],
                [{"text": "⬅️ Back to History", "callback_data": "hist_page:1"}],
            ]
        }
        await telegram_client.edit_message_text({
            "chat_id": chat_id,
            "message_id": message_id,
            "text": receipt_text,
            "reply_markup": drilldown_markup,
            "parse_mode": "Markdown",
        })
        return {"status": "ok"}


    # Handle PIN Reset Trigger Callback
    if click_data == "trigger_reset_pin":
        await state_manager.set_session(
            user_id=str(telegramuser_id),
            state="AWAITING_RESET_CONTACT",
            intent="reset_pin",
            payload={}
        )
        await telegram_client.send_message({
            "chat_id": chat_id,
            "text": (
                "🛡️ **Reset Transaction PIN**\n\n"
                "To verify your identity, tap the button below to share your registered phone number:"
            ),
            "reply_markup": {
                "keyboard": [
                    [{"text": "📱 Verify with Phone Number", "request_contact": True}]
                ],
                "resize_keyboard": True,
                "one_time_keyboard": True
            },
            "parse_mode": "Markdown"
        })
        return {"status": "ok"}

    # Handle PIN Authorization Preference Selection
    if click_data.startswith("pin_mode:"):
        mode = click_data.split(":")[1]
        if profile:
            profile.pin_mode = mode
            await db.commit()

            session = await state_manager.get_session(str(telegramuser_id))
            if session:
                await state_manager.set_session(
                    user_id=str(telegramuser_id),
                    state="AWAITING_PIN",
                    intent=session.get("intent"),
                    payload=session.get("payload")
                )

            mode_text = "remembered for 5 minutes" if mode == "5min" else "required for every trade"
            await telegram_client.edit_message_text({
                "chat_id": chat_id,
                "message_id": message_id,
                "text": f"✅ Preference saved: PIN will be **{mode_text}**.\n\n🔐 Please enter your **4-digit transaction PIN** to authorize this payment:",
                "parse_mode": "Markdown"
            })
            return {"status": "ok"}

    # Handle Onboarding Inline Callbacks
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

    # Handle preset funding amount buttons
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
            else None
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

    elif click_data in ["menu_electricity", "menu_cable", "menu_betting", "menu_internet"]:
        key_target = (
            "electricity_prompt"
            if click_data == "menu_electricity"
            else ("cable_prompt" if click_data == "menu_cable" else ("internet_prompt" if click_data == "menu_internet" else "betting_prompt"))
        )
        await telegram_client.edit_message_text(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": tx_copy.get(key_target, tx_copy["coming_soon"]),
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
    message_id = payload.message.message_id
    raw_message = update.get("message", {})

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
        session = await state_manager.get_session(str(telegramuser_id))
        current_state = session.get("state") if session else None

        # -----------------------------------------------------------------
        # PIN RESET FLOW: Step 1 (Contact Shared Verification)
        # -----------------------------------------------------------------
        if current_state == "AWAITING_RESET_CONTACT":
            contact_data = raw_message.get("contact")
            if not contact_data:
                await telegram_client.send_message({
                    "chat_id": chat_id,
                    "text": "❌ Please tap the '📱 Verify with Phone Number' button below to continue, or type 'cancel'."
                })
                return {"success": 200, "result": "awaiting_contact"}

            sender_uid = contact_data.get("user_id")
            shared_phone = contact_data.get("phone_number", "")

            # Security verification
            if sender_uid != telegramuser_id or normalize_phone(shared_phone) != normalize_phone(profile.phone_num):
                await telegram_client.send_message({
                    "chat_id": chat_id,
                    "text": "❌ Phone number verification failed. The shared contact does not match your registered MyPadi profile.",
                    "reply_markup": {"remove_keyboard": True}
                })
                await state_manager.clear_session(str(telegramuser_id))
                return {"success": 200, "result": "reset_verification_failed"}

            # Verification passed -> Move to AWAITING_NEW_PIN
            await state_manager.set_session(
                user_id=str(telegramuser_id),
                state="AWAITING_NEW_PIN",
                intent="reset_pin",
                payload={}
            )
            await telegram_client.send_message({
                "chat_id": chat_id,
                "text": "✅ Identity verified successfully!\n\n🔐 Please enter your **new 4-digit transaction PIN**:",
                "reply_markup": {"remove_keyboard": True},
                "parse_mode": "Markdown"
            })
            return {"success": 200, "result": "contact_verified"}

        # -----------------------------------------------------------------
        # PIN RESET FLOW: Step 2 (Capture & Save New PIN)
        # -----------------------------------------------------------------
        if current_state == "AWAITING_NEW_PIN":
            await delete_telegram_message(chat_id, message_id)

            new_pin_input = user_message.strip()
            if not new_pin_input.isdigit() or len(new_pin_input) != 4:
                await telegram_client.send_message({
                    "chat_id": chat_id,
                    "text": "❌ PIN must be exactly 4 digits. Please enter a valid 4-digit PIN:"
                })
                return {"success": 200, "result": "invalid_new_pin"}

            hashed_new_pin = bcrypt.hashpw(new_pin_input.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            profile.hash_pin = hashed_new_pin
            await db.commit()

            # Clear failure attempts and locks
            await redis_client.delete(f"pin_fails:{telegramuser_id}")
            await redis_client.delete(f"pin_lockout:{telegramuser_id}")
            await state_manager.clear_session(str(telegramuser_id))

            await telegram_client.send_message({
                "chat_id": chat_id,
                "text": (
                    "🎉 **Transaction PIN Reset Successful!**\n\n"
                    "Your new PIN is now active and secured. You can continue trading safely!\n\n"
                    "Type 'menu' anytime to view available options."
                ),
                "parse_mode": "Markdown"
            })
            return {"success": 200, "result": "pin_reset_complete"}

        # -----------------------------------------------------------------
        # TRANSACTION PIN VERIFICATION INTERCEPT
        # -----------------------------------------------------------------
        if current_state == "AWAITING_PIN":
            await delete_telegram_message(chat_id, message_id)

            # Check if wallet is locked out
            is_locked = await redis_client.get(f"pin_lockout:{telegramuser_id}")
            if is_locked:
                ttl = await redis_client.ttl(f"pin_lockout:{telegramuser_id}")
                minutes_left = max(1, ttl // 60)
                await telegram_client.send_message({
                    "chat_id": chat_id,
                    "text": f"⏳ **Account Temporarily Locked**\n\nToo many incorrect PIN attempts. Please wait {minutes_left} minute(s) before trying again or tap Reset PIN below:",
                    "reply_markup": {
                        "inline_keyboard": [
                            [{"text": "🔄 Reset PIN Now", "callback_data": "trigger_reset_pin"}]
                        ]
                    },
                    "parse_mode": "Markdown"
                })
                return {"success": 200, "result": "account_locked"}

            pin_input = user_message.strip()
            if not pin_input.isdigit() or len(pin_input) != 4:
                await telegram_client.send_message({
                    "chat_id": chat_id,
                    "text": "❌ PIN must be exactly 4 digits. Please re-enter your PIN (or reply 'cancel'):"
                })
                return {"success": 200, "result": "invalid_pin_format"}

            # Verify against bcrypt hash stored in profile
            is_valid_pin = False
            if profile.hash_pin:
                is_valid_pin = bcrypt.checkpw(pin_input.encode("utf-8"), profile.hash_pin.encode("utf-8"))

            if not is_valid_pin:
                # Increment failure count in Redis
                fail_key = f"pin_fails:{telegramuser_id}"
                fails = await redis_client.incr(fail_key)
                await redis_client.expire(fail_key, 3600)

                if fails >= 5:
                    await redis_client.set(f"pin_lockout:{telegramuser_id}", "locked", ex=900)
                    await state_manager.clear_session(str(telegramuser_id))
                    await telegram_client.send_message({
                        "chat_id": chat_id,
                        "text": "🚨 **Security Alert**\n\n5 incorrect PIN attempts reached. Your wallet transactions are temporarily locked for 15 minutes.\n\nTap below to reset your PIN immediately:",
                        "reply_markup": {
                            "inline_keyboard": [
                                [{"text": "🔄 Reset PIN Now", "callback_data": "trigger_reset_pin"}]
                            ]
                        },
                        "parse_mode": "Markdown"
                    })
                    return {"success": 200, "result": "locked_out"}

                elif fails >= 3:
                    await telegram_client.send_message({
                        "chat_id": chat_id,
                        "text": f"❌ Incorrect PIN. ({fails}/5 attempts used).\n\nIf you've forgotten your PIN, you can reset it instantly:",
                        "reply_markup": {
                            "inline_keyboard": [
                                [{"text": "🔄 Forgot / Reset PIN", "callback_data": "trigger_reset_pin"}]
                            ]
                        }
                    })
                    return {"success": 200, "result": "pin_failed_warning"}

                else:
                    await telegram_client.send_message({
                        "chat_id": chat_id,
                        "text": f"❌ Incorrect transaction PIN. ({fails}/3 attempts). Please try again (or reply 'cancel'):"
                    })
                    return {"success": 200, "result": "pin_verification_failed"}

            # PIN is valid -> Clear failure counters
            await redis_client.delete(f"pin_fails:{telegramuser_id}")

            # If user selected 5-min caching mode, set 300s TTL in Redis
            if profile.pin_mode == "5min":
                await redis_client.set(f"pin_auth:{telegramuser_id}", "authenticated", ex=300)

            # PIN validated: Execute the pending transaction
            intent = session.get("intent")
            slots = session.get("payload", {}).get("slots", {})
            await state_manager.clear_session(str(telegramuser_id))

            handler = get_vending_handler(intent)
            if not handler:
                await telegram_client.send_message({
                    "chat_id": chat_id,
                    "text": "❌ Transaction handler unavailable."
                })
                return {"success": 200, "result": "no_handler"}

            exec_res = await handler.execute(db=db, profile=profile, slots=slots)
            bot_reply = exec_res.get("message", "Transaction completed.")
            reply_markup = exec_res.get("reply_markup")

            msg_payload = {
                "chat_id": chat_id,
                "text": bot_reply,
                "parse_mode": "Markdown"
            }
            if reply_markup:
                msg_payload["reply_markup"] = reply_markup

            await telegram_client.send_message(msg_payload)
            return {"success": 200, "result": "pin_authorized_and_executed"}

        # -----------------------------------------------------------------
        # PRIORITY INTERCEPT: Custom Funding Amount Input State
        # -----------------------------------------------------------------
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

        # -----------------------------------------------------------------
        # Gatekeeping: Onboarding states
        # -----------------------------------------------------------------
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

        # -----------------------------------------------------------------
        # Active User Commands & Conversation Pipeline
        # -----------------------------------------------------------------
        user_lang = profile.lang or "english"
        tx_copy = TRANSACTION_RESPONSES.get(user_lang, TRANSACTION_RESPONSES["english"])

        if is_balance_inquiry(user_message):
            await state_manager.clear_session(str(telegramuser_id))
            current_balance = (
                profile.user_wallet
                if profile and profile.user_wallet is not None
                else Decimal("0.00")
            )
            if not isinstance(current_balance, Decimal):
                current_balance = Decimal(str(current_balance))

            resp_template = tx_copy.get(
                "balance_response",
                "💰 *Your MyPadi Wallet Balance is:* *₦{balance}*\n\nTap below to top up your wallet anytime:"
            )
            bal_text = resp_template.format(balance=f"{current_balance:,.2f}")

            fund_markup = {
                "inline_keyboard": [
                    [{"text": "💳 Fund Wallet via Paystack", "callback_data": "trigger_fund_wallet"}]
                ]
            }
            await telegram_client.send_message({
                "chat_id": chat_id,
                "text": bal_text,
                "reply_markup": fund_markup,
                "parse_mode": "Markdown",
            })
            return {"success": 200, "message": "balance_displayed"}

        if user_message.lower() in ["/history", "history"]:
            history_text, history_markup = await render_history_page(db=db, profile=profile, page=1)
            await telegram_client.send_message({
                "chat_id": chat_id,
                "text": history_text,
                "reply_markup": history_markup,
                "parse_mode": "Markdown",
            })
            return {"success": 200, "message": "history_summary"}

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

        if "balance is running low" in bot_reply.lower():
            if not reply_markup:
                reply_markup = {"inline_keyboard": []}
            if "inline_keyboard" in reply_markup:
                reply_markup["inline_keyboard"].append([{"text": "💳 Fund Wallet via Paystack", "callback_data": "trigger_fund_wallet"}])

        msg_payload = {
            "chat_id": chat_id,
            "text": bot_reply,
            "parse_mode": "Markdown",
        }
        if reply_markup:
            msg_payload["reply_markup"] = reply_markup

        await telegram_client.send_message(msg_payload)
        return {"success": 200, "message": pipeline_res.get("status")}

    else:
        # Brand New User Creation
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

        res = await OnboardingHandler.process_onboarding(
            db=db,
            profile=new_profile,
            text=user_message,
            message_obj=payload.message,
            telegram_user_data=payload.message.message_from,
        )
        return {"success": 201, "result": res}