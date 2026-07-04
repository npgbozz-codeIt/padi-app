# src/main.py
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, status

# Internal database and structure imports
from src.database.db_conn import engine, AsyncSessionLocal
from src.models.base import Base
from src.routers.telegram import router as telegram_router
from src.services.plan_sync import sync_data_plans_to_db


# 1. Background worker runner task loop configuration
async def recurring_plan_sync_worker():
    """Loops indefinitely in the background, syncing plans every 2 hours."""
    # Give the server a few seconds to fully boot up before running the first sync
    await asyncio.sleep(5)

    while True:
        try:
            print("⏳ Scheduled Worker: Refreshing Bigisub cache data plans...")
            async with AsyncSessionLocal() as session:
                await sync_data_plans_to_db(session)
        except Exception as e:
            print(f"🚨 Background worker sync dropped: {e}")

        # Sleep for 2 hours (2 * 60 * 60 seconds)
        await asyncio.sleep(7200)


# 2. Your existing single lifespan manager, extended with background worker scheduling
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("checking database connection...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)  # Development table creator
        print("database connection established successfully")
    except Exception as e:
        print(f"database connection failed: {e}")

    # 🚀 Kickoff background synchronization thread here safely
    print("🚀 Spawning data plan sync background worker process...")
    bg_task = asyncio.create_task(recurring_plan_sync_worker())

    yield  # 🟢 The entire API server runs here dynamically...

    # This block fires when the server turns off
    print("🛑 App shutting down: Cancelling background worker tasks...")
    bg_task.cancel()


# 3. App Initialization
app = FastAPI(lifespan=lifespan, title="MyPadi Chatbot API", version="1.0")

app.include_router(
    telegram_router, prefix="/webhook/telegram", tags=["Telegram Webhook"]
)


@app.get("/", status_code=status.HTTP_200_OK)
@app.get("/health", status_code=status.HTTP_200_OK)
def check_app_health():
    return {"app_name": "MyPadi Chatbot API", "version": "1.0", "health": "Perfect"}
