from abc import ABC, abstractmethod
from typing import Any, Dict
from pydantic import BaseModel, Field


class ConversionResult(BaseModel):
    """Standard payload model for conversion quotes and calculations."""
    success: bool = True
    source_amount: float
    target_amount: float
    fee: float = 0.0
    rate: float = 1.0
    summary_text: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseConversionStrategy(ABC):
    """Abstract contract for all conversion strategies in Mypadi."""

    @property
    @abstractmethod
    def conversion_type(self) -> str:
        """Unique key identifying the strategy."""
        pass

    @abstractmethod
    async def validate_and_quote(
        self, amount: float, **kwargs: Any
    ) -> ConversionResult:
        """Calculate rates, fees, and return a preview quote."""
        pass

    @abstractmethod
    async def execute(
        self, user_id: str, amount: float, destination: str, **kwargs: Any
    ) -> Dict[str, Any]:
        """Perform the actual conversion transaction or external service call."""
        pass