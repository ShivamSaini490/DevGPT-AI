from app.tools.calculator import calculator
from app.tools.document_search import search_uploaded_documents
from app.tools.figma import figma_tools
from app.tools.github import github_tools
from app.tools.image_generation import generate_image
from app.tools.memory_recall import recall_memory
from app.tools.memory_save import remember_this
from app.tools.stock_market import get_stock_quote
from app.tools.weather import get_live_weather
from app.tools.web_search import web_search


# Always offered to the model.
tools = [
    calculator,
    search_uploaded_documents,
    remember_this,
    recall_memory,
    web_search,
    get_live_weather,
    get_stock_quote,
]

# Offered only in the matching chat mode, so ordinary requests stay small.
MODE_TOOLS = {
    "image": [generate_image],
    "github": github_tools,
    "figma": figma_tools,
}


def tools_for_mode(mode: str | None) -> list:
    return tools + MODE_TOOLS.get(mode or "", [])


all_tools = tools + [tool for extra in MODE_TOOLS.values() for tool in extra]
