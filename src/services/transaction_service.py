# src/services/transaction_service.py
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.profile import Profile
from src.models.transaction import Transaction, TransactionStatus, TransactionType
from src.services.telegram import logger, telegram_client

ADMIN_CHAT_ID = os.getenv("ADMIN_TELEGRAM_ID")


class TransactionService:
    @staticmethod
    def generate_reference(prefix: str = "MP") -> str:
        """Generates an 8-character unique reference like MP-AIR-A1B2C3D4."""
        short_id = uuid.uuid4().hex[:8].upper()
        return f"{prefix}-{short_id}"

    @classmethod
    async def record_transaction(
        cls,
        db: AsyncSession,
        profile: Profile,
        tx_type: TransactionType,
        amount: Decimal,
        recipient: str,
        provider: Optional[str] = None,
        status: TransactionStatus = TransactionStatus.SUCCESSFUL,
        token_or_details: Optional[str] = None,
        custom_ref: Optional[str] = None,
    ) -> Transaction:
        """
        Creates a ledger entry in PostgreSQL, captures balance_after,
        and commits the record atomically.
        """
        prefix_map = {
            TransactionType.AIRTIME: "MP-AIR",
            TransactionType.DATA: "MP-DAT",
            TransactionType.ELECTRICITY: "MP-ELC",
            TransactionType.CABLETV: "MP-CAB",
            TransactionType.BETTING: "MP-BET",
            TransactionType.DEPOSIT: "MP-DEP",
        }
        ref_prefix = prefix_map.get(tx_type, "MP-TXN")
        reference = custom_ref or cls.generate_reference(ref_prefix)

        txn = Transaction(
            profile_id=profile.id,
            tx_type=tx_type,
            amount=amount,
            recipient=recipient,
            provider=provider.upper() if provider else None,
            reference=reference,
            status=status,
            token_or_details=token_or_details,
            balance_after=profile.user_wallet,
        )
        db.add(txn)
        await db.commit()
        await db.refresh(txn)

        logger.info(
            f"📒 [Ledger Entry] Ref: {reference} | Type: {tx_type.value} | "
            f"Amount: ₦{amount:,.2f} | Balance After: ₦{profile.user_wallet:,.2f}"
        )
        return txn

    @staticmethod
    def format_receipt(
        txn: Transaction,
        service_label: str,
        detail_label: Optional[str] = None,
    ) -> str:
        """
        Formats a clean, high-contrast Telegram text receipt with single-tap
        copyable monospaced code blocks for references, numbers, and tokens.
        """
        created_time = txn.date_created.strftime("%d %b %Y, %I:%M %p")
        
        lines = [
            "🧾 *MYPADI TRANSACTION RECEIPT*",
            "──────────────────────────",
            f"• *Service:*       {service_label}",
            f"• *Recipient:*     `{txn.recipient}`",
            f"• *Amount Paid:*   ₦{txn.amount:,.2f}",
            f"• *Reference:*     `{txn.reference}`",
            f"• *Date & Time:*   {created_time}",
        ]

        if txn.token_or_details:
            header = detail_label or "Details"
            lines.append(f"• *{header}:*   `{txn.token_or_details}`")

        balance_display = (
            f"₦{txn.balance_after:,.2f}" if txn.balance_after is not None else "N/A"
        )
        lines.extend([
            "──────────────────────────",
            f"• *Wallet Balance:* *{balance_display}*",
            "",
            "_Tap any code block above to copy instantly!_",
        ])

        return "\n".join(lines)

    @staticmethod
    async def dispatch_admin_alert(
        event_title: str,
        details: dict,
        level: str = "INFO",
    ):
        """
        Dispatches real-time internal alerts directly to the Admin Telegram ID.
        """
        if not ADMIN_CHAT_ID:
            logger.warning("ADMIN_TELEGRAM_ID not set; skipping admin alert dispatch.")
            return

        icon = "🚨" if level == "ERROR" else ("⚠️" if level == "WARNING" else "🔔")
        alert_lines = [f"{icon} *[ADMIN ALERT: {event_title.upper()}]*", "──────────────────────────"]
        for key, val in details.items():
            alert_lines.append(f"• *{key}:* `{val}`")
        alert_lines.append(f"• *Timestamp:* {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

        try:
            await telegram_client.send_message({
                "chat_id": int(ADMIN_CHAT_ID),
                "text": "\n".join(alert_lines),
                "parse_mode": "Markdown",
            })
        except Exception as e:
            logger.error(f"Failed to dispatch admin alert: {e}")