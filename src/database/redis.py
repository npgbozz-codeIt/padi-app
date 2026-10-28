# src/database/redis.py
import os
import redis.asyncio as aioredis
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Centralized connection pool configured via environment variable
redis_pool = aioredis.ConnectionPool.from_url(
    REDIS_URL,
    decode_responses=True,
    protocol=2,
)

redis_client = aioredis.Redis(connection_pool=redis_pool)


async def get_redis_client() -> aioredis.Redis:
    """Returns the shared async Redis client instance."""
    return redis_client


async def close_redis() -> None:
    """Gracefully closes the Redis connection pool."""
    await redis_client.aclose()
