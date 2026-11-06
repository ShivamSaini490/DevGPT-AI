import json
from datetime import datetime, timezone

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.config import (
    ALPHA_VANTAGE_API_KEY,
    ALPHA_VANTAGE_QUOTE_URL,
    EXTERNAL_API_TIMEOUT_SECONDS,
    FINNHUB_API_KEY,
    FINNHUB_QUOTE_URL,
)


class StockQuoteInput(BaseModel):
    symbol: str = Field(description="Stock-market ticker symbol to look up.")


def _as_float(value):
    if value in (None, ""):
        return None
    return float(str(value).rstrip("%"))


def _alpha_vantage_result(symbol: str, payload: dict) -> dict | None:
    quote = payload.get("Global Quote", {})
    if not quote or not quote.get("05. price"):
        return None

    trading_day = quote.get("07. latest trading day")
    quoted_at = None
    if trading_day:
        quoted_at = datetime.strptime(trading_day, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        ).isoformat()

    return {
        "symbol": quote.get("01. symbol") or symbol,
        "current_price": _as_float(quote.get("05. price")),
        "change": _as_float(quote.get("09. change")),
        "percent_change": _as_float(quote.get("10. change percent")),
        "day_high": _as_float(quote.get("03. high")),
        "day_low": _as_float(quote.get("04. low")),
        "day_open": _as_float(quote.get("02. open")),
        "previous_close": _as_float(quote.get("08. previous close")),
        "quoted_at_utc": quoted_at,
    }


@tool(args_schema=StockQuoteInput)
def get_stock_quote(symbol: str) -> str:
    """Get the latest available stock-market quote for a ticker symbol."""

    if not ALPHA_VANTAGE_API_KEY and not FINNHUB_API_KEY:
        return (
            "Stock market tool is not configured. "
            "Add ALPHA_VANTAGE_API_KEY to backend/.env."
        )

    symbol = symbol.strip().upper()
    if not symbol:
        return "Stock quote lookup requires a ticker symbol."

    try:
        with httpx.Client(timeout=EXTERNAL_API_TIMEOUT_SECONDS) as client:
            if ALPHA_VANTAGE_API_KEY:
                response = client.get(
                    ALPHA_VANTAGE_QUOTE_URL,
                    params={
                        "function": "GLOBAL_QUOTE",
                        "symbol": symbol,
                        "apikey": ALPHA_VANTAGE_API_KEY,
                    },
                )
                response.raise_for_status()
                result = _alpha_vantage_result(symbol, response.json())
                if result is None:
                    return f"No stock quote found for symbol '{symbol}'."
                return json.dumps(result, ensure_ascii=False)

            response = client.get(
                FINNHUB_QUOTE_URL,
                params={"symbol": symbol},
                headers={"X-Finnhub-Token": FINNHUB_API_KEY},
            )
            response.raise_for_status()
            quote = response.json()

        if not quote or (not quote.get("t") and not quote.get("c")):
            return f"No stock quote found for symbol '{symbol}'."

        quote_timestamp = quote.get("t")
        quoted_at = None
        if quote_timestamp:
            quoted_at = datetime.fromtimestamp(
                quote_timestamp,
                tz=timezone.utc,
            ).isoformat()

        result = {
            "symbol": symbol,
            "current_price": quote.get("c"),
            "change": quote.get("d"),
            "percent_change": quote.get("dp"),
            "day_high": quote.get("h"),
            "day_low": quote.get("l"),
            "day_open": quote.get("o"),
            "previous_close": quote.get("pc"),
            "quoted_at_utc": quoted_at,
        }
        return json.dumps(result, ensure_ascii=False)
    except httpx.TimeoutException:
        return "Stock market service timed out. Please try again."
    except (httpx.HTTPError, TypeError, ValueError, OSError):
        return "Stock market service could not complete the request. Please try again."
