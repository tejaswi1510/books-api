from fastapi import APIRouter

from app.api.v1.endpoints import assistant, auth, books

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(books.router)
api_router.include_router(assistant.router)
