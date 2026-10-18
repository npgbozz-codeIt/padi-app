# src/services/session_manager.py
import json
from typing import Dict, Any, Optional
import redis.asyncio as aioredis

redis_pool = aioredis.ConnectionPool(
    host="localhost", port=6379, db=0, decode_responses=True, protocol=2
)
redis_client = aioredis.Redis(connection_pool=redis_pool)


class SessionManager:
    @staticmethod
    async def get_session(chat_id: int) -> Dict[str, Any]:
        """Fetch current session state for a user chat."""
        key = f"session:{chat_id}"
        data = await redis_client.get(key)
        if data:
            try:
                return json.loads(data)
            except Exception:
                return {}
        return {}

    @staticmethod
    async def update_session(chat_id: int, intent: str, slots: Dict[str, Any], ttl: int = 300) -> None:
        """Store or update session intent and slots in Redis with a 5-minute TTL."""
        key = f"session:{chat_id}"
        session = await SessionManager.get_session(chat_id)
        
        session["intent"] = intent
        current_slots = session.get("slots", {})
        
        # Merge new non-null values
        for k, v in slots.items():
            if v is not None:
                current_slots[k] = v
                
        session["slots"] = current_slots
        await redis_client.set(key, json.dumps(session), ex=ttl)

    @staticmethod
    async def clear_session(chat_id: int) -> None:
        """Purge active user session upon transaction completion or cancellation."""
        key = f"session:{chat_id}"
        await redis_client.delete(key)