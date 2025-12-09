"""
FastAPI Application Entry Point

Nöbet Dağıtım Motoru - Ana uygulama dosyası.

Çalıştırma:
    uvicorn app.main:app --reload --port 8000

Production:
    gunicorn -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000 app.main:app
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import schedule, schedule_senior
from app.core.config import get_settings

# Logging yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    yield
    logger.info("Shutting down...")


def create_app() -> FastAPI:
    """FastAPI application factory"""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="""
# Nöbet Dağıtım Motoru API

Bu servis, nöbet atamalarını optimize eden bir REST API'dir.

## Özellikler

- **OR-Tools CP-SAT Solver**: Google'ın constraint programming çözücüsü
- **Çok seviyeli kurallar**: Hard constraint'lerden soft preference'lara
- **Adil dağıtım**: A/B/C/Weekend/Night fairness
- **Tarihsel denge**: Geçmiş dönemleri de hesaba katar

## Kullanım

`POST /schedule/compute` endpoint'ine JSON request gönderin.
        """,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Production'da kısıtla
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(
        schedule.router,
        prefix="/schedule",
        tags=["Schedule"],
    )

    # Senior Scheduler Router
    app.include_router(
        schedule_senior.router,
        prefix="/schedule",
        tags=["Senior Schedule"],
    )

    @app.get("/", tags=["Root"])
    async def root():
        """Root endpoint - API bilgisi"""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/schedule/health",
        }

    return app


# Ana uygulama instance'ı
app = create_app()
