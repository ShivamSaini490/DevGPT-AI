from langchain_tavily import TavilySearch

from app.core import config  # noqa: F401


web_search = TavilySearch(
    max_results=3,
    topic="general",
    search_depth="basic",
)
