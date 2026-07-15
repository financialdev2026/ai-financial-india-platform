from contextlib import asynccontextmanager
from pathlib import Path
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.dashboard import router as dashboard_router
from src.scheduler import start_scheduler, stop_scheduler, get_scheduler_status


FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "")


@asynccontextmanager
async def lifespan(app):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="PrismEdge AI API",
    version="1.0.0",
    lifespan=lifespan,
)

origins = [
    "http://localhost:5173",
    "http://localhost:8000",
    "http://localhost:3000",
    "null",
    "*",
]
if RENDER_URL:
    origins.insert(0, RENDER_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    dashboard_router,
    prefix="/dashboard",
    tags=["Dashboard"]
)


@app.get("/api")
def root():
    return {
        "message": "PrismEdge AI Backend Running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/scheduler/status")
def scheduler_status():
    return get_scheduler_status()


# Mount frontend static files LAST (after all API routes)
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
