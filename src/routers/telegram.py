# src/routers/telegram
from fastapi import APIRouter, Depends
from src.schemas.telegram import TelegramWebhookInput
from typing import Annotated

# from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.database.db_conn import get_db
from src.models.identity import UserIdentity

router = APIRouter()


@router.post("")
async def telegram_webhook(
    payload: TelegramWebhookInput, db: Annotated[AsyncSession, Depends(get_db)]
):

    telegramuser_id = payload.message.message_from.id
    stmt = select(UserIdentity).where(
        UserIdentity.platform_id == str(telegramuser_id),
        UserIdentity.platform == "Telegram",
    )
    result = await db.execute(stmt)
    existing_user = result.scalars().first()
    if existing_user:
        return {
            "success": 200,
            "status": "user is registered",
            "profile_id": existing_user.profile_id,
        }
    return {"status": "user not found"}
