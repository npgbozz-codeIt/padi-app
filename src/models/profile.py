from src.models.base import Base
from src.models.identity import UserIdentity
from src.models.virtual_acct import VirtualAcct
from datetime import datetime
from typing import List, Optional
from decimal import Decimal
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy import String, Numeric, DateTime, text
import uuid


class Profile(Base):
    __tablename__ = "profile"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_tag: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    user_wallet: Mapped[Decimal] = mapped_column(Numeric(12, 2), server_default="0.00")
    # paystack kyc information
    first_name: Mapped[str] = mapped_column(String(125))
    last_name: Mapped[str] = mapped_column(String(125))
    email: Mapped[str] = mapped_column(String(125), unique=True)
    bnv: Mapped[str] = mapped_column(String(11), unique=True)
    # transactional pin
    hash_pin: Mapped[str] = mapped_column(String(225), unique=True)
    # relashionships
    identities: Mapped[List["UserIdentity"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    user_vda: Mapped[Optional["VirtualAcct"]] = relationship(
        back_populates="profile", uselist=False
    )
    date_created: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("Now()")
    )
