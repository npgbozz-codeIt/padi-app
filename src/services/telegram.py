# src/services/telegram.py
import os
import httpx
import logging
from typing import Optional

# Hook directly into Uvicorn's active terminal stream to bypass text buffering
logger = logging.getLogger("uvicorn.error")


class TelegramBotClient:
    def __init__(self):
        self._cached_username: Optional[str] = None

    @property
    def base_url(self) -> str:
        """Dynamically extracts and cleans the token at runtime to prevent initialization issues."""
        raw_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        clean_token = raw_token.strip().strip('"').strip("'")
        return f"https://api.telegram.org/bot{clean_token}"

    async def get_bot_username(self) -> str:
        """
        Fetches and caches the bot's actual Telegram username dynamically via the getMe API endpoint.
        Prevents broken referral links if the bot handle changes in the future.
        """
        if self._cached_username:
            return self._cached_username

        url = f"{self.base_url}/getMe"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        username = data.get("result", {}).get("username")
                        if username:
                            self._cached_username = username
                            return username
            except Exception as e:
                logger.error(f"⚠️ [Telegram API getMe Exception]: {e}")

        # Fallback to default if API call fails
        return "MyPadi_Bot"

    async def generate_referral_link(self, referral_code: str) -> str:
        """Constructs a dynamic deep-link referral URL for a given user referral code."""
        bot_username = await self.get_bot_username()
        return f"https://t.me/{bot_username}?start=ref_{referral_code}"

    async def send_message(self, payload: dict) -> bool:
        """Sends a brand new message or custom button keyboard card to a user."""
        url = f"{self.base_url}/sendMessage"

        logger.info(
            f"📩 [Telegram API Outbound] Target Chat ID: {payload.get('chat_id')} | Payload: {payload}"
        )

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, json=payload)
                logger.info(
                    f"📥 [Telegram API Response] HTTP Status: {response.status_code} | Body: {response.text}"
                )
                return response.status_code == 200
            except Exception as e:
                logger.error(
                    f"❌ [Telegram API Exception]: Failed to connect to endpoint: {e}"
                )
                return False

    async def edit_message_text(self, payload: dict) -> bool:
        """Edits an existing inline button message in-place to save screen space."""
        url = f"{self.base_url}/editMessageText"
        logger.info(f"📩 [Telegram API Edit] Target Chat ID: {payload.get('chat_id')}")

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url, json=payload)
                logger.info(
                    f"📥 [Telegram API Edit Response] HTTP Status: {response.status_code} | Body: {response.text}"
                )
                return response.status_code == 200
            except Exception as e:
                logger.error(f"❌ [Telegram API Edit Exception]: {e}")
                return False

    async def send_chat_action(self, chat_id: int, action: str = "typing") -> bool:
        """
        Triggers a chat state visibility packet (e.g., 'typing', 'uploading_document')
        directly down Telegram's network pipes to improve perceived latency.
        """
        url = f"{self.base_url}/sendChatAction"
        payload = {"chat_id": chat_id, "action": action}

        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.post(url, json=payload)
                return response.status_code == 200
            except Exception as e:
                logger.error(f"❌ [Telegram API ChatAction Exception]: {e}")
                return False


# Instantiate clean singleton instance
telegram_client = TelegramBotClient()