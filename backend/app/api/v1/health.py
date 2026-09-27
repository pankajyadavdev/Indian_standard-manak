from fastapi import APIRouter, Depends, status, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.session import get_db
from app.core.config import settings
from app.core.metrics import render_metrics
from app.api.deps import require_permission
from app.models.user import User
from app.services.embedding_service import embedding_status
import os

router = APIRouter(prefix="/health", tags=["Health & Observability"])

@router.get("", status_code=status.HTTP_200_OK)
def liveness():
    """Liveness probe to confirm the service process is up."""
    return {
        "status": "UP",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }

@router.get("/ready", status_code=status.HTTP_200_OK)
def readiness(response: Response, db: Session = Depends(get_db)):
    """
    Readiness probe to confirm all backend dependencies (Database, Storage)
    are functional before receiving traffic.
    """
    checks = {
        "database": False,
        "storage": False,
        "embedding_model": embedding_status(),
    }
    
    # 1. Check Database connection
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        checks["database_error"] = str(e)

    # 2. Check upload directory accessibility
    try:
        upload_path = os.path.abspath(settings.UPLOAD_DIR)
        os.makedirs(upload_path, exist_ok=True)
        test_file = os.path.join(upload_path, ".health_check_probe")
        with open(test_file, "w") as f:
            f.write("probe")
        os.remove(test_file)
        checks["storage"] = True
    except Exception as e:
        checks["storage_error"] = str(e)

    is_healthy = checks["database"] and checks["storage"]
    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "READY" if is_healthy else "DEGRADED",
        "checks": checks,
        "environment": settings.ENVIRONMENT
    }

@router.get("/info", status_code=status.HTTP_200_OK)
def system_info():
    """Returns general platform information."""
    return {
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "model": settings.EMBEDDING_MODEL_NAME
    }


@router.get("/metrics", response_class=PlainTextResponse)
def metrics_endpoint(current_user: User = Depends(require_permission("audit:read"))):
    """Expose aggregate Prometheus-format metrics to authorized operators."""
    return PlainTextResponse(render_metrics(), media_type="text/plain; version=0.0.4; charset=utf-8")
