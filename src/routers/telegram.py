# src/routers/telegram
from fastapi import APIRouter, Depends, status
from src.schemas.telegram import TelegramWebhookInput
from typing import Annotated

# from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.database.db_conn import get_db
from src.models.identity import UserIdentity
from src.models.profile import Profile
from src.utils.tag_generator import tag_generator

router = APIRouter()


@router.post("", status_code=status.HTTP_200_OK)
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
    else:
        firstName = payload.message.message_from.first_name
        lastName = payload.message.message_from.username
        new_tag = tag_generator(firstname=firstName, lastname=lastName)

        new_profile = Profile(
            user_tag=new_tag,
            first_name=firstName,
            last_name=lastName,
            email=f"{new_tag.replace('@', '')}@mypadi.com.ng",
        )
        db.add(new_profile)
        await db.flush()  # Flush to get the new profile ID

        new_identity = UserIdentity(
            platform="Telegram",
            platform_id=str(telegramuser_id),
            profile_id=new_profile.id,
        )
        db.add(new_identity)
        await db.commit()  # Commit the transaction
        await db.refresh()

        return {
            "success": 201,
            "status": "user created successfully",
            "profile_id": new_profile.id,
            "email": new_profile.email,
            "user_tag": new_tag,
        }
