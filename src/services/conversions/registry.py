from typing import Any, Dict, Optional
from src.services.conversions.base import BaseConversionStrategy, ConversionResult


class ConversionRegistry:
    """Central registry for managing and invoking dynamic conversion strategies."""

    def __init__(self) -> None:
        self._strategies: Dict[str, BaseConversionStrategy] = {}

    def register(self, strategy: BaseConversionStrategy) -> None:
        """Register a strategy instance using its unique conversion_type key."""
        self._strategies[strategy.conversion_type] = strategy

    def get(self, conversion_type: str) -> Optional[BaseConversionStrategy]:
        """Retrieve a strategy by its key."""
        return self._strategies.get(conversion_type)

    async def get_quote(
        self, conversion_type: str, amount: float, **kwargs: Any
    ) -> ConversionResult:
        """Fetch a quote directly from the registered strategy."""
        strategy = self.get(conversion_type)
        if not strategy:
            return ConversionResult(
                success=False,
                source_amount=amount,
                target_amount=0.0,
                summary_text=f"Unsupported conversion type: '{conversion_type}'",
            )
        return await strategy.validate_and_quote(amount, **kwargs)

    async def process(
        self,
        conversion_type: str,
        user_id: str,
        amount: float,
        destination: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute a conversion using the registered strategy."""
        strategy = self.get(conversion_type)
        if not strategy:
            return {
                "success": False,
                "error": f"No strategy registered for conversion type '{conversion_type}'",
            }
        try:
            result = await strategy.execute(user_id, amount, destination, **kwargs)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


# Global instance for app-wide import
conversion_registry = ConversionRegistry()