"""
PrismEdge AI Smart Data Scheduler.

Refreshes each data source at its optimal interval based on when
the data actually changes in the real world. Uses APScheduler
running inside the FastAPI process.

Refresh Schedule (all times IST):
  - Stocks + Sectors:     Daily 4:00 PM (after NSE 3:30 PM close + 30min settle)
  - Technical Indicators: Daily 4:15 PM (derives from stocks, needs stock fetch first)
  - Volume Analysis:      Daily 4:15 PM (derives from stocks)
  - News (API + RSS):     Every 2 hours, 8 AM - 8 PM IST (most time-sensitive)
  - News NLP + Score:     Every 2 hours, 8 AM - 10 PM IST (cascades from news fetch)
  - FII/DII:              Daily 7:00 PM (NSE publishes ~6:30 PM)
  - Economic Data:        Weekly Monday 8:00 AM (macro data changes slowly)
  - Risk Engine + Report:  Every 2 hours, cascading (after scores refresh)
"""

import logging
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone, timedelta
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

DATABASE_URL = "sqlite:///data/financial_market.db"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def now_ist():
    return datetime.now(IST)


def is_market_hours():
    """Check if current IST time is within NSE trading hours (9:15 AM - 3:30 PM)."""
    t = now_ist()
    return t.weekday() < 5 and t.hour >= 9 and t.hour < 16


def is_news_window():
    """Check if current IST time is within news refresh window (8 AM - 8 PM)."""
    t = now_ist()
    return t.weekday() < 5 and 8 <= t.hour <= 20


def run_script(script_path):
    """Run a pipeline script as a subprocess. Returns (success, output)."""
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            logger.error("Script failed: %s\n%s", script_path, result.stderr[-500:] if result.stderr else "")
            return False, result.stderr
        return True, result.stdout
    except subprocess.TimeoutExpired:
        logger.error("Script timed out: %s", script_path)
        return False, "timeout"
    except Exception as exc:
        logger.error("Script error: %s - %s", script_path, exc)
        return False, str(exc)


def record_freshness(job_name, status="ok", error=""):
    """Record when a job last ran in the freshness table."""
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS scheduler_freshness (
                    job_name TEXT PRIMARY KEY,
                    last_run TEXT,
                    last_status TEXT,
                    last_error TEXT,
                    run_count INTEGER DEFAULT 0
                )
            """))
            conn.execute(text("""
                INSERT INTO scheduler_freshness (job_name, last_run, last_status, last_error, run_count)
                VALUES (:job, :ts, :status, :error, 1)
                ON CONFLICT(job_name) DO UPDATE SET
                    last_run = excluded.last_run,
                    last_status = excluded.last_status,
                    last_error = excluded.last_error,
                    run_count = scheduler_freshness.run_count + 1
            """), {
                "job": job_name,
                "ts": now_ist().isoformat(),
                "status": status,
                "error": error[:500] if error else "",
            })
            conn.commit()
    except Exception as exc:
        logger.warning("Could not record freshness for %s: %s", job_name, exc)


# ============================================================
# JOB FUNCTIONS - Each runs a specific pipeline stage
# ============================================================

def job_fetch_stocks():
    """Fetch stock + sector data from Yahoo Finance. Runs daily after market close."""
    logger.info("[SCHEDULER] Fetching stocks and sectors...")
    t0 = time.time()

    ok1, out1 = run_script("src/data_fetching/stock_fetcher.py")
    ok2, out2 = run_script("src/data_fetching/sector_fetcher.py")

    if ok1 and ok2:
        # Load into DB
        run_script("src/database/load_stocks.py")
        run_script("src/database/load_sectors.py")
        record_freshness("stocks")
        record_freshness("sectors")
        logger.info("[SCHEDULER] Stocks + sectors fetched in %.1fs", time.time() - t0)
    else:
        err = out1 if not ok1 else out2
        record_freshness("stocks", "error", err)
        record_freshness("sectors", "error", err)
        logger.error("[SCHEDULER] Stock/sector fetch failed: %s", err[:200])


def job_compute_indicators():
    """Compute technical indicators from stock data. Runs after stock fetch."""
    logger.info("[SCHEDULER] Computing technical indicators...")
    t0 = time.time()

    ok, out = run_script("src/data_fetching/technical_fetcher.py")
    if ok:
        run_script("src/database/load_indicators.py")
        record_freshness("indicators")
        logger.info("[SCHEDULER] Indicators computed in %.1fs", time.time() - t0)
    else:
        record_freshness("indicators", "error", out)
        logger.error("[SCHEDULER] Indicator computation failed: %s", out[:200])


def job_fetch_news():
    """Fetch news from Marketaux API + RSS feeds. Runs every 2 hours during business hours."""
    if not is_news_window():
        logger.info("[SCHEDULER] Outside news window, skipping.")
        return

    logger.info("[SCHEDULER] Fetching news...")
    t0 = time.time()

    ok1, out1 = run_script("src/data_fetching/news_fetcher.py")
    ok2, out2 = run_script("src/data_fetching/rss_news_fetcher.py")

    if ok1 or ok2:
        run_script("src/data_fetching/news_merger.py")
        run_script("src/database/load_news.py")
        record_freshness("news")
        logger.info("[SCHEDULER] News fetched in %.1fs", time.time() - t0)
    else:
        record_freshness("news", "error", f"Marketaux: {out1[:200]} | RSS: {out2[:200]}")
        logger.error("[SCHEDULER] News fetch failed")


def job_fetch_fii_dii():
    """Fetch FII/DII institutional flows from NSE. Runs daily after market close."""
    logger.info("[SCHEDULER] Fetching FII/DII data...")
    t0 = time.time()

    ok, out = run_script("src/data_fetching/fii_dii_fetcher.py")
    if ok:
        run_script("src/database/load_fii_dii.py")
        record_freshness("fii_dii")
        logger.info("[SCHEDULER] FII/DII fetched in %.1fs", time.time() - t0)
    else:
        record_freshness("fii_dii", "error", out)
        logger.error("[SCHEDULER] FII/DII fetch failed: %s", out[:200])


def job_fetch_economic():
    """Fetch economic data (currently hardcoded). Runs weekly."""
    logger.info("[SCHEDULER] Fetching economic data...")
    t0 = time.time()

    ok, out = run_script("src/data_fetching/economic_fetcher.py")
    if ok:
        run_script("src/database/load_economic.py")
        record_freshness("economic")
        logger.info("[SCHEDULER] Economic data fetched in %.1fs", time.time() - t0)
    else:
        record_freshness("economic", "error", out)
        logger.error("[SCHEDULER] Economic fetch failed: %s", out[:200])


def job_run_nlp():
    """Run FinBERT sentiment on news. Runs every 2 hours after news fetch."""
    if not is_news_window():
        return

    logger.info("[SCHEDULER] Running news NLP pipeline...")
    t0 = time.time()

    ok, out = run_script("src/nlp/news_sentiment_pipeline.py")
    if ok:
        record_freshness("nlp")
        logger.info("[SCHEDULER] NLP completed in %.1fs", time.time() - t0)
    else:
        record_freshness("nlp", "error", out)
        logger.error("[SCHEDULER] NLP failed: %s", out[:200])


def job_score_technical():
    """Score technical indicators. Runs after indicators are computed."""
    logger.info("[SCHEDULER] Scoring technical data...")
    t0 = time.time()
    ok, out = run_script("src/risk_analysis/technical_score.py")
    if ok:
        record_freshness("score_technical")
        logger.info("[SCHEDULER] Technical scoring done in %.1fs", time.time() - t0)
    else:
        record_freshness("score_technical", "error", out)
        logger.error("[SCHEDULER] Technical scoring failed: %s", out[:200])


def job_score_volume():
    """Score volume analysis. Runs after stocks are loaded."""
    logger.info("[SCHEDULER] Scoring volume data...")
    t0 = time.time()
    ok, out = run_script("src/risk_analysis/volume_analysis.py")
    if ok:
        record_freshness("score_volume")
        logger.info("[SCHEDULER] Volume scoring done in %.1fs", time.time() - t0)
    else:
        record_freshness("score_volume", "error", out)
        logger.error("[SCHEDULER] Volume scoring failed: %s", out[:200])


def job_score_economic():
    """Score economic indicators. Runs weekly or after economic fetch."""
    logger.info("[SCHEDULER] Scoring economic data...")
    t0 = time.time()
    ok, out = run_script("src/risk_analysis/economic_score.py")
    if ok:
        record_freshness("score_economic")
        logger.info("[SCHEDULER] Economic scoring done in %.1fs", time.time() - t0)
    else:
        record_freshness("score_economic", "error", out)
        logger.error("[SCHEDULER] Economic scoring failed: %s", out[:200])


def job_score_fii_dii():
    """Score FII/DII flows. Runs after FII/DII fetch."""
    logger.info("[SCHEDULER] Scoring FII/DII data...")
    t0 = time.time()
    ok, out = run_script("src/risk_analysis/fii_dii_score.py")
    if ok:
        record_freshness("score_fii_dii")
        logger.info("[SCHEDULER] FII/DII scoring done in %.1fs", time.time() - t0)
    else:
        record_freshness("score_fii_dii", "error", out)
        logger.error("[SCHEDULER] FII/DII scoring failed: %s", out[:200])


def job_score_news():
    """Score news sentiment. Runs after NLP completes."""
    logger.info("[SCHEDULER] Scoring news sentiment...")
    t0 = time.time()
    ok, out = run_script("src/risk_analysis/news_score.py")
    if ok:
        record_freshness("score_news")
        logger.info("[SCHEDULER] News scoring done in %.1fs", time.time() - t0)
    else:
        record_freshness("score_news", "error", out)
        logger.error("[SCHEDULER] News scoring failed: %s", out[:200])


def job_run_risk_engine():
    """Run the risk engine + generate report. Runs after all scores are fresh."""
    logger.info("[SCHEDULER] Running risk engine...")
    t0 = time.time()
    ok1, out1 = run_script("src/risk_analysis/risk_engine.py")
    ok2, out2 = run_script("src/reporting/market_report.py")
    if ok1 and ok2:
        record_freshness("risk_engine")
        record_freshness("report")
        logger.info("[SCHEDULER] Risk engine + report done in %.1fs", time.time() - t0)
    else:
        err = out1 if not ok1 else out2
        record_freshness("risk_engine", "error", err)
        logger.error("[SCHEDULER] Risk engine failed: %s", err[:200])


# ============================================================
# COMPOSITE JOBS - Chain dependent steps
# ============================================================

def job_market_close_refresh():
    """Full post-market refresh: stocks -> indicators -> scores -> risk -> report.
    Runs daily at 4:15 PM IST (after stock fetch at 4:00 PM)."""
    logger.info("[SCHEDULER] === Post-market full refresh starting ===")
    t0 = time.time()

    # Step 1: Indicators (stocks should already be fetched by 4:00 PM job)
    job_compute_indicators()

    # Step 2: All scores in parallel-ish (they're independent)
    job_score_technical()
    job_score_volume()
    job_score_economic()

    # Step 3: Risk engine + report
    job_run_risk_engine()

    logger.info("[SCHEDULER] === Post-market refresh done in %.1fs ===", time.time() - t0)


def job_fii_dii_refresh():
    """FII/DII post-market refresh: fetch -> score -> risk -> report.
    Runs daily at 7:15 PM IST (after NSE publishes at ~6:30 PM)."""
    logger.info("[SCHEDULER] === FII/DII refresh starting ===")
    t0 = time.time()

    job_fetch_fii_dii()
    job_score_fii_dii()
    job_run_risk_engine()

    logger.info("[SCHEDULER] === FII/DII refresh done in %.1fs ===", time.time() - t0)


def job_news_cycle():
    """News refresh cycle: fetch -> NLP -> score -> risk -> report.
    Runs every 2 hours during business hours."""
    if not is_news_window():
        return

    logger.info("[SCHEDULER] === News cycle starting ===")
    t0 = time.time()

    job_fetch_news()
    job_run_nlp()
    job_score_news()
    job_run_risk_engine()

    logger.info("[SCHEDULER] === News cycle done in %.1fs ===", time.time() - t0)


def job_initial_startup():
    """Run a lightweight pipeline on server startup. Skips NLP to avoid OOM."""
    logger.info("[SCHEDULER] Checking if startup refresh is needed...")
    t0 = time.time()

    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS scheduler_freshness (
                    job_name TEXT PRIMARY KEY,
                    last_run TEXT,
                    last_status TEXT,
                    last_error TEXT,
                    run_count INTEGER DEFAULT 0
                )
            """))
            result = conn.execute(text(
                "SELECT last_run FROM scheduler_freshness WHERE job_name = 'risk_engine'"
            ))
            row = result.fetchone()

        if row and row[0]:
            last_run = datetime.fromisoformat(row[0])
            age_hours = (now_ist() - last_run).total_seconds() / 3600
            if age_hours < 4:
                logger.info("[SCHEDULER] Data is %.1f hours old, skipping startup refresh.", age_hours)
                return
            logger.info("[SCHEDULER] Data is %.1f hours old, running startup refresh.", age_hours)
        else:
            logger.info("[SCHEDULER] No freshness record found, running startup refresh.")

        job_fetch_stocks()
        job_compute_indicators()
        job_fetch_news()
        job_fetch_fii_dii()
        job_fetch_economic()

        job_score_technical()
        job_score_volume()
        job_score_economic()
        job_score_fii_dii()
        job_score_news()

        job_run_risk_engine()
    except Exception as exc:
        logger.error("[SCHEDULER] Startup refresh error: %s", exc)

    logger.info("[SCHEDULER] === Startup refresh done in %.1fs ===", time.time() - t0)


# ============================================================
# SCHEDULER SETUP
# ============================================================

scheduler = BackgroundScheduler(timezone="Asia/Kolkata")


def setup_scheduler():
    """Configure all scheduled jobs with optimal intervals."""

    # --- DAILY JOBS (market hours dependent) ---

    # Stocks + sectors: Daily 4:00 PM IST (after NSE close)
    scheduler.add_job(
        job_fetch_stocks,
        CronTrigger(hour=16, minute=0, day_of_week="mon-fri", timezone="Asia/Kolkata"),
        id="fetch_stocks",
        name="Fetch Stocks & Sectors",
        replace_existing=True,
    )

    # Full post-market refresh: Daily 4:15 PM IST
    scheduler.add_job(
        job_market_close_refresh,
        CronTrigger(hour=16, minute=15, day_of_week="mon-fri", timezone="Asia/Kolkata"),
        id="market_close_refresh",
        name="Post-Market Full Refresh",
        replace_existing=True,
    )

    # FII/DII: Daily 7:15 PM IST (after NSE publishes)
    scheduler.add_job(
        job_fii_dii_refresh,
        CronTrigger(hour=19, minute=15, day_of_week="mon-fri", timezone="Asia/Kolkata"),
        id="fii_dii_refresh",
        name="FII/DII Post-Market Refresh",
        replace_existing=True,
    )

    # Economic: Weekly Monday 8:00 AM IST
    scheduler.add_job(
        job_fetch_economic,
        CronTrigger(hour=8, minute=0, day_of_week="mon", timezone="Asia/Kolkata"),
        id="fetch_economic",
        name="Weekly Economic Data",
        replace_existing=True,
    )

    # --- RECURRING JOBS (interval-based) ---

    # News cycle: Every 2 hours, 8 AM - 8 PM IST
    scheduler.add_job(
        job_news_cycle,
        IntervalTrigger(hours=2),
        id="news_cycle",
        name="News Fetch + NLP + Score",
        replace_existing=True,
    )

    # --- JOBS THAT RUN ON DEMAND OR AS PART OF COMPOSITE ---

    # The following are called by composite jobs above, not scheduled independently:
    # - job_compute_indicators (called by market_close_refresh)
    # - job_run_nlp (called by news_cycle)
    # - job_score_* (called by composite jobs)
    # - job_run_risk_engine (called by composite jobs)

    logger.info("[SCHEDULER] All jobs configured.")


def get_scheduler_status():
    """Return current scheduler state for the API endpoint."""
    jobs = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": next_run.isoformat() if next_run else None,
            "trigger": str(job.trigger),
        })

    # Load freshness data
    freshness = []
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            # Ensure table exists
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS scheduler_freshness (
                    job_name TEXT PRIMARY KEY,
                    last_run TEXT,
                    last_status TEXT,
                    last_error TEXT,
                    run_count INTEGER DEFAULT 0
                )
            """))
            result = conn.execute(text("SELECT * FROM scheduler_freshness ORDER BY job_name"))
            for row in result:
                freshness.append({
                    "job": row[0],
                    "last_run": row[1],
                    "status": row[2],
                    "error": row[3] or "",
                    "run_count": row[4],
                })
    except Exception as exc:
        logger.warning("Could not read freshness: %s", exc)

    return {
        "scheduler_running": scheduler.running,
        "current_time_ist": now_ist().isoformat(),
        "is_market_hours": is_market_hours(),
        "jobs": jobs,
        "freshness": freshness,
    }


def start_scheduler():
    """Start the scheduler. Called from FastAPI lifespan."""
    setup_scheduler()
    scheduler.start()
    logger.info("[SCHEDULER] Started with %d jobs", len(scheduler.get_jobs()))

    # Run initial startup refresh in a background thread
    import threading
    thread = threading.Thread(target=job_initial_startup, daemon=True)
    thread.start()


def stop_scheduler():
    """Stop the scheduler. Called from FastAPI lifespan."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[SCHEDULER] Shutdown complete.")
