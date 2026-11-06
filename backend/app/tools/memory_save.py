from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from app.db import save_memory


@tool
def remember_this(memory: str, config: RunnableConfig) -> str:
    """
    Save an important user preference or fact into long-term memory.
    Use this when the user asks you to remember something.
    """

    return save_memory(
        thread_id=config["configurable"]["thread_id"],
        memory=memory,
    )
