from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://vetbox:vetbox@localhost:5432/vetbox"
)

engine = create_engine(DATABASE_URL, echo=True, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DatabaseManager:
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal

    def get_session(self) -> Session:
        return self.SessionLocal()

    def create_tables(self):
        Base.metadata.create_all(bind=self.engine)

# Example usage:
# db = DatabaseManager()
# db.create_tables()
# with db.get_session() as session:
#     # use session for queries