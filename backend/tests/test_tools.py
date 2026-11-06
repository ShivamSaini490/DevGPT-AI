import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import httpx

from app.tools.calculator import calculator
from app.tools.document_search import search_uploaded_documents
from app.tools.memory_recall import recall_memory
from app.tools.memory_save import remember_this
from app.tools.registry import tools
from app.tools.stock_market import get_stock_quote
from app.tools.weather import get_live_weather
from app.tools.web_search import web_search
import app.tools.document_search as document_search_module
import app.tools.memory_recall as memory_recall_module
import app.tools.memory_save as memory_save_module
import app.tools.stock_market as stock_module
import app.tools.weather as weather_module


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://example.test")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("error", request=request, response=response)


class FakeClient:
    def __init__(self, responses=None, error=None, **kwargs):
        self.responses = list(responses or [])
        self.error = error
        self.requests = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def get(self, url, **kwargs):
        self.requests.append((url, kwargs))
        if self.error:
            raise self.error
        return self.responses.pop(0)


def test_calculator_handles_valid_and_unsafe_expressions():
    assert calculator.invoke({"expression": "math.sqrt(16) + 2"}) == "6.0"
    assert calculator.invoke({"expression": "sum([1, 2, 3])"}) == "6"
    assert calculator.invoke({"expression": "__import__('os')"}).startswith(
        "Calculation error:"
    )


def test_runnable_config_and_wrapped_tools(monkeypatch):
    captured = {}
    config = {"configurable": {"thread_id": "thread-7"}}

    def fake_retrieve(query, thread_id):
        captured["document"] = (query, thread_id)
        return "document result"

    def fake_save(thread_id, memory):
        captured["save"] = (thread_id, memory)
        return "saved"

    def fake_search(thread_id, query):
        captured["recall"] = (thread_id, query)
        return "recalled"

    monkeypatch.setattr(document_search_module, "retrieve_from_rag", fake_retrieve)
    monkeypatch.setattr(memory_save_module, "save_memory", fake_save)
    monkeypatch.setattr(memory_recall_module, "search_memory", fake_search)

    assert search_uploaded_documents.invoke(
        {"query": "find this"}, config=config
    ) == "document result"
    assert remember_this.invoke(
        {"memory": "remember me"}, config=config
    ) == "saved"
    assert recall_memory.invoke({"query": "what"}, config=config) == "recalled"
    assert captured == {
        "document": ("find this", "thread-7"),
        "save": ("thread-7", "remember me"),
        "recall": ("thread-7", "what"),
    }

    for wrapped_tool in (
        search_uploaded_documents,
        remember_this,
        recall_memory,
    ):
        properties = wrapped_tool.args_schema.model_json_schema()["properties"]
        assert "config" not in properties


def test_concurrent_tools_isolate_documents_and_share_global_memory(monkeypatch):
    def fake_retrieve(query, thread_id):
        return f"document for {thread_id}"

    monkeypatch.setattr(document_search_module, "retrieve_from_rag", fake_retrieve)
    memories_saved = Barrier(2)

    def use_tools(thread_id):
        config = {"configurable": {"thread_id": thread_id}}
        assert remember_this.invoke(
            {"memory": f"memory for {thread_id}"},
            config=config,
        ) == "Memory saved successfully."
        memories_saved.wait()
        return (
            search_uploaded_documents.invoke({"query": "document"}, config=config),
            recall_memory.invoke({"query": "memory"}, config=config),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(use_tools, "thread-a")
        second = executor.submit(use_tools, "thread-b")
        first_result = first.result()
        second_result = second.result()

    assert first_result[0] == "document for thread-a"
    assert second_result[0] == "document for thread-b"
    expected_memories = {
        "- memory for thread-a",
        "- memory for thread-b",
    }
    assert set(first_result[1].splitlines()) == expected_memories
    assert set(second_result[1].splitlines()) == expected_memories


def test_tool_registry_contains_all_expected_tools():
    names = {item.name for item in tools}

    assert {
        "calculator",
        "search_uploaded_documents",
        "remember_this",
        "recall_memory",
        "tavily_search",
        "get_live_weather",
        "get_stock_quote",
    }.issubset(names)

    weather_schema = get_live_weather.args_schema.model_json_schema()
    stock_schema = get_stock_quote.args_schema.model_json_schema()
    assert weather_schema["properties"]["location"]["description"]
    assert weather_schema["properties"]["units"]["enum"] == [
        "metric",
        "imperial",
        "standard",
    ]
    assert stock_schema["properties"]["symbol"]["description"]
    assert web_search.max_results == 3
    assert web_search.search_depth == "basic"


def test_weather_reports_missing_configuration(monkeypatch):
    monkeypatch.setattr(weather_module, "WEATHER_API_KEY", "")
    monkeypatch.setattr(weather_module, "OPENWEATHER_API_KEY", "")

    assert get_live_weather.invoke({"location": "Delhi"}) == (
        "Weather tool is not configured. Add WEATHER_API_KEY to backend/.env."
    )


def test_weather_validates_location_and_returns_live_result(monkeypatch):
    monkeypatch.setattr(weather_module, "WEATHER_API_KEY", "")
    monkeypatch.setattr(weather_module, "OPENWEATHER_API_KEY", "test-key")
    assert get_live_weather.invoke({"location": "   "}) == (
        "Weather lookup requires a city or location."
    )

    client = FakeClient(
        responses=[
            FakeResponse(
                [{"lat": 28.61, "lon": 77.21, "name": "Delhi", "country": "IN"}]
            ),
            FakeResponse(
                {
                    "name": "Delhi",
                    "main": {"temp": 27, "feels_like": 28, "humidity": 50},
                    "wind": {"speed": 3.5},
                    "weather": [{"description": "clear sky"}],
                    "sys": {"country": "IN"},
                }
            ),
        ]
    )
    monkeypatch.setattr(weather_module.httpx, "Client", lambda **kwargs: client)

    result = json.loads(
        get_live_weather.invoke({"location": "Delhi", "units": "invalid"})
    )

    assert result["location"] == "Delhi"
    assert result["temperature"] == 27
    assert result["condition"] == "clear sky"
    assert result["units"] == "metric"
    assert client.requests[1][1]["params"]["units"] == "metric"


def test_weather_handles_not_found_and_timeout(monkeypatch):
    monkeypatch.setattr(weather_module, "WEATHER_API_KEY", "")
    monkeypatch.setattr(weather_module, "OPENWEATHER_API_KEY", "test-key")
    not_found_client = FakeClient(responses=[FakeResponse([])])
    monkeypatch.setattr(
        weather_module.httpx,
        "Client",
        lambda **kwargs: not_found_client,
    )
    assert get_live_weather.invoke({"location": "Unknown"}) == (
        "No weather location found for 'Unknown'."
    )

    timeout = httpx.ReadTimeout("timeout")
    monkeypatch.setattr(
        weather_module.httpx,
        "Client",
        lambda **kwargs: FakeClient(error=timeout),
    )
    assert get_live_weather.invoke({"location": "Delhi"}) == (
        "Weather service timed out. Please try again."
    )


def test_weatherapi_is_preferred_and_preserves_result_contract(monkeypatch):
    monkeypatch.setattr(weather_module, "WEATHER_API_KEY", "weatherapi-key")
    monkeypatch.setattr(weather_module, "OPENWEATHER_API_KEY", "legacy-key")
    client = FakeClient(
        responses=[
            FakeResponse(
                {
                    "location": {
                        "name": "Delhi",
                        "region": "Delhi",
                        "country": "India",
                    },
                    "current": {
                        "temp_c": 27,
                        "temp_f": 80.6,
                        "feelslike_c": 28,
                        "feelslike_f": 82.4,
                        "humidity": 50,
                        "wind_kph": 12.6,
                        "wind_mph": 7.8,
                        "condition": {"text": "Sunny"},
                    },
                }
            )
        ]
    )
    monkeypatch.setattr(weather_module.httpx, "Client", lambda **kwargs: client)

    result = json.loads(get_live_weather.invoke({"location": "Delhi"}))

    assert result == {
        "location": "Delhi",
        "state": "Delhi",
        "country": "India",
        "condition": "Sunny",
        "temperature": 27,
        "feels_like": 28,
        "humidity_percent": 50,
        "wind_speed": 3.5,
        "units": "metric",
    }
    assert client.requests[0][0] == weather_module.WEATHERAPI_CURRENT_URL
    assert client.requests[0][1]["params"]["key"] == "weatherapi-key"


def test_stock_reports_missing_configuration_and_validates_symbol(monkeypatch):
    monkeypatch.setattr(stock_module, "ALPHA_VANTAGE_API_KEY", "")
    monkeypatch.setattr(stock_module, "FINNHUB_API_KEY", "")
    assert get_stock_quote.invoke({"symbol": "AAPL"}) == (
        "Stock market tool is not configured. "
        "Add ALPHA_VANTAGE_API_KEY to backend/.env."
    )

    monkeypatch.setattr(stock_module, "ALPHA_VANTAGE_API_KEY", "")
    monkeypatch.setattr(stock_module, "FINNHUB_API_KEY", "test-key")
    assert get_stock_quote.invoke({"symbol": "  "}) == (
        "Stock quote lookup requires a ticker symbol."
    )


def test_stock_returns_quote_and_handles_empty_result(monkeypatch):
    monkeypatch.setattr(stock_module, "ALPHA_VANTAGE_API_KEY", "")
    monkeypatch.setattr(stock_module, "FINNHUB_API_KEY", "test-key")
    client = FakeClient(
        responses=[
            FakeResponse(
                {
                    "c": 200.5,
                    "d": 1.5,
                    "dp": 0.75,
                    "h": 202,
                    "l": 198,
                    "o": 199,
                    "pc": 199,
                    "t": 1_700_000_000,
                }
            )
        ]
    )
    monkeypatch.setattr(stock_module.httpx, "Client", lambda **kwargs: client)

    result = json.loads(get_stock_quote.invoke({"symbol": " aapl "}))

    assert result["symbol"] == "AAPL"
    assert result["current_price"] == 200.5
    assert result["quoted_at_utc"].endswith("+00:00")
    assert client.requests[0][1]["params"]["symbol"] == "AAPL"

    empty_client = FakeClient(responses=[FakeResponse({})])
    monkeypatch.setattr(stock_module.httpx, "Client", lambda **kwargs: empty_client)
    assert get_stock_quote.invoke({"symbol": "NONE"}) == (
        "No stock quote found for symbol 'NONE'."
    )


def test_stock_handles_timeout(monkeypatch):
    monkeypatch.setattr(stock_module, "ALPHA_VANTAGE_API_KEY", "")
    monkeypatch.setattr(stock_module, "FINNHUB_API_KEY", "test-key")
    monkeypatch.setattr(
        stock_module.httpx,
        "Client",
        lambda **kwargs: FakeClient(error=httpx.ReadTimeout("timeout")),
    )

    assert get_stock_quote.invoke({"symbol": "AAPL"}) == (
        "Stock market service timed out. Please try again."
    )


def test_alpha_vantage_is_preferred_and_preserves_result_contract(monkeypatch):
    monkeypatch.setattr(stock_module, "ALPHA_VANTAGE_API_KEY", "alpha-key")
    monkeypatch.setattr(stock_module, "FINNHUB_API_KEY", "legacy-key")
    client = FakeClient(
        responses=[
            FakeResponse(
                {
                    "Global Quote": {
                        "01. symbol": "AAPL",
                        "02. open": "199.0000",
                        "03. high": "202.0000",
                        "04. low": "198.0000",
                        "05. price": "200.5000",
                        "07. latest trading day": "2026-11-04",
                        "08. previous close": "199.0000",
                        "09. change": "1.5000",
                        "10. change percent": "0.7500%",
                    }
                }
            )
        ]
    )
    monkeypatch.setattr(stock_module.httpx, "Client", lambda **kwargs: client)

    result = json.loads(get_stock_quote.invoke({"symbol": "aapl"}))

    assert result == {
        "symbol": "AAPL",
        "current_price": 200.5,
        "change": 1.5,
        "percent_change": 0.75,
        "day_high": 202.0,
        "day_low": 198.0,
        "day_open": 199.0,
        "previous_close": 199.0,
        "quoted_at_utc": "2026-11-04T00:00:00+00:00",
    }
    assert client.requests[0][0] == stock_module.ALPHA_VANTAGE_QUOTE_URL
    assert client.requests[0][1]["params"]["apikey"] == "alpha-key"

