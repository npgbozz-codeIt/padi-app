from __future__ import annotations

from typing import Any, Dict
from src.services.bigisub import bigisub_client
from src.services.conversions.base import BaseConversionStrategy, ConversionResult
from src.services.conversions.registry import conversion_registry
from src.utils.electricity_margin_calculator import (
    calculate_convenience_fee,
    calculate_electricity_retail_cost,
)


class ElectricityConversionStrategy(BaseConversionStrategy):
    """Handles meter validation, margin calculation, and electricity vending via Bigisub."""

    @property
    def conversion_type(self) -> str:
        return "electricity"

    async def validate_and_quote(
        self, amount: float, **kwargs: Any
    ) -> ConversionResult:
        meter_number = kwargs.get("meter_number") or kwargs.get("destination", "")
        disco = kwargs.get("disco") or kwargs.get("provider", "")
        meter_type = kwargs.get("meter_type", "prepaid")

        if not meter_number or not disco:
            return ConversionResult(
                success=False,
                source_amount=amount,
                target_amount=0.0,
                summary_text="Meter number and electricity provider (disco) are required.",
            )

        # 1. Calculate convenience fee & total retail cost using existing utils
        service_fee = calculate_convenience_fee(amount)
        total_payable = calculate_electricity_retail_cost(amount)

        # 2. Verify meter with Bigisub API
        verification = await bigisub_client.verify_electricity_meter(
            disco=disco,
            meter_number=str(meter_number),
            meter_type=meter_type,
        )

        if not verification.get("success"):
            return ConversionResult(
                success=False,
                source_amount=amount,
                target_amount=total_payable,
                fee=service_fee,
                summary_text=f"Meter verification failed: {verification.get('error')}",
            )

        customer_name = verification.get("customer_name", "Verified User")

        return ConversionResult(
            success=True,
            source_amount=amount,
            target_amount=total_payable,
            fee=service_fee,
            rate=1.0,
            summary_text=(
                f"Electricity Token for {customer_name} ({str(disco).upper()} - {meter_number}): "
                f"₦{amount:,.2f} + ₦{service_fee:,.2f} fee"
            ),
            metadata={
                "disco": disco,
                "meter_number": str(meter_number),
                "meter_type": meter_type,
                "customer_name": customer_name,
                "address": verification.get("address"),
            },
        )

    async def execute(
        self, user_id: str, amount: float, destination: str, **kwargs: Any
    ) -> Dict[str, Any]:
        disco = kwargs.get("disco") or kwargs.get("provider")
        phone = kwargs.get("phone") or kwargs.get("phone_number", destination)
        meter_type = kwargs.get("meter_type", "prepaid")

        if not disco:
            return {
                "success": False,
                "error": "Electricity provider (disco) parameter is required.",
            }

        # Vend electricity via Bigisub
        response = await bigisub_client.vend_electricity(
            disco=disco,
            meter_number=destination,
            amount=amount,
            phone=str(phone),
            meter_type=meter_type,
        )
        return response


# Auto-register strategy instance
conversion_registry.register(ElectricityConversionStrategy())