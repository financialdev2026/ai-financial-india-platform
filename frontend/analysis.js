const pageType = document.body.dataset.analysis;
const _isLocal = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
const API_ROOT = (_isLocal ? "http://localhost:8000" : window.location.origin) + "/dashboard";
const formatNumber = new Intl.NumberFormat("en-IN");

const copy = {
  technical: {
    title: "Price Signals",
    description: "Latest per-stock technical snapshot. This avoids letting old price-indicator rows dominate the current view.",
    cards: (b) => [
      ["Tracked stocks", b.report.technical_analysis.tracked_stocks],
      ["Average score", Number(b.report.technical_analysis.average_score).toFixed(3)],
      ["Best stock", b.report.technical_analysis.best_stock],
      ["Weakest stock", b.report.technical_analysis.worst_stock],
      ["As of", b.report.technical_analysis.as_of],
      ["Average confidence", `${Number(b.report.technical_analysis.average_confidence).toFixed(2)}%`]
    ],
    rows: (b) => b.stocks.map((s) => [s.ticker, s.technicalSignal, s.technicalScore.toFixed(3), `RSI ${s.rsi.toFixed(1)}`]),
    headers: ["Ticker", "Signal", "Score", "Indicator"]
  },
  news: {
    title: "News Sentiment",
    description: "Recency-aware sector sentiment from the backend news pipeline. Older articles decay before scores are produced.",
    cards: (b) => [
      ["Scored sectors", b.report.news_analysis.scored_sectors],
      ["Recent articles used", b.report.news_analysis.article_count],
      ["Positive", b.report.news_analysis.positive_articles],
      ["Neutral", b.report.news_analysis.neutral_articles],
      ["Negative", b.report.news_analysis.negative_articles],
      ["Latest article", String(b.report.news_analysis.latest_article_at).slice(0, 10)]
    ],
    rows: (b) => b.news.slice(0, 40).map((n) => [n.sector || "MARKET", n.sentiment, `${Number(n.confidence).toFixed(1)}%`, n.title]),
    headers: ["Sector", "Sentiment", "Confidence", "Headline"]
  },
  volume: {
    title: "Volume Flow",
    description: "Latest volume participation by stock. Volume ratio compares current volume with rolling average volume.",
    cards: (b) => [
      ["Tracked stocks", b.report.volume_analysis.tracked_stocks],
      ["Average score", Number(b.report.volume_analysis.average_score).toFixed(3)],
      ["Average ratio", `${Number(b.report.volume_analysis.average_ratio).toFixed(2)}x`],
      ["Highest volume stock", b.report.volume_analysis.highest_volume_stock],
      ["Highest ratio", `${Number(b.report.volume_analysis.highest_volume_ratio).toFixed(2)}x`],
      ["As of", b.report.volume_analysis.as_of]
    ],
    rows: (b) => b.stocks.slice().sort((a, b2) => b2.volumeRatio - a.volumeRatio).map((s) => [s.ticker, s.volumeSignal, `${s.volumeRatio.toFixed(2)}x`, formatNumber.format(s.volume)]),
    headers: ["Ticker", "Signal", "Volume Ratio", "Volume"]
  },
  economy: {
    title: "Economy",
    description: "Macro score from repo rate, GDP growth and inflation. These are slower-moving indicators, so their latest date is shown clearly.",
    cards: (b) => {
      const e = b.report.economic_analysis;
      return [
        ["Signal", e.signal],
        ["Economic score", Number(e.economic_score).toFixed(3)],
        ["Repo rate", `${e.repo_rate}%`],
        ["GDP growth", `${e.gdp_growth}%`],
        ["Inflation", `${e.inflation}%`],
        ["As of", e.as_of]
      ];
    },
    rows: (b) => b.economicScores.map((e) => [e.date, e.signal, Number(e.economic_score).toFixed(3), e.reason || "Macro conditions scored"]),
    headers: ["Date", "Signal", "Score", "Reason"]
  },
  institutional: {
    title: "Institutional Flow",
    description: "Latest FII/DII buying and selling. The upgraded backend de-duplicates repeated rows before producing the current score.",
    cards: (b) => {
      const i = b.report.institutional_analysis;
      return [
        ["Net flow", `Rs ${Number(i.net_flow).toFixed(2)} cr`],
        ["Average score", Number(i.average_score).toFixed(3)],
        ["Buyers", i.buyers],
        ["Sellers", i.sellers],
        ["Average confidence", `${Number(i.average_confidence).toFixed(2)}%`],
        ["As of", i.as_of]
      ];
    },
    rows: (b) => b.institutionalFlows.map((f) => [f.date, f.client_type, `Rs ${Number(f.net_value).toFixed(2)} cr`, f.signal]),
    headers: ["Date", "Client", "Net Flow", "Signal"]
  }
};

initAnalysis();

async function initAnalysis() {
  const response = await fetch("data/bundle.json", { cache: "no-store" });
  const bundle = await response.json();
  const live = await fetchLiveAnalysis(pageType);
  if (live) mergeLiveAnalysis(bundle, pageType, live);
  const config = copy[pageType] || copy.technical;
  document.title = `PrismEdge AI | ${config.title}`;
  document.querySelector("#analysisTitle").textContent = config.title;
  document.querySelector("#analysisDescription").textContent = config.description;
  document.querySelector("#analysisCards").innerHTML = config.cards(bundle).map(([label, value]) => `
    <article class="analysis-card" data-tip="${escapeHtml(config.description)}">
      <small>${escapeHtml(label)}</small>
      <strong>${escapeHtml(value ?? "--")}</strong>
    </article>
  `).join("");
  document.querySelector("#analysisTable").innerHTML = `
    <div class="analysis-row header">${config.headers.map((h) => `<span>${escapeHtml(h)}</span>`).join("")}</div>
    ${config.rows(bundle).map((row) => `<div class="analysis-row">${row.map((cell) => `<span>${escapeHtml(cell ?? "--")}</span>`).join("")}</div>`).join("")}
  `;
}

async function fetchLiveAnalysis(type) {
  const endpoint = {
    technical: "technical",
    news: "news",
    volume: "volume",
    economy: "economy",
    institutional: "institutional"
  }[type];

  if (!endpoint) return null;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 1200);
  try {
    const response = await fetch(`${API_ROOT}/${endpoint}`, {
      cache: "no-store",
      signal: controller.signal
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

function mergeLiveAnalysis(bundle, type, live) {
  if (!live || !live.summary) return;
  if (type === "technical") bundle.report.technical_analysis = live.summary;
  if (type === "news") bundle.report.news_analysis = live.summary;
  if (type === "volume") bundle.report.volume_analysis = live.summary;
  if (type === "economy") bundle.report.economic_analysis = live.summary;
  if (type === "institutional") bundle.report.institutional_analysis = live.summary;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
