import json
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
import os

import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine as create_sa_engine

from src.api.dashboard import router as dashboard_router
from src.scheduler import start_scheduler, stop_scheduler, get_scheduler_status


FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
BACKEND_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BACKEND_DIR / "data"
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "")


def seed_from_bundle():
    bundle_path = FRONTEND_DIR / "data" / "bundle.json"
    report_path = BACKEND_DIR / "reports" / "market_report.json"
    if not bundle_path.exists():
        print("[SEED] bundle.json not found, skipping.")
        return
    try:
        se = create_sa_engine("sqlite:///data/financial_market.db")
        cnt = pd.read_sql("SELECT COUNT(*) AS c FROM market_reports", se)["c"].iloc[0]
        if cnt > 0:
            print("[SEED] market_reports already has data, skipping.")
            return
    except Exception:
        pass

    with open(bundle_path, "r", encoding="utf-8") as f:
        bundle = json.load(f)
    rpt = bundle.get("report", {})
    s = rpt.get("executive_summary", {})
    scores = rpt.get("score_breakdown", {})
    today = datetime.now().strftime("%Y-%m-%d")
    se = create_sa_engine("sqlite:///data/financial_market.db")

    pd.DataFrame([{
        "date": s.get("date", today),
        "recommendation": s.get("recommendation", "HOLD"),
        "overall_score": s.get("overall_score", 0.0),
        "confidence": s.get("confidence", 50.0),
        "market_risk": s.get("market_risk", "MEDIUM"),
        "agreement_score": s.get("agreement", 50.0),
    }]).to_sql("market_reports", con=se, if_exists="replace", index=False)

    pd.DataFrame([{
        "date": s.get("date", today),
        "technical_score": scores.get("Technical", {}).get("score", 0.0),
        "news_score": scores.get("News", {}).get("score", 0.0),
        "volume_score": scores.get("Volume", {}).get("score", 0.0),
        "economic_score": scores.get("Economic", {}).get("score", 0.0),
        "fii_score": scores.get("Institutional", {}).get("score", 0.0),
        "final_score": s.get("overall_score", 0.0),
        "signal": s.get("recommendation", "HOLD"),
        "confidence": s.get("confidence", 50.0),
        "agreement_score": s.get("agreement", 50.0),
        "reason": s.get("reason", "Seeded from bundle data — pipeline will refresh."),
    }]).to_sql("risk_scores", con=se, if_exists="replace", index=False)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "executive_summary": s,
            "score_breakdown": rpt.get("score_breakdown", {}),
            "technical_analysis": rpt.get("technical_analysis", {}),
            "news_analysis": rpt.get("news_analysis", {}),
            "volume_analysis": rpt.get("volume_analysis", {}),
            "economic_analysis": rpt.get("economic_analysis", {}),
            "institutional_analysis": rpt.get("institutional_analysis", {}),
            "data_quality": rpt.get("data_quality", {}),
        }, f, indent=2)

    print("[SEED] Initial dashboard data seeded from bundle.json")


@asynccontextmanager
async def lifespan(app):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from src.database.db_setup import metadata, engine
        metadata.create_all(engine)
        print("[STARTUP] Database tables initialized.")
    except Exception as exc:
        print(f"[WARN] Database init failed: {exc}")
    seed_from_bundle()
    try:
        start_scheduler()
    except Exception as exc:
        print(f"[WARN] Scheduler failed to start: {exc}")
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
    db_exists = (DATA_DIR / "financial_market.db").exists()
    return {
        "status": "healthy",
        "database": "ready" if db_exists else "not initialized",
    }


@app.get("/scheduler/status")
def scheduler_status():
    return get_scheduler_status()


# Mount frontend static files LAST (after all API routes)
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
