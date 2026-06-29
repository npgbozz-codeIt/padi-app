# src/schemas/telegram
from src.schemas.base import BaseModel
from pydantic import ConfigDict, Field
from typing import Optional


class TelegramUser(BaseModel):
    id: int
    is_bot: bool
    first_name: str
    username: Optional[str] = None
    language_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TelegramMessage(BaseModel):
    message_id: int
    message_from: TelegramUser = Field(..., alias="from")
    date: int
    text: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TelegramWebhookInput(BaseModel):
    update_id: int
    message: TelegramMessage

    model_config = ConfigDict(from_attributes=True)
