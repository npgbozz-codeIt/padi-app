import os
import logging
import httpx
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

# logger to catch api errors
logger = logging.getLogger(__name__)


class BigisubClient:
    def __init__(self):
        self.base_url = os.getenv(
            "BIGISUB_BASE_URL", "https://bigisub.ng/api/v2/"
        ).rstrip(
            "/",
        )
        self.api_key = os.getenv("BIGISUB_API_KEY")
        self.usermail = os.getenv("BIGISUB_USERNAME_MAIL")
        self.password = os.getenv("BIGISUB_PASSWORD")
        self.bigi_transaction_pin = os.getenv("BIGISUB_PIN", "2000")
        self.headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def get_merchant_balance(self):
        """
        Logs into Bigisub using POST to fetch and parse the master merchant wallet balance.
        """
        url = f"{self.base_url}/auth/login/"
        payload = {"email_or_username": self.usermail, "password": self.password}

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(url, headers=self.headers, json=payload)
                if response.status_code == 200:
                    response_json = response.json()
                    # Guard check to ensure API returns a successful internal status flag
                    if response_json.get("success") is True:
                        # Safely navigate nested data -> user -> walletBalance dictionary tree block
                        data_block = response_json.get("data", {})
                        user_data_block = data_block.get("user", {})
                        wallet_balance = user_data_block.get(
                            "walletBalance", user_data_block.get("balance", 0.0)
                        )

                        return float(wallet_balance)
                    else:
                        logger.error(
                            f"Bigisub API returned an unsuccessful response: {response_json}"
                        )
                        return None
                else:
                    logger.error(
                        f"Bigisub API request failed with status code {response.status_code}: {response.text}"
                    )
                    return None
            except httpx.RequestError as exc:
                logger.error(f"An error occurred while requesting Bigisub API: {exc}")
                return None

    async def vend_airtime(self, phone: str, amount: int, network: str) -> dict:
        """
        Sends an asynchronous request to Bigisub to process a live VTU airtime transaction.
        """
        url = f"{self.base_url}/vtu/airtime/purchase/"
        # network mapping to match Bigisub's expected network ID values
        network_mapping = {"mtn": 1, "glo": 2, "airtel": 3, "9mobile": 4}
        # cleaning the incoming parameter
        clean_network = network.strip().lower()
        network_id = network_mapping.get(clean_network)

        if not network_id:
            logger.error(f"❌ Unsupported network identifier requested: {network}")
            return {
                "success": False,
                "error": f"Network provider '{network}' is not supported.",
            }
        airtime_payload = {
            "network": network_id,
            "phone_number": phone,
            "amount": str(amount),
            "airtime_type": "vtu",
            "pin": self.bigi_transaction_pin,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(
                    url, headers=self.headers, json=airtime_payload
                )
                if response.status_code in [200, 201]:
                    response_json = response.json()
                    if response.get("success") is True:
                        return {
                            "success": True,
                            "error": None,
                            "transaction_id": response_json.get("data", {}).get(
                                "transaction_id", {}
                            ),
                            "message": response_json.get(
                                "message", "Airtime purchase successful"
                            ),
                        }
                    else:
                        logger.error(
                            f"Bigisub API returned an unsuccessful response: {response_json}"
                        )
                        return {
                            "success": False,
                            "error": response_json.get(
                                "message", "Airtime purchase failed"
                            ),
                        }
                else:
                    #  Read the exact error message from Bigisub out of the 400 Bad Request payload
                    try:
                        error_json = response.json()
                        error_msg = error_json.get("message", "Validation failed")

                        # Check for nested validation error dictionaries
                        if "errors" in error_json and error_json["errors"]:
                            # Extract the first error message from the dictionary list
                            first_err_key = list(error_json["errors"].keys())[0]
                            error_msg = error_json["errors"][first_err_key][0]
                    except Exception:
                        error_msg = "Vendor validation error occurred."

                    logger.error(
                        f"❌ Bigisub Airtime Reject ({response.status_code}): {response.text}"
                    )
                    return {"success": False, "error": error_msg}
            except httpx.RequestError as exc:
                logger.error(f"An error occurred while requesting Bigisub API: {exc}")
                return {"error": "error accessing airtime endpoint"}

    async def vend_data(
        self,
        phone: str,
        plan_id: int,
        network: str,
    ) -> dict:
        """
        Sends an asynchronous request to Bigisub to process a live VTU airtime transaction.
        """
        url = f"{self.base_url}/vtu/data/purchase/"
        network_mapping = {"mtn": 1, "glo": 2, "airtel": 3, "9mobile": 4}
        clean_network = network.strip().lower()
        network_id = network_mapping.get(clean_network)
        if not network_id:
            logger.error(
                f"❌ Unsupported network provider requested for data: {network}"
            )
            return {
                "success": False,
                "error": f"Network provider '{network}' is not supported.",
            }
        data_payload = {
            "network": network_id,
            "plan": plan_id,
            "phone_number": str(phone),
            "pin": self.bigi_transaction_pin,
            "ported_number": True,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(
                    url, headers=self.headers, json=data_payload
                )
                if response.status_code in [200, 201]:
                    response_json = response.json()
                    if response_json.get("success") is True:
                        return {
                            "success": True,
                            "error": None,
                            "transaction_id": response_json.get("data", {}).get(
                                "transaction_id", {}
                            ),
                            "message": response_json.get(
                                "message", "Data purchase successful"
                            ),
                        }
                    else:
                        logger.error(
                            f"❌ Bigisub rejected data purchase validation: {response_json}"
                        )
                        return {
                            "success": False,
                            "error": response_json.get(
                                "message", "Data purchase failed"
                            ),
                        }
                else:
                    #  Read the exact error message from Bigisub out of the 400 Bad Request payload
                    try:
                        error_json = response.json()
                        error_msg = error_json.get("message", "Validation failed")

                        # Check for nested validation error dictionaries
                        if "errors" in error_json and error_json["errors"]:
                            # Extract the first error message from the dictionary list
                            first_err_key = list(error_json["errors"].keys())[0]
                            error_msg = error_json["errors"][first_err_key][0]
                    except Exception:
                        error_msg = "Vendor validation error occurred."

                    logger.error(
                        f"❌ Bigisub Data Reject ({response.status_code}): {response.text}"
                    )
                    return {"success": False, "error": error_msg}
            except httpx.RequestError as exc:
                logger.error(
                    f"🚨 Network error occurred while connecting to Bigisub: {exc}"
                )
                return {
                    "success": False,
                    "error": "Connection to payment gateway timed out.",
                }

    async def fetch_live_data_plans(self, network_id: int | None = None) -> dict:
        """
        Fetches the complete list of available data plans directly from Bigisub.
        Allows optional filtering by network_id (1=MTN, 2=Glo, 3=Airtel, 4=9mobile).
        """
        url = f"{self.base_url}/vtu/data/plans/"

        # Build query parameters if filtering by a specific network provider
        params = {}
        if network_id:
            params["network"] = network_id

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                response = await client.get(url, headers=self.headers, params=params)

                if response.status_code == 200:
                    response_json = response.json()
                    if response_json.get("success") is True:
                        return {
                            "success": True,
                            "plans": response_json.get("data", []),
                            "error": None,
                        }
                    return {
                        "success": False,
                        "plans": [],
                        "error": response_json.get("message"),
                    }

                logger.error(
                    f"❌ Bigisub Plan Fetch Failed ({response.status_code}): {response.text}"
                )
                return {
                    "success": False,
                    "plans": [],
                    "error": f"HTTP Error {response.status_code}",
                }

            except httpx.RequestError as exc:
                logger.error(f"🚨 Network error fetching Bigisub data plans: {exc}")
                return {"success": False, "plans": [], "error": "Connection timed out."}


# Instantiating single global object machine for use across system layers
bigisub_client = BigisubClient()
