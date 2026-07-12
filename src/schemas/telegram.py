# src/schemas/telegram.py
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


class TelegramChat(BaseModel):
    """Parses Telegram's incoming chat context object (required for tracking active chat IDs)."""

    id: int
    type: str
    title: Optional[str] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TelegramContact(BaseModel):
    phone_number: str
    first_name: str
    user_id: Optional[int] = None


class TelegramMessage(BaseModel):
    message_id: int
    message_from: TelegramUser = Field(..., alias="from")
    chat: TelegramChat  # 🎯 Added this field to allow 'payload.message.chat.id' to work safely
    date: int
    text: Optional[str] = None
    contact: Optional[TelegramContact] = None

    model_config = ConfigDict(from_attributes=True)


class TelegramWebhookInput(BaseModel):
    update_id: int
    message: TelegramMessage

    model_config = ConfigDict(from_attributes=True)
