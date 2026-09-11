"""FastAPI application factory.

Mounts the versioned routers and configures CORS. Kept as a factory
(``create_app``) so tests can build an isolated instance, while the module
level ``app`` is what uvicorn imports (``uvicorn app.main:app``).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, users
from app.core.config import settings


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.PROJECT_VERSION,
        description="Offline-first hospital record keeping system API.",
    )

    if settings.BACKEND_CORS_ORIGINS:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.BACKEND_CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    application.include_router(auth.router, prefix=settings.API_V1_STR)
    application.include_router(users.router, prefix=settings.API_V1_STR)

    @application.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        """Liveness probe."""
        return {
            "status": "ok",
            "project": settings.PROJECT_NAME,
            "version": settings.PROJECT_VERSION,
        }

    return application


app = create_app()
