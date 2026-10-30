# src/services/handlers/registry.py
from typing import Optional
from src.services.handlers.base import BaseVendingHandler
from src.services.handlers.airtime import AirtimeHandler
from src.services.handlers.data import DataHandler
from src.services.handlers.electricity import ElectricityHandler

HANDLER_REGISTRY = {
    "airtime": AirtimeHandler(),
    "buy_airtime": AirtimeHandler(),
    "data": DataHandler(),
    "buy_data": DataHandler(),
    "electricity": ElectricityHandler(),
    "payfor_electricity": ElectricityHandler(),
    "pay_electricity": ElectricityHandler(),
}


def get_vending_handler(intent: str) -> Optional[BaseVendingHandler]:
    """
    Retrieves the dedicated service handler for a given intent.
    """
    if not intent:
        return None
    return HANDLER_REGISTRY.get(intent.lower().strip())
