from fastapi import APIRouter
from app.api.v1 import health, auth, documents, analysis

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(documents.router)
api_router.include_router(analysis.router)
