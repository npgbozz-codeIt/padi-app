from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# this will be our postgre connection url
DATABASE_URL = "postgresql://postgres:dbpassword123@localhost:5432/mypadi_db"

engine = create_engine(DATABASE_URL, echo=False)

sessionLocal = sessionmaker(autoflush=False, autcommit=False, bind=engine)


# our database independent injection
def get_db():
    with sessionLocal as db:
        yield db
