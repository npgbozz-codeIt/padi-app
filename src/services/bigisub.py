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
        self.headers = {
            "Authorization": f"{self.api_key}",
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


# Instantiating single global object machine for use across system layers
bigisub_client = BigisubClient()
