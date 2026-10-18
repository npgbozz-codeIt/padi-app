# src/models/transaction.py
import uuid
from decimal import Decimal
from enum import Enum
from datetime import datetime, timezone
from sqlalchemy import String, Numeric, DateTime, ForeignKey, Enum as SLEnum, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from src.models.base import Base


class TransactionType(str, Enum):
    AIRTIME = "airtime"
    DATA = "data"
    INTERNET = "internet"
    BETTING = "betting"
    EDUCATION = "education"
    ELECTRICITY = "electricity"  # Added ELECTRICITY
    CABLETV = "cabletv"
    P2P_TRANSFER = "p2p_transfer"
    DEPOSIT = "deposit"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    SUCCESSFUL = "successful"
    FAILED = "failed"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profile.id", ondelete="CASCADE"), nullable=False
    )

    tx_type: Mapped[TransactionType] = mapped_column(
        SLEnum(TransactionType), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    recipient: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=True)

    reference: Mapped[str] = mapped_column(String, unique=True, nullable=True)
    status: Mapped[TransactionStatus] = mapped_column(
        SLEnum(TransactionStatus), default=TransactionStatus.PENDING, nullable=False
    )

    # Fulfillment specific: Token for electricity, bundle size for data, etc.
    token_or_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Financial snapshot after transaction completion
    balance_after: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    date_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )