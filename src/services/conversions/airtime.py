from __future__ import annotations

from typing import Any, Dict
from src.services.bigisub import bigisub_client
from src.services.conversions.base import BaseConversionStrategy, ConversionResult
from src.services.conversions.registry import conversion_registry
from src.utils.network_detector import detect_network


class AirtimeConversionStrategy(BaseConversionStrategy):
    """Handles network detection, validation, and VTU airtime vending via Bigisub."""

    @property
    def conversion_type(self) -> str:
        return "airtime"

    async def validate_and_quote(
        self, amount: float, **kwargs: Any
    ) -> ConversionResult:
        phone_number = kwargs.get("phone_number") or kwargs.get("destination", "")
        network = kwargs.get("network") or detect_network(phone_number)

        if not network:
            return ConversionResult(
                success=False,
                source_amount=amount,
                target_amount=0.0,
                summary_text="Unable to detect network operator for this phone number.",
            )

        if amount < 50:
            return ConversionResult(
                success=False,
                source_amount=amount,
                target_amount=0.0,
                summary_text="Minimum airtime purchase is ₦50.",
            )

        return ConversionResult(
            success=True,
            source_amount=amount,
            target_amount=amount,
            fee=0.0,
            rate=1.0,
            summary_text=f"Airtime: ₦{amount:,.2f} to {phone_number} ({network.upper()})",
            metadata={
                "network": network.lower(),
                "phone_number": str(phone_number),
            },
        )

    async def execute(
        self, user_id: str, amount: float, destination: str, **kwargs: Any
    ) -> Dict[str, Any]:
        network = kwargs.get("network") or detect_network(destination)
        if not network:
            return {
                "success": False,
                "error": "Valid network provider is required for airtime vending.",
            }

        # Dispatch live VTU request to Bigisub
        response = await bigisub_client.vend_airtime(
            phone=destination,
            amount=amount,
            network=network,
        )
        return response


# Auto-register strategy instance
conversion_registry.register(AirtimeConversionStrategy())