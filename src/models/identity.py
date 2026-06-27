from src.models.base import Base
import uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey


class UserIdentity(Base):
    __tablename__ = "identities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(20))
    platform_id: Mapped[str] = mapped_column(String(50), index=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profile.id", ondelete="CASCADE")
    )
    # relationship
    profile: Mapped["Profile"] = relationship(back_populates="identities")
