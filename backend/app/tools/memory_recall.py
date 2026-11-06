from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from app.db import search_memory


@tool
def recall_memory(query: str, config: RunnableConfig) -> str:
    """Recall saved long-term memories about the user or this conversation."""

    return search_memory(
        thread_id=config["configurable"]["thread_id"],
        query=query,
    )
