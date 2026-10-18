# src/routers/paystack_webhook.py
import hmac
import hashlib
import logging
from decimal import Decimal
from fastapi import APIRouter, Request, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database.db_conn import get_db
from src.models.profile import Profile
from src.services.financial.paystack import PaystackFinancialProvider
from src.services.telegram import telegram_client

router = APIRouter(prefix="/webhook", tags=["Webhook"])
logger = logging.getLogger("uvicorn.error")
paystack_provider = PaystackFinancialProvider()


@router.post("/paystack", status_code=status.HTTP_200_OK)
async def paystack_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Receives async events from Paystack (e.g., charge.success),
    verifies the signature, credits the user's wallet, and notifies them on Telegram.
    """
    body_bytes = await request.body()
    paystack_signature = request.headers.get("x-paystack-signature", "")

    # 1. Verify Webhook Signature for security
    computed_signature = hmac.new(
        paystack_provider.secret_key.encode("utf-8"),
        body_bytes,
        hashlib.sha512
    ).hexdigest()

    if computed_signature != paystack_signature:
        logger.warning("🛡️ [Paystack Webhook] Invalid signature detected!")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_data = await request.json()
    event_type = event_data.get("event")
    data = event_data.get("data", {})

    logger.info(f"📥 [Paystack Webhook Received] Event: {event_type}")

    # 2. Handle Successful Charge Event
    if event_type == "charge.success":
        email = data.get("customer", {}).get("email")
        amount_in_kobo = data.get("amount", 0)
        
        # FIX: Cast to Decimal to prevent TypeError with database Numeric fields
        amount_naira = Decimal(amount_in_kobo) / Decimal(100)
        reference = data.get("reference")

        if not email:
            return {"status": "ignored", "reason": "no email in payload"}

        # 3. Find User Profile in DB
        stmt = select(Profile).where(Profile.email == email)
        res = await db.execute(stmt)
        profile = res.scalars().first()

        if profile:
            # Credit wallet safely using Decimal arithmetic
            profile.user_wallet += amount_naira
            await db.commit()
            logger.info(f"💰 [Wallet Credited] User {profile.id} credited with ₦{amount_naira:,.2f}")

            # 4. Find user's Telegram Chat ID via their UserIdentity mapping
            from src.models.identity import UserIdentity
            id_stmt = select(UserIdentity).where(
                UserIdentity.profile_id == profile.id,
                UserIdentity.platform == "Telegram"
            )
            id_res = await db.execute(id_stmt)
            identity = id_res.scalars().first()

            if identity:
                chat_id = int(identity.platform_id)
                success_msg = (
                    f"🎉 **Wallet Funded Successfully!**\n\n"
                    f"Your payment of **₦{amount_naira:,.2f}** was received via Paystack.\n"
                    f"• Reference: `{reference}`\n"
                    f"• New Wallet Balance: **₦{profile.user_wallet:,.2f}**\n\n"
                    f"You can now trade seamlessly! Type 'menu' anytime."
                )
                await telegram_client.send_message({
                    "chat_id": chat_id,
                    "text": success_msg,
                    "parse_mode": "Markdown"
                })

    return {"status": "success"}