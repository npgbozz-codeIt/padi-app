from __future__ import annotations

from typing import Any, Dict
from src.services.bigisub import bigisub_client
from src.services.conversions.base import BaseConversionStrategy, ConversionResult
from src.services.conversions.registry import conversion_registry
from src.utils.network_detector import detect_network


class DataConversionStrategy(BaseConversionStrategy):
    """Handles data bundle validation, plan mapping, and data vending via Bigisub."""

    @property
    def conversion_type(self) -> str:
        return "data"

    async def validate_and_quote(
        self, amount: float, **kwargs: Any
    ) -> ConversionResult:
        phone_number = kwargs.get("phone_number") or kwargs.get("destination", "")
        plan_id = kwargs.get("plan_id")
        plan_name = kwargs.get("plan_name", "Data Plan")
        network = kwargs.get("network") or detect_network(phone_number)

        if not plan_id:
            return ConversionResult(
                success=False,
                source_amount=amount,
                target_amount=0.0,
                summary_text="Please select a valid data plan.",
            )

        if not network:
            return ConversionResult(
                success=False,
                source_amount=amount,
                target_amount=0.0,
                summary_text="Network provider could not be resolved.",
            )

        return ConversionResult(
            success=True,
            source_amount=amount,
            target_amount=amount,
            fee=0.0,
            rate=1.0,
            summary_text=f"{network.upper()} {plan_name} to {phone_number} (₦{amount:,.2f})",
            metadata={
                "network": network.lower(),
                "phone_number": str(phone_number),
                "plan_id": int(plan_id),
                "plan_name": plan_name,
            },
        )

    async def execute(
        self, user_id: str, amount: float, destination: str, **kwargs: Any
    ) -> Dict[str, Any]:
        plan_id = kwargs.get("plan_id")
        network = kwargs.get("network") or detect_network(destination)

        if not plan_id or not network:
            return {
                "success": False,
                "error": "Missing required plan_id or network parameter.",
            }

        # Dispatch live data purchase to Bigisub
        response = await bigisub_client.vend_data(
            phone=destination,
            plan_id=int(plan_id),
            network=network,
        )
        return response


# Auto-register strategy instance
conversion_registry.register(DataConversionStrategy())