import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

db_url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg://", 1)
engine = create_engine(db_url, pool_pre_ping=True)

schema_sql = (Path(__file__).parent / "schema.sql").read_text()

with engine.begin() as conn:
    for statement in schema_sql.split(";"):
        if statement.strip():
            conn.execute(text(statement))

with engine.connect() as conn:
    rows = conn.execute(text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' ORDER BY table_name"
    )).fetchall()

print("Tables in the database:")
for row in rows:
    print(" -", row[0])