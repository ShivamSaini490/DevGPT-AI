import logging
import re
from html import unescape
from xml.etree import ElementTree

import httpx
from ddgs import DDGS
from langchain_core.tools import tool
from langchain_tavily import TavilySearch

from app.core.config import EXTERNAL_API_TIMEOUT_SECONDS, TAVILY_API_KEY


_tavily_search = None
_tavily_auth_rejected = False
_GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
_HTML_TAG = re.compile(r"<[^>]+>")
logger = logging.getLogger(__name__)


def _get_tavily_search():
    global _tavily_search

    if _tavily_search is None:
        _tavily_search = TavilySearch(
            max_results=5,
            topic="general",
            search_depth="advanced",
            include_answer="advanced",
            tavily_api_key=TAVILY_API_KEY,
        )

    return _tavily_search


def _google_news_search(query: str) -> dict | str:
    """Keyless live-search fallback for missing or rejected Tavily keys."""
    # The router adds source-quality instructions on a second line for Tavily.
    # News search works better with only the user's original question.
    search_query = query.partition("\n")[0].strip()
    try:
        response = httpx.get(
            _GOOGLE_NEWS_RSS_URL,
            params={"q": search_query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
            headers={"User-Agent": "DevGPT/0.1"},
            timeout=EXTERNAL_API_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        response.raise_for_status()
        root = ElementTree.fromstring(response.content)
    except (httpx.HTTPError, ElementTree.ParseError) as exc:
        return f"Live web search failed: {exc}"

    results = []
    for item in root.findall("./channel/item")[:5]:
        title = unescape(item.findtext("title", "")).strip()
        url = item.findtext("link", "").strip()
        published = item.findtext("pubDate", "").strip()
        raw_description = item.findtext("description", "")
        description = unescape(_HTML_TAG.sub(" ", raw_description))
        description = " ".join(description.split())
        if title and url:
            results.append(
                {
                    "title": title,
                    "url": url,
                    "published_date": published,
                    "content": description,
                }
            )

    if not results:
        return "Live web search returned no results."

    return {
        "provider": "Google News RSS fallback",
        "query": search_query,
        "results": results,
    }


def _general_web_search(query: str) -> dict | str:
    """Search the general web for definitions, documentation, and niche topics."""
    search_query = query.partition("\n")[0].strip()
    try:
        raw_results = DDGS(timeout=8).text(
            search_query,
            region="us-en",
            safesearch="moderate",
            max_results=5,
            backend="yahoo",
        )
    except Exception as exc:
        logger.warning("General web fallback failed: %s", exc)
        return _google_news_search(query)

    results = [
        {
            "title": item.get("title", ""),
            "url": item.get("href", ""),
            "content": item.get("body", ""),
        }
        for item in raw_results
        if item.get("title") and item.get("href")
    ]
    if not results:
        return _google_news_search(query)

    return {
        "provider": "General web search fallback",
        "query": search_query,
        "results": results,
    }


def _is_tavily_auth_error(result: object) -> bool:
    if not isinstance(result, dict) or not result.get("error"):
        return False
    error_text = str(result["error"]).lower()
    return "401" in error_text and (
        "unauthorized" in error_text or "api key" in error_text
    )


@tool("tavily_search")
def web_search(query: str) -> str | dict:
    """Search the web for current, recent, or time-sensitive information."""
    global _tavily_auth_rejected

    if TAVILY_API_KEY and not _tavily_auth_rejected:
        try:
            result = _get_tavily_search().invoke({"query": query})
            if not (isinstance(result, dict) and result.get("error")):
                return result
            if _is_tavily_auth_error(result):
                _tavily_auth_rejected = True
                logger.warning(
                    "Tavily rejected its API key; using the live fallback "
                    "for subsequent searches"
                )
        except Exception:
            # A live fallback is more useful than exposing a provider-specific
            # authentication, quota, or transient network failure to the model.
            pass

    return _general_web_search(query)
