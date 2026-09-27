from fastapi import APIRouter
from app.api.v1 import health, auth, documents, analysis, standards, projects, audit, reviews

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(documents.router)
api_router.include_router(analysis.router)
api_router.include_router(standards.router)
api_router.include_router(projects.router)
api_router.include_router(audit.router)
api_router.include_router(reviews.router)
