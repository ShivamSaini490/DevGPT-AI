from fastapi import APIRouter

from app.api.routes import chat, conversations, documents, pages, sessions


api_router = APIRouter()
api_router.include_router(pages.router)
api_router.include_router(conversations.router)
api_router.include_router(documents.router)
api_router.include_router(chat.router)
api_router.include_router(sessions.router)
