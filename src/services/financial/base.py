# src/services/financial/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseFinancialProvider(ABC):
    """
    Abstract Base Class defining the contract for financial operations.
    Allows seamless swapping between Paystack, Rubies, or other BaaS providers.
    """

    @abstractmethod
    async def verify_bvn(self, bvn: str) -> Dict[str, Any]:
        """
        Validates an 11-digit BVN string.
        Returns dict containing success status and identity details.
        """
        pass

    @abstractmethod
    async def create_customer(
        self, first_name: str, last_name: str, email: str, phone: str
    ) -> Dict[str, Any]:
        """
        Registers a customer with the provider.
        Returns dict containing provider customer code/ID.
        """
        pass

    @abstractmethod
    async def provision_dedicated_account(
        self, customer_code: str, preferred_bank: Optional[str] = "wema-bank"
    ) -> Dict[str, Any]:
        """
        Provisions a Dedicated Virtual Account (DVA) for deposits.
        Returns dict with bank_name, account_number, account_name, and customer_code.
        """
        pass