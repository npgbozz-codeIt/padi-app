# src/services/onboarding_handler.py
import re
import uuid
import bcrypt
import logging
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.profile import Profile
from src.models.virtual_acct import VirtualAcct
from src.services.telegram import telegram_client
from src.services.financial.paystack import PaystackFinancialProvider

logger = logging.getLogger("uvicorn.error")
paystack_provider = PaystackFinancialProvider()


class OnboardingHandler:
    @staticmethod
    async def process_onboarding(
        db: AsyncSession,
        profile: Profile,
        text: Optional[str] = None,
        message_obj: Optional[Any] = None,
        callback_data: Optional[str] = None,
        telegram_user_data: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Drives the multi-turn onboarding state machine including Telegram name extraction,
        inline language selection, progressive BVN verification, PIN security, and account setup.
        """
        current_state = profile.user_state or "awaiting_language"
        chat_id = message_obj.chat.id if message_obj and message_obj.chat else None
        msg_id = message_obj.message_id if message_obj else None

        async def send(payload: dict):
            if chat_id:
                await telegram_client.send_message(payload)

        # 1. State: Awaiting Language Selection
        if current_state == "awaiting_language":
            chosen_lang = None
            if callback_data and callback_data.startswith("lang_"):
                chosen_lang = callback_data.replace("lang_", "").strip().lower()
            elif text:
                t = text.strip().lower()
                if t in ["english", "pidgin", "hausa"]:
                    chosen_lang = t

            if chosen_lang in ["english", "pidgin", "hausa"]:
                profile.lang = chosen_lang
                profile.user_state = "awaiting_phone"
                await db.commit()

                await send({
                    "chat_id": chat_id,
                    "text": (
                        f"✅ Language set to **{chosen_lang.upper()}**!\n\n"
                        "Please tap the button below to share your phone number securely, "
                        "or type your 11-digit phone number manually:"
                    ),
                    "reply_markup": {
                        "keyboard": [[{"text": "📱 Share My Phone Number", "request_contact": True}]],
                        "resize_keyboard": True,
                        "one_time_keyboard": True,
                    },
                })
                return {"status": "handled"}
            else:
                await send({
                    "chat_id": chat_id,
                    "text": "Welcome to MyPadi! 🇳🇬 Please select your preferred language below:",
                    "reply_markup": {
                        "inline_keyboard": [
                            [
                                {"text": "🇬🇧 English", "callback_data": "lang_english"},
                                {"text": "🗣️ Pidgin", "callback_data": "lang_pidgin"},
                                {"text": "🇳🇬 Hausa", "callback_data": "lang_hausa"},
                            ]
                        ]
                    },
                })
                return {"status": "handled"}

        # 2. State: Awaiting Phone Number
        elif current_state == "awaiting_phone":
            phone_number = None
            if message_obj and message_obj.contact and message_obj.contact.phone_number:
                phone_number = message_obj.contact.phone_number
            elif text:
                clean_phone = text.strip()
                match = re.search(r"\b(0\d{9,10}|234\d{10})\b", clean_phone)
                if match:
                    phone_number = match.group(1)

            if not phone_number or len(phone_number) < 10:
                await send({
                    "chat_id": chat_id,
                    "text": "❌ Invalid phone number format. Please tap the share button or enter a valid 11-digit phone number.",
                })
                return {"status": "handled"}

            if phone_number.startswith("234"):
                phone_number = "0" + phone_number[3:]

            profile.phone_num = phone_number
            profile.user_state = "awaiting_name_confirm"
            await db.commit()

            # Extract name from Telegram user metadata if passed
            tg_first = getattr(telegram_user_data, "first_name", "") or "Padi"
            tg_last = getattr(telegram_user_data, "last_name", "") or ""

            profile.first_name = tg_first
            profile.last_name = tg_last if tg_last else "User"
            await db.commit()

            await send({
                "chat_id": chat_id,
                "text": (
                    f"📱 Phone number recorded!\n\n"
                    f"We retrieved your name from Telegram as:\n"
                    f"👤 **{profile.first_name} {profile.last_name}**\n\n"
                    f"Is this correct, or would you like to edit it?"
                ),
                "reply_markup": {
                    "inline_keyboard": [
                        [
                            {"text": "✅ Yes, It's Correct", "callback_data": "name_confirm_yes"},
                            {"text": "✏️ Edit Name", "callback_data": "name_confirm_edit"},
                        ]
                    ]
                },
            })
            return {"status": "handled"}

        # 3. State: Awaiting Name Confirmation / Input
        elif current_state == "awaiting_name_confirm":
            if callback_data == "name_confirm_yes":
                profile.user_state = "awaiting_bvn"
                await db.commit()
                await send({
                    "chat_id": chat_id,
                    "text": (
                        "🔒 **Secure Your Wallet & Account**\n\n"
                        "We need your **11-digit BVN** solely to generate your personal deposit account "
                        "and verify your identity as mandated by regulations. We cannot access your bank funds.\n\n"
                        "Kindly type out your 11-digit BVN:"
                    ),
                    "reply_markup": {"remove_keyboard": True},
                })
                return {"status": "handled"}
            elif callback_data == "name_confirm_edit":
                profile.user_state = "awaiting_name_input"
                await db.commit()
                await send({
                    "chat_id": chat_id,
                    "text": "✏️ Please type your correct **First Name and Last Name** (e.g., *Oladoye Idreez*):",
                    "reply_markup": {"remove_keyboard": True},
                })
                return {"status": "handled"}
            else:
                await send({
                    "chat_id": chat_id,
                    "text": "Please tap one of the buttons above to confirm your name or edit it.",
                })
                return {"status": "handled"}

        elif current_state == "awaiting_name_input":
            name_text = (text or "").strip()
            parts = name_text.split()
            if len(parts) < 2:
                await send({
                    "chat_id": chat_id,
                    "text": "❌ Please provide both your **First Name** and **Last Name** (e.g., *Oladoye Idreez*):",
                })
                return {"status": "handled"}

            profile.first_name = parts[0]
            profile.last_name = " ".join(parts[1:])
            profile.user_state = "awaiting_bvn"
            await db.commit()

            await send({
                "chat_id": chat_id,
                "text": (
                    f"✅ Name updated to **{profile.first_name} {profile.last_name}**!\n\n"
                    "🔒 **Secure Your Wallet & Account**\n\n"
                    "We need your **11-digit BVN** solely to generate your personal deposit account "
                    "and verify your identity as mandated by regulations.\n\n"
                    "Kindly type out your 11-digit BVN:"
                ),
            })
            return {"status": "handled"}

        # 4. State: Awaiting BVN & Progressive Verification Fallback
        elif current_state == "awaiting_bvn":
            if callback_data == "verify_later":
                profile.bvn_verified = False
                profile.user_state = "awaiting_pin_setup"
                await db.commit()
                await send({
                    "chat_id": chat_id,
                    "text": (
                        "⏩ **BVN Verification Deferred**\n\n"
                        "No worries! You can verify your BVN anytime later from your wallet to unlock permanent account benefits.\n\n"
                        "🔐 Now, enter a secure **4-digit transaction PIN** to protect your wallet:"
                    ),
                    "reply_markup": {"remove_keyboard": True},
                })
                return {"status": "handled"}

            bvn_input = (text or "").strip()
            if not bvn_input.isdigit() or len(bvn_input) != 11:
                await send({
                    "chat_id": chat_id,
                    "text": "❌ BVN must be exactly 11 digits. Please check and re-enter your BVN, or skip for now:",
                    "reply_markup": {
                        "inline_keyboard": [[{"text": "⏩ Verify Later (Skip for Now)", "callback_data": "verify_later"}]]
                    },
                })
                return {"status": "handled"}

            if chat_id:
                await telegram_client.send_chat_action(chat_id, "typing")

            bvn_result = await paystack_provider.verify_bvn(bvn_input)
            if not bvn_result.get("status"):
                await send({
                    "chat_id": chat_id,
                    "text": (
                        f"❌ BVN Verification Failed: {bvn_result.get('message', 'Invalid BVN details.')}\n\n"
                        "You can re-enter your BVN or skip for now and verify later:"
                    ),
                    "reply_markup": {
                        "inline_keyboard": [[{"text": "⏩ Verify Later (Skip for Now)", "callback_data": "verify_later"}]]
                    },
                })
                return {"status": "handled"}

            profile.bnv = bvn_input
            profile.bvn_verified = True
            profile.user_state = "awaiting_pin_setup"
            await db.commit()

            await send({
                "chat_id": chat_id,
                "text": "🎉 BVN verified successfully!\n\n🔐 Now, enter a secure **4-digit transaction PIN** to protect your wallet:",
                "reply_markup": {"remove_keyboard": True},
            })
            return {"status": "handled"}

        # 5. State: Awaiting PIN Setup
        elif current_state == "awaiting_pin_setup":
            pin_input = (text or "").strip()

            if msg_id and chat_id:
                url_delete = f"{telegram_client.base_url}/deleteMessage"
                import httpx
                async with httpx.AsyncClient() as client:
                    await client.post(url_delete, json={"chat_id": chat_id, "message_id": msg_id})

            if not pin_input.isdigit() or len(pin_input) != 4:
                await send({
                    "chat_id": chat_id,
                    "text": "❌ PIN must be exactly 4 digits (e.g., 2026). Please enter your 4-digit PIN:",
                })
                return {"status": "handled"}

            hashed = bcrypt.hashpw(pin_input.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            profile.hash_pin = hashed
            profile.user_state = "awaiting_referral"
            await db.commit()

            await send({
                "chat_id": chat_id,
                "text": (
                    "🔒 PIN saved and secured!\n\n"
                    "🎁 **Got a Referral Code?**\n"
                    "If a friend invited you, enter their referral code now, or tap **Skip**:"
                ),
                "reply_markup": {
                    "inline_keyboard": [[{"text": "⏩ Skip Referral", "callback_data": "skip_referral"}]]
                },
            })
            return {"status": "handled"}

        # 6. State: Awaiting Referral Code & Final Provisioning
        elif current_state == "awaiting_referral":
            ref_input = (text or "").strip() if text else ""
            if callback_data == "skip_referral" or ref_input.lower() == "skip":
                profile.referred_by = None
            elif ref_input:
                profile.referred_by = ref_input

            unique_tag = f"PADI-{uuid.uuid4().hex[:6].upper()}"
            profile.referral_code = unique_tag
            profile.user_state = "active"
            await db.commit()

            if chat_id:
                await telegram_client.send_chat_action(chat_id, "typing")
                await send({
                    "chat_id": chat_id,
                    "text": "🚀 Finalizing your secure MyPadi account setup...",
                })

            ref_link = await telegram_client.generate_referral_link(unique_tag)

            # If user verified BVN, attempt DVA provisioning
            if profile.bvn_verified:
                cust_res = await paystack_provider.create_customer(
                    first_name=profile.first_name,
                    last_name=profile.last_name,
                    email=profile.email or f"{profile.id}@mypadi.app",
                    phone=profile.phone_num,
                )

                if cust_res.get("status"):
                    cust_code = cust_res.get("customer_code")
                    dva_res = await paystack_provider.provision_dedicated_account(cust_code)

                    if dva_res.get("status"):
                        virtual_acc = VirtualAcct(
                            profile_id=profile.id,
                            bank_name=dva_res.get("bank_name"),
                            accoount_num=dva_res.get("account_number"),
                            account_name=dva_res.get("account_name"),
                            paystack_customer_code=cust_code,
                        )
                        db.add(virtual_acc)
                        await db.commit()

                        success_card = (
                            f"🥳 **Welcome to MyPadi, Boss!**\n"
                            f"Your account is fully verified and secured.\n\n"
                            f"🏦 **Your Dedicated Deposit Account**\n"
                            f"• Bank: {dva_res.get('bank_name')}\n"
                            f"• Account Number: `{dva_res.get('account_number')}`\n"
                            f"• Account Name: {dva_res.get('account_name')}\n"
                            f"• Wallet Balance: ₦0.00\n\n"
                            f"🔗 **Your Referral Link:**\n"
                            f"`{ref_link}`\n\n"
                            f"*Transfer any amount to your virtual account to fund your wallet instantly! Type 'menu' anytime.*"
                        )
                        await send({"chat_id": chat_id, "text": success_card, "reply_markup": {"remove_keyboard": True}})
                        return {"status": "completed"}

            # Fallback for unverified BVN or DVA provisioning hiccup
            welcome_card = (
                f"🥳 **Welcome to MyPadi, Boss!**\n"
                f"Your account is active, your wallet is ready (Balance: ₦0.00), and you're officially a Padian!\n\n"
                f"🔗 **Your Referral Link:**\n"
                f"`{ref_link}`\n\n"
                f"*Type 'menu' anytime to buy data, airtime, or check your wallet.*"
            )
            await send({"chat_id": chat_id, "text": welcome_card, "reply_markup": {"remove_keyboard": True}})
            return {"status": "completed"}

        return {"status": "unknown"}