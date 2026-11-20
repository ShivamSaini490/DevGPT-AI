"""Detect questions that must be grounded in a live web search."""

from __future__ import annotations

import re
from datetime import date


_EXPLICIT_CURRENT = re.compile(
    r"\b(?:latest|current(?:ly)?|today(?:'s)?|right\s+now|recent(?:ly)?|"
    r"newest|up[ -]to[ -]date|as\s+of|live|breaking|this\s+(?:week|month|year)|"
    r"news|release(?:d)?|version)\b",
    re.IGNORECASE,
)
_CURRENT_ROLE = re.compile(
    r"\bwho\s+(?:is|are)\s+(?:the\s+)?(?:current\s+)?(?:"
    r"president|prime\s+minister|chief\s+minister|cm|chancellor|"
    r"vice\s+president|governor|mayor|"
    r"chief\s+executive(?:\s+officer)?|ceo|chair(?:man|woman|person)?|"
    r"secretary[ -]general|head\s+of\s+state|pope|monarch|king|queen|leader"
    r")\b",
    re.IGNORECASE,
)
_WEATHER_REQUEST = re.compile(
    r"\b(?:weather|forecast|temperature|rain(?:ing)?|snow(?:ing)?|humidity)\b",
    re.IGNORECASE,
)
_MARKET_REQUEST = re.compile(
    r"\b(?:stock|share)\s+(?:price|quote)\b|\bmarket\s+quote\b|"
    r"\bticker\s+(?:price|quote)\b",
    re.IGNORECASE,
)
_CLOCK_REQUEST = re.compile(
    r"\b(?:what(?:'s|\s+is)\s+)?(?:the\s+)?(?:time|date|day)\s+"
    r"(?:is\s+it\s+)?(?:now|today)\b",
    re.IGNORECASE,
)
_SHORT_TERM_IN_CONTEXT = re.compile(
    r"^\s*[a-z][a-z0-9-]{1,9}\s+(?:in|for)\s+.{3,100}[?.]?\s*$",
    re.IGNORECASE,
)
_NON_WEB_MODES = {"image", "github", "figma"}


def needs_live_web_search(message: str, mode: str | None = None) -> bool:
    """Return whether an answer could be stale without live web results."""
    if not message.strip() or (mode or "") in _NON_WEB_MODES:
        return False

    # These requests have purpose-built live tools, and the local clock is more
    # reliable than a search result for date/time questions.
    if (
        _WEATHER_REQUEST.search(message)
        or _MARKET_REQUEST.search(message)
        or _CLOCK_REQUEST.search(message)
    ):
        return False

    return bool(
        (mode or "") in {"web_search", "deep_research"}
        or _EXPLICIT_CURRENT.search(message)
        or _CURRENT_ROLE.search(message)
        or _SHORT_TERM_IN_CONTEXT.match(message)
    )


def live_search_query(message: str, current_date: date | None = None) -> str:
    """Make recency and source quality explicit to the search provider."""
    today = (current_date or date.today()).isoformat()
    return (
        f"{message.strip()}\n"
        f"Verify the current answer as of {today}. Prefer official and primary sources."
    )
