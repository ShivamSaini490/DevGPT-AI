from langchain_core.tools import tool
from langchain_tavily import TavilySearch

from app.core.config import TAVILY_API_KEY


_tavily_search = None


def _get_tavily_search():
    global _tavily_search

    if _tavily_search is None:
        _tavily_search = TavilySearch(
            max_results=3,
            topic="general",
            search_depth="basic",
            tavily_api_key=TAVILY_API_KEY,
        )

    return _tavily_search


@tool("tavily_search")
def web_search(query: str) -> str:
    """Search the web for current, recent, or time-sensitive information."""
    if not TAVILY_API_KEY:
        return (
            "Web search is not configured. "
            "Add TAVILY_API_KEY to backend/.env."
        )

    return _get_tavily_search().invoke({"query": query})
