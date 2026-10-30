# src/services/bigisub.py
import os
import re
import logging
from decimal import Decimal
import httpx
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# DisCo acronym / alias normalization map matching Bigisub v2 specs
DISCO_MAPPING = {
    "abedc": "aba-electric",
    "aba": "aba-electric",
    "aedc": "abuja-electric",
    "abuja": "abuja-electric",
    "ikedc": "ikeja-electric",
    "ikeja": "ikeja-electric",
    "ekedc": "eko-electric",
    "eko": "eko-electric",
    "ibedc": "ibadan-electric",
    "ibadan": "ibadan-electric",
    "eedc": "enugu-electric",
    "enugu": "enugu-electric",
    "bedc": "benin-electric",
    "benin": "benin-electric",
    "jedc": "jos-electric",
    "jed": "jos-electric",
    "jos": "jos-electric",
    "kaedco": "kaduna-electric",
    "kaedc": "kaduna-electric",
    "kaduna": "kaduna-electric",
    "kedco": "kano-electric",
    "kano": "kano-electric",
    "phed": "portharcourt-electric",
    "phedc": "portharcourt-electric",
    "portharcourt": "portharcourt-electric",
    "port harcourt": "portharcourt-electric",
    "port-harcourt": "portharcourt-electric",
    "yedc": "yola-electric",
    "yola": "yola-electric",
}

DISCO_SHORT_NAMES = {
    "aba-electric": "ABEDC",
    "abuja-electric": "AEDC",
    "benin-electric": "BEDC",
    "eko-electric": "EKEDC",
    "enugu-electric": "EEDC",
    "ibadan-electric": "IBEDC",
    "ikeja-electric": "IKEDC",
    "jos-electric": "JED",
    "kaduna-electric": "KAEDCO",
    "kano-electric": "KEDCO",
    "portharcourt-electric": "PHED",
    "yola-electric": "YEDC",
}

# BigiSub live provider minimums: (min_prepaid, min_postpaid) in NGN
DISCO_MIN_AMOUNTS = {
    "aba-electric": (Decimal("500"), Decimal("500")),
    "abuja-electric": (Decimal("1000"), Decimal("1000")),
    "benin-electric": (Decimal("1000"), Decimal("500")),
    "eko-electric": (Decimal("1000"), Decimal("500")),
    "enugu-electric": (Decimal("500"), Decimal("500")),
    "ibadan-electric": (Decimal("2000"), Decimal("2000")),
    "ikeja-electric": (Decimal("1000"), Decimal("500")),
    "jos-electric": (Decimal("1000"), Decimal("500")),
    "kaduna-electric": (Decimal("1200"), Decimal("500")),
    "kano-electric": (Decimal("500"), Decimal("500")),
    "portharcourt-electric": (Decimal("500"), Decimal("500")),
    "yola-electric": (Decimal("500"), Decimal("500")),
}


def resolve_disco_code(raw: Optional[str]) -> Optional[str]:
    """Resolves natural-language DisCo names/acronyms to BigiSub's canonical code."""
    if not raw:
        return None
    val = getattr(raw, "value", raw)
    clean = str(val).strip().lower()
    if clean in DISCO_SHORT_NAMES:
        return clean
    if clean in DISCO_MAPPING:
        return DISCO_MAPPING[clean]
    stripped = (
        clean.replace("electricity", "")
        .replace("electric", "")
        .replace("disco", "")
        .strip(" -_")
    )
    if stripped in DISCO_MAPPING:
        return DISCO_MAPPING[stripped]
    for alias, code in sorted(DISCO_MAPPING.items(), key=lambda x: -len(x[0])):
        if re.search(rf"\b{re.escape(alias)}\b", clean):
            return code
    return None


def get_disco_min_amount(disco_code: str, meter_type: str = "prepaid") -> Decimal:
    """Returns BigiSub's minimum vend amount (as Decimal) for a DisCo and meter type."""
    min_pre, min_post = DISCO_MIN_AMOUNTS.get(
        disco_code, (Decimal("1000"), Decimal("1000"))
    )
    return min_post if str(meter_type).lower() == "postpaid" else min_pre


class BigisubClient:
    def __init__(self):
        self.base_url = os.getenv(
            "BIGISUB_BASE_URL", "https://api.bigisub.ng/api/v2"
        ).rstrip("/")
        self.api_key = os.getenv("BIGISUB_API_KEY", "")
        self.bigi_transaction_pin = os.getenv("BIGISUB_PIN", "1234")
        self.headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self._client: Optional[httpx.AsyncClient] = None

    def get_client(self) -> httpx.AsyncClient:
        """
        Lazy initialization of a shared HTTP connection pool.
        Prevents opening/closing TCP and TLS handshakes on every single request.
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=self.headers,
                timeout=20.0,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
            )
        return self._client

    async def close(self):
        """
        Gracefully closes the HTTP connection pool on application shutdown.
        """
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ==================== ELECTRICITY BILLS ====================

    async def fetch_electricity_providers(self) -> Dict[str, Any]:
        """
        GET /bills/electricity/providers/
        Retrieves list of active DisCos and their provider codes.
        """
        url = f"{self.base_url}/bills/electricity/providers/"
        client = self.get_client()

        try:
            response = await client.get(url)
            if response.status_code == 200:
                res_data = response.json()
                providers = res_data.get("data", {}).get("providers", [])
                return {"success": True, "providers": providers, "error": None}

            logger.error(f"❌ Fetch Providers Error ({response.status_code}): {response.text}")
            return {"success": False, "providers": [], "error": f"Vendor returned HTTP {response.status_code}"}

        except httpx.RequestError as exc:
            logger.error(f"🚨 Network error fetching electricity providers: {exc}")
            return {"success": False, "providers": [], "error": "Connection to gateway timed out."}

    async def verify_meter(
        self, meter_number: str, disco_id: str, meter_type: str = "prepaid"
    ) -> Dict[str, Any]:
        """
        POST /bills/electricity/verify/
        Verifies a meter number with the specified DisCo and returns customer details.
        """
        url = f"{self.base_url}/bills/electricity/verify/"
        company_slug = resolve_disco_code(disco_id) or str(disco_id).strip().lower()
        clean_meter = re.sub(r"\D", "", str(meter_number))

        payload = {
            "company": company_slug,
            "meter_no": clean_meter,
            "meter_type": str(meter_type or "prepaid").strip().lower(),
        }

        client = self.get_client()
        try:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                res_data = response.json()
                if res_data.get("success") is True or res_data.get("status") == "success":
                    data_obj = res_data.get("data", {}) or {}
                    customer_name = (
                        data_obj.get("customer_name")
                        or res_data.get("customer_name")
                        or ""
                    ).strip()
                    if not customer_name:
                        return {
                            "success": False,
                            "error": "Meter verified, but customer name was not returned by the DisCo.",
                        }
                    customer_address = (
                        data_obj.get("customer_address")
                        or data_obj.get("address")
                        or res_data.get("customer_address")
                        or res_data.get("address")
                    )
                    return {
                        "success": True,
                        "customer_name": customer_name,
                        "customer_address": customer_address,
                        "address": customer_address,
                        "meter_number": data_obj.get("meter_number") or clean_meter,
                        "meter_type": data_obj.get("meter_type") or payload["meter_type"],
                        "disco": data_obj.get("disco") or company_slug,
                        "error": None,
                    }
                return {
                    "success": False,
                    "error": res_data.get("message", "Meter verification failed."),
                }

            error_msg = "Could not verify meter number."
            try:
                error_json = response.json()
                error_msg = error_json.get("message", error_msg)
            except Exception:
                pass

            logger.error(f"❌ Bigisub Meter Verify Error ({response.status_code}): {response.text}")
            return {"success": False, "error": error_msg}

        except httpx.RequestError as exc:
            logger.error(f"🚨 Network error verifying meter: {exc}")
            return {"success": False, "error": "Connection to gateway timed out."}

    async def verify_electricity_meter(
        self, provider: str, meter_number: str, meter_type: str = "prepaid"
    ) -> Dict[str, Any]:
        """Backward-compatible wrapper around verify_meter."""
        return await self.verify_meter(
            meter_number=meter_number, disco_id=provider, meter_type=meter_type
        )

    async def vend_electricity(
        self,
        meter_number: str,
        amount: Any,
        disco_id: str,
        meter_type: str = "prepaid",
        customer_name: str = "",
        phone_number: str = "",
        customer_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        POST /bills/electricity/pay/
        Executes electricity payment using verified customer name and meter details.
        """
        url = f"{self.base_url}/bills/electricity/pay/"
        company_slug = resolve_disco_code(disco_id) or str(disco_id).strip().lower()
        clean_meter = re.sub(r"\D", "", str(meter_number))
        clean_amount = int(Decimal(str(amount)))

        payload: Dict[str, Any] = {
            "company": company_slug,
            "meter_no": clean_meter,
            "meter_type": str(meter_type or "prepaid").strip().lower(),
            "phone_number": str(phone_number),
            "amount": clean_amount,
            "Customer_name": str(customer_name),
            "pin": str(self.bigi_transaction_pin),
        }
        if customer_address:
            payload["customer_address"] = str(customer_address)

        client = self.get_client()
        try:
            response = await client.post(url, json=payload)
            if response.status_code in [200, 201]:
                res_data = response.json()
                if res_data.get("success") is True or res_data.get("status") == "success":
                    data_obj = res_data.get("data", {}) or {}
                    return {
                        "success": True,
                        "error": None,
                        "transaction_id": data_obj.get("transaction_id"),
                        "reference": data_obj.get("reference") or data_obj.get("transaction_id"),
                        "token": data_obj.get("token") or res_data.get("token"),
                        "units": data_obj.get("units") or res_data.get("units"),
                        "amount": data_obj.get("amount"),
                        "charged_amount": data_obj.get("charged_amount"),
                        "service_charge": data_obj.get("service_charge"),
                        "customer_name": data_obj.get("customer_name") or customer_name,
                        "message": res_data.get("message", "Electricity payment successful"),
                    }
                return {
                    "success": False,
                    "error": res_data.get("message", "Electricity payment failed"),
                }

            error_msg = "Electricity payment failed at vendor level."
            try:
                error_json = response.json()
                error_msg = error_json.get("message", error_msg)
            except Exception:
                pass

            logger.error(f"❌ Bigisub Electricity Pay Error ({response.status_code}): {response.text}")
            return {"success": False, "error": error_msg}

        except httpx.RequestError as exc:
            logger.error(f"🚨 Network error connecting to Bigisub: {exc}")
            return {
                "success": False,
                "error": "Connection to payment gateway timed out.",
                "timeout": True,
            }

    # ==================== AIRTIME ====================

    async def vend_airtime(self, phone: str, amount: float, network: str) -> Dict[str, Any]:
        """
        POST /vtu/airtime/purchase/
        Executes instant VTU airtime vending.
        """
        url = f"{self.base_url}/vtu/airtime/purchase/"
        network_mapping = {"mtn": 1, "glo": 2, "airtel": 3, "9mobile": 4}
        network_id = network_mapping.get(str(network).strip().lower())

        if not network_id:
            return {"success": False, "error": f"Network provider '{network}' is not supported."}

        payload = {
            "network": network_id,
            "phone_number": str(phone),
            "amount": str(int(amount)),
            "airtime_type": "vtu",
            "pin": str(self.bigi_transaction_pin),
        }

        client = self.get_client()
        try:
            response = await client.post(url, json=payload)
            if response.status_code in [200, 201]:
                res_data = response.json()
                if res_data.get("success") is True or res_data.get("status") == "success":
                    data_obj = res_data.get("data", {}) or {}
                    return {
                        "success": True,
                        "error": None,
                        "transaction_id": data_obj.get("transaction_id"),
                        "reference": data_obj.get("reference"),
                        "message": res_data.get("message", "Airtime purchase successful"),
                    }
                return {"success": False, "error": res_data.get("message", "Airtime purchase failed")}

            error_msg = "Airtime vending failed at vendor level."
            try:
                error_json = response.json()
                error_msg = error_json.get("message", error_msg)
            except Exception:
                pass

            logger.error(f"❌ Bigisub Airtime Error ({response.status_code}): {response.text}")
            return {"success": False, "error": error_msg}

        except httpx.RequestError as exc:
            logger.error(f"🚨 Network error connecting to Bigisub: {exc}")
            return {"success": False, "error": "Connection to gateway timed out."}

    # ==================== DATA ====================

    async def fetch_live_data_plans(
        self, network: Optional[str] = None, plantype: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        GET /vtu/data/plans/
        Fetches active data plans with optional filtering (network, plantype).
        """
        url = f"{self.base_url}/vtu/data/plans/"
        params = {}

        if network:
            network_mapping = {"mtn": 1, "glo": 2, "airtel": 3, "9mobile": 4}
            net_id = network_mapping.get(str(network).strip().lower())
            if net_id:
                params["network"] = net_id
        if plantype:
            params["plantype"] = plantype.upper()

        client = self.get_client()
        try:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                res_data = response.json()
                plans = res_data.get("data", []) if isinstance(res_data, dict) else res_data
                return {"success": True, "plans": plans, "error": None}

            logger.error(f"❌ Fetch Data Plans Error ({response.status_code}): {response.text}")
            return {"success": False, "plans": [], "error": f"Vendor returned HTTP {response.status_code}"}

        except httpx.RequestError as exc:
            logger.error(f"🚨 Network error fetching data plans: {exc}")
            return {"success": False, "plans": [], "error": "Connection to gateway timed out."}

    async def vend_data(self, phone: str, plan_id: int, network: str) -> Dict[str, Any]:
        """
        POST /vtu/data/purchase/
        Executes data plan purchase using plan ID.
        """
        url = f"{self.base_url}/vtu/data/purchase/"
        network_mapping = {"mtn": 1, "glo": 2, "airtel": 3, "9mobile": 4}
        network_id = network_mapping.get(str(network).strip().lower())

        if not network_id:
            return {"success": False, "error": f"Network provider '{network}' is not supported."}

        payload = {
            "network": network_id,
            "plan": int(plan_id),
            "phone_number": str(phone),
            "pin": str(self.bigi_transaction_pin),
            "ported_number": True,
        }

        client = self.get_client()
        try:
            response = await client.post(url, json=payload)
            if response.status_code in [200, 201]:
                res_data = response.json()
                if res_data.get("success") is True or res_data.get("status") == "success":
                    data_obj = res_data.get("data", {}) or {}
                    return {
                        "success": True,
                        "error": None,
                        "transaction_id": data_obj.get("transaction_id"),
                        "message": res_data.get("message", "Data purchase successful"),
                    }
                return {"success": False, "error": res_data.get("message", "Data purchase failed")}

            error_msg = "Data purchase failed."
            try:
                error_json = response.json()
                error_msg = error_json.get("message", error_msg)
            except Exception:
                pass

            logger.error(f"❌ Bigisub Data Error ({response.status_code}): {response.text}")
            return {"success": False, "error": error_msg}

        except httpx.RequestError as exc:
            logger.error(f"🚨 Network error connecting to Bigisub: {exc}")
            return {"success": False, "error": "Connection to payment gateway timed out."}

    # ==================== ACCOUNT BALANCE ====================

    async def check_balance(self) -> Dict[str, Any]:
        """
        GET /user/balance/
        Retrieves current wallet balance.
        """
        url = f"{self.base_url}/user/balance/"
        client = self.get_client()
        try:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                balance_val = data.get("balance", 0.0)
                if isinstance(data, dict) and "data" in data and "balance" in data["data"]:
                    balance_val = data["data"]["balance"]
                return {"success": True, "balance": float(balance_val)}
            return {"success": False, "error": f"Failed with status {response.status_code}"}
        except httpx.RequestError as exc:
            return {"success": False, "error": str(exc)}


bigisub_client = BigisubClient()
