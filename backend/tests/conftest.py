import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

TEST_DATABASE_URL = (
    "postgresql+psycopg://devgpt_test:devgpt_test_password"
    "@127.0.0.1:5436/devgpt_test"
)
TEST_LANGGRAPH_DATABASE_URL = (
    "postgresql://devgpt_test:devgpt_test_password"
    "@127.0.0.1:5436/devgpt_test"
)
TEST_CLIENT_ID = "11111111-1111-4111-8111-111111111111"

# Set test-only values before any application module imports configuration.
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("LANGGRAPH_DATABASE_URL", TEST_LANGGRAPH_DATABASE_URL)
os.environ["USE_POSTGRES_COMPONENTS"] = "false"
os.environ["APP_NAME"] = "DevGPT API"
os.environ["APP_VERSION"] = "0.1.0"
os.environ["GOOGLE_API_KEY"] = "test-google-key"
os.environ["GROQ_API_KEY"] = "test-groq-key"
os.environ["GROQ_MODEL"] = "openai/gpt-oss-120b"
os.environ["TAVILY_API_KEY"] = "test-tavily-key"
os.environ["WEATHER_API_KEY"] = ""
os.environ["ALPHA_VANTAGE_API_KEY"] = ""
os.environ["OPENWEATHER_API_KEY"] = ""
os.environ["FINNHUB_API_KEY"] = ""
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["REQUIRE_CLIENT_ID"] = "true"
os.environ["ENABLE_CLEANUP_TASK"] = "false"


@pytest.fixture(scope="session", autouse=True)
def database():
    from app.db.session import engine, init_db

    try:
        init_db()
    except Exception as exc:
        pytest.fail(
            "The isolated test database is unavailable. Start it with "
            "`docker compose -f compose.test.yaml up -d --wait` before pytest. "
            f"Original error: {exc}"
        )

    yield

    graph_module = sys.modules.get("app.agents.graph")
    if graph_module is not None:
        graph_module._CHECKPOINT_POOL.close()
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_application_tables(database):
    from app.db.models import (
        ChatMessage,
        ClientSession,
        Conversation,
        DocumentChunk,
        LongTermMemory,
    )
    from app.db.session import engine

    tables = (
        DocumentChunk,
        LongTermMemory,
        ChatMessage,
        Conversation,
        ClientSession,
    )
    with engine.begin() as connection:
        for model in tables:
            connection.execute(delete(model))

    yield

    with engine.begin() as connection:
        for model in tables:
            connection.execute(delete(model))


@pytest.fixture(scope="session")
def client(database):
    from app.main import app

    with TestClient(
        app,
        headers={"X-Client-Id": TEST_CLIENT_ID},
    ) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def client_id():
    return TEST_CLIENT_ID


@pytest.fixture(scope="session")
def client_headers():
    return {"X-Client-Id": TEST_CLIENT_ID}


@pytest.fixture(scope="session")
def unauthenticated_client(database):
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
