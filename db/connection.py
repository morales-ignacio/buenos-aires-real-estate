import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

raw_url = os.environ["DATABASE_URL"]
db_url = raw_url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(db_url, pool_pre_ping=True)


def get_engine():
    return engine


if __name__ == "__main__":
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version()")).scalar()
    print("Connected to:", version)