import logging
from typing import Any, Dict, Optional
from src.schemas.enums import IntentEnum
from src.services import nlu_engine
from src.services.orchestrator import process_user_vending_intent

logger = logging.getLogger(__name__)


async def handle_user_text_request(
    user_id: str, user_text: str, execute: bool = False
) -> Dict[str, Any]:
    """
    1. Classifies intent from raw user text.
    2. Extracts missing slots based on intent.
    3. Bridges structured slots to orchestrator vending pipeline.
    
    Set `execute=False` (default) for dry-run quotes, or `execute=True` to vend live.
    """
    # 1. Intent Classification
    intent_data = await nlu_engine.classify_intent(user_text)
    action = getattr(intent_data, "action", IntentEnum.UNKNOWN)

    action_val = action.value if hasattr(action, "value") else str(action)
    logger.info(f"Detected Intent: {action_val}")

    if action_val == IntentEnum.GREETING.value:
        return {
            "success": True,
            "response_type": "text",
            "action": action_val,
            "message": "Hello! How can I help you with airtime, data, or bill payments today?",
        }

    if action_val in (IntentEnum.UNKNOWN.value, "help"):
        return {
            "success": False,
            "response_type": "text",
            "action": action_val,
            "message": "I didn't quite catch that. You can try saying something like 'Buy 500 airtime for 08012345678' or 'Pay 2000 AEDC electricity'.",
        }

    # 2. Extract slots and map parameters according to schema attribute names
    conversion_type: Optional[str] = None
    destination: Optional[str] = None
    amount: Optional[float] = None
    extra_kwargs: Dict[str, Any] = {}

    if action_val == IntentEnum.BUY_AIRTIME.value:
        slots = await nlu_engine.extract_airtime_slots(user_text)
        conversion_type = "airtime"
        destination = slots.phone_number
        amount = slots.amount
        if slots.network:
            extra_kwargs["network"] = slots.network.value if hasattr(slots.network, "value") else str(slots.network)

    elif action_val == IntentEnum.BUY_DATA.value:
        slots = await nlu_engine.extract_datapurchase_slots(user_text)
        conversion_type = "data"
        destination = slots.phone_number
        amount = slots.amount
        if slots.provider:
            extra_kwargs["network"] = slots.provider.value if hasattr(slots.provider, "value") else str(slots.provider)
        if slots.types:
            extra_kwargs["data_type"] = slots.types

    elif action_val in (IntentEnum.PAY_ELECTRICITY.value, "pay_electricity"):
        slots = await nlu_engine.extract_electricity_slots(user_text)
        conversion_type = "electricity"
        destination = slots.meter_no
        amount = slots.amount
        if slots.company:
            extra_kwargs["disco"] = slots.company.value if hasattr(slots.company, "value") else str(slots.company)
        if slots.meter_type:
            extra_kwargs["meter_type"] = slots.meter_type
        if slots.phone_number:
            extra_kwargs["phone"] = slots.phone_number

    else:
        return {
            "success": False,
            "response_type": "text",
            "action": action_val,
            "message": f"Service type '{action_val}' is not yet supported.",
        }

    # 3. Parameter Completeness Check
    if not amount or amount <= 0:
        return {
            "success": False,
            "response_type": "missing_param",
            "action": action_val,
            "missing_param": "amount",
            "message": "Please specify the amount you want to purchase.",
        }

    if not destination:
        return {
            "success": False,
            "response_type": "missing_param",
            "action": action_val,
            "missing_param": "destination",
            "message": "Please provide the target phone number or meter number.",
        }

    # 4. Pass structured slots to Orchestrator
    vending_result = await process_user_vending_intent(
        conversion_type=conversion_type,
        user_id=user_id,
        amount=float(amount),
        destination=str(destination),
        execute=execute,
        **extra_kwargs,
    )

    return {
        "success": vending_result.get("success", False),
        "response_type": "vending_quote",
        "action": action_val,
        "details": vending_result,
    }