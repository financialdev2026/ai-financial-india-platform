import os
import json
import time
import requests

GROQ_KEY = (
    os.getenv("PRISMEDGE_AGENT_API_KEY")
    or os.getenv("GROQ_API_KEY")
)
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("PRISMEDGE_AGENT_MODEL", "llama-3.3-70b-versatile")


def analyze_sentiment(text: str) -> dict:
    if not GROQ_KEY:
        return _keyword_fallback(text)

    prompt = (
        "You are a financial sentiment classifier. "
        "Classify the following headline as POSITIVE, NEGATIVE, or NEUTRAL.\n"
        "Return ONLY a JSON object with keys: label (positive/negative/neutral), "
        "score (0.0 to 1.0 confidence). No explanation.\n\n"
        f"Headline: {text}"
    )

    try:
        resp = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {GROQ_KEY}",
                "Content-Type": "application/json",
                "User-Agent": "PrismEdge/1.0",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "max_tokens": 60,
            },
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        result = json.loads(raw)
        label = result["label"].lower().strip()
        score = float(result["score"])

        if label not in ("positive", "negative", "neutral"):
            raise ValueError(f"Unexpected label: {label}")

        return {"label": label, "score": max(0.0, min(1.0, score))}

    except Exception as exc:
        print(f"[WARN] Groq sentiment failed ({exc}), using keyword fallback")
        return _keyword_fallback(text)


def analyze_sentiment_batch(texts: list[str]) -> list[dict]:
    if not texts:
        return []
    if not GROQ_KEY:
        return [_keyword_fallback(t) for t in texts]

    BATCH_SIZE = 30
    all_results = []

    for batch_start in range(0, len(texts), BATCH_SIZE):
        batch = texts[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(texts) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  Batch {batch_num}/{total_batches} ({len(batch)} articles)...")

        result = _call_groq_batch_with_retry(batch)
        all_results.extend(result)

        if batch_start + BATCH_SIZE < len(texts):
            time.sleep(2)

    return all_results


def _call_groq_batch_with_retry(texts, max_retries=3):
    for attempt in range(max_retries):
        try:
            return _call_groq_batch(texts)
        except Exception as exc:
            wait = 4 * (2 ** attempt)
            if attempt < max_retries - 1:
                print(f"  Retry {attempt+1}/{max_retries} in {wait}s ({exc})")
                time.sleep(wait)
            else:
                print(f"  All retries exhausted, using keyword fallback")
                return [_keyword_fallback(t) for t in texts]


def _call_groq_batch(texts: list[str]) -> list[dict]:
    numbered = "\n".join(
        f"{i+1}. {t[:200]}" for i, t in enumerate(texts)
    )
    prompt = (
        "You are a financial sentiment classifier for Indian markets.\n"
        "Classify each headline below as POSITIVE, NEGATIVE, or NEUTRAL.\n"
        "Return a JSON array with one object per headline, in the same order.\n"
        "Each object must have keys: label (positive/negative/neutral), "
        "score (0.0 to 1.0 confidence).\n"
        "Return ONLY the JSON array, no explanation.\n\n"
        f"{numbered}"
    )

    resp = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "PrismEdge/1.0",
        },
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 80 * len(texts),
        },
        timeout=30,
    )
    resp.raise_for_status()
    raw = resp.json()["choices"][0]["message"]["content"].strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    results = json.loads(raw)

    if isinstance(results, dict):
        results = list(results.values())
    if not isinstance(results, list):
        raise ValueError(f"Unexpected response type: {type(results)}")

    cleaned = []
    for r in results:
        label = r.get("label", "neutral").lower().strip()
        score = float(r.get("score", 0.5))
        if label not in ("positive", "negative", "neutral"):
            label = "neutral"
        cleaned.append({
            "label": label,
            "score": max(0.0, min(1.0, score)),
        })

    while len(cleaned) < len(texts):
        cleaned.append({"label": "neutral", "score": 0.5})

    return cleaned[:len(texts)]


def _keyword_fallback(text: str) -> dict:
    positive_words = {
        "surge", "rally", "gain", "profit", "growth", "rise", "jump",
        "bullish", "strong", "beat", "record", "upgrade", "boom",
        "positive", "outperform", "recovery", "soar", "boost",
    }
    negative_words = {
        "crash", "fall", "drop", "loss", "decline", "slump", "bearish",
        "weak", "miss", "cut", "downgrade", "recession", "inflation",
        "negative", "underperform", "crisis", "plunge", "fear", "risk",
    }
    words = set(text.lower().split())
    pos = len(words & positive_words)
    neg = len(words & negative_words)
    total = pos + neg

    if total == 0:
        return {"label": "neutral", "score": 0.5}
    if pos > neg:
        return {"label": "positive", "score": round(0.6 + 0.4 * pos / total, 2)}
    if neg > pos:
        return {"label": "negative", "score": round(0.6 + 0.4 * neg / total, 2)}
    return {"label": "neutral", "score": 0.5}


if __name__ == "__main__":
    samples = [
        "Reliance Industries reports strong quarterly earnings.",
        "Sensex crashes 800 points amid global sell-off.",
        "RBI holds rates steady at 6.5%.",
    ]
    print("--- Single ---")
    for s in samples:
        print(f"{s} -> {analyze_sentiment(s)}")
    print("\n--- Batch ---")
    results = analyze_sentiment_batch(samples)
    for s, r in zip(samples, results):
        print(f"{s} -> {r}")
