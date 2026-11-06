from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import DATABASE_URL


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def init_db():
    from app.db import models  # noqa: F401

    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE conversations "
                "ADD COLUMN IF NOT EXISTS client_id VARCHAR"
            )
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_conversations_client_id "
                "ON conversations (client_id)"
            )
        )
