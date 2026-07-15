_classifier = None
_load_error = None


def _get_classifier():
    global _classifier, _load_error
    if _classifier is None and _load_error is None:
        try:
            from transformers import pipeline
            print("Loading FinBERT...")
            _classifier = pipeline(
                "text-classification",
                model="ProsusAI/finbert"
            )
            print("FinBERT Loaded Successfully")
        except Exception as exc:
            _load_error = str(exc)
            print(f"[WARN] Could not load FinBERT: {exc}")
    return _classifier


def analyze_sentiment(text: str):
    classifier = _get_classifier()
    if classifier is None:
        return {
            "label": "neutral",
            "score": 0.5
        }
    result = classifier(text)[0]

    return {
        "label": result["label"].lower(),
        "score": float(result["score"])
    }


if __name__ == "__main__":

    sample_news = (
        "Reliance Industries reports "
        "strong quarterly earnings."
    )

    result = analyze_sentiment(
        sample_news
    )

    print(result)