# src/services/transaction_service.py
import io
import os
import uuid
import xml.sax.saxutils as saxutils
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

import resvg_py

from src.models.profile import Profile
from src.models.transaction import Transaction, TransactionStatus, TransactionType
from src.services.telegram import logger, telegram_client

ADMIN_CHAT_ID = os.getenv("ADMIN_TELEGRAM_ID")
TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "assets", "receipt_template.svg"
)


class TransactionService:
    @staticmethod
    def generate_reference(prefix: str = "MP") -> str:
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
        created_time = txn.date_created.strftime("%d %b %Y, %I:%M %p")
        status_display = "SUCCESSFUL ✅"
        if txn.status == TransactionStatus.FAILED:
            status_display = "FAILED (Refunded) ❌"
        elif txn.status == TransactionStatus.PENDING:
            status_display = "PENDING ⏳"

        lines = [
            "🧾 *MYPADI TRANSACTION RECEIPT*",
            "──────────────────────────",
            f"• *Status:*        {status_display}",
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

    @classmethod
    def generate_image_receipt_bytes(cls, txn: Transaction) -> io.BytesIO:
        """
        Populates receipt_template.svg with transaction data
        and converts it into high-resolution PNG bytes using Rust-powered resvg.
        """
        real_template_path = os.path.abspath(TEMPLATE_PATH)
        if not os.path.exists(real_template_path):
            raise FileNotFoundError(f"SVG template missing at: {real_template_path}")

        with open(real_template_path, "r", encoding="utf-8") as f:
            template = f.read()

        category_title = f"{txn.provider or ''} {txn.tx_type.value.upper()} VEND".strip()

        if txn.tx_type == TransactionType.ELECTRICITY:
            token_header = "20-DIGIT PREPAID TOKEN (ENTER ON METER)"
            token_val = txn.token_or_details or "PENDING GENERATION"
            row1_label = "METER / ACCOUNT"
        elif txn.tx_type == TransactionType.DATA:
            token_header = "DATA PLAN FULFILLMENT"
            token_val = txn.token_or_details or "ACTIVE DATA BUNDLE"
            row1_label = "RECIPIENT LINE"
        else:
            token_header = "FULFILLMENT CONFIRMATION"
            token_val = "DISPATCHED SUCCESSFULLY"
            row1_label = "RECIPIENT LINE"

        status_label = "PAID // INSTANT" if txn.status == TransactionStatus.SUCCESSFUL else "FAILED"
        created_str = txn.date_created.strftime("%d %b %Y // %H:%M:%S")

        replacements = {
            "{{STATUS_LABEL}}": status_label,
            "{{AMOUNT}}": f"NGN {txn.amount:,.2f}",
            "{{SERVICE_CATEGORY}}": category_title,
            "{{TOKEN_HEADER}}": token_header,
            "{{TOKEN_VALUE}}": str(token_val),
            "{{ROW1_LABEL}}": row1_label,
            "{{ROW1_VALUE}}": str(txn.recipient),
            "{{PROVIDER_VALUE}}": f"{txn.provider or 'MYPADI'} NETWORK",
            "{{TIMESTAMP}}": created_str,
            "{{REFERENCE}}": str(txn.reference),
        }

        for key, val in replacements.items():
            safe_val = saxutils.escape(str(val))
            template = template.replace(key, safe_val)

        png_raw = resvg_py.svg_to_bytes(svg_string=template)
        png_io = io.BytesIO(bytes(png_raw))
        png_io.seek(0)
        return png_io

    @staticmethod
    async def dispatch_admin_alert(
        event_title: str,
        details: dict,
        level: str = "INFO",
    ):
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