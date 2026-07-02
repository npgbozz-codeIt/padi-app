# src/routers/telegram.py
from fastapi import APIRouter, Depends, status
from src.schemas.telegram import TelegramWebhookInput
from src.schemas.enums import OnboardingState, UserLang
from typing import Annotated
import re

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

# internal imports
from src.database.db_conn import get_db
from src.models.identity import UserIdentity
from src.models.profile import Profile
from src.utils.tag_generator import tag_generator
from src.utils.responses import ONBOARDING_RESPONSES
from src.services.nlu_engine import (
    classify_intent,
    extract_airtime_slots,
    extract_datapurchase_slots,
    extract_betting_slots,
    extract_cabletv_slots,
    extract_electricity_slots,
    extract_education_slots,
    extract_isp_slots,
)

router = APIRouter()


@router.post("", status_code=status.HTTP_200_OK)
async def telegram_webhook(
    payload: TelegramWebhookInput, db: Annotated[AsyncSession, Depends(get_db)]
):
    telegramuser_id = payload.message.message_from.id

    stmt = (
        select(UserIdentity)
        .options(joinedload(UserIdentity.profile))
        .where(
            UserIdentity.platform_id == str(telegramuser_id),
            UserIdentity.platform == "Telegram",
        )
    )
    result = await db.execute(stmt)
    existing_user = result.scalars().first()

    if existing_user:
        profile = existing_user.profile

        # FIX: Force .lower() to safely map onto lowercase Enum schemas
        try:
            db_state = (
                profile.user_state.lower()
                if profile.user_state
                else "awaiting_language"
            )
            profile_state = OnboardingState(db_state)
        except ValueError:
            profile_state = OnboardingState.AWAITING_LANGUAGE

        user_message = (payload.message.text or "").strip()

        # Resolve user language context cleanly
        user_lang = profile.lang or "english"
        copy_text = ONBOARDING_RESPONSES.get(user_lang, ONBOARDING_RESPONSES["english"])

        if not user_message and not payload.message.contact:
            return {
                "success": 200,
                "status": "ignored",
                "reasons": "empty messages can't be processed",
            }

        # ========================================================
        # STEP 1: ACTIVE STATE PROGRESSION GATEKEEPER
        # ========================================================

        # Condition A: Awaiting Language Input
        if profile_state == OnboardingState.AWAITING_LANGUAGE:
            cleaned_input = user_message.lower()
            if cleaned_input not in ["english", "pidgin", "hausa"]:
                return {
                    "success": 200,
                    "status": "onboarding_error",
                    "message": copy_text["invalid_lang"],
                }

            # Save selection and transition state
            profile.lang = cleaned_input
            profile.user_state = OnboardingState.AWAITING_PHONE.value
            await db.commit()

            # Resolve copy with the newly specified language immediately
            new_copy = ONBOARDING_RESPONSES[cleaned_input]
            return {
                "success": 200,
                "status": "onboarding_progress",
                "steps": "phone_number_request",
                "message": new_copy["ask_phone"],
            }

        # Condition B: Awaiting Phone Number
        elif profile_state == OnboardingState.AWAITING_PHONE:
            if payload.message.contact and payload.message.contact.phone_number:
                phone = payload.message.contact.phone_number
            else:
                phone = re.sub(r"\s+", "", user_message)

            profile.phone_num = phone
            profile.user_state = OnboardingState.AWAITING_BVN.value
            await db.commit()

            return {
                "success": 200,
                "status": "onboarding_progress",
                "steps": "bvn_verification",
                "message": copy_text["ask_bvn"],
            }

        # Condition C: Awaiting 11-digit BVN
        elif profile_state == OnboardingState.AWAITING_BVN:
            clean_bvn = re.sub(r"\D", "", user_message)
            if len(clean_bvn) != 11:
                return {
                    "success": 200,
                    "status": "onboarding_error",
                    "message": copy_text["invalid_bvn"],
                }

            profile.bnv = clean_bvn
            profile.user_state = OnboardingState.AWAITING_PIN.value
            await db.commit()

            return {
                "success": 200,
                "status": "onboarding_progress",
                "steps": "transaction_pin_creation",
                "message": copy_text["ask_pin"],
            }

        # Condition D: Awaiting Initial Pin Setup
        elif profile_state == OnboardingState.AWAITING_PIN:
            clean_pin = re.sub(r"\D", "", user_message)
            if len(clean_pin) != 4:
                return {
                    "success": 200,
                    "status": "onboarding_error",
                    "message": copy_text["invalid_pin"],
                }

            profile.hash_pin = clean_pin
            profile.user_state = OnboardingState.AWAITING_PIN_CONFIRMATION.value
            await db.commit()

            return {
                "success": 200,
                "status": "onboarding_progress",
                "steps": "transaction_pin_confirmation",
                "message": copy_text["confirm_pin"],
            }

        # Condition E: Confirming Pin Matching Values
        elif profile_state == OnboardingState.AWAITING_PIN_CONFIRMATION:
            clean_pin = re.sub(r"\D", "", user_message)

            if clean_pin != profile.hash_pin:
                profile.user_state = OnboardingState.AWAITING_PIN.value
                profile.hash_pin = None
                await db.commit()
                return {
                    "success": 200,
                    "status": "onboarding_error",
                    "message": copy_text["mismatch_pin"],
                }

            profile.user_state = OnboardingState.COMPLETED.value
            await db.commit()

            return {
                "success": 200,
                "status": "onboarding_complete",
                "message": copy_text["completed"],
            }

        # ========================================================
        # STEP 2: FULL TRANSACTION ENGINE (Only hits if COMPLETED)
        # ========================================================
        elif profile_state == OnboardingState.COMPLETED:
            nlu_analysis = await classify_intent(user_message)

            extracted_slots = None
            if nlu_analysis.action == "airtime_purchase":
                extracted_slots = await extract_airtime_slots(user_message)
            elif nlu_analysis.action == "data_purchase":
                extracted_slots = await extract_datapurchase_slots(user_message)
            elif nlu_analysis.action == "betting_payment":
                extracted_slots = await extract_betting_slots(user_message)
            elif nlu_analysis.action == "cabletv_payment":
                extracted_slots = await extract_cabletv_slots(user_message)
            elif nlu_analysis.action == "electricity_payment":
                extracted_slots = await extract_electricity_slots(user_message)
            elif nlu_analysis.action == "education_payment":
                extracted_slots = await extract_education_slots(user_message)
            elif nlu_analysis.action == "isp_payment":
                extracted_slots = await extract_isp_slots(user_message)

            return {
                "success": 200,
                "status": "user is verified and active",
                "profile_id": existing_user.profile_id,
                "intent_analysis": nlu_analysis.model_dump(),
                "extracted_slots": (
                    extracted_slots.model_dump() if extracted_slots else None
                ),
            }

    else:
        # User not found logic - triggers initial row initialization
        firstName = payload.message.message_from.first_name
        lastName = payload.message.message_from.username or "Padi"
        new_tag = tag_generator(firstname=firstName, lastname=lastName)

        new_profile = Profile(
            user_tag=new_tag,
            first_name=firstName,
            last_name=lastName,
            email=f"{new_tag.replace('@', '')}@mypadi.com.ng",
            user_state=OnboardingState.AWAITING_LANGUAGE.value,
        )
        db.add(new_profile)
        await db.flush()
        generated_profile_id = new_profile.id

        new_identity = UserIdentity(
            platform="Telegram",
            platform_id=str(telegramuser_id),
            profile_id=generated_profile_id,
        )
        db.add(new_identity)
        await db.commit()

        init_copy = ONBOARDING_RESPONSES["english"]["ask_lang"]

        return {
            "success": 201,
            "status": "user created successfully",
            "profile_id": generated_profile_id,
            "email": new_profile.email,
            "user_tag": new_tag,
            "message": init_copy,
        }
