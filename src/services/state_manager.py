# src/services/state_manager.py
import json
import logging
import os
from typing import Any, Dict, Optional
import redis.asyncio as redis
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL", 300))  # 5-minute timeout


class StateManager:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None

    async def get_redis(self) -> redis.Redis:
        """
        Lazy initialization of async Redis client connection.
        """
        if self.redis_client is None:
            self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        return self.redis_client

    async def close(self):
        """
        Closes Redis connection pool cleanly.
        """
        if self.redis_client:
            await self.redis_client.close()

    def _get_key(self, user_id: str) -> str:
        return f"mypadi:session:{user_id}"

    async def get_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves current active conversation session for a user.
        """
        r = await self.get_redis()
        key = self._get_key(user_id)
        data = await r.get(key)
        if data:
            try:
                return json.loads(data)
            except Exception as exc:
                logger.error(f"Failed to parse session state for {user_id}: {exc}")
                return None
        return None

    async def set_session(
        self, user_id: str, state: str, intent: str, payload: Dict[str, Any]
    ) -> bool:
        """
        Saves user session state with automatic TTL expiration.
        States: 'IDLE', 'AWAITING_SLOT', 'PENDING_CONFIRMATION'
        """
        r = await self.get_redis()
        key = self._get_key(user_id)
        session_data = {
            "state": state,
            "intent": intent,
            "payload": payload,
        }
        await r.set(key, json.dumps(session_data), ex=SESSION_TTL_SECONDS)
        return True

    async def clear_session(self, user_id: str) -> bool:
        """
        Deletes active session when transaction finishes or is cancelled.
        """
        r = await self.get_redis()
        key = self._get_key(user_id)
        await r.delete(key)
        return True


state_manager = StateManager()