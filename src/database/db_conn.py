# src/database/db_conn
# from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# from sqlalchemy.orm import sessionmaker

# this will be our postgre connection url
DATABASE_URL = "postgresql+asyncpg://postgres:dbpassword123@localhost:5432/mypadi_db"

engine = create_async_engine(DATABASE_URL, echo=True)

# sessionLocal = sesasionmaker(autoflush=False, autcommit=False, bind=engine)
AsyncSessionLocal = async_sessionmaker(
    autoflush=False, autocommit=False, bind=engine, class_=AsyncSession
)


# our database independent injection
async def get_db():
    async with AsyncSessionLocal() as db:
        yield db
