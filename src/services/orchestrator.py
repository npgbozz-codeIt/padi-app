# src/services/orchestrator.py
import logging
from typing import Any, Dict
from src.services.bigisub import bigisub_client
from src.utils.network_detector import detect_network

logger = logging.getLogger(__name__)


async def process_user_vending_intent(
    conversion_type: str,
    user_id: str,
    amount: float,
    destination: str,
    execute: bool = False,
    **kwargs,
) -> Dict[str, Any]:
    """
    Orchestrates quote generation and live vending execution via Bigisub.
    """
    # ---------------- AIRTIME ----------------
    if conversion_type == "airtime":
        # Automatically detect network from phone number if not explicitly provided or incorrect
        detected_net = detect_network(destination)
        network = kwargs.get("network") or detected_net or "mtn"
        
        if not execute:
            return {
                "success": True,
                "type": "airtime",
                "quote": f"Airtime: ₦{float(amount):,.2f} to {destination} ({network.upper()})",
                "metadata": {"network": network, "phone_number": destination, "amount": float(amount)},
            }
        
        return await bigisub_client.vend_airtime(
            phone=destination, amount=float(amount), network=network
        )

    # ---------------- DATA ----------------
    elif conversion_type == "data":
        detected_net = detect_network(destination)
        network = kwargs.get("network") or detected_net or "mtn"
        plan_id = kwargs.get("plan_id")

        if not execute:
            return {
                "success": True,
                "type": "data",
                "quote": f"Data purchase: plan {plan_id} for {destination} ({network.upper()})",
                "metadata": {"network": network, "phone_number": destination, "plan_id": plan_id},
            }

        return await bigisub_client.vend_data(
            phone=destination, plan_id=plan_id, network=network
        )

    # ---------------- ELECTRICITY ----------------
    elif conversion_type == "electricity":
        provider = kwargs.get("disco", "aedc")
        meter_type = kwargs.get("meter_type", "prepaid")
        phone = kwargs.get("phone", "08000000000")

        # Step 1: Verify Meter
        verify_res = await bigisub_client.verify_meter(
            meter_number=destination, disco_id=provider, meter_type=meter_type
        )

        if not verify_res.get("success"):
            return {
                "success": False,
                "type": "electricity",
                "error": verify_res.get("error", "Meter verification failed."),
            }

        customer_name = verify_res.get("customer_name", "Valued Customer")

        # Step 2: Return Quote (Dry Run)
        if not execute:
            return {
                "success": True,
                "type": "electricity",
                "quote": f"Electricity: ₦{float(amount):,.2f} for Meter {destination} ({provider.upper()}) - Account Name: {customer_name}",
                "metadata": {
                    "provider": provider,
                    "meter_number": destination,
                    "meter_type": meter_type,
                    "customer_name": customer_name,
                    "amount": float(amount),
                },
            }

        # Step 3: Execute Purchase
        return await bigisub_client.vend_electricity(
            meter_number=destination,
            amount=amount,
            disco_id=provider,
            meter_type=meter_type,
            customer_name=customer_name,
            phone_number=phone,
        )

    return {"success": False, "error": f"Unsupported conversion type: {conversion_type}"}


async def process_user_intent_and_slots(
    chat_id: int, user_message: str, profile: Any, db: Any
) -> str:
    """
    Compatibility wrapper bridging legacy telegram router calls to the new pipeline.
    """
    from src.services.pipeline import handle_incoming_user_message
    
    user_id = str(chat_id)
    pipeline_res = await handle_incoming_user_message(user_id=user_id, message_text=user_message)
    return pipeline_res.get("message", "I am processing your request.")
