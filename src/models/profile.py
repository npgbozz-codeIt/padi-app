# src/models/profile.py
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base
from src.models.identity import UserIdentity
from src.models.virtual_acct import VirtualAcct


class Profile(Base):
    __tablename__ = "profile"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_tag: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    user_wallet: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), server_default="0.00", nullable=False
    )

    # Paystack KYC & Identification Information
    first_name: Mapped[str] = mapped_column(String(125))
    last_name: Mapped[str] = mapped_column(String(125))
    phone_num: Mapped[Optional[str]] = mapped_column(
        String(15), unique=True, nullable=True, index=True
    )
    lang: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, default="english"
    )
    user_state: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, default="awaiting_language"
    )
    email: Mapped[str] = mapped_column(String(125), unique=True)
    bnv: Mapped[Optional[str]] = mapped_column(String(11), unique=True, nullable=True)

    # Progressive Profiling Field
    bvn_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    # Transactional PIN (Unique constraint removed to prevent IntegrityErrors)
    hash_pin: Mapped[Optional[str]] = mapped_column(String(225), nullable=True)
    # Transaction Authorization Mode ("always" or "5min")
    pin_mode: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, default=None
    )


    # Viral Growth & Referral Tracking Fields
    referral_code: Mapped[Optional[str]] = mapped_column(
        String(50), unique=True, index=True, nullable=True
    )
    referred_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationships
    identities: Mapped[List["UserIdentity"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    user_vda: Mapped[Optional["VirtualAcct"]] = relationship(
        back_populates="profile",
        uselist=False,
    )

    date_created: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("Now()")
    )