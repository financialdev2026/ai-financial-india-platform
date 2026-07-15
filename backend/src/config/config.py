"""
=========================================================
Global Configuration

Every configurable value in the project lives here.

=========================================================
"""

from pathlib import Path

# =====================================================
# PROJECT ROOT
# =====================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# =====================================================
# DATA
# =====================================================

DATA_FOLDER = PROJECT_ROOT / "data"

RAW_DATA_FOLDER = DATA_FOLDER / "raw"

PROCESSED_DATA_FOLDER = DATA_FOLDER / "processed"

REPORT_FOLDER = PROJECT_ROOT / "reports"

LOG_FOLDER = PROJECT_ROOT / "logs"

# =====================================================
# DATABASE
# =====================================================

DATABASE_URL = "sqlite:///data/financial_market.db"

DATABASE_FILE = DATA_FOLDER / "financial_market.db"

# =====================================================
# RAW DATA
# =====================================================

STOCK_DATA = RAW_DATA_FOLDER / "stocks"

SECTOR_DATA = RAW_DATA_FOLDER / "sectors"

NEWS_DATA = RAW_DATA_FOLDER / "news"

ECONOMIC_DATA = RAW_DATA_FOLDER / "economic"

FII_DII_DATA = RAW_DATA_FOLDER / "fii_dii"

# =====================================================
# PROCESSED DATA
# =====================================================

INDICATOR_DATA = PROCESSED_DATA_FOLDER / "indicators"

# =====================================================
# MODEL NAMES
# =====================================================

FINBERT_MODEL = "ProsusAI/finbert"

# =====================================================
# RISK ENGINE WEIGHTS
# =====================================================

TECHNICAL_WEIGHT = 0.40

NEWS_WEIGHT = 0.25

VOLUME_WEIGHT = 0.15

ECONOMIC_WEIGHT = 0.10

FII_WEIGHT = 0.10

# =====================================================
# SIGNAL THRESHOLDS
# =====================================================

STRONG_BUY = 0.60

BUY = 0.20

HOLD = -0.20

SELL = -0.60

# =====================================================
# REPORTING
# =====================================================

REPORT_NAME = "market_report"

JSON_REPORT = REPORT_FOLDER / "market_report.json"

CSV_REPORT = REPORT_FOLDER / "score_breakdown.csv"

PDF_REPORT = REPORT_FOLDER / "market_report.pdf"

# =====================================================
# API
# =====================================================

API_TITLE = "Foresight AI API"

API_VERSION = "1.0.0"