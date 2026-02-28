from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.tools import router as tools_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-driven COO Agent for Conut hackathon. OpenClaw-ready tool endpoints.",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tools_router)


@app.get("/health", tags=["system"])
def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "raw_data_dir": str(settings.raw_data_dir),
        "processed_data_dir": str(settings.processed_data_dir),
    }
