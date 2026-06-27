#scr/schemas/onboarding
from decimal import Decimal

from src.schemas import Base
from pydantic import EmailStr, Field, ConfigDict, field_validator
from typing import Optional
import uuid


class OnboardingInput(Base):
    first_name: str = Field(min_length=2, max_length=100)
    last_name: str = Field(min_length=2, max_length=100)
    phone_num: str = Field(min_length=11, max_length=13)
    email: EmailStr = Field(max_length=150)
    bvn: str = Field(default=None, min_length=11)
    

    model_config = ConfigDict(from_attributes=True)

    @field_validator("bvn")
    def validate_bvn(cls, value):
        if not value.isdigit():
            raise ValueError("BVN must contain only digits.")
        if len(value) != 11:
            raise ValueError("BVN must be exactly 11 digits long.")
        return value
class OnboardingResponse(Base):
    id: uuid.UUID
    email: EmailStr = Field(max_length=150)
    user_tag: str = Field(min_length=5, max_length=100)
    wallet_balance: Decimal = Field(default=0.00, ge=0.00)
    is_verified : bool = Field(default=False)
    model_config = ConfigDict(from_attributes=True)