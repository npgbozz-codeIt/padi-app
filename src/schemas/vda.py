#scr/schemas/vda
from src.schemas.base import Base
from pydantic import EmailStr, Field, ConfigDict



class VdaRequest(Base):
    first_name: str = Field(..., min_length=5, max_length=100)
    last_name: str = Field(..., min_length=5, max_length=100)
    email: EmailStr = Field(..., max_length=150)
    bvn: str = Field(..., min_length=11)
    phone_num: str = Field(..., min_length=11, max_length=13)

    model_config = ConfigDict(from_attributes=True)
