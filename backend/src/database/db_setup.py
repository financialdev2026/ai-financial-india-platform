from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    Integer,
    String,
    Float
)

engine = create_engine(
    "sqlite:///data/financial_market.db"
)

metadata = MetaData()

stocks = Table(
    "stocks",
    metadata,

    Column("id", Integer, primary_key=True),

    Column("ticker", String),
    Column("date", String),

    Column("open", Float),
    Column("high", Float),
    Column("low", Float),
    Column("close", Float),

    Column("volume", Float)
)

sectors = Table(
    "sectors",
    metadata,

    Column("id", Integer, primary_key=True),

    Column("sector", String),
    Column("date", String),

    Column("open", Float),
    Column("high", Float),
    Column("low", Float),
    Column("close", Float),

    Column("volume", Float)
)

news = Table(
    "news",
    metadata,

    Column("id", Integer, primary_key=True),

    Column("title", String),
    Column("description", String),
    Column("source", String),
    Column("published_at", String),
    Column("url", String)
)

news_sentiment = Table(
    "news_sentiment",
    metadata,

    Column("id", Integer, primary_key=True),

    Column("title", String),

    Column("sector", String),

    Column("sentiment", String),

    Column("confidence", Float),

    Column("source", String),

    Column("published_at", String)
)

economic_data = Table(
    "economic_data",
    metadata,

    Column(
        "id",
        Integer,
        primary_key=True
    ),

    Column(
        "date",
        String
    ),

    Column(
        "indicator",
        String
    ),

    Column(
        "value",
        Float
    ),

    Column(
        "source",
        String
    )
)

technical_indicators = Table(
    "technical_indicators",
    metadata,

    Column("id", Integer, primary_key=True, autoincrement=True),

    Column("ticker", String, nullable=False),
    Column("date", String, nullable=False),

    # Momentum
    Column("rsi", Float),

    # MACD
    Column("macd", Float),
    Column("macd_signal", Float),
    Column("macd_histogram", Float),

    # Bollinger Bands
    Column("bb_upper", Float),
    Column("bb_middle", Float),
    Column("bb_lower", Float)
)

fii_dii = Table(
    "fii_dii",
    metadata,

    Column("id", Integer, primary_key=True),

    Column("date", String),

    Column("client_type", String),

    Column("buy_value", Float),

    Column("sell_value", Float),

    Column("net_value", Float)
)

technical_scores = Table(
    "technical_scores",
    metadata,

    Column("id", Integer, primary_key=True, autoincrement=True),

    Column("ticker", String, nullable=False),
    Column("date", String, nullable=False),

    Column("macd_score", Float),
    Column("rsi_score", Float),
    Column("bollinger_score", Float),

    Column("technical_score", Float),

    Column("signal", String),

    Column("confidence", Float),

    Column("reason", String)
)

economic_scores = Table(
    "economic_scores",
    metadata,

    Column("id", Integer, primary_key=True, autoincrement=True),

    Column("date", String),

    Column("repo_rate", Float),

    Column("gdp_growth", Float),

    Column("inflation", Float),

    Column("repo_score", Float),

    Column("gdp_score", Float),

    Column("inflation_score", Float),

    Column("economic_score", Float),

    Column("signal", String),

    Column("confidence", Float),

    Column("reason", String)
)

fii_dii_scores = Table(
    "fii_dii_scores",
    metadata,

    Column("id", Integer, primary_key=True, autoincrement=True),

    Column("date", String),

    Column("client_type", String),

    Column("buy_value", Float),
    Column("sell_value", Float),
    Column("net_value", Float),

    Column("flow_score", Float),

    Column("signal", String),

    Column("confidence", Float),

    Column("reason", String)
)

news_scores = Table(
    "news_scores",
    metadata,

    Column("id", Integer, primary_key=True, autoincrement=True),

    Column("sector", String),

    Column("positive_articles", Integer),
    Column("neutral_articles", Integer),
    Column("negative_articles", Integer),

    Column("average_confidence", Float),

    Column("weighted_sentiment", Float),

    Column("news_score", Float),

    Column("signal", String),

    Column("confidence", Float),

    Column("reason", String)
)

risk_scores = Table(
    "risk_scores",
    metadata,

    Column("id", Integer, primary_key=True, autoincrement=True),

    Column("date", String),

    Column("technical_score", Float),

    Column("news_score", Float),

    Column("volume_score", Float),

    Column("economic_score", Float),

    Column("fii_score", Float),

    Column("final_score", Float),

    Column("signal", String),

    Column("confidence", Float),

    Column("agreement_score", Float),

    Column("reason", String)
)

market_reports = Table(
    "market_reports",
    metadata,

    Column("id", Integer, primary_key=True, autoincrement=True),

    Column("date", String),

    Column("recommendation", String),

    Column("overall_score", Float),

    Column("confidence", Float),

    Column("market_risk", String),

    Column("agreement_score", Float)
)

volume_scores = Table(
    "volume_scores",
    metadata,

    Column("id", Integer, primary_key=True, autoincrement=True),

    Column("ticker", String, nullable=False),
    Column("date", String, nullable=False),

    Column("volume_score", Float),
    Column("volume_ratio", Float),
    Column("volume_signal", String),
    Column("confidence", Float),
    Column("reason", String)
)

metadata.create_all(engine)

print("All database tables created successfully")

