# run_sync.py
import asyncio
import logging
from src.database.db_conn import (
    AsyncSessionLocal,
)
from src.services.plan_sync import sync_data_plans_to_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("⚡ Manually executing database data plan cache seed...")
    # Acquire a clean database session context safely outside a router
    async with AsyncSessionLocal() as session:
        result = await sync_data_plans_to_db(session)
        logger.info(f"Database sync output execution result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
