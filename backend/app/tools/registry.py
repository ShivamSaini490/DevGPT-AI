from app.tools.calculator import calculator
from app.tools.document_search import search_uploaded_documents
from app.tools.memory_recall import recall_memory
from app.tools.memory_save import remember_this
from app.tools.stock_market import get_stock_quote
from app.tools.weather import get_live_weather
from app.tools.web_search import web_search


tools = [
    calculator,
    search_uploaded_documents,
    remember_this,
    recall_memory,
    web_search,
    get_live_weather,
    get_stock_quote,
]
