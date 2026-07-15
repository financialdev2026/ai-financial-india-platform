# PrismEdge AI Frontend

Interactive website for the AI Financial Market Intelligence & Risk Analysis Platform.

## Run

```bat
npm run dev
```

Open `http://localhost:5173`.

The site first loads `data/bundle.json`, which is generated from the backend database, CSV files, `dashboard.json`, and `market_report.json`. It also tries to refresh from `http://localhost:8000/dashboard/` when the FastAPI backend is running.

## Included Views

- Market overview with recommendation, risk, confidence, agreement, and score gauge
- Risk-engine trend chart with line, bar, and area modes
- Weight simulator for Technical, News, Volume, Economic, and Institutional modules
- Stock explorer with search, sorting, price charts, RSI, volume, and technical scores
- Sector sentiment and momentum board
- News sentiment feed with sector and sentiment filters
- AI reasoning and backend coverage panels
- Dedicated analysis pages: `technical.html`, `news.html`, `volume.html`, `economy.html`, and `institutional.html`

## Live API

Start the backend API first:

```bat
..\backend\start_api.bat
```

Then start the frontend:

```bat
npm run dev
```

The command center and dedicated analysis pages try FastAPI first and fall back to `data/bundle.json` if the backend is offline.

## PrismEdge Agent

The agent always answers from the local dashboard/report context. For open-ended questions beyond the report, set a Gemini API key before starting the backend:

```bat
set GEMINI_API_KEY=your_gemini_api_key_here
set PRISMEDGE_AGENT_MODEL=gemini-1.5-flash
```

PowerShell:

```powershell
$env:GEMINI_API_KEY="your_gemini_api_key_here"
$env:PRISMEDGE_AGENT_MODEL="gemini-1.5-flash"
```

Then start the FastAPI backend. If only `GEMINI_API_KEY` exists, PrismEdge automatically uses Gemini. Without this key, the agent uses the built-in PrismEdge retrieval and explanation fallback.

## Firebase Auth Hook

Authentication is intentionally not hardcoded. Copy `firebase-config.example.js` to `firebase-config.js`, fill in your Firebase project values, and connect Firebase custom claims to the role hierarchy:

- `viewer`: read-only dashboard access
- `analyst`: dashboard, exports, and simulations
- `admin`: full access including users and pipeline controls
