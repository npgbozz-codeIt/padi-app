# src/services/financial/paystack.py
import os
import httpx
import logging
from typing import Dict, Any, Optional
from src.services.financial.base import BaseFinancialProvider

logger = logging.getLogger("uvicorn.error")

PAYSTACK_BASE_URL = "https://api.paystack.co"


class PaystackFinancialProvider(BaseFinancialProvider):
    """
    Concrete implementation of BaseFinancialProvider using Paystack API.
    """

    def __init__(self):
        raw_secret = os.getenv("PAYSTACK_SECRET_KEY", "")
        self.secret_key = raw_secret.strip().strip('"').strip("'")

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    async def verify_bvn(self, bvn: str) -> Dict[str, Any]:
        """Verify 11-digit BVN via Paystack bank resolve endpoint."""
        url = f"{PAYSTACK_BASE_URL}/bank/resolve_bvn/{bvn}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.get(url, headers=self._headers)
                data = response.json()
                if response.status_code == 200 and data.get("status") is True:
                    return {"status": True, "data": data.get("data")}
                return {
                    "status": False,
                    "message": data.get("message", "BVN verification failed."),
                }
            except Exception as e:
                logger.error(f"Paystack BVN Resolution Exception: {e}")
                return {"status": False, "message": "Verification service unavailable."}

    async def create_customer(
        self, first_name: str, last_name: str, email: str, phone: str
    ) -> Dict[str, Any]:
        """Create customer on Paystack."""
        url = f"{PAYSTACK_BASE_URL}/customer"
        payload = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(url, json=payload, headers=self._headers)
                data = response.json()
                if response.status_code in (200, 201) and data.get("status") is True:
                    cust_data = data.get("data", {})
                    return {
                        "status": True,
                        "customer_code": cust_data.get("customer_code"),
                        "data": cust_data,
                    }
                return {
                    "status": False,
                    "message": data.get("message", "Failed to create customer."),
                }
            except Exception as e:
                logger.error(f"Paystack Customer Creation Exception: {e}")
                return {"status": False, "message": "Customer creation failed."}

    async def provision_dedicated_account(
        self, customer_code: str, preferred_bank: Optional[str] = "wema-bank"
    ) -> Dict[str, Any]:
        """Provision a Dedicated Virtual Account (DVA) for a Paystack customer."""
        url = f"{PAYSTACK_BASE_URL}/dedicated_account"
        payload = {
            "customer": customer_code,
            "preferred_bank": preferred_bank,
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                response = await client.post(url, json=payload, headers=self._headers)
                data = response.json()
                if response.status_code in (200, 201) and data.get("status") is True:
                    dva_data = data.get("data", {})
                    bank_info = dva_data.get("bank", {})
                    return {
                        "status": True,
                        "account_number": str(dva_data.get("account_number")),
                        "account_name": dva_data.get("account_name"),
                        "bank_name": bank_info.get("name", "Deposit Bank"),
                        "customer_code": customer_code,
                    }
                return {
                    "status": False,
                    "message": data.get("message", "Failed to provision virtual account."),
                }
            except Exception as e:
                logger.error(f"Paystack DVA Exception: {e}")
                return {"status": False, "message": "Virtual account service unavailable."}

    async def initialize_transaction(
        self, email: str, amount_in_kobo: int, reference: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initialize a Paystack checkout transaction to generate a hosted payment link
        for wallet funding (fallback option when DVA/BVN is pending).
        """
        url = f"{PAYSTACK_BASE_URL}/transaction/initialize"
        payload = {
            "email": email,
            "amount": amount_in_kobo,
        }
        if reference:
            payload["reference"] = reference

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(url, json=payload, headers=self._headers)
                data = response.json()
                if response.status_code in (200, 201) and data.get("status") is True:
                    tx_data = data.get("data", {})
                    return {
                        "status": True,
                        "authorization_url": tx_data.get("authorization_url"),
                        "reference": tx_data.get("reference"),
                        "access_code": tx_data.get("access_code"),
                    }
                return {
                    "status": False,
                    "message": data.get("message", "Failed to initialize payment link."),
                }
            except Exception as e:
                logger.error(f"Paystack Transaction Initialize Exception: {e}")
                return {"status": False, "message": "Payment initialization service unavailable."}