from fastapi import FastAPI, status
from contextlib import asynccontextmanager
from src.database.db_conn import engine
from src.models.base import Base
from src.routers.telegram import router as telegram_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("checking database connection...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("database connection established successfully")
    except Exception as e:
        print(f"database connection failed: {e}")
    yield


app = FastAPI(lifespan=lifespan, title="MyPadi Chatbot API", version="1.0")
# router registration lines here
app.include_router(
    telegram_router, prefix="/webhook/telegram", tags=["Telegram Webhook"]
)


@app.get("/", status_code=status.HTTP_200_OK)
@app.get("/health", status_code=status.HTTP_200_OK)
def check_app_health():
    return {"app_name": "MyPadi Chatbot API", "version": "1.0", "health": "Perfect"}
