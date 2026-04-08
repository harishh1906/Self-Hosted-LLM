import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://virtue:virtuepass@postgres:5432/virtue"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,        # Detect stale connections
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800          # Recycle connections every 30 min
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
