import json
import logging
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine

logger = logging.getLogger(__name__)

from src.config.config import DATABASE_URL
from src.utils.freshness import latest_per_group, latest_rows


router = APIRouter()
engine = create_engine(DATABASE_URL)
REPORT_PATH = Path("reports/market_report.json")


class AgentQuestion(BaseModel):
    question: str


AGENT_PROVIDER = os.getenv(
    "PRISMEDGE_AGENT_PROVIDER",
    "openai",
).lower()
AGENT_MODEL = os.getenv(
    "PRISMEDGE_AGENT_MODEL",
    "llama-3.3-70b-versatile",
)
AGENT_API_URL = os.getenv(
    "PRISMEDGE_AGENT_API_URL",
    "https://api.groq.com/openai/v1/chat/completions",
)
AGENT_API_KEY = (
    os.getenv("PRISMEDGE_AGENT_API_KEY")
    or os.getenv("GROQ_API_KEY")
    or os.getenv("OPENAI_API_KEY")
)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


def read_table(name):
    return pd.read_sql(f"SELECT * FROM {name}", engine)


def records(df):
    return json.loads(df.to_json(orient="records", date_format="iso"))


def scalar_count(table_name):
    try:
        return int(pd.read_sql(f"SELECT COUNT(*) AS count FROM {table_name}", engine)["count"].iloc[0])
    except Exception:
        return 0


def load_report():
    if REPORT_PATH.exists():
        with open(REPORT_PATH, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}


def current_payload():
    market_reports = read_table("market_reports")
    risk = read_table("risk_scores")
    technical = read_table("technical_scores")
    volume = read_table("volume_scores")
    news = read_table("news_scores")
    economic = read_table("economic_scores")
    institutional = read_table("fii_dii_scores")

    if market_reports.empty or risk.empty:
        raise HTTPException(
            status_code=404,
            detail="Run src/run_pipeline.py before requesting the dashboard.",
        )

    report = load_report()
    latest_technical = latest_per_group(
        technical,
        group_column="ticker",
        required_columns=["technical_score"],
    ).sort_values("technical_score", ascending=False)

    latest_volume = latest_per_group(
        volume,
        group_column="ticker",
        required_columns=["volume_score", "volume_ratio"],
    ).sort_values("volume_ratio", ascending=False)

    return {
        "market_reports": market_reports,
        "risk": risk,
        "technical": latest_technical,
        "volume": latest_volume,
        "news": news.sort_values("sector_rank"),
        "economic": latest_rows(economic),
        "institutional": latest_rows(institutional),
        "report": report,
    }


@router.get("/")
def get_dashboard():
    try:
        data = current_payload()
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(
            status_code=503,
            detail=f"Dashboard data is not ready: {exc}",
        ) from exc

    report = data["report"]
    summary = report.get(
        "executive_summary",
        data["market_reports"].iloc[-1].to_dict(),
    )
    latest_risk = latest_rows(data["risk"])

    return {
        "executive_summary": summary,
        "score_breakdown": report.get("score_breakdown", {}),
        "technical_scores": records(data["technical"]),
        "volume_scores": records(data["volume"]),
        "news_scores": records(data["news"]),
        "economic_scores": records(data["economic"]),
        "institutional_scores": records(data["institutional"]),
        "risk": latest_risk.iloc[-1].to_dict(),
        "analysis": {
            "technical": report.get("technical_analysis", {}),
            "news": report.get("news_analysis", {}),
            "volume": report.get("volume_analysis", {}),
            "economic": report.get("economic_analysis", {}),
            "institutional": report.get("institutional_analysis", {}),
        },
        "data_quality": report.get("data_quality", {}),
        "coverage": {
            "stocks": scalar_count("stocks"),
            "technical_scores": scalar_count("technical_scores"),
            "volume_scores": scalar_count("volume_scores"),
            "news_items": scalar_count("news"),
            "news_sentiment": scalar_count("news_sentiment"),
            "sectors": scalar_count("sectors"),
            "economic_rows": scalar_count("economic_data"),
            "institutional_rows": scalar_count("fii_dii"),
        },
    }


@router.get("/technical")
def get_technical_analysis():
    data = current_payload()
    return {
        "summary": data["report"].get("technical_analysis", {}),
        "rows": records(data["technical"]),
        "explanation": "Latest per-stock technical snapshot using current RSI, MACD, Bollinger and signal data.",
    }


@router.get("/news")
def get_news_analysis():
    data = current_payload()
    latest_news = pd.read_sql(
        """
        SELECT title, sector, sentiment, confidence, source, published_at
        FROM news_sentiment
        ORDER BY published_at DESC
        LIMIT 80
        """,
        engine,
    )
    return {
        "summary": data["report"].get("news_analysis", {}),
        "sectors": records(data["news"]),
        "rows": records(latest_news),
        "explanation": "Recency-aware news sentiment by sector. Older headlines decay before influencing the score.",
    }


@router.get("/volume")
def get_volume_analysis():
    data = current_payload()
    return {
        "summary": data["report"].get("volume_analysis", {}),
        "rows": records(data["volume"]),
        "explanation": "Latest volume participation snapshot using current volume ratio against rolling average volume.",
    }


@router.get("/economy")
def get_economic_analysis():
    data = current_payload()
    return {
        "summary": data["report"].get("economic_analysis", {}),
        "rows": records(data["economic"]),
        "explanation": "Latest macro snapshot from repo rate, GDP growth and inflation.",
    }


@router.get("/institutional")
def get_institutional_analysis():
    data = current_payload()
    return {
        "summary": data["report"].get("institutional_analysis", {}),
        "rows": records(data["institutional"]),
        "explanation": "Latest de-duplicated FII/DII institutional flow snapshot.",
    }


@router.get("/auth/roles")
def get_auth_roles():
    return {
        "roles": [
            {"name": "viewer", "level": 1, "description": "Read-only dashboard access."},
            {"name": "analyst", "level": 2, "description": "Dashboard access plus exports and simulations."},
            {"name": "admin", "level": 3, "description": "Full access including user and data-pipeline controls."},
        ],
        "firebase": "Provide frontend/firebase-config.js and Firebase custom claims to activate real authentication.",
    }


def tokenize(text):
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(text).lower())
        if len(token) > 2
    }


def is_definition_question(text):
    q = str(text).lower()
    tokens = tokenize(q)
    return (
        "what is" in q
        or "what are" in q
        or "what does" in q
        or "define" in tokens
        or "meaning" in tokens
        or "mean" in tokens
        or "means" in tokens
        or ("explain" in tokens and not ({"why", "buy", "sell"} & tokens))
    )


def agent_glossary():
    return [
        {
            "title": "Volume analysis",
            "keywords": "volume analysis volume flow define definition meaning participation liquidity average volume unusual trading",
            "text": (
                "Volume analysis studies trading participation. In PrismEdge, it compares each stock's "
                "current volume with its normal average volume to detect whether price moves are supported "
                "by real market activity. High relative volume makes a move more meaningful; weak volume "
                "makes a move less reliable."
            ),
        },
        {
            "title": "Technical analysis",
            "keywords": "technical analysis price signals define definition meaning indicators",
            "text": (
                "Technical analysis reads price-based indicators such as MACD, RSI, Bollinger position, "
                "trend, and recent price behavior. It answers whether the market's price action currently "
                "looks bullish, bearish, or neutral."
            ),
        },
        {
            "title": "RSI",
            "keywords": "rsi relative strength index overbought oversold momentum oscillator define meaning",
            "text": (
                "RSI (Relative Strength Index) measures momentum on a 0-100 scale. Values above 70 suggest "
                "a stock may be overbought (price extended to the upside); values below 30 suggest it may be "
                "oversold (price extended to the downside). PrismEdge uses RSI as one of its technical signals "
                "to gauge whether a stock's recent price move is losing steam or gaining strength."
            ),
        },
        {
            "title": "MACD",
            "keywords": "macd moving average convergence divergence trend momentum define meaning",
            "text": (
                "MACD (Moving Average Convergence Divergence) compares two moving averages to reveal trend "
                "direction and momentum. When the MACD line crosses above the signal line it suggests bullish "
                "momentum; crossing below suggests bearish momentum. PrismEdge uses MACD crossovers and "
                "histogram strength as part of its price signal scoring."
            ),
        },
        {
            "title": "Bollinger Bands",
            "keywords": "bollinger bands volatility upper lower middle standard deviation define meaning",
            "text": (
                "Bollinger Bands plot a middle moving average with upper and lower bands set at two standard "
                "deviations. Price near the upper band suggests the stock is relatively expensive; near the "
                "lower band suggests relatively cheap. Wide bands indicate high volatility; narrow bands "
                "indicate low volatility. PrismEdge uses Bollinger position to assess price stretch."
            ),
        },
        {
            "title": "News sentiment",
            "keywords": "news sentiment analysis define definition meaning articles headlines finbert positive negative neutral",
            "text": (
                "News sentiment analysis converts recent financial headlines and articles into positive, "
                "neutral, or negative evidence. PrismEdge weights this by confidence and recency so old "
                "headlines have less effect on today's view."
            ),
        },
        {
            "title": "Sector strength",
            "keywords": "sector strength analysis define definition meaning sector score board momentum news index",
            "text": (
                "Sector strength combines recent sector index momentum with news sentiment when sector news "
                "is available. It is designed to show which parts of the market are leading or lagging."
            ),
        },
        {
            "title": "Coverage",
            "keywords": "coverage mean definition rows available data quality count current records",
            "text": (
                "Coverage means how much current data the system has for a section, such as "
                "the number of stocks, sectors, articles, or institutional records included in the latest analysis."
            ),
        },
        {
            "title": "Overall score",
            "keywords": "overall score mean definition weighted combined market direction",
            "text": (
                "Overall score is the weighted blend of price signals, news sentiment, volume flow, "
                "economy, and institutional flow. Positive values support a bullish outcome; negative values "
                "support a bearish outcome."
            ),
        },
        {
            "title": "Confidence",
            "keywords": "confidence score mean definition certainty reliability conviction model confidence evidence guarantee",
            "text": (
                "Confidence estimates how strongly the available evidence supports the current recommendation. "
                "It blends signal strength, agreement between analysis engines, and data coverage quality. "
                "A higher confidence score means the output is better supported, but it is not a guarantee "
                "of future market movement."
            ),
        },
        {
            "title": "Agreement",
            "keywords": "agreement score mean definition modules engines align same direction consensus technical news volume economy institutional",
            "text": (
                "Agreement score measures how many independent analysis engines point in the same direction. "
                "For example, if technicals, news, volume, economy, and institutional flow mostly support "
                "the same view, agreement is high. If they conflict, agreement is lower and the recommendation "
                "should be treated more cautiously."
            ),
        },
        {
            "title": "Weighted contribution",
            "keywords": "weighted contribution mean definition module weight effect score",
            "text": (
                "Weighted contribution is the actual effect a module has on the final score after applying "
                "that module's importance weight."
            ),
        },
        {
            "title": "Volume ratio",
            "keywords": "volume ratio mean definition average trading activity unusual participation",
            "text": (
                "Volume ratio compares current trading volume with normal volume. A value above 1.0 means "
                "participation is higher than usual."
            ),
        },
        {
            "title": "Economy analysis",
            "keywords": "economy economic macro analysis define definition meaning repo inflation gdp",
            "text": (
                "Economy analysis checks macro conditions such as repo rate, GDP growth, and inflation. "
                "It helps decide whether the broader economic backdrop supports or pressures the market."
            ),
        },
        {
            "title": "Institutional flow",
            "keywords": "institutional flow analysis define definition meaning fii dii net buying selling",
            "text": (
                "Institutional flow tracks whether FIIs and DIIs are net buyers or sellers. Positive net "
                "flow suggests large investors are adding money; negative net flow suggests they are reducing exposure."
            ),
        },
        {
            "title": "Market risk",
            "keywords": "market risk define definition meaning safe danger confidence agreement score",
            "text": (
                "Market risk summarizes how cautious the recommendation should be. PrismEdge uses signal "
                "agreement, model confidence, and final score strength to classify risk."
            ),
        },
        {
            "title": "FII and DII",
            "keywords": "fii dii mean definition institutional foreign domestic investors",
            "text": (
                "FII means Foreign Institutional Investors and DII means Domestic Institutional Investors. "
                "Their net flow shows whether large institutions are adding or removing money from the market."
            ),
        },
        {
            "title": "Freshness",
            "keywords": "freshness stale old latest current date data quality definition",
            "text": (
                "Freshness checks whether each section is using recent data. Stale sections are reduced in "
                "impact so old data does not dominate newer insights."
            ),
        },
    ]


def build_agent_facts(dashboard):
    summary = dashboard["executive_summary"]
    scores = dashboard["score_breakdown"]
    analysis = dashboard["analysis"]
    quality = dashboard["data_quality"]
    facts = agent_glossary() + [
        {
            "title": "Current recommendation",
            "keywords": "recommendation signal score confidence agreement overall outcome market",
            "text": (
                f"Current recommendation is {summary['recommendation']} with overall score "
                f"{summary['overall_score']:.3f}, confidence {summary['confidence']:.2f}%, "
                f"agreement {summary['agreement']:.1f}%, and {summary['market_risk']} risk."
            ),
        },
        {
            "title": "Reason",
            "keywords": "why reason explain because driver drivers contribution",
            "text": f"The model reason is: {summary['reason']}.",
        },
        {
            "title": "Freshness",
            "keywords": "fresh date stale old latest current coverage rows data quality",
            "text": (
                f"Freshness: technical {quality.get('technical_date', 'n/a')}, "
                f"volume {quality.get('volume_date', 'n/a')}, news {quality.get('news_date', 'n/a')}, "
                f"economy {quality.get('economic_date', 'n/a')}, institutional {quality.get('fii_date', 'n/a')}."
            ),
        },
    ]

    module_names = {
        "Technical": "Price Signals",
        "News": "News Sentiment",
        "Volume": "Volume Flow",
        "Economic": "Economy",
        "Institutional": "Institutional Flow",
    }
    for module, values in scores.items():
        facts.append(
            {
                "title": module_names.get(module, module),
                "keywords": f"{module} {module_names.get(module, module)} score weight contribution signal module",
                "text": (
                    f"{module_names.get(module, module)} score is {values.get('score', 0):.3f}, "
                    f"weight is {values.get('weight', 0)}%, and weighted contribution is "
                    f"{values.get('contribution', 0):.3f}."
                ),
            }
        )

    tech = analysis.get("technical", {})
    facts.append(
        {
            "title": "Tracked stocks",
            "keywords": "stock stocks ticker strongest weakest best worst technical price rsi macd",
            "text": (
                f"Best current stock is {tech.get('best_stock', 'n/a')} with score "
                f"{tech.get('best_score', 0):.3f}; weakest is {tech.get('worst_stock', 'n/a')} "
                f"with score {tech.get('worst_score', 0):.3f}."
            ),
        }
    )

    news = analysis.get("news", {})
    facts.append(
        {
            "title": "News detail",
            "keywords": "news sentiment headline article articles positive neutral negative sector",
            "text": (
                f"News analysis used {news.get('article_count', 'n/a')} recent articles. "
                f"Positive: {news.get('positive_articles', 'n/a')}, neutral: "
                f"{news.get('neutral_articles', 'n/a')}, negative: {news.get('negative_articles', 'n/a')}. "
                f"Best sector is {news.get('best_sector', 'n/a')}."
            ),
        }
    )

    volume = analysis.get("volume", {})
    facts.append(
        {
            "title": "Volume detail",
            "keywords": "volume participation trading ratio highest unusual average",
            "text": (
                f"Highest volume stock is {volume.get('highest_volume_stock', 'n/a')} at "
                f"{volume.get('highest_volume_ratio', 0):.2f}x average volume. "
                f"Average volume ratio is {volume.get('average_ratio', 0):.2f}x."
            ),
        }
    )

    economy = analysis.get("economic", {})
    facts.append(
        {
            "title": "Economy detail",
            "keywords": "economy economic macro repo rate gdp growth inflation",
            "text": (
                f"Macro snapshot: repo rate {economy.get('repo_rate', 'n/a')}%, "
                f"GDP growth {economy.get('gdp_growth', 'n/a')}%, inflation "
                f"{economy.get('inflation', 'n/a')}%, signal {economy.get('signal', 'n/a')}."
            ),
        }
    )

    inst = analysis.get("institutional", {})
    facts.append(
        {
            "title": "Institutional detail",
            "keywords": "institutional fii dii fund flow buying selling net",
            "text": (
                f"Institutional net flow is Rs {inst.get('net_flow', 0):.2f} cr. "
                f"Buyers: {inst.get('buyers', 'n/a')}, sellers: {inst.get('sellers', 'n/a')}."
            ),
        }
    )

    for row in dashboard.get("technical_scores", [])[:10]:
        facts.append(
            {
                "title": f"Stock {row.get('ticker')}",
                "keywords": f"{row.get('ticker')} stock ticker technical price signal confidence",
                "text": (
                    f"{row.get('ticker')} has technical score {row.get('technical_score')}, "
                    f"signal {row.get('signal')}, confidence {row.get('confidence')}%, "
                    f"reason: {row.get('reason')}."
                ),
            }
        )

    for row in dashboard.get("news_scores", [])[:8]:
        facts.append(
            {
                "title": f"Sector {row.get('sector')}",
                "keywords": f"{row.get('sector')} sector news sentiment score articles",
                "text": (
                    f"{row.get('sector')} news score is {row.get('news_score')}, "
                    f"signal {row.get('signal')}, confidence {row.get('confidence')}%, "
                    f"reason: {row.get('reason')}."
                ),
            }
        )

    return facts


def retrieve_facts(question, facts, limit=3):
    question_tokens = tokenize(question)
    if not question_tokens:
        return facts[:limit]

    ranked = []
    for fact in facts:
        haystack = f"{fact['title']} {fact.get('keywords', '')} {fact['text']}"
        tokens = tokenize(haystack)
        overlap = len(question_tokens & tokens)
        substring_bonus = sum(1 for token in question_tokens if token in haystack.lower())
        score = overlap * 3 + substring_bonus
        ranked.append((score, fact))

    ranked = sorted(ranked, key=lambda item: item[0], reverse=True)
    selected = [fact for score, fact in ranked if score > 0][:limit]
    return selected or facts[:limit]


def agent_context(dashboard):
    summary = dashboard["executive_summary"]
    facts = build_agent_facts(dashboard)
    context_lines = [
        "PrismEdge AI current dashboard context:",
        (
            f"Recommendation: {summary.get('recommendation')}; score: "
            f"{summary.get('overall_score')}; confidence: {summary.get('confidence')}%; "
            f"agreement: {summary.get('agreement')}%; risk: {summary.get('market_risk')}."
        ),
        f"Reason: {summary.get('reason')}.",
    ]
    context_lines.extend(f"- {fact['title']}: {fact['text']}" for fact in facts[:18])
    return "\n".join(context_lines)


def agent_system_prompt():
    return (
        "You are PrismEdge Agent, a clear, careful assistant inside an Indian market "
        "intelligence product. Answer any user question helpfully. When the question is "
        "about markets, PrismEdge data, stocks, sectors, scores, or the dashboard, ground "
        "the answer in the provided context. Do not pretend to be a SEBI-registered adviser, "
        "do not give personalized investment advice, and do not guarantee outcomes. If the "
        "question is unrelated to finance, answer normally and concisely."
    )


def ask_openai_agent(question, dashboard):
    payload = {
        "model": AGENT_MODEL,
        "temperature": 0.35,
        "messages": [
            {"role": "system", "content": agent_system_prompt()},
            {"role": "system", "content": agent_context(dashboard)},
            {"role": "user", "content": question},
        ],
    }
    request = urllib.request.Request(
        AGENT_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {AGENT_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "PrismEdge/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=18) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, TimeoutError, urllib.error.URLError, urllib.error.HTTPError, ValueError):
        return ""


def ask_gemini_agent(question, dashboard):
    if not AGENT_API_KEY:
        logger.warning("No Gemini API key configured.")
        return ""
    primary = AGENT_MODEL or "gemini-2.0-flash"
    fallbacks = [
        m for m in [
            primary,
            "gemini-2.0-flash",
            "gemini-2.0-flash-001",
            "gemini-2.5-flash",
            "gemini-3.5-flash",
            "gemini-flash-latest",
        ]
        if m != primary
    ] + [primary]
    seen = set()
    models_to_try = []
    for m in [primary] + fallbacks:
        if m not in seen:
            seen.add(m)
            models_to_try.append(m)

    for model in models_to_try:
        api_url = os.getenv(
            "PRISMEDGE_GEMINI_API_URL",
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        )
        separator = "&" if "?" in api_url else "?"
        url = f"{api_url}{separator}key={AGENT_API_KEY}"
        payload = {
            "systemInstruction": {
                "parts": [{"text": f"{agent_system_prompt()}\n\n{agent_context(dashboard)}"}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": question}],
                }
            ],
            "generationConfig": {
                "temperature": 0.35,
                "maxOutputTokens": 900,
            },
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=18) as response:
                data = json.loads(response.read().decode("utf-8"))
            parts = data["candidates"][0]["content"]["parts"]
            result = "\n".join(part.get("text", "") for part in parts).strip()
            if result:
                return result
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            logger.warning("Gemini %s HTTP %s: %s", model, exc.code, body[:300])
            continue
        except (KeyError, TimeoutError, urllib.error.URLError, ValueError) as exc:
            logger.warning("Gemini %s error: %s", model, exc)
            continue
    return ""


def ask_llm_agent(question, dashboard):
    if AGENT_API_KEY:
        result = ask_openai_agent(question, dashboard)
        if result:
            return result
    if GEMINI_API_KEY:
        return ask_gemini_agent(question, dashboard)
    return ""


def answer_from_report(question, dashboard):
    q = question.lower()
    q_tokens = tokenize(question)
    summary = dashboard["executive_summary"]
    scores = dashboard["score_breakdown"]
    analysis = dashboard["analysis"]
    quality = dashboard["data_quality"]

    if q_tokens & {"who", "identity", "yourself"} and q_tokens & {"you", "are", "agent"}:
        return (
            "I am PrismEdge Agent, the assistant inside PrismEdge AI. I can explain the dashboard, "
            "market scores, confidence, agreement, data freshness, stocks, sectors, and risk reasoning. "
            "When an AI provider is configured, I can also answer broader general questions."
        )

    tech = analysis.get("technical", {})
    volume = analysis.get("volume", {})
    news = analysis.get("news", {})
    economy = analysis.get("economic", {})
    inst = analysis.get("institutional", {})

    if q_tokens & {"rsi", "overbought", "oversold"}:
        facts = retrieve_facts(question, agent_glossary(), limit=1)
        definition = " ".join(fact["text"] for fact in facts) if facts else ""
        return (
            f"{definition} "
            f"Current technical signal score is {scores.get('Technical', {}).get('score', 0):.3f}. "
            f"Best stock by price signals is {tech.get('best_stock', 'n/a')} and weakest is {tech.get('worst_stock', 'n/a')}. "
            f"Signal reason: {tech.get('best_reason', 'n/a')}."
        )

    if q_tokens & {"macd", "convergence", "divergence"}:
        facts = retrieve_facts(question, agent_glossary(), limit=1)
        definition = " ".join(fact["text"] for fact in facts) if facts else ""
        return (
            f"{definition} "
            f"Current technical signal score is {scores.get('Technical', {}).get('score', 0):.3f}. "
            f"Best stock is {tech.get('best_stock', 'n/a')}, signal: {tech.get('best_reason', 'n/a')}."
        )

    if q_tokens & {"bollinger", "bands", "volatility"}:
        facts = retrieve_facts(question, agent_glossary(), limit=1)
        definition = " ".join(fact["text"] for fact in facts) if facts else ""
        return (
            f"{definition} "
            f"Current technical signal score is {scores.get('Technical', {}).get('score', 0):.3f}. "
            f"Best stock is {tech.get('best_stock', 'n/a')}, weakest is {tech.get('worst_stock', 'n/a')}."
        )

    if is_definition_question(question):
        facts = retrieve_facts(question, agent_glossary(), limit=1)
        answer = " ".join(fact["text"] for fact in facts)
        if q_tokens & {"volume", "participation", "liquidity"}:
            answer += (
                f" Current Volume Flow score is {scores.get('Volume', {}).get('score', 0):.3f}; "
                f"the strongest current volume signal is {volume.get('highest_volume_stock', 'n/a')} "
                f"at {volume.get('highest_volume_ratio', 0):.2f}x average volume."
            )
        return answer

    if any(word in q for word in ["why", "reason", "explain", "outcome"]):
        return (
            f"The model says {summary['recommendation']} because {summary['reason']}. "
            f"The overall score is {summary['overall_score']:.3f}, confidence is "
            f"{summary['confidence']:.2f}%, and agreement is {summary['agreement']:.1f}%."
        )

    if any(word in q for word in ["risk", "safe", "danger"]):
        return (
            f"Market risk is {summary['market_risk']}. This is based on score strength, "
            f"module agreement, and confidence. Current confidence is {summary['confidence']:.2f}%."
        )

    if any(word in q for word in ["technical", "price", "stock", "rsi", "macd"]):
        tech = analysis.get("technical", {})
        return (
            f"Price Signals are {scores.get('Technical', {}).get('score', 0):.3f}. "
            f"The best current stock is {tech.get('best_stock', 'n/a')} and the weakest is "
            f"{tech.get('worst_stock', 'n/a')}. Data is as of {quality.get('technical_date', 'n/a')}."
        )

    if any(word in q for word in ["news", "sentiment", "headline"]):
        news = analysis.get("news", {})
        return (
            f"News Sentiment score is {scores.get('News', {}).get('score', 0):.3f}. "
            f"It used {news.get('article_count', 'n/a')} recent articles across "
            f"{news.get('scored_sectors', 'n/a')} scored sectors. Latest news date: "
            f"{quality.get('news_date', 'n/a')}."
        )

    if any(word in q for word in ["volume", "participation"]):
        volume = analysis.get("volume", {})
        return (
            f"Volume Flow score is {scores.get('Volume', {}).get('score', 0):.3f}. "
            f"The highest volume stock is {volume.get('highest_volume_stock', 'n/a')} at "
            f"{volume.get('highest_volume_ratio', 0):.2f}x average volume."
        )

    if any(word in q for word in ["economy", "economic", "repo", "inflation", "gdp"]):
        economy = analysis.get("economic", {})
        return (
            f"Economy score is {scores.get('Economic', {}).get('score', 0):.3f}. "
            f"Repo rate is {economy.get('repo_rate', 'n/a')}%, GDP growth is "
            f"{economy.get('gdp_growth', 'n/a')}%, and inflation is "
            f"{economy.get('inflation', 'n/a')}%."
        )

    if any(word in q for word in ["institutional", "fii", "dii", "flow"]):
        inst = analysis.get("institutional", {})
        return (
            f"Institutional Flow score is {scores.get('Institutional', {}).get('score', 0):.3f}. "
            f"Latest net flow is Rs {inst.get('net_flow', 0):.2f} cr as of "
            f"{quality.get('fii_date', 'n/a')}."
        )

    if any(word in q for word in ["fresh", "date", "old", "stale", "coverage"]):
        return (
            "Freshness check: "
            f"technical {quality.get('technical_date', 'n/a')}, "
            f"volume {quality.get('volume_date', 'n/a')}, "
            f"news {quality.get('news_date', 'n/a')}, "
            f"economy {quality.get('economic_date', 'n/a')}, "
            f"institutional {quality.get('fii_date', 'n/a')}."
        )

    facts = retrieve_facts(question, build_agent_facts(dashboard))
    answer = " ".join(fact["text"] for fact in facts)
    return (
        f"{answer} "
        f"Bottom line: current output is {summary['recommendation']} with score "
        f"{summary['overall_score']:.3f} and {summary['market_risk']} risk."
    )


@router.post("/agent")
def ask_outcome_agent(payload: AgentQuestion):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    dashboard = get_dashboard()
    llm_answer = ask_llm_agent(question, dashboard)
    fallback_answer = answer_from_report(question, dashboard)
    source = "PrismEdge LLM agent plus current dashboard snapshot"
    if llm_answer:
        answer = llm_answer
    else:
        answer = fallback_answer
        source = "PrismEdge AI backend report and current dashboard snapshot"
    return {
        "question": question,
        "answer": answer,
        "source": source,
        "llm_used": bool(llm_answer),
    }
