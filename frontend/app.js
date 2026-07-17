const IS_LOCAL = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
const API_BASE = IS_LOCAL ? "http://localhost:8000" : window.location.origin;
const API_URL = API_BASE + "/dashboard/";
const AGENT_URL = API_BASE + "/dashboard/agent";

const state = {
  bundle: null,
  selectedStock: null,
  chartMode: "line",
  weights: {},
  activeSection: "overview"
};

const colors = {
  Technical: "#36d399",
  News: "#5aa7ff",
  Volume: "#f2b84b",
  Economic: "#a88bff",
  Institutional: "#ff6b66"
};

const moduleCopy = {
  Technical: '<span class="cd-green">Technical Health</span> — compares RSI, MACD and Bollinger indicators. <span class="cd-blue">Current values</span> show <span class="cd-green">positive momentum</span> when indicators align upward.',
  News: '<span class="cd-blue">News Sentiment</span> — uses recent articles with recency decay. <span class="cd-green">Positive articles</span> boost score; <span class="cd-red">negative headlines</span> reduce it.',
  Volume: '<span class="cd-orange">Volume Flow</span> — checks whether trading volume <span class="cd-blue">confirms or weakens</span> price participation. High volume with price rise is <span class="cd-green">supportive</span>.',
  Economic: '<span class="cd-purple">Economic Health</span> — reads <span class="cd-blue">repo rate, GDP growth and inflation</span>. <span class="cd-green">Falling inflation</span> is positive; <span class="cd-red">rising rates</span> can be cautious.',
  Institutional: '<span class="cd-purple">Institutional Activity</span> — tracks <span class="cd-blue">FII/DII net buying or selling</span>. <span class="cd-green">Net inflows</span> are bullish; <span class="cd-red">outflows</span> are bearish.'
};

const formatNumber = new Intl.NumberFormat("en-IN");
const formatCurrency = new Intl.NumberFormat("en-IN", {
  maximumFractionDigits: 2,
  minimumFractionDigits: 2
});

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

init();

async function init() {
  bindNavigation();
  bindActions();
  initScrollReveal();
  initParticles();
  initScheduler();
  await loadData();
  renderAll();
}

async function loadData() {
  const response = await fetch("data/bundle.json", { cache: "no-store" });
  state.bundle = await response.json();
  enrichSectors(state.bundle.sectors);
  state.selectedStock = state.bundle.stocks.slice().sort((a, b) => b.technicalScore - a.technicalScore)[0];
  setupWeights();
  await refreshLiveApi(false);
}

function enrichSectors(sectors) {
  if (!Array.isArray(sectors)) return;
  sectors.forEach((sector) => {
    const series = sector.series || [];
    if (series.length >= 2) {
      const first = Number(series[0].close);
      const last = Number(series[series.length - 1].close);
      if (first > 0 && Number.isFinite(first) && Number.isFinite(last)) {
        sector.changePct = Number(((last - first) / first * 100).toFixed(2));
      }
    }
    const change = Number(sector.changePct || 0);
    const news = Number(sector.newsScore || 0);
    const hasNews = Number.isFinite(news) && news !== 0;
    if (hasNews) {
      sector.strengthScore = Number((news * 0.6 + (change / 10) * 0.4).toFixed(4));
    } else if (change !== 0) {
      sector.strengthScore = Number((Math.tanh(change / 5) * 0.4).toFixed(4));
    } else if (!Number.isFinite(Number(sector.strengthScore))) {
      sector.strengthScore = NaN;
    }
  });
}

async function refreshLiveApi(showToast = true) {
  setApiState("Checking backend", "Trying API...", false);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10000);
  try {
    const response = await fetch(API_URL, { cache: "no-store", signal: controller.signal });
    if (!response.ok) throw new Error(`Backend returned ${response.status}`);
    const live = await response.json();
    mergeLiveDashboard(live);
    setApiState("Live API connected", "Using backend /dashboard plus local bundle", true);
    if (showToast) toast("Live backend data refreshed.");
  } catch (error) {
    setApiState("Offline bundle", "Backend unavailable; using generated data bundle", false);
    if (showToast) toast("Backend was not reachable, so the local bundle stayed active.");
  } finally {
    clearTimeout(timer);
  }
}

function mergeLiveDashboard(live) {
  if (!live || !state.bundle) return;
  const summary = live.executive_summary || {};
  const risk = live.risk || {};
  state.bundle.report.executive_summary = {
    ...state.bundle.report.executive_summary,
    date: summary.date || risk.date || state.bundle.report.executive_summary.date,
    recommendation: summary.recommendation || risk.signal || state.bundle.report.executive_summary.recommendation,
    overall_score: Number(summary.overall_score ?? risk.final_score ?? state.bundle.report.executive_summary.overall_score),
    confidence: Number(summary.confidence ?? risk.confidence ?? state.bundle.report.executive_summary.confidence),
    agreement: Number(summary.agreement ?? risk.agreement_score ?? state.bundle.report.executive_summary.agreement),
    market_risk: summary.market_risk || state.bundle.report.executive_summary.market_risk,
    reason: summary.reason || risk.reason || state.bundle.report.executive_summary.reason
  };
  if (live.score_breakdown && Object.keys(live.score_breakdown).length) {
    state.bundle.report.score_breakdown = live.score_breakdown;
    setupWeights();
  }
  if (live.data_quality && Object.keys(live.data_quality).length) {
    state.bundle.report.data_quality = live.data_quality;
  }
  if (live.analysis) {
    state.bundle.report.technical_analysis = live.analysis.technical || state.bundle.report.technical_analysis;
    state.bundle.report.news_analysis = live.analysis.news || state.bundle.report.news_analysis;
    state.bundle.report.volume_analysis = live.analysis.volume || state.bundle.report.volume_analysis;
    state.bundle.report.economic_analysis = live.analysis.economic || state.bundle.report.economic_analysis;
    state.bundle.report.institutional_analysis = live.analysis.institutional || state.bundle.report.institutional_analysis;
  }
  if (Array.isArray(live.technical_scores)) {
    const latestScores = new Map();
    live.technical_scores.forEach((row) => {
      if (row.ticker && row.technical_score !== null) latestScores.set(row.ticker, row);
    });
    state.bundle.stocks.forEach((stock) => {
      const score = latestScores.get(stock.ticker);
      if (score) {
        stock.technicalScore = Number(score.technical_score || stock.technicalScore);
        stock.technicalSignal = score.signal || stock.technicalSignal;
        stock.technicalConfidence = Number(score.confidence || stock.technicalConfidence);
        stock.technicalReason = score.reason || stock.technicalReason;
      }
    });
  }
  if (Array.isArray(live.news_scores)) {
    const latestNewsScores = new Map();
    live.news_scores.forEach((row) => {
      if (row.sector && row.sector !== "UNKNOWN") latestNewsScores.set(row.sector, row);
    });
    state.bundle.sectors.forEach((sector) => {
      const score = latestNewsScores.get(sector.sector);
      if (score) {
        sector.newsScore = Number(score.news_score);
        sector.strengthScore = Number.isFinite(Number(sector.strengthScore))
          ? Number(sector.strengthScore)
          : Number(score.news_score);
        sector.signal = score.signal;
        sector.confidence = Number(score.confidence || 0);
        sector.positiveArticles = Number(score.positive_articles || 0);
        sector.neutralArticles = Number(score.neutral_articles || 0);
        sector.negativeArticles = Number(score.negative_articles || 0);
        sector.reason = score.reason;
      } else {
        sector.newsScore = NaN;
        sector.strengthScore = Number.isFinite(Number(sector.strengthScore)) ? Number(sector.strengthScore) : NaN;
        sector.signal = sector.signal || "UNKNOWN";
        sector.reason = sector.reason || "No recent sector-specific news articles available.";
      }
    });
  }
}

function setupWeights() {
  state.weights = Object.fromEntries(
    Object.entries(state.bundle.report.score_breakdown).map(([module, data]) => [module, Number(data.weight)])
  );
}

function renderAll() {
  renderSummary();
  renderCommandRibbon();
  renderTrend();
  renderModuleBoard();
  renderStockMatrix();
  renderWeights();
  renderModuleChart();
  renderStocks();
  renderSelectedStock();
  renderSectorFilters();
  renderSectors();
  renderNews();
  renderReasoning();
  renderReasoningPreview();
  renderHealth();
  renderPlatformStatus();
  bindTooltips();
}

function renderSummary() {
  const summary = state.bundle.report.executive_summary;
  const technical = state.bundle.report.technical_analysis;
  const volume = state.bundle.report.volume_analysis;
  $("#recommendation").textContent = summary.recommendation;
  $("#riskBadge").textContent = `${summary.market_risk} Risk`;
  $("#reasonText").textContent = `${summary.reason}. Report date: ${summary.date}.`;
  $("#overallScore").textContent = Number(summary.overall_score).toFixed(3);
  $("#confidence").textContent = `${Number(summary.confidence).toFixed(2)}%`;
  $("#agreement").textContent = `${Number(summary.agreement).toFixed(1)}%`;
  $("#bestStock").textContent = technical.best_stock;
  $("#bestStockNote").textContent = `Best score ${Number(technical.best_score).toFixed(2)}; weakest ${technical.worst_stock}`;
  $("#highestVolume").textContent = volume.highest_volume_stock;
  $("#volumeNote").textContent = `${Number(volume.highest_volume_ratio).toFixed(2)}x average volume`;
  drawGauge($("#scoreGauge"), Number(summary.overall_score), summary.recommendation);
}

function renderCommandRibbon() {
  const report = state.bundle.report || {};
  const summary = report.executive_summary || {};
  const quality = report.data_quality || state.bundle.dashboard?.data_quality || {};
  const coverage = state.bundle.coverage || {};
  const currentRows = ["technical_rows", "volume_rows", "news_rows", "economic_rows", "fii_rows"]
    .map((key) => Number(quality[key] || 0))
    .reduce((sum, value) => sum + value, 0);
  const totalRows = Number(coverage.technicalScores || 0)
    + Number(coverage.volumeScores || 0)
    + Number(coverage.newsSentiment || 0)
    + Number(coverage.economicRows || 0)
    + Number(coverage.institutionalRows || 0);

  function formatTimestamp(val) {
    if (!val || val === "--") return "--";
    try {
      const d = new Date(val);
      if (isNaN(d)) return val;
      return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) + " " +
        d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
    } catch { return val; }
  }

  $("#reportDate").textContent = summary.date || "--";
  $("#technicalFreshness").textContent = formatTimestamp(quality.technical_date);
  $("#newsFreshness").textContent = formatTimestamp(quality.news_date);
  $("#flowFreshness").textContent = formatTimestamp(quality.fii_date);
  $("#coverageScore").textContent = totalRows
    ? `${formatNumber.format(currentRows)} current / ${formatNumber.format(totalRows)} rows`
    : "--";
}

function renderModuleBoard() {
  const breakdown = state.bundle.report.score_breakdown || {};
  const moduleLabels = {
    Technical: "Technical Health",
    News: "News Sentiment",
    Volume: "Volume Flow",
    Economic: "Economic Health",
    Institutional: "Institutional Activity"
  };
  $("#moduleBoard").innerHTML = Object.entries(breakdown).map(([module, data]) => {
    const score = Number(data.score || 0);
    const contribution = Number(data.contribution || 0);
    const width = Math.min(100, Math.max(3, Math.abs(contribution) / 0.28 * 100));
    const color = score >= 0.2 ? (colors[module] || "#36d399") : score <= -0.2 ? "#ff6b66" : "#f2b84b";
    const stance = score >= 0.2 ? "supportive" : score <= -0.2 ? "negative" : "neutral";
    const label = moduleLabels[module] || module;
    return `
      <div class="module-row" data-tip="${escapeHtml(moduleCopy[module] || "Model module")}">
        <div>
          <strong>${label}</strong><br>
          <small>${stance} | weight ${data.weight}%</small>
        </div>
        <div class="module-track" aria-label="${module} contribution">
          <div class="module-fill" style="width:${width}%; background:${color}"></div>
        </div>
        <div>
          <strong>${score.toFixed(3)}</strong><br>
          <small>${signed(contribution)}</small>
        </div>
        <div class="module-details">
          ${moduleCopy[module] || ""}
          <br>Current weighted contribution: <span class="cd-blue">${signed(contribution)}</span>.
        </div>
      </div>
    `;
  }).join("");
}

function renderStockMatrix() {
  const stocks = state.bundle.stocks.slice().sort((a, b) => b.technicalScore - a.technicalScore);
  $("#stockMatrix").innerHTML = stocks.map((stock) => {
    const score = Number(stock.technicalScore || 0);
    const tone = score >= 0.2 ? "rgba(54, 211, 153, 0.16)" : score <= -0.2 ? "rgba(255, 107, 102, 0.16)" : "rgba(242, 184, 75, 0.12)";
    const border = score >= 0.2 ? "rgba(54, 211, 153, 0.38)" : score <= -0.2 ? "rgba(255, 107, 102, 0.38)" : "rgba(242, 184, 75, 0.28)";
    return `
      <button class="matrix-cell" style="background:${tone}; border-color:${border}" data-stock="${stock.ticker}" data-tip="Click to inspect ${stock.ticker} price chart, score, volume ratio and latest indicator values.">
        <strong>${stock.ticker}</strong>
        <span>${score.toFixed(2)}</span>
        <small>${signed(stock.changePct)}% | ${stock.technicalSignal}</small>
      </button>
    `;
  }).join("");

  $$("#stockMatrix [data-stock]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedStock = state.bundle.stocks.find((stock) => stock.ticker === button.dataset.stock);
      document.querySelector("#stocks")?.scrollIntoView({ behavior: "smooth", block: "start" });
      renderStocks();
      renderSelectedStock();
    });
  });
}

function renderTrend() {
  drawLineChart($("#trendChart"), state.bundle.dashboard.chart, {
    mode: state.chartMode,
    valueKey: "score",
    labelKey: "day",
    color: "#1f8a5b",
    min: 0,
    max: 0.75,
    formatter: (v) => v.toFixed(2)
  });
}

function renderWeights() {
  const container = $("#weightControls");
  container.innerHTML = "";
  Object.entries(state.bundle.report.score_breakdown).forEach(([module, data]) => {
    const row = document.createElement("div");
    row.className = "weight-row";
    row.innerHTML = `
      <div class="weight-meta">
        <span>${module}</span>
        <span><b data-weight-value="${module}">${state.weights[module]}</b>% | score ${Number(data.score).toFixed(3)}</span>
      </div>
      <input type="range" min="0" max="70" step="1" value="${state.weights[module]}" data-weight="${module}" aria-label="${module} weight" data-tip="${escapeHtml(moduleCopy[module] || "Adjust model weight")}">
    `;
    container.appendChild(row);
  });
  $$("[data-weight]").forEach((input) => {
    input.addEventListener("input", (event) => {
      const module = event.target.dataset.weight;
      state.weights[module] = Number(event.target.value);
      $(`[data-weight-value="${module}"]`).textContent = state.weights[module];
      renderModuleChart();
    });
  });
}

function renderModuleChart() {
  const breakdown = state.bundle.report.score_breakdown;
  const totalWeight = Object.values(state.weights).reduce((sum, weight) => sum + weight, 0) || 1;
  const weightedScore = Object.entries(breakdown).reduce((sum, [module, data]) => {
    return sum + Number(data.score) * (state.weights[module] / totalWeight);
  }, 0);
  $("#simScore").textContent = weightedScore.toFixed(3);
  $("#simSignal").textContent = signalForScore(weightedScore);

  const shortLabels = { Technical: "Tech", News: "News", Volume: "Vol", Economic: "Econ", Institutional: "Inst" };
  const values = Object.entries(breakdown).map(([module, data]) => ({
    module,
    label: shortLabels[module] || module,
    value: Number(data.score) * (state.weights[module] / totalWeight),
    rawScore: Number(data.score),
    color: colors[module] || "#1f8a5b"
  }));
  drawBarChart($("#moduleChart"), values, { max: 0.45 });
  $("#moduleLegend").innerHTML = values.map((item) => `
    <span><b style="color:${item.color}">${item.label}</b><br>${item.rawScore.toFixed(3)} score | ${state.weights[item.module]}% weight</span>
  `).join("");
}

function renderStocks() {
  const search = $("#stockSearch").value.trim().toUpperCase();
  const sort = $("#stockSort").value;
  const stocks = state.bundle.stocks
    .filter((stock) => stock.ticker.includes(search))
    .sort((a, b) => {
      if (sort === "change") return b.changePct - a.changePct;
      if (sort === "volume") return b.volume - a.volume;
      if (sort === "ticker") return a.ticker.localeCompare(b.ticker);
      return b.technicalScore - a.technicalScore;
    });

  $("#stockList").innerHTML = stocks.map((stock) => `
    <button class="stock-card ${state.selectedStock?.ticker === stock.ticker ? "active" : ""}" data-stock="${stock.ticker}" data-tip="Click to view ${stock.ticker} chart, price levels, confidence and volume ratio.">
      <span>
        <strong>${stock.ticker}</strong>
        <small>${stock.technicalSignal} | RSI ${stock.rsi.toFixed(1)}</small>
      </span>
      <span>
        <strong>${signed(stock.changePct)}%</strong>
        <small>Rs ${formatCurrency.format(stock.close)}</small>
      </span>
    </button>
  `).join("");

  $$("[data-stock]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedStock = state.bundle.stocks.find((stock) => stock.ticker === button.dataset.stock);
      renderStocks();
      renderSelectedStock();
    });
  });
}

function renderSelectedStock() {
  const stock = state.selectedStock;
  if (!stock) return;
  $("#selectedTicker").textContent = stock.ticker;
  $("#selectedSignal").textContent = stock.technicalSignal;
  drawLineChart($("#stockChart"), stock.series, {
    mode: "area",
    valueKey: "close",
    labelKey: "date",
    color: stock.changePct >= 0 ? "#1f8a5b" : "#c84c45",
    formatter: (v) => `Rs ${v.toFixed(0)}`
  });
  $("#stockStats").innerHTML = [
    ["Close", `Rs ${formatCurrency.format(stock.close)}`],
    ["Daily Change", `${signed(stock.changePct)}%`],
    ["Volume", formatNumber.format(stock.volume)],
    ["Technical Score", stock.technicalScore.toFixed(3)],
    ["Confidence", `${stock.technicalConfidence.toFixed(1)}%`],
    ["Volume Ratio", `${stock.volumeRatio.toFixed(2)}x`],
    ["Open", `Rs ${formatCurrency.format(stock.open)}`],
    ["High", `Rs ${formatCurrency.format(stock.high)}`],
    ["Low", `Rs ${formatCurrency.format(stock.low)}`]
  ].map(([label, value]) => `<div class="stat"><span>${label}</span><strong>${value}</strong></div>`).join("");
}

function renderSectorFilters() {
  const sectors = ["all", ...new Set(state.bundle.news.map((item) => item.sector).filter(Boolean))].sort();
  $("#sectorFilter").innerHTML = sectors.map((sector) => `
    <option value="${sector}">${sector === "all" ? "All sectors" : sector}</option>
  `).join("");
}

function renderSectors() {
  const metric = $("#sectorMetric").value;
  const numericValues = state.bundle.sectors
    .map((sector) => metricValue(sector, metric))
    .filter((value) => Number.isFinite(value));
  const maxValue = Math.max(...numericValues.map((value) => Math.abs(value)), 1);
  $("#sectorGrid").innerHTML = state.bundle.sectors.map((sector) => {
    const value = metricValue(sector, metric);
    const hasValue = Number.isFinite(value);
    const intensity = hasValue ? Math.max(0.28, Math.min(1, Math.abs(value) / maxValue)) : 0.18;
    const color = hasValue
      ? value >= 0
        ? `rgba(31, 138, 91, ${0.62 + intensity * 0.32})`
        : `rgba(200, 76, 69, ${0.62 + intensity * 0.32})`
      : "rgba(76, 88, 100, 0.58)";
    const reason = sector.reason || "Sector strength uses the latest available sector index data and news sentiment when available.";
    return `
      <article class="sector-card" style="background:${color}" data-tip="${escapeHtml(reason)}">
        <div>
          <small>${sector.signal || signalFromScore(value)}</small>
          <h3>${sector.sector}</h3>
        </div>
        <div>
          <strong>${metricLabel(value, metric)}</strong>
          <small>${reason}</small>
        </div>
      </article>
    `;
  }).join("");
}

function renderNews() {
  const sentiment = $("#sentimentFilter").value;
  const sector = $("#sectorFilter").value || "all";
  const filtered = state.bundle.news.filter((item) => {
    const sentimentMatch = sentiment === "all" || item.sentiment === sentiment;
    const sectorMatch = sector === "all" || item.sector === sector;
    return sentimentMatch && sectorMatch;
  });
  const counts = state.bundle.news.reduce((acc, item) => {
    acc[item.sentiment] = (acc[item.sentiment] || 0) + 1;
    return acc;
  }, {});
  $("#newsSummary").innerHTML = [
    ["Loaded", state.bundle.news.length],
    ["Positive", counts.positive || 0],
    ["Neutral", counts.neutral || 0],
    ["Negative", counts.negative || 0]
  ].map(([label, value]) => `<div class="news-pill"><span>${label}</span><strong>${formatNumber.format(value)}</strong></div>`).join("");

  $("#newsList").innerHTML = filtered.slice(0, 28).map((item) => `
    <article class="news-card" data-tip="Sentiment confidence and sector mapping come from the backend news sentiment pipeline.">
      <div class="tag-row">
        <span class="tag ${item.sentiment}">${item.sentiment}</span>
        <span class="tag">${item.sector || "MARKET"}</span>
        <span class="tag">${Number(item.confidence).toFixed(1)}%</span>
      </div>
      <a href="${item.url || "#"}" target="_blank" rel="noreferrer">${escapeHtml(item.title)}</a>
      <p>${escapeHtml(item.description || "No article description was supplied by the backend feed.")}</p>
      <small>${item.source || "Unknown source"} · ${item.published_at || "No timestamp"}</small>
    </article>
  `).join("");
}

function renderReasoning() {
  const text = state.bundle.report.ai_reasoning || state.bundle.dashboard.ai_explanation || "";
  $("#aiReasoning").innerHTML = text
    .replaceAll("â€¢", "-")
    .replaceAll("•", "-")
    .split(/\n{2,}/)
    .filter(Boolean)
    .map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`)
    .join("");
}

function renderReasoningPreview() {
  const text = state.bundle.report.ai_reasoning || state.bundle.dashboard.ai_explanation || "";
  const paragraphs = text
    .replaceAll("Ã¢â‚¬Â¢", "-")
    .replaceAll("â€¢", "-")
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);

  $("#aiReasoningPreview").innerHTML = paragraphs
    .slice(0, 2)
    .map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`)
    .join("");
}

function renderHealth() {
  const coverage = state.bundle.coverage;
  const rows = [
    ["Stock price rows", coverage.stocks],
    ["Technical scores", coverage.technicalScores],
    ["Volume scores", coverage.volumeScores],
    ["News articles", coverage.newsItems],
    ["Sentiment rows", coverage.newsSentiment],
    ["Sector rows", coverage.sectors],
    ["Economic rows", coverage.economicRows],
    ["FII/DII rows", coverage.institutionalRows]
  ];
  const flows = state.bundle.institutionalFlows.slice(0, 2).map((flow) => `
    <div class="health-item">
      <span><strong>${flow.client_type}</strong><small>${flow.date} | ${flow.signal}</small></span>
      <strong>Rs ${formatCurrency.format(flow.net_value)} cr</strong>
    </div>
  `).join("");
  $("#dataHealth").innerHTML = rows.map(([label, value]) => `
    <div class="health-item"><span>${label}</span><strong>${formatNumber.format(value)}</strong></div>
  `).join("") + flows + `
    <div class="health-item"><span>Bundle generated</span><strong>${state.bundle.generatedAt.replace("T", " ")}</strong></div>
  `;
}

function drawGauge(canvas, value, label) {
  const ctx = setupCanvas(canvas);
  const { width, height } = canvas.getBoundingClientRect();
  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.min(width, height) * 0.36;
  const start = Math.PI * 0.72;
  const end = Math.PI * 2.28;
  const pct = Math.max(0, Math.min(1, (value + 0.8) / 1.6));

  ctx.lineWidth = 20;
  ctx.lineCap = "round";
  ctx.strokeStyle = "#dfe7df";
  ctx.beginPath();
  ctx.arc(cx, cy, radius, start, end);
  ctx.stroke();

  const gradient = ctx.createLinearGradient(cx - radius, cy, cx + radius, cy);
  gradient.addColorStop(0, "#c84c45");
  gradient.addColorStop(0.48, "#c47c17");
  gradient.addColorStop(1, "#1f8a5b");
  ctx.strokeStyle = gradient;
  ctx.beginPath();
  ctx.arc(cx, cy, radius, start, start + (end - start) * pct);
  ctx.stroke();

  ctx.fillStyle = "#62706c";
  ctx.font = "700 12px Inter, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(label, cx, cy + radius + 34);
}

function drawLineChart(canvas, rows, options) {
  const ctx = setupCanvas(canvas);
  const rect = canvas.getBoundingClientRect();
  const width = rect.width;
  const height = rect.height;
  const pad = { top: 18, right: 24, bottom: 34, left: 48 };
  const values = rows.map((row) => Number(row[options.valueKey]));
  const min = options.min ?? Math.min(...values);
  const max = options.max ?? Math.max(...values);
  const range = max - min || 1;
  const x = (index) => pad.left + (index / Math.max(1, rows.length - 1)) * (width - pad.left - pad.right);
  const y = (value) => height - pad.bottom - ((value - min) / range) * (height - pad.top - pad.bottom);

  drawAxes(ctx, width, height, pad, min, max, options.formatter);

  if (options.mode === "bars") {
    const barWidth = Math.max(8, (width - pad.left - pad.right) / rows.length - 8);
    rows.forEach((row, index) => {
      ctx.fillStyle = options.color;
      ctx.globalAlpha = 0.78;
      const barHeight = height - pad.bottom - y(Number(row[options.valueKey]));
      ctx.fillRect(x(index) - barWidth / 2, y(Number(row[options.valueKey])), barWidth, barHeight);
      ctx.globalAlpha = 1;
    });
  } else {
    ctx.beginPath();
    rows.forEach((row, index) => {
      const px = x(index);
      const py = y(Number(row[options.valueKey]));
      index ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
    });
    if (options.mode === "area") {
      ctx.lineTo(x(rows.length - 1), height - pad.bottom);
      ctx.lineTo(x(0), height - pad.bottom);
      ctx.closePath();
      const gradient = ctx.createLinearGradient(0, pad.top, 0, height - pad.bottom);
      gradient.addColorStop(0, `${options.color}55`);
      gradient.addColorStop(1, `${options.color}08`);
      ctx.fillStyle = gradient;
      ctx.fill();
    }
    ctx.beginPath();
    rows.forEach((row, index) => {
      const px = x(index);
      const py = y(Number(row[options.valueKey]));
      index ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
    });
    ctx.lineWidth = 3;
    ctx.strokeStyle = options.color;
    ctx.stroke();
  }

  ctx.fillStyle = "#62706c";
  ctx.font = "700 11px Inter, sans-serif";
  ctx.textAlign = "center";
  rows.forEach((row, index) => {
    if (index === 0 || index === rows.length - 1 || index % Math.ceil(rows.length / 6) === 0) {
      ctx.fillText(String(row[options.labelKey]).slice(5), x(index), height - 10);
    }
  });
}

function drawBarChart(canvas, values, options) {
  const ctx = setupCanvas(canvas);
  const rect = canvas.getBoundingClientRect();
  const width = rect.width;
  const height = rect.height;
  const pad = { top: 20, right: 18, bottom: 42, left: 42 };
  const max = options.max || Math.max(...values.map((item) => item.value), 1);
  const barWidth = (width - pad.left - pad.right) / values.length - 12;
  drawAxes(ctx, width, height, pad, 0, max, (v) => v.toFixed(2));
  values.forEach((item, index) => {
    const x = pad.left + index * (barWidth + 12) + 8;
    const barHeight = (item.value / max) * (height - pad.top - pad.bottom);
    const y = height - pad.bottom - barHeight;
    ctx.fillStyle = item.color;
    ctx.fillRect(x, y, barWidth, barHeight);
    ctx.fillStyle = "#14201f";
    ctx.font = "800 11px Inter, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(item.label.slice(0, 4), x + barWidth / 2, height - 15);
  });
}

function drawAxes(ctx, width, height, pad, min, max, formatter) {
  ctx.strokeStyle = "#d9e0da";
  ctx.lineWidth = 1;
  ctx.fillStyle = "#62706c";
  ctx.font = "700 11px Inter, sans-serif";
  ctx.textAlign = "right";
  for (let i = 0; i <= 4; i += 1) {
    const y = pad.top + (i / 4) * (height - pad.top - pad.bottom);
    const value = max - (i / 4) * (max - min);
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(width - pad.right, y);
    ctx.stroke();
    ctx.fillText(formatter ? formatter(value) : value.toFixed(2), pad.left - 8, y + 4);
  }
}

function setupCanvas(canvas) {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, rect.width, rect.height);
  return ctx;
}

function bindNavigation() {
  const links = $$(".nav-list a");
  const sections = links.map((link) => $(link.getAttribute("href"))).filter(Boolean);
  window.addEventListener("scroll", () => {
    const current = sections.findLast((section) => section.getBoundingClientRect().top <= 130);
    if (!current) return;
    links.forEach((link) => link.classList.toggle("active", link.getAttribute("href") === `#${current.id}`));
  }, { passive: true });
}

function bindActions() {
  $("#refreshButton").addEventListener("click", async () => {
    await refreshLiveApi(true);
    renderAll();
  });
  $("#exportButton").addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(state.bundle, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `prismedge-export-${Date.now()}.json`;
    link.click();
    URL.revokeObjectURL(url);
    closeDownloadMenu();
  });
  $("#exportPdfButton").addEventListener("click", () => { generatePDF(); closeDownloadMenu(); });
  $("#exportCsvButton").addEventListener("click", () => { exportCSV(); closeDownloadMenu(); });
  initDownloadDropdown();
  initFloatingAgent();
  $("#resetWeights").addEventListener("click", () => {
    setupWeights();
    renderWeights();
    renderModuleChart();
  });
  $("#stockSearch").addEventListener("input", renderStocks);
  $("#stockSort").addEventListener("change", renderStocks);
  $("#sectorMetric").addEventListener("change", renderSectors);
  $("#sentimentFilter").addEventListener("change", renderNews);
  $("#sectorFilter").addEventListener("change", renderNews);
  $("#agentForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = $("#agentQuestion");
    const question = input.value.trim();
    if (!question) return;
    input.value = "";
    await askAgent(question);
  });
  $$("[data-agent-prompt]").forEach((button) => {
    button.addEventListener("click", () => askAgent(button.dataset.agentPrompt));
  });
  $$("[data-chart-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      $$("[data-chart-mode]").forEach((item) => item.classList.toggle("active", item === button));
      state.chartMode = button.dataset.chartMode;
      renderTrend();
    });
  });
  window.addEventListener("resize", debounce(renderAll, 140));
}

function initDownloadDropdown() {
  const trigger = $("#downloadTrigger");
  const menu = $("#downloadMenu");
  if (!trigger || !menu) return;
  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    menu.hidden = !menu.hidden;
  });
  document.addEventListener("click", () => { menu.hidden = true; });
}

function closeDownloadMenu() {
  const menu = $("#downloadMenu");
  if (menu) menu.hidden = true;
}

function exportCSV() {
  if (!state.bundle) return;
  const stocks = state.bundle.stocks || [];
  const header = "Ticker,Close,Change%,Volume,TechnicalScore,TechnicalSignal,RSI,VolumeRatio";
  const rows = stocks.map(s =>
    [s.ticker, s.close, s.changePct, s.volume, s.technicalScore, s.technicalSignal, s.rsi, s.volumeRatio].join(",")
  );
  const csv = [header, ...rows].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `prismedge-stocks-${Date.now()}.csv`;
  link.click();
  URL.revokeObjectURL(url);
  toast("CSV exported.");
}

function initFloatingAgent() {
  const bubble = $("#floatingAgentBubble");
  const panel = $("#floatingAgentPanel");
  const closeBtn = $("#floatingAgentClose");
  const form = $("#floatingAgentForm");
  const input = $("#floatingAgentInput");

  if (!bubble || !panel) return;

  bubble.addEventListener("click", () => {
    panel.hidden = !panel.hidden;
  });

  closeBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    panel.hidden = true;
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const question = input.value.trim();
    if (!question) return;
    input.value = "";
    await askFloatingAgent(question);
  });

  $$("[data-float-prompt]").forEach(btn => {
    btn.addEventListener("click", () => askFloatingAgent(btn.dataset.floatPrompt));
  });
}

async function askFloatingAgent(question) {
  const messages = $("#floatingAgentMessages");
  if (!messages) return;

  const userMsg = document.createElement("div");
  userMsg.className = "floating-agent-message user";
  userMsg.textContent = question;
  messages.appendChild(userMsg);

  const thinkMsg = document.createElement("div");
  thinkMsg.className = "floating-agent-message agent thinking";
  thinkMsg.textContent = "Thinking...";
  messages.appendChild(thinkMsg);
  messages.scrollTop = messages.scrollHeight;

  let answer = "";
  let source = "";
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 22000);
    const response = await fetch(AGENT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      signal: controller.signal
    });
    clearTimeout(timer);
    const data = await response.json();
    if (response.ok) {
      answer = data.answer || "";
      source = data.source || "";
    } else {
      answer = localAgentAnswer(question);
      source = "local fallback";
    }
  } catch (err) {
    answer = localAgentAnswer(question);
    source = "local fallback (backend unreachable)";
  }

  if (source && source.includes("backend report")) {
    answer += "\n(LLM not available — used local analysis)";
  }

  thinkMsg.textContent = answer;
  thinkMsg.classList.remove("thinking");
  messages.scrollTop = messages.scrollHeight;
}

function renderPlatformStatus() {
  const grid = $("#platformStatusGrid");
  if (!grid) return;
  const quality = state.bundle?.report?.data_quality || {};
  const apiLive = $("#apiPulse")?.classList.contains("live");
  const cards = [
    { label: "Database", status: state.bundle ? "ok" : "error", detail: state.bundle ? "Bundle loaded" : "No data" },
    { label: "FastAPI", status: apiLive ? "ok" : "warn", detail: apiLive ? "Connected" : "Offline mode" },
    { label: "News Pipeline", status: quality.news_date ? "ok" : "warn", detail: quality.news_date || "No news data" },
    { label: "AI Engine", status: "ok", detail: "Groq LLM active" },
    { label: "FII/DII Data", status: quality.fii_date ? "ok" : "warn", detail: quality.fii_date || "No flow data" },
    { label: "Market Data", status: quality.technical_date ? "ok" : "warn", detail: quality.technical_date || "No price data" },
  ];
  grid.innerHTML = cards.map(c => `
    <div class="platform-status-card">
      <span class="platform-status-dot ${c.status}"></span>
      <div><strong>${c.label}</strong><small>${c.detail}</small></div>
    </div>
  `).join("");
}

async function askAgent(question) {
  appendAgentMessage("user", question);
  const thinking = appendAgentMessage("agent", "Thinking through the dashboard context...", true);
  let answer = "";
  let source = "";

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 22000);
    const response = await fetch(AGENT_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      signal: controller.signal
    });
    clearTimeout(timer);
    if (response.ok) {
      const data = await response.json();
      answer = data.answer || "";
      source = data.source || "";
    } else {
      const err = await response.json().catch(() => ({}));
      answer = `Backend error: ${err.detail || response.statusText}`;
    }
  } catch {
    answer = "Could not reach the backend. Using local answers.";
  }

  if (!answer) {
    answer = localAgentAnswer(question);
    source = "local fallback";
  }

  if (source && source.includes("backend report")) {
    answer += "\n(LLM not available — used local analysis)";
  }

  thinking.textContent = answer;
  thinking.classList.remove("thinking");
}

function appendAgentMessage(type, text, thinking = false) {
  const log = $("#agentLog");
  const message = document.createElement("div");
  message.className = `agent-message ${type}`;
  if (thinking) message.classList.add("thinking");
  message.textContent = text;
  log.appendChild(message);
  log.scrollTop = log.scrollHeight;
  return message;
}

function localAgentAnswer(question) {
  const q = question.toLowerCase();
  const report = state.bundle.report;
  const summary = report.executive_summary;
  const scores = report.score_breakdown;
  const quality = report.data_quality || {};
  const tokens = tokenizeText(question);

  if (isDefinitionQuestion(question)) {
    const facts = retrieveLocalFacts(question, buildLocalGlossary(), 1);
    let answer = facts.map((fact) => fact.text).join(" ");
    if (tokens.has("volume") || tokens.has("participation") || tokens.has("liquidity")) {
      answer += ` Current Volume Flow score is ${Number(scores.Volume?.score || 0).toFixed(3)}; the strongest current volume signal is ${report.volume_analysis.highest_volume_stock} at ${Number(report.volume_analysis.highest_volume_ratio).toFixed(2)}x average volume.`;
    }
    return answer;
  }

  if (q.includes("why") || q.includes("reason") || q.includes("buy") || q.includes("outcome")) {
    return `The model says ${summary.recommendation} because ${summary.reason}. Overall score is ${Number(summary.overall_score).toFixed(3)}, confidence is ${Number(summary.confidence).toFixed(2)}%, and agreement is ${Number(summary.agreement).toFixed(1)}%.`;
  }

  if (q.includes("fresh") || q.includes("old") || q.includes("date")) {
    return `Freshness: price signals ${quality.technical_date || "n/a"}, volume ${quality.volume_date || "n/a"}, news ${quality.news_date || "n/a"}, economy ${quality.economic_date || "n/a"}, institutional flow ${quality.fii_date || "n/a"}.`;
  }

  if (q.includes("risk")) {
    return `Risk is ${summary.market_risk}. The score is ${Number(summary.overall_score).toFixed(3)} and confidence is ${Number(summary.confidence).toFixed(2)}%, so the model has a positive view but not maximum certainty.`;
  }

  if (q.includes("stock") || q.includes("strong")) {
    const best = state.bundle.stocks.slice().sort((a, b) => b.technicalScore - a.technicalScore)[0];
    return `${best.ticker} is currently strongest by price-signal score at ${best.technicalScore.toFixed(3)} with signal ${best.technicalSignal}.`;
  }

  if (q.includes("news")) {
    return `News score is ${Number(scores.News?.score || 0).toFixed(3)}. The news model is recency-aware, so older headlines have less effect.`;
  }

  if (q.includes("volume")) {
    return `Volume score is ${Number(scores.Volume?.score || 0).toFixed(3)}. Highest volume stock is ${report.volume_analysis.highest_volume_stock} at ${Number(report.volume_analysis.highest_volume_ratio).toFixed(2)}x average volume.`;
  }

  if (q.includes("economy") || q.includes("inflation") || q.includes("repo") || q.includes("gdp")) {
    const e = report.economic_analysis;
    return `Economy score is ${Number(scores.Economic?.score || 0).toFixed(3)}. Repo rate is ${e.repo_rate}%, GDP growth is ${e.gdp_growth}%, and inflation is ${e.inflation}%.`;
  }

  if (q.includes("institutional") || q.includes("fii") || q.includes("dii")) {
    const i = report.institutional_analysis;
    return `Institutional score is ${Number(scores.Institutional?.score || 0).toFixed(3)}. Latest net flow is Rs ${Number(i.net_flow).toFixed(2)} cr.`;
  }

  const facts = retrieveLocalFacts(question, buildLocalFacts());
  return `${facts.map((fact) => fact.text).join(" ")} Bottom line: current output is ${summary.recommendation}, score ${Number(summary.overall_score).toFixed(3)}, risk ${summary.market_risk}.`;
}

function isDefinitionQuestion(text) {
  const q = String(text).toLowerCase();
  const tokens = tokenizeText(q);
  return q.includes("what is")
    || q.includes("what are")
    || q.includes("what does")
    || tokens.has("define")
    || tokens.has("meaning")
    || tokens.has("mean")
    || tokens.has("means")
    || (tokens.has("explain") && !tokens.has("why") && !tokens.has("buy") && !tokens.has("sell"));
}

function buildLocalGlossary() {
  return [
    {
      title: "Volume analysis",
      keywords: "volume analysis volume flow define definition meaning participation liquidity average volume unusual trading",
      text: "Volume analysis studies trading participation. In PrismEdge, it compares each stock's current volume with its normal average volume to detect whether price moves are supported by real market activity. High relative volume makes a move more meaningful; weak volume makes a move less reliable."
    },
    {
      title: "Technical analysis",
      keywords: "technical analysis price signals define definition meaning rsi macd bollinger indicators",
      text: "Technical analysis reads price-based indicators such as MACD, RSI, Bollinger position, trend, and recent price behavior. It answers whether the market's price action currently looks bullish, bearish, or neutral."
    },
    {
      title: "News sentiment",
      keywords: "news sentiment analysis define definition meaning articles headlines finbert positive negative neutral",
      text: "News sentiment analysis converts recent financial headlines and articles into positive, neutral, or negative evidence. PrismEdge weights this by confidence and recency so old headlines have less effect on today's view."
    },
    {
      title: "Sector strength",
      keywords: "sector strength analysis define definition meaning sector score board momentum news index",
      text: "Sector strength combines recent sector index momentum with news sentiment when sector news is available. It is designed to show which parts of the market are leading or lagging."
    },
    {
      title: "Coverage",
      keywords: "coverage mean definition rows available data quality count current records",
      text: "Coverage means how much current data the system has for a section, such as the number of stocks, sectors, articles, or institutional records included in the latest analysis."
    },
    {
      title: "Overall score",
      keywords: "overall score mean definition weighted combined market direction",
      text: "Overall score is the weighted blend of price signals, news sentiment, volume flow, economy, and institutional flow. Positive values support a bullish outcome; negative values support a bearish outcome."
    },
    {
      title: "Confidence",
      keywords: "confidence score mean definition certainty reliability conviction model confidence evidence guarantee",
      text: "Confidence estimates how strongly the available evidence supports the current recommendation. It blends signal strength, agreement between analysis engines, and data coverage quality. A higher confidence score means the output is better supported, but it is not a guarantee of future market movement."
    },
    {
      title: "Agreement",
      keywords: "agreement score mean definition modules engines align same direction consensus technical news volume economy institutional",
      text: "Agreement score measures how many independent analysis engines point in the same direction. For example, if technicals, news, volume, economy, and institutional flow mostly support the same view, agreement is high. If they conflict, agreement is lower and the recommendation should be treated more cautiously."
    },
    {
      title: "Weighted contribution",
      keywords: "weighted contribution mean definition module weight effect score",
      text: "Weighted contribution is the actual effect a module has on the final score after applying that module's importance weight."
    },
    {
      title: "Volume ratio",
      keywords: "volume ratio mean definition average trading activity unusual participation",
      text: "Volume ratio compares current trading volume with normal volume. A value above 1.0 means participation is higher than usual."
    },
    {
      title: "Economy analysis",
      keywords: "economy economic macro analysis define definition meaning repo inflation gdp",
      text: "Economy analysis checks macro conditions such as repo rate, GDP growth, and inflation. It helps decide whether the broader economic backdrop supports or pressures the market."
    },
    {
      title: "Institutional flow",
      keywords: "institutional flow analysis define definition meaning fii dii net buying selling",
      text: "Institutional flow tracks whether FIIs and DIIs are net buyers or sellers. Positive net flow suggests large investors are adding money; negative net flow suggests they are reducing exposure."
    },
    {
      title: "Market risk",
      keywords: "market risk define definition meaning safe danger confidence agreement score",
      text: "Market risk summarizes how cautious the recommendation should be. PrismEdge uses signal agreement, model confidence, and final score strength to classify risk."
    },
    {
      title: "FII and DII",
      keywords: "fii dii mean definition institutional foreign domestic investors",
      text: "FII means Foreign Institutional Investors and DII means Domestic Institutional Investors. Their net flow shows whether large institutions are adding or removing money from the market."
    },
    {
      title: "Freshness",
      keywords: "freshness stale old latest current date data quality definition",
      text: "Freshness checks whether each section is using recent data. Stale sections are reduced in impact so old data does not dominate newer insights."
    }
  ];
}

function buildLocalFacts() {
  const report = state.bundle.report;
  const summary = report.executive_summary;
  const scores = report.score_breakdown;
  const quality = report.data_quality || {};
  const facts = [
    ...buildLocalGlossary(),
    {
      title: "Current recommendation",
      keywords: "recommendation signal score confidence agreement overall outcome market",
      text: `Current recommendation is ${summary.recommendation} with overall score ${Number(summary.overall_score).toFixed(3)}, confidence ${Number(summary.confidence).toFixed(2)}%, agreement ${Number(summary.agreement).toFixed(1)}%, and ${summary.market_risk} risk.`
    },
    {
      title: "Reason",
      keywords: "why reason explain because driver drivers contribution",
      text: `The model reason is: ${summary.reason}.`
    },
    {
      title: "Freshness",
      keywords: "fresh date stale old latest current coverage rows data quality",
      text: `Freshness: price signals ${quality.technical_date || "n/a"}, volume ${quality.volume_date || "n/a"}, news ${quality.news_date || "n/a"}, economy ${quality.economic_date || "n/a"}, institutional ${quality.fii_date || "n/a"}.`
    }
  ];

  Object.entries(scores).forEach(([module, values]) => {
    facts.push({
      title: module,
      keywords: `${module} score weight contribution signal module`,
      text: `${module} score is ${Number(values.score || 0).toFixed(3)}, weight is ${values.weight}%, and weighted contribution is ${Number(values.contribution || 0).toFixed(3)}.`
    });
  });

  const tech = report.technical_analysis || {};
  facts.push({
    title: "Tracked stocks",
    keywords: "stock stocks ticker strongest weakest best worst technical price rsi macd",
    text: `Best current stock is ${tech.best_stock || "n/a"} with score ${Number(tech.best_score || 0).toFixed(3)}; weakest is ${tech.worst_stock || "n/a"} with score ${Number(tech.worst_score || 0).toFixed(3)}.`
  });

  const news = report.news_analysis || {};
  facts.push({
    title: "News detail",
    keywords: "news sentiment headline article articles positive neutral negative sector",
    text: `News analysis used ${news.article_count ?? "n/a"} recent articles. Positive: ${news.positive_articles ?? "n/a"}, neutral: ${news.neutral_articles ?? "n/a"}, negative: ${news.negative_articles ?? "n/a"}. Best sector is ${news.best_sector || "n/a"}.`
  });

  const volume = report.volume_analysis || {};
  facts.push({
    title: "Volume detail",
    keywords: "volume participation trading ratio highest unusual average",
    text: `Highest volume stock is ${volume.highest_volume_stock || "n/a"} at ${Number(volume.highest_volume_ratio || 0).toFixed(2)}x average volume. Average volume ratio is ${Number(volume.average_ratio || 0).toFixed(2)}x.`
  });

  const economy = report.economic_analysis || {};
  facts.push({
    title: "Economy detail",
    keywords: "economy economic macro repo rate gdp growth inflation",
    text: `Macro snapshot: repo rate ${economy.repo_rate ?? "n/a"}%, GDP growth ${economy.gdp_growth ?? "n/a"}%, inflation ${economy.inflation ?? "n/a"}%, signal ${economy.signal || "n/a"}.`
  });

  const institutional = report.institutional_analysis || {};
  facts.push({
    title: "Institutional detail",
    keywords: "institutional fii dii fund flow buying selling net",
    text: `Institutional net flow is Rs ${Number(institutional.net_flow || 0).toFixed(2)} cr. Buyers: ${institutional.buyers ?? "n/a"}, sellers: ${institutional.sellers ?? "n/a"}.`
  });

  state.bundle.stocks.slice(0, 10).forEach((stock) => {
    facts.push({
      title: stock.ticker,
      keywords: `${stock.ticker} stock ticker technical price signal confidence volume rsi macd`,
      text: `${stock.ticker} has technical score ${stock.technicalScore.toFixed(3)}, signal ${stock.technicalSignal}, RSI ${stock.rsi.toFixed(1)}, volume ratio ${stock.volumeRatio.toFixed(2)}x, and latest close Rs ${formatCurrency.format(stock.close)}.`
    });
  });

  state.bundle.sectors.forEach((sector) => {
    facts.push({
      title: sector.sector,
      keywords: `${sector.sector} sector news sentiment score`,
      text: `${sector.sector} sector has news score ${Number(sector.newsScore || 0).toFixed(3)}, signal ${sector.signal}, and reason: ${sector.reason}.`
    });
  });

  return facts;
}

function retrieveLocalFacts(question, facts, limit = 3) {
  const questionTokens = tokenizeText(question);
  if (!questionTokens.size) return facts.slice(0, limit);

  const ranked = facts.map((fact) => {
    const haystack = `${fact.title} ${fact.keywords} ${fact.text}`.toLowerCase();
    const tokens = tokenizeText(haystack);
    let overlap = 0;
    questionTokens.forEach((token) => {
      if (tokens.has(token)) overlap += 1;
      if (haystack.includes(token)) overlap += 0.5;
    });
    return { score: overlap, fact };
  }).sort((a, b) => b.score - a.score);

  const selected = ranked.filter((item) => item.score > 0).slice(0, limit).map((item) => item.fact);
  return selected.length ? selected : facts.slice(0, limit);
}

function tokenizeText(text) {
  return new Set(
    String(text)
      .toLowerCase()
      .match(/[a-z0-9]+/g)
      ?.filter((token) => token.length > 2) || []
  );
}

function bindTooltips() {
  $$("[data-tip]").forEach((element) => {
    if (!element.getAttribute("aria-label")) {
      element.setAttribute("aria-label", element.dataset.tip);
    }
  });
}

function setApiState(title, detail, live) {
  $("#apiState").textContent = title;
  $("#apiDetail").textContent = detail;
  $("#apiPulse").classList.toggle("live", live);
}

function toast(message) {
  const toastEl = $("#toast");
  toastEl.textContent = message;
  toastEl.classList.add("show");
  clearTimeout(toastEl.timer);
  toastEl.timer = setTimeout(() => toastEl.classList.remove("show"), 2600);
}

function signalForScore(score) {
  if (score >= 0.6) return "STRONGLY BULLISH";
  if (score >= 0.2) return "BULLISH";
  if (score >= -0.2) return "CAUTIOUS";
  if (score >= -0.6) return "BEARISH";
  return "STRONGLY BEARISH";
}

function metricValue(sector, metric) {
  if (metric === "change") return Number.isFinite(Number(sector.changePct)) ? Number(sector.changePct) : null;
  if (metric === "volume") return Number.isFinite(Number(sector.volume)) ? Number(sector.volume) : null;
  if (Number.isFinite(Number(sector.strengthScore))) return Number(sector.strengthScore);
  return Number.isFinite(Number(sector.newsScore)) ? Number(sector.newsScore) : null;
}

function metricLabel(value, metric) {
  if (!Number.isFinite(value)) return "Awaiting news data";
  if (metric === "change") return `${signed(value)}%`;
  if (metric === "volume") return formatNumber.format(value);
  return Number(value).toFixed(3);
}

function signed(value) {
  return `${value >= 0 ? "+" : ""}${Number(value).toFixed(2)}`;
}

function signalFromScore(score) {
  if (!Number.isFinite(Number(score))) return "UNKNOWN";
  const value = Number(score);
  if (value >= 0.65) return "STRONGLY BULLISH";
  if (value >= 0.2) return "BULLISH";
  if (value > -0.2) return "CAUTIOUS";
  if (value > -0.65) return "BEARISH";
  return "STRONGLY BEARISH";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function debounce(fn, wait) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

function generatePDF() {
  if (!window.jspdf) {
    toast("PDF library is still loading or blocked. Try again in a moment.");
    return;
  }
  try {
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  const summary = state.bundle.report.executive_summary;
  const breakdown = state.bundle.report.score_breakdown;
  const tech = state.bundle.report.technical_analysis;
  const volume = state.bundle.report.volume_analysis;
  const news = state.bundle.report.news_analysis;
  const reasoning = state.bundle.report.ai_reasoning || "";
  const width = doc.internal.pageSize.getWidth();
  let y = 15;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(18);
  doc.text("PrismEdge AI", 14, y);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(120);
  doc.text("Indian Market Intelligence Report", 14, y + 6);
  doc.text(`Generated: ${new Date().toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}`, 14, y + 11);
  doc.setTextColor(0);
  y += 20;

  doc.setDrawColor(37, 52, 66);
  doc.line(14, y, width - 14, y);
  y += 8;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(13);
  doc.text("Executive Summary", 14, y);
  y += 7;

  doc.setFontSize(10);
  doc.setFont("helvetica", "normal");
  const rows = [
    ["Overall Bias", summary.recommendation || "--"],
    ["Overall Score", Number(summary.overall_score).toFixed(3)],
    ["Confidence", `${Number(summary.confidence).toFixed(2)}%`],
    ["Agreement", `${Number(summary.agreement).toFixed(1)}%`],
    ["Market Risk", summary.market_risk || "--"],
    ["Report Date", summary.date || "--"],
  ];
  rows.forEach(([label, value]) => {
    doc.setFont("helvetica", "bold");
    doc.text(label, 14, y);
    doc.setFont("helvetica", "normal");
    doc.text(String(value), 70, y);
    y += 6;
  });

  y += 2;
  doc.setFont("helvetica", "bold");
  doc.setFontSize(10);
  doc.text("Reason:", 14, y);
  y += 5;
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  const reasonLines = doc.splitTextToSize(summary.reason || "No reason available.", width - 28);
  doc.text(reasonLines, 14, y);
  y += reasonLines.length * 4.5 + 4;

  doc.setDrawColor(37, 52, 66);
  doc.line(14, y, width - 14, y);
  y += 8;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(13);
  doc.text("Score Breakdown", 14, y);
  y += 7;

  doc.setFontSize(9);
  doc.setFont("helvetica", "bold");
  doc.text("Module", 14, y);
  doc.text("Score", 75, y);
  doc.text("Weight", 105, y);
  doc.text("Contribution", 135, y);
  y += 5;
  doc.setFont("helvetica", "normal");
  Object.entries(breakdown).forEach(([module, data]) => {
    doc.text(module, 14, y);
    doc.text(Number(data.score).toFixed(3), 75, y);
    doc.text(`${data.weight}%`, 105, y);
    doc.text(Number(data.contribution).toFixed(3), 135, y);
    y += 5;
  });
  y += 4;

  doc.setDrawColor(37, 52, 66);
  doc.line(14, y, width - 14, y);
  y += 8;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(13);
  doc.text("Top Stocks by Technical Score", 14, y);
  y += 7;
  doc.setFontSize(9);
  doc.setFont("helvetica", "bold");
  doc.text("Ticker", 14, y);
  doc.text("Score", 50, y);
  doc.text("Signal", 80, y);
  doc.text("RSI", 115, y);
  doc.text("Volume Ratio", 145, y);
  y += 5;
  doc.setFont("helvetica", "normal");
  const topStocks = state.bundle.stocks
    .slice()
    .sort((a, b) => b.technicalScore - a.technicalScore)
    .slice(0, 10);
  topStocks.forEach((stock) => {
    doc.text(stock.ticker, 14, y);
    doc.text(stock.technicalScore.toFixed(3), 50, y);
    doc.text(stock.technicalSignal || "--", 80, y);
    doc.text(stock.rsi ? stock.rsi.toFixed(1) : "--", 115, y);
    doc.text(stock.volumeRatio ? `${stock.volumeRatio.toFixed(2)}x` : "--", 145, y);
    y += 5;
  });
  y += 4;

  doc.setDrawColor(37, 52, 66);
  doc.line(14, y, width - 14, y);
  y += 8;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(13);
  doc.text("AI Reasoning", 14, y);
  y += 6;
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  const reasoningLines = doc.splitTextToSize(reasoning || "No reasoning available.", width - 28);
  doc.text(reasoningLines, 14, y);
  y += reasoningLines.length * 4.5 + 6;

  if (y > 260) {
    doc.addPage();
    y = 15;
  }

  doc.setDrawColor(37, 52, 66);
  doc.line(14, y, width - 14, y);
  y += 6;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(8);
  doc.text("Disclaimer", 14, y);
  y += 4;
  doc.setFont("helvetica", "normal");
  doc.setFontSize(7);
  const disclaimer = doc.splitTextToSize(
    "PrismEdge AI is an analytics and educational tool only. It is not a SEBI-registered Investment Adviser or Research Analyst, and it does not provide personalised investment advice, research recommendations, directional calls, portfolio management, or any solicitation to trade securities. Market data, AI outputs, scores, and explanations may be incomplete, delayed, or incorrect. Investments and trading involve risk, including loss of capital. Verify all information independently and consult a qualified SEBI-registered adviser before making financial decisions.",
    width - 28
  );
  doc.text(disclaimer, 14, y);

  doc.save(`PrismEdge-AI-Report-${new Date().toISOString().slice(0, 10)}.pdf`);
  toast("PDF report exported.");
  } catch (err) {
    console.error("PDF generation failed:", err);
    toast("PDF export failed. Check console for details.");
  }
}

function initScrollReveal() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
        const metrics = entry.target.querySelectorAll(".metric");
        metrics.forEach((m) => m.classList.add("visible"));
      }
    });
  }, { threshold: 0.1, rootMargin: "0px 0px -40px 0px" });

  document.querySelectorAll(".reveal").forEach((el) => observer.observe(el));

  const metricObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) entry.target.classList.add("visible");
    });
  }, { threshold: 0.2 });

  document.querySelectorAll(".metric").forEach((el) => metricObserver.observe(el));
}

function initParticles() {
  const canvas = document.getElementById("particleCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  let particles = [];
  let animFrame;
  let paused = false;

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }

  function createParticle() {
    return {
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - 0.5) * 0.25,
      vy: (Math.random() - 0.5) * 0.25,
      r: Math.random() * 1.2 + 0.4,
      a: Math.random() * 0.3 + 0.08,
      c: ["54,211,153", "67,212,232", "168,139,255"][Math.floor(Math.random() * 3)],
    };
  }

  function initParticleArray() {
    const count = Math.min(Math.floor((canvas.width * canvas.height) / 30000), 30);
    particles = Array.from({ length: count }, createParticle);
  }

  function draw() {
    if (paused) { animFrame = requestAnimationFrame(draw); return; }
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    for (let i = 0; i < particles.length; i++) {
      const p = particles[i];
      p.x += p.vx;
      p.y += p.vy;
      if (p.x < 0) p.x = canvas.width;
      if (p.x > canvas.width) p.x = 0;
      if (p.y < 0) p.y = canvas.height;
      if (p.y > canvas.height) p.y = 0;

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, 6.28);
      ctx.fillStyle = `rgba(${p.c},${p.a})`;
      ctx.fill();

      for (let j = i + 1; j < particles.length; j++) {
        const p2 = particles[j];
        const dx = p.x - p2.x;
        const dy = p.y - p2.y;
        if (Math.abs(dx) > 120 || Math.abs(dy) > 120) continue;
        const d2 = dx * dx + dy * dy;
        if (d2 < 14400) {
          ctx.beginPath();
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.strokeStyle = `rgba(67,212,232,${0.05 * (1 - d2 / 14400)})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }

    animFrame = requestAnimationFrame(draw);
  }

  document.addEventListener("visibilitychange", () => {
    paused = document.hidden;
  });

  resize();
  initParticleArray();
  draw();

  window.addEventListener("resize", () => {
    resize();
    initParticleArray();
  });
}

const SCHEDULER_URL = API_BASE + "/scheduler/status";

function initScheduler() {
  const toggle = $("#schedulerToggle");
  const body = $("#schedulerBody");
  if (!toggle) return;

  toggle.addEventListener("click", () => {
    body.hidden = !body.hidden;
  });

  fetchSchedulerStatus();
  setInterval(fetchSchedulerStatus, 60000);
}

async function fetchSchedulerStatus() {
  const dot = $("#schedulerDot");
  const statusText = $("#schedulerStatusText");
  const freshnessEl = $("#schedulerFreshness");
  if (!dot) return;

  try {
    const res = await fetch(SCHEDULER_URL, { signal: AbortSignal.timeout(3000) });
    if (!res.ok) throw new Error(`${res.status}`);
    const data = await res.json();

    if (data.scheduler_running) {
      dot.className = "scheduler-dot running";
      statusText.textContent = data.is_market_hours ? "Market hours active" : "Off-hours mode";
    } else {
      dot.className = "scheduler-dot";
      statusText.textContent = "Scheduler stopped";
    }

    if (freshnessEl && data.freshness && data.freshness.length) {
      const jobLabels = {
        stocks: "Stocks",
        sectors: "Sectors",
        indicators: "Indicators",
        news: "News",
        nlp: "NLP Sentiment",
        fii_dii: "FII/DII",
        economic: "Economic",
        score_technical: "Tech Score",
        score_volume: "Volume Score",
        score_economic: "Econ Score",
        score_fii_dii: "FII Score",
        score_news: "News Score",
        risk_engine: "Risk Engine",
        report: "Report",
      };

      freshnessEl.innerHTML = data.freshness.map((f) => {
        const label = jobLabels[f.job] || f.job;
        const isStale = f.status === "error";
        const statusClass = isStale ? "stale" : "fresh";
        const timeStr = f.last_run ? new Date(f.last_run).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }) : "never";
        return `<div class="scheduler-freshness-row"><span>${label}</span><span class="${statusClass}">${timeStr} ${f.status === "error" ? "(!)" : ""}</span></div>`;
      }).join("");
    }
  } catch {
    dot.className = "scheduler-dot error";
    statusText.textContent = "Backend offline";
  }
}
