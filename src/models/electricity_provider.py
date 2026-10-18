# src/models/electricity_provider.py
from sqlalchemy import String, Integer, Boolean, Numeric, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from src.models.base import Base


class ElectricityProvider(Base):
    """
    Local-cache registry for active Electricity Distribution Companies (DisCos).
    Kept in sync with Bigisub upstream API.
    """
    __tablename__ = "electricity_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # The exact service string or ID expected by Bigisub (e.g., "ikeja-electric")
    provider_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    
    # Customer friendly name (e.g., "Ikeja Electric (IKEDC)")
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    
    # Toggle to dynamically disable a DisCo locally if they are undergoing downtime
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Supported payment modes: "prepaid", "postpaid", or "both"
    supported_modes: Mapped[str] = mapped_column(String(50), default="both")

    # Upstream discount or commission rate if any (e.g., 0.01 for 1% commission earned by platform)
    commission_rate: Mapped[float] = mapped_column(Numeric(5, 4), default=0.0000)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )