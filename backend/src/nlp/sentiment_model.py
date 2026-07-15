from transformers import pipeline

print("Loading FinBERT...")

classifier = pipeline(
    "text-classification",
    model="ProsusAI/finbert"
)

print("FinBERT Loaded Successfully")


def analyze_sentiment(text: str):

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