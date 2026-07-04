# src/models/data_plan.py
import uuid
from enum import Enum
from datetime import datetime, timezone
from sqlalchemy import String, Numeric, Boolean, DateTime, Integer, Enum as SLEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from src.models.base import Base


class PlanType(str, Enum):
    SME = "sme"
    GIFTING = "gifting"
    CORPORATE = "corporate"


class DataPlan(Base):
    __tablename__ = "data_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    vendor_plan_id: Mapped[int] = mapped_column(
        Integer, unique=True, nullable=False
    )  # e.g., 135

    network_id: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, 3, 4
    network_name: Mapped[str] = mapped_column(String, nullable=False)  # "MTN", "GLO"
    plan_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # Keeps string matching simple ("SME", "GIFTING")

    size: Mapped[str] = mapped_column(String, nullable=False)  # "1.5GB"
    validity: Mapped[str] = mapped_column(String, nullable=False)  # "30 days"

    wholesale_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    retail_amount: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=False
    )  # Price calculated via margin_calculator

    plan_disabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_synced: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
