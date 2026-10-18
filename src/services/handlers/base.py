# src/services/handlers/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.profile import Profile


class BaseVendingHandler(ABC):
    intent_name: str
    required_slots: List[str]

    @abstractmethod
    async def extract_slots(self, text: str, current_slots: Dict[str, Any]) -> Dict[str, Any]:
        """Extract parameters from text and merge with existing session slots."""
        pass

    @abstractmethod
    async def execute(self, db: AsyncSession, profile: Profile, slots: Dict[str, Any]) -> Dict[str, Any]:
        """Execute vendor API call and return execution result dictionary."""
        pass

    def get_missing_slot_prompt(self, missing_slot: str, user_lang: str) -> str:
        """Return localized prompt requesting missing information."""
        prompts = {
            "amount": {
                "english": "How much would you like to purchase? (e.g., 500)",
                "pidgin": "How much you wan buy, boss? (e.g., 500)",
                "hausa": "Nawa kuke son saya? (misali, 500)",
            },
            "network": {
                "english": "Which network provider is this for? (MTN, Glo, Airtel, 9mobile)",
                "pidgin": "Which network be dis? (MTN, Glo, Airtel, 9mobile)",
                "hausa": "Wace hanyar sadarwa ce? (MTN, Glo, Airtel, 9mobile)",
            },
            "phone_number": {
                "english": "Please provide the target phone number for this transaction.",
                "pidgin": "Abeg drop the phone number wey go receive am.",
                "hausa": "Da fatan za a bayar da lambar wayar.",
            },
            "meter_number": {
                "english": "Please enter your meter number.",
                "pidgin": "Abeg drop your meter number.",
                "hausa": "Da fatan za a shigar da lambar mita.",
            }
        }
        
        slot_dict = prompts.get(missing_slot, {})
        return slot_dict.get(
            user_lang, 
            slot_dict.get("english", f"Please provide the missing {missing_slot} detail.")
        )