import time
import uuid
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import settings
from app.core.logging import logger
from app.core.rate_limit import RateLimitMiddleware
from app.core.metrics import record_http_request
from app.api.router import api_router
from app.db.session import engine
from app.db.base import Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing IS Platform backend services...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database schemas verified.")
    yield
    logger.info("Shutting down IS Platform backend services...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Enterprise Tender Compliance & Verification Platform against Indian Standards (BIS)",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/api/redoc" if settings.ENVIRONMENT != "production" else None,
    openapi_url="/api/openapi.json" if settings.ENVIRONMENT != "production" else None,
)

# Custom Middleware for Request ID & OWASP Security Headers
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", "")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", request_id):
            request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start_time = time.time()
        
        response = await call_next(request)
        
        process_time = (time.time() - start_time) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
        
        # Hardened OWASP Security Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; "
            "frame-ancestors 'none';"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"

        route = getattr(request.scope.get("route"), "path", "unmatched")
        if route != "unmatched" and request.url.path.startswith("/api/v1/"):
            route = f"/api/v1{route}"
        record_http_request(request.method, route, response.status_code, process_time / 1000.0)
        logger.info(
            "http.request",
            extra={
                "request_id": request_id,
                "extra_data": {
                    "method": request.method,
                    "route": route,
                    "status": response.status_code,
                    "duration_ms": round(process_time, 2),
                },
            },
        )
        
        return response

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=settings.RATE_LIMIT_PER_MINUTE, window_seconds=60)

# CORS Middleware with strict origin enforcement
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Request Validation Error Handler (Sanitizes Pydantic validation errors)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    req_id = getattr(request.state, "request_id", "unknown")
    sanitized_errors = []
    for error in exc.errors():
        location = " -> ".join(str(part) for part in error.get("loc", []))
        msg = error.get("msg", "Validation error")
        sanitized_errors.append({"field": location, "message": msg})
        
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "message": "The request payload failed schema validation",
            "details": sanitized_errors,
            "request_id": req_id
        }
    )

# Global safe exception handler: prevents internal stack traces in responses
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        f"Unhandled exception during request {request.method} {request.url.path}: {str(exc)}",
        exc_info=True,
        extra={"request_id": req_id}
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please contact system administrator with the Request ID.",
            "request_id": req_id
        }
    )

# Include API Router
app.include_router(api_router)

@app.get("/")
def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/api/docs" if settings.ENVIRONMENT != "production" else "Disabled in production",
        "health": "/api/v1/health"
    }

# Endpoint for validating 500 error sanitization
@app.get("/api/v1/simulate-error")
def simulate_internal_error():
    raise RuntimeError("Intentional error for verifying safe exception masking")
