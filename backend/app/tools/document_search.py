from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from app.rag import retrieve_from_rag


@tool
def search_uploaded_documents(query: str, config: RunnableConfig) -> str:
    """
    Search uploaded documents for relevant information.
    Use this when the user asks about uploaded PDFs, DOCX, TXT, notes, files, or documents.
    """

    return retrieve_from_rag(
        query=query,
        thread_id=config["configurable"]["thread_id"],
    )
