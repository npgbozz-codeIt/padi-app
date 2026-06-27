from fastapi import FastAPI, status
from contextlib import asynccontextmanager
from src.database.db_conn import engine
from src.models.base import Base
import src.models


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("checking database connection...")
    try:
        Base.metadata.create_all(bind=engine)
        print("database connection established successfully")
    except Exception as e:
        print(f"database connection failed: {e}")
    yield


app = FastAPI(lifespan=lifespan, title="MyPadi Chatbot API", version="1.0")


@app.get("/health", status_code=status.HTTP_200_OK)
def check_app_health():
    return {"app_name": "MyPadi Chatbot API", "version": "1.0", "health": "Perfect"}
