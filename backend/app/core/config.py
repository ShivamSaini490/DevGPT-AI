import os
from urllib.parse import quote

import certifi
from dotenv import load_dotenv

from app.core.paths import ENV_FILE


load_dotenv(ENV_FILE)

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _usable_secret(name: str) -> str:
    value = os.getenv(name, "").strip()
    lowered = value.lower()
    if not value or lowered.startswith("your ") or "replace-with" in lowered:
        return ""
    return value


APP_NAME = os.getenv("APP_NAME", "DevGPT API")
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = _as_bool(os.getenv("DEBUG"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
SECRET_KEY = _usable_secret("SECRET_KEY")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "3000"))
MAX_TOOL_OUTPUT_CHARS = int(os.getenv("MAX_TOOL_OUTPUT_CHARS", "4000"))
REQUIRE_CLIENT_ID = _as_bool(os.getenv("REQUIRE_CLIENT_ID"), default=True)
CLOSE_GRACE_SECONDS = int(os.getenv("CLOSE_GRACE_SECONDS", "45"))
IDLE_TIMEOUT_MINUTES = int(os.getenv("IDLE_TIMEOUT_MINUTES", "10"))
CHAT_RETENTION_HOURS = int(os.getenv("CHAT_RETENTION_HOURS", "24"))
CLEANUP_INTERVAL_SECONDS = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "60"))
ENABLE_CLEANUP_TASK = _as_bool(
    os.getenv("ENABLE_CLEANUP_TASK"),
    default=True,
)
CORS_ORIGINS = [
    origin.strip()
    for origin in (
        os.getenv("CORS_ORIGINS")
        or "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]

GOOGLE_API_KEY = _usable_secret("GOOGLE_API_KEY")
GROQ_API_KEY = _usable_secret("GROQ_API_KEY")
DEFAULT_GROQ_MODEL = os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b"
TAVILY_API_KEY = _usable_secret("TAVILY_API_KEY")

WEATHER_API_KEY = _usable_secret("WEATHER_API_KEY")
ALPHA_VANTAGE_API_KEY = _usable_secret("ALPHA_VANTAGE_API_KEY")
OPENWEATHER_API_KEY = _usable_secret("OPENWEATHER_API_KEY")
FINNHUB_API_KEY = _usable_secret("FINNHUB_API_KEY")

# Optional integrations used by the chat "+" menu.
GITHUB_TOKEN = _usable_secret("GITHUB_TOKEN")
FIGMA_TOKEN = _usable_secret("FIGMA_TOKEN")
# Groq vision model used to read attached photos and sketches.
VISION_MODEL = (
    os.getenv("VISION_MODEL") or "qwen/qwen3.8-27b"
)
# Text-to-image endpoint; "{prompt}" is replaced with the URL-encoded prompt.
IMAGE_GENERATION_URL = os.getenv(
    "IMAGE_GENERATION_URL",
    "https://image.pollinations.ai/prompt/{prompt}"
    "?width=1024&height=1024&nologo=true&seed={seed}",
)
# Groq accepts base64 images up to 4 MB.
MAX_IMAGE_MB = int(os.getenv("MAX_IMAGE_MB", "4"))
DEEP_RESEARCH_CONTEXT_TOKENS = int(
    os.getenv("DEEP_RESEARCH_CONTEXT_TOKENS", "8000")
)
GITHUB_API_URL = "https://api.github.com"
FIGMA_API_URL = "https://api.figma.com/v1"

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5435"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "devgpt")
POSTGRES_USER = os.getenv("POSTGRES_USER", "devgpt")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "devgpt_local_password")

_derived_database_url = (
    "postgresql+psycopg://"
    f"{quote(POSTGRES_USER, safe='')}:{quote(POSTGRES_PASSWORD, safe='')}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{quote(POSTGRES_DB, safe='')}"
)
if os.getenv("POSTGRES_SSLMODE"):
    _derived_database_url += (
        f"?sslmode={os.getenv('POSTGRES_SSLMODE')}"
    )

    if os.getenv("POSTGRES_CHANNEL_BINDING"):
        _derived_database_url += (
            f"&channel_binding={os.getenv('POSTGRES_CHANNEL_BINDING')}"
        )
_use_postgres_components = _as_bool(os.getenv("USE_POSTGRES_COMPONENTS"))
DATABASE_URL = (
    _derived_database_url
    if _use_postgres_components
    else os.getenv("DATABASE_URL", _derived_database_url)
)
_derived_langgraph_database_url = _derived_database_url.replace(
    "postgresql+psycopg://", "postgresql://", 1
)
LANGGRAPH_DATABASE_URL = (
    _derived_langgraph_database_url
    if _use_postgres_components
    else os.getenv(
        "LANGGRAPH_DATABASE_URL",
        DATABASE_URL.replace("postgresql+psycopg://", "postgresql://", 1),
    )
)

LANGSMITH_PROJECT = (
    os.getenv("LANGSMITH_PROJECT")
    or os.getenv("LANGSMITH_PROJECT_NAME")
    or "DevGPT"
)
os.environ.setdefault("LANGSMITH_PROJECT", LANGSMITH_PROJECT)

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 3072

WEATHERAPI_CURRENT_URL = "https://api.weatherapi.com/v1/current.json"
OPENWEATHER_GEOCODING_URL = "https://api.openweathermap.org/geo/1.0/direct"
OPENWEATHER_CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
ALPHA_VANTAGE_QUOTE_URL = "https://www.alphavantage.co/query"
FINNHUB_QUOTE_URL = "https://finnhub.io/api/v1/quote"

EXTERNAL_API_TIMEOUT_SECONDS = 10.0
