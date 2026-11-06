import json
import os
import subprocess
import sys


def test_component_database_settings_and_aliases_are_integrated():
    environment = os.environ.copy()
    environment.update(
        {
            "USE_POSTGRES_COMPONENTS": "true",
            "POSTGRES_HOST": "postgres",
            "POSTGRES_PORT": "5432",
            "POSTGRES_DB": "devgpt",
            "POSTGRES_USER": "dev user",
            "POSTGRES_PASSWORD": "p@ss word",
            "SECRET_KEY": "Your Secret Key Here",
            "CORS_ORIGINS": "https://one.example, https://two.example ",
            "MAX_UPLOAD_MB": "25",
            "MAX_CONTEXT_TOKENS": "2500",
            "MAX_TOOL_OUTPUT_CHARS": "3500",
            "REQUIRE_CLIENT_ID": "false",
            "CLOSE_GRACE_SECONDS": "30",
            "IDLE_TIMEOUT_MINUTES": "15",
            "CHAT_RETENTION_HOURS": "48",
            "CLEANUP_INTERVAL_SECONDS": "120",
            "ENABLE_CLEANUP_TASK": "false",
            "GOOGLE_API_KEY": "test-google-embedding-key",
            "GROQ_API_KEY": "Your Groq API Key Here",
            "GROQ_MODEL": "openai/gpt-oss-20b",
            "LANGSMITH_PROJECT_NAME": "Project Alias",
        }
    )
    environment.pop("DATABASE_URL", None)
    environment.pop("LANGGRAPH_DATABASE_URL", None)
    environment.pop("LANGSMITH_PROJECT", None)

    script = (
        "import json; from app.core import config; "
        "print(json.dumps({"
        "'database_url': config.DATABASE_URL, "
        "'langgraph_url': config.LANGGRAPH_DATABASE_URL, "
        "'secret_key': config.SECRET_KEY, "
        "'cors_origins': config.CORS_ORIGINS, "
        "'max_upload_mb': config.MAX_UPLOAD_MB, "
        "'max_context_tokens': config.MAX_CONTEXT_TOKENS, "
        "'max_tool_output_chars': config.MAX_TOOL_OUTPUT_CHARS, "
        "'require_client_id': config.REQUIRE_CLIENT_ID, "
        "'close_grace_seconds': config.CLOSE_GRACE_SECONDS, "
        "'idle_timeout_minutes': config.IDLE_TIMEOUT_MINUTES, "
        "'chat_retention_hours': config.CHAT_RETENTION_HOURS, "
        "'cleanup_interval_seconds': config.CLEANUP_INTERVAL_SECONDS, "
        "'enable_cleanup_task': config.ENABLE_CLEANUP_TASK, "
        "'google_api_key': config.GOOGLE_API_KEY, "
        "'groq_api_key': config.GROQ_API_KEY, "
        "'groq_model': config.DEFAULT_GROQ_MODEL, "
        "'langsmith_project': config.LANGSMITH_PROJECT"
        "}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    settings = json.loads(result.stdout)

    assert settings["database_url"] == (
        "postgresql+psycopg://dev%20user:p%40ss%20word@postgres:5432/devgpt"
    )
    assert settings["langgraph_url"] == (
        "postgresql://dev%20user:p%40ss%20word@postgres:5432/devgpt"
    )
    assert settings["secret_key"] == ""
    assert settings["cors_origins"] == [
        "https://one.example",
        "https://two.example",
    ]
    assert settings["max_upload_mb"] == 25
    assert settings["max_context_tokens"] == 2500
    assert settings["max_tool_output_chars"] == 3500
    assert settings["require_client_id"] is False
    assert settings["close_grace_seconds"] == 30
    assert settings["idle_timeout_minutes"] == 15
    assert settings["chat_retention_hours"] == 48
    assert settings["cleanup_interval_seconds"] == 120
    assert settings["enable_cleanup_task"] is False
    assert settings["google_api_key"] == "test-google-embedding-key"
    assert settings["groq_api_key"] == ""
    assert settings["groq_model"] == "openai/gpt-oss-20b"
    assert settings["langsmith_project"] == "Project Alias"


def test_cors_origins_use_react_dev_server_defaults():
    environment = os.environ.copy()
    environment["CORS_ORIGINS"] = ""

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json; from app.core.config import CORS_ORIGINS; "
            "print(json.dumps(CORS_ORIGINS))",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert json.loads(result.stdout) == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
