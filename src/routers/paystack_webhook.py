# src/routers/paystack_webhook.py
import hmac
import hashlib
import json
import os
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.db_conn import get_db
from src.models.identity import UserIdentity
from src.models.profile import Profile
from src.models.transaction import Transaction, TransactionStatus, TransactionType
from src.services.telegram import logger, telegram_client
from src.services.transaction_service import TransactionService

router = APIRouter(prefix="/webhook", tags=["Paystack Webhook"])

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")


@router.post("/paystack", status_code=status.HTTP_200_OK)
async def paystack_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_paystack_signature: Annotated[str | None, Header()] = None,
):
    """
    Listens for live Paystack events, verifies cryptographic HMAC signatures,
    credits the customer's wallet atomically, records the deposit in the ledger,
    notifies the user on Telegram, and alerts the admin.
    """
    raw_body = await request.body()

    # 1. Cryptographic HMAC SHA-512 Signature Verification
    if not PAYSTACK_SECRET_KEY:
        logger.error("PAYSTACK_SECRET_KEY is not configured in environment.")
        raise HTTPException(status_code=500, detail="Server misconfiguration")

    if not x_paystack_signature:
        logger.warning("Missing x-paystack-signature header.")
        raise HTTPException(status_code=400, detail="Missing signature header")

    computed_signature = hmac.new(
        key=PAYSTACK_SECRET_KEY.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha512,
    ).hexdigest()

    if not hmac.compare_digest(computed_signature, x_paystack_signature):
        logger.warning("Invalid Paystack webhook signature detected.")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # 2. Parse Event Payload
    try:
        event_payload = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        logger.error(f"Failed to parse Paystack webhook JSON: {e}")
        return {"status": "error", "message": "Invalid JSON payload"}

    event_type = event_payload.get("event")
    data = event_payload.get("data", {})

    logger.info(f"🔔 [Paystack Webhook] Received event: {event_type}")

    # Process only successful charges
    if event_type != "charge.success":
        return {"status": "ignored", "reason": f"Unhandled event type: {event_type}"}

    reference = data.get("reference")
    amount_kobo = data.get("amount", 0)
    customer_email = data.get("customer", {}).get("email", "").strip().lower()

    if not reference or amount_kobo <= 0:
        logger.warning(f"Malformed charge.success payload: ref={reference}, kobo={amount_kobo}")
        return {"status": "ignored", "reason": "Malformed payload"}

    amount_naira = Decimal(str(amount_kobo)) / Decimal("100")

    # 3. Idempotency Guard (Check if reference was already recorded)
    stmt_check = select(Transaction).where(Transaction.reference == reference)
    res_check = await db.execute(stmt_check)
    existing_txn = res_check.scalars().first()

    if existing_txn:
        logger.info(f"🛡️ [Idempotency] Deposit reference {reference} already processed. Skipping.")
        return {"status": "success", "message": "Transaction already recorded"}

    # 4. Locate Customer Profile
    stmt_user = (
        select(Profile)
        .options(selectinload(Profile.identities))
        .where(Profile.email.ilike(customer_email))
    )
    res_user = await db.execute(stmt_user)
    profile = res_user.scalars().first()

    if not profile:
        logger.error(f"No profile found matching customer email: {customer_email}")
        return {"status": "error", "message": "User not found"}

    # 5. Atomic Decimal Wallet Credit
    current_wallet = profile.user_wallet if profile.user_wallet is not None else Decimal("0.00")
    profile.user_wallet = current_wallet + amount_naira
    await db.flush()

    # 6. Centralized Ledger Record via TransactionService
    deposit_txn = await TransactionService.record_transaction(
        db=db,
        profile=profile,
        tx_type=TransactionType.DEPOSIT,
        amount=amount_naira,
        recipient=profile.user_tag,
        provider="PAYSTACK",
        status=TransactionStatus.SUCCESSFUL,
        custom_ref=reference,
        token_or_details="Paystack Wallet Top-up",
    )

    # 7. Notify User on Telegram
    tg_identity = next(
        (ident for ident in profile.identities if ident.platform == "Telegram"), None
    )
    if tg_identity and tg_identity.platform_id:
        chat_id = int(tg_identity.platform_id)
        user_receipt_text = (
            "🎉 *Wallet Funded Successfully!*\n\n"
            f"Your payment of *₦{amount_naira:,.2f}* was received via Paystack.\n"
            f"• *Reference:* `{reference}`\n"
            f"• *New Wallet Balance:* *₦{profile.user_wallet:,.2f}*\n\n"
            "You can now trade seamlessly! Type 'menu' anytime."
        )
        try:
            await telegram_client.send_message({
                "chat_id": chat_id,
                "text": user_receipt_text,
                "parse_mode": "Markdown",
            })
        except Exception as e:
            logger.error(f"Failed to deliver funding confirmation to user {chat_id}: {e}")

    # 8. Dispatch Real-Time Admin Alert
    await TransactionService.dispatch_admin_alert(
        event_title="Wallet Funded",
        details={
            "User": profile.user_tag,
            "Amount": f"₦{amount_naira:,.2f}",
            "Reference": reference,
            "New Balance": f"₦{profile.user_wallet:,.2f}",
        },
        level="INFO",
    )

    return {"status": "success", "reference": reference, "credited": float(amount_naira)}