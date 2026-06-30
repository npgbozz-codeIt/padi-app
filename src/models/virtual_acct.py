from typing import TYPE_CHECKING

from src.models.base import Base
from datetime import datetime
import uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, text, ForeignKey

if TYPE_CHECKING:
    from src.models.profile import Profile


class VirtualAcct(Base):
    __tablename__ = "virtualacct"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profile.id"))
    bank_name: Mapped[str] = mapped_column(String(125))
    accoount_num: Mapped[str] = mapped_column(String(10), unique=True)
    account_name: Mapped[str] = mapped_column(String(125))
    paystack_customer_code: Mapped[str] = mapped_column(String(125))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("Now()"))
    # relationship
    profile: Mapped["Profile"] = relationship(back_populates="user_vda")  # type: ignore
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=text("Now()"), onupdate=text("NOW()")
    )
