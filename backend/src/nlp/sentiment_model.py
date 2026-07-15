_classifier = None


def _get_classifier():
    global _classifier
    if _classifier is None:
        from transformers import pipeline
        print("Loading FinBERT...")
        _classifier = pipeline(
            "text-classification",
            model="ProsusAI/finbert"
        )
        print("FinBERT Loaded Successfully")
    return _classifier


def analyze_sentiment(text: str):
    classifier = _get_classifier()
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