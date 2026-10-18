# src/database/db_conn
# from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# from sqlalchemy.orm import sessionmaker

# this will be our postgre connection url
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/mypadi_db"

engine = create_async_engine(DATABASE_URL, echo=False)

# sessionLocal = sesasionmaker(autoflush=False, autcommit=False, bind=engine)
AsyncSessionLocal = async_sessionmaker(
    autoflush=False,
    autocommit=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# our database independent injection
async def get_db():
    async with AsyncSessionLocal() as db:
        yield db
