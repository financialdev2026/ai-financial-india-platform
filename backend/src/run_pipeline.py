import subprocess
import sys
import os


SCRIPTS = [

    # =====================================================
    # DATABASE
    # =====================================================

    "src/database/db_setup.py",

    # =====================================================
    # WEEK 1 - DATA COLLECTION
    # =====================================================

    "src/data_fetching/stock_fetcher.py",
    "src/data_fetching/sector_fetcher.py",
    "src/data_fetching/news_fetcher.py",
    "src/data_fetching/rss_news_fetcher.py",
    "src/data_fetching/news_merger.py",
    "src/data_fetching/economic_fetcher.py",
    "src/data_fetching/fii_dii_fetcher.py",
    "src/data_fetching/technical_fetcher.py",

    # =====================================================
    # DATABASE LOADERS
    # =====================================================

    "src/database/load_stocks.py",
    "src/database/load_sectors.py",
    "src/database/load_news.py",
    "src/database/load_economic.py",
    "src/database/load_fii_dii.py",
    "src/database/load_indicators.py",

    # =====================================================
    # WEEK 2 - NLP
    # =====================================================

    "src/nlp/news_sentiment_pipeline.py",

    # If sector mapping becomes a standalone script
    # uncomment this.

    # "src/nlp/sector_mapping.py",

    # =====================================================
    # WEEK 3 - RISK ANALYSIS
    # =====================================================

    "src/risk_analysis/technical_score.py",

    "src/risk_analysis/volume_analysis.py",

    "src/risk_analysis/economic_score.py",

    "src/risk_analysis/fii_dii_score.py",

    "src/risk_analysis/news_score.py",

    "src/risk_analysis/risk_engine.py",

    "src/reporting/market_report.py"

]


def run_script(script):

    print("\n" + "=" * 70)

    print(f"Running: {script}")

    print("=" * 70)

    env = os.environ.copy()
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env["PYTHONPATH"] = backend_dir + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        [sys.executable, script],
        env=env,
    )

    if result.returncode != 0:

        raise RuntimeError(
            f"\nPipeline Failed\n\n{script}"
        )


def main():

    print("\n")
    print("=" * 70)
    print("        FORSIGHT AI MASTER PIPELINE")
    print("=" * 70)

    for script in SCRIPTS:

        run_script(script)

    print("\n")
    print("=" * 70)
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":

    main()