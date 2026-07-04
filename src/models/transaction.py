# src/models/transaction.py
import uuid
from enum import Enum
from datetime import datetime, timezone
from sqlalchemy import String, Numeric, DateTime, ForeignKey, Enum as SLEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from src.models.base import Base


class TransactionType(str, Enum):
    AIRTIME = "airtime"
    DATA = "data"
    INTERNET = "internet"
    BETTING = "betting"
    EDUCATION = "education"
    CABLETV = "cabletv"
    P2P_TRANSFER = "p2p_transfer"
    DEPOSIT = "deposit"


class TransactionStatus(str, Enum):
    PENDING = "pending"
    SUCCESSFUL = "successful"
    FAILED = "failed"


class Transaction(Base):
    __tablename__ = "transactions"

    # Modern SQLAlchemy v2 Mapping Definitions
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profile.id", ondelete="CASCADE"), nullable=False
    )

    tx_type: Mapped[TransactionType] = mapped_column(
        SLEnum(TransactionType), nullable=False
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    recipient: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=True)

    reference: Mapped[str] = mapped_column(String, unique=True, nullable=True)
    status: Mapped[TransactionStatus] = mapped_column(
        SLEnum(TransactionStatus), default=TransactionStatus.PENDING, nullable=False
    )

    # Secure, non-deprecated timezone-aware timestamp creation logic
    date_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
