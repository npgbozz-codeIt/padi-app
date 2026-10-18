# src/models/electricity.py
from sqlalchemy import ForeignKey, Numeric, String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from typing import Optional
from src.models.base import Base


class ElectricityTransaction(Base):
    __tablename__ = "electricity_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE"), nullable=False
    )

    # Meter Profile Metrics
    disco_name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # e.g., ikeja-electric
    meter_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    meter_type: Mapped[str] = mapped_column(String(20), default="prepaid")
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Financial Auditing
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    fee: Mapped[float] = mapped_column(Numeric(10, 2), default=0.00)

    # Processing Metrics
    status: Mapped[str] = mapped_column(
        String(20), default="PENDING"
    )  # PENDING, SUCCESSFUL, FAILED
    vendor_reference: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, unique=True
    )
    meter_token: Mapped[Optional[str]] = mapped_column(
        String(120), nullable=True
    )  # Populated with voucher token numbers
    units: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # e.g., 45.2kWh

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
