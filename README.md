# RideSafe - Traffic Accident Analysis & Prediction System

<div align="center">

**A web application for analyzing traffic accidents and predicting accident risk in Imus, Philippines**

[Features](#features) • [Setup](#setup) • [Architecture](#architecture) • [Usage](#usage)

</div>

---

## Overview

RideSafe is a traffic safety platform that uses historical incident data (2022–2024) and machine learning to help analyze accident patterns in Imus City. Users can explore interactive dashboards and heatmaps, run barangay-level risk predictions, download PDF summary reports, and ask questions via an optional RAG chatbot grounded in curated insights.

## Screenshots

<div align="center">
  <img src="static/screenshots/dashboard.jpg" alt="Dashboard" width="400">
   <img src="static/screenshots/offense.jpg" alt="offense" width="400">
  <img src="static/screenshots/heat-map.jpg" alt="Heatmap" width="400">
  <img src="static/screenshots/prediction.jpg" alt="Prediction" width="400">
  <img src="static/screenshots/brgy-predict.jpg" alt="brgy-predict" width="400">
  <img src="static/screenshots/report.jpg" alt="Report" width="400">
   <img src="static/screenshots/chatbot.jpg" alt="chatbot" width="400">
</div>

## Features

**Key capabilities:**

- **Accident prediction**: ML-powered risk assessment by barangay and hour of day using a Random Forest classifier
- **Interactive dashboards**: Dynamic bar graphs, heatmaps, and time-series charts built with Plotly and Folium
- **PDF reports**: Multi-section barangay summary (KPIs, hourly chart, historical breakdown, ML recommendations) — run a prediction first, then download
- **Geospatial analysis**: Accident density mapping using GeoJSON data of Imus barangays
- **Ask RideSafe**: In-dashboard RAG chatbot (`/#ask`, `/chat` redirects) with Gemini + pgvector retrieval, plus allowlisted live DB/ML tools for rankings and predictions
- **Sidebar dashboard**: Full-screen shell with Overview, Offense Analytics (glossary), Geospatial Heatmap, Predictions, and Ask RideSafe
- **Production-ready**: Postgres-backed data layer, startup caching, health checks, and rate limiting

## Tech Stack

- **Backend**: Flask (Python 3.12+)
- **Database**: PostgreSQL + pgvector (production / Docker) / SQLite (local fallback; dashboard only)
- **Machine learning**: Scikit-learn (Random Forest + SMOTE)
- **LLM / RAG**: Google Gemini (`gemini-embedding-001`, flash chat) via `GOOGLE_API_KEY`
- **Frontend**: HTML5, CSS3, JavaScript, Plotly.js
- **Mapping**: Folium, GeoPandas
- **Report generation**: pdfkit (wkhtmltopdf), Jinja2

## Setup Instructions

### Prerequisites

- **Python 3.12+**
- **traffic-incident.xlsx** in the project root (used once to seed the database)
- **wkhtmltopdf** (required for PDF generation locally; included in Docker image)
  - Windows: Download from [wkhtmltopdf.org](https://wkhtmltopdf.org/downloads.html)
  - macOS: `brew install wkhtmltopdf`
  - Linux: `apt-get install wkhtmltopdf`
  - Optional: set `WKHTMLTOPDF_PATH` if the binary is not on PATH

### Local development (SQLite)

1. **Clone and install**

   ```bash
   git clone https://github.com/Mich-Tapawan/RideSafe.git
   cd RideSafe
   python -m venv venv
   venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```

2. **Place** `traffic-incident.xlsx` in the project root.

3. **Seed the database** (creates `.data/ridesafe.db` if `DATABASE_URL` is not set)

   ```bash
   python -m scripts.seed_database
   ```

4. **Run the app**

   ```bash
   python app.py
   ```

5. **Open** `http://localhost:5000`

### Local development (Docker + Postgres)

1. Copy [`.env.example`](.env.example) to `.env` and set at least:

   ```bash
   GOOGLE_API_KEY=your_key_here
   ```

2. Start local Postgres (pgvector) + the app:

   ```bash
   docker compose up --build
   ```

   Compose always sets `DATABASE_URL` to the local `db` service (`postgresql://ridesafe:ridesafe@db:5432/ridesafe`). A Supabase URL in `.env` is ignored by Docker — use Render env vars for production.

Open `http://localhost:10000`. The web container seeds analytics, builds the RAG corpus (when `GOOGLE_API_KEY` is set), then starts Gunicorn.

Without `GOOGLE_API_KEY`, the dashboard still runs; `/chat` and `/api/chat` return a clear “not ready” / missing-key message.

### Supabase (Postgres + pgvector)

Use this when moving off Render’s free Postgres (or for any cloud DB).

1. In the [Supabase](https://supabase.com) project **RideSafe** → **Database** → **Extensions**, enable **`vector`** (pgvector).
2. **Project Settings** → **Database** → copy the **URI** connection string.
   - Prefer the **Transaction pooler** (port **6543**) for the web app (Gunicorn / Render).
   - Use the **Session** pooler or direct host for one-off troubleshooting if needed.
3. Set **`DATABASE_URL` on Render** (or any non-Compose host) — not in Docker Compose:

   ```bash
   DATABASE_URL=postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
   ```

   The app adds `sslmode=require` automatically for non-local hosts.
4. Seed + build RAG (first time, or after `--force`):

   ```bash
   python -m scripts.seed_database
   python -m scripts.build_rag_corpus
   ```

   Or restart the Docker/Render web service — startup seeds if empty and builds the
   RAG corpus in a background thread (so the web port binds immediately).

Startup creates analytics + RAG tables (`rag_documents`, `rag_chunks` with `vector(768)`), and an HNSW index for cosine search when permitted.

### Production (Render + Supabase)

Deploy with the included [`render.yaml`](render.yaml) Blueprint. It provisions a **Docker web service** only — **Postgres is on Supabase**.

In the Render dashboard, set:

| Variable | Notes |
| -------- | ----- |
| `DATABASE_URL` | Supabase **Transaction pooler** URI (port 6543) |
| `GOOGLE_API_KEY` | Required for Ask RideSafe / RAG corpus |
| `SECRET_KEY` | Strong random value in production |
| `CHAT_ADMIN_PASSWORD` | Optional override |

Health checks use `/health`.

The Docker entrypoint starts Gunicorn immediately. On import the app seeds analytics if empty, warms caches, and builds the RAG corpus in a **background thread** (idempotent; skips when already populated). Chat may be briefly unavailable until embeddings finish.

On **Render free**, Ask RideSafe runs in lean mode (`RENDER=true`): prefer live tools over embedding when possible, shorter Gemini timeouts, and Gunicorn worker recycling — ask concise questions if a request fails.

On **Render free**, Ask RideSafe runs in lean mode (`RENDER=true`): prefer live tools over embedding when possible, shorter Gemini timeouts, and Gunicorn worker recycling — ask concise questions if a request fails.

### Keeping the free tier awake

Render’s free web service sleeps after ~15 minutes of idle traffic. To reduce cold starts:

1. **GitHub Actions (included)** — [`.github/workflows/keep-alive.yml`](.github/workflows/keep-alive.yml) pings `/health` every 10 minutes.
   - After deploy, set a repository **variable** (or secret): `RENDER_URL` = `https://your-service.onrender.com` (no trailing slash).
   - Path: GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **Variables** → New variable.
   - You can also run it manually under **Actions** → **Keep Render awake** → **Run workflow**.
2. **UptimeRobot (optional)** — Create an HTTP monitor on `https://your-service.onrender.com/health` every 5–10 minutes.

Always ping **`/health`**, not `/` (the homepage is expensive to generate).

## Environment variables

| Variable | Description | Default |
| -------- | ----------- | ------- |
| `DATABASE_URL` | Postgres URI (Supabase pooler or local). Non-local hosts get `sslmode=require` | SQLite at `.data/ridesafe.db` |
| `GOOGLE_API_KEY` | Gemini API key for embeddings + chat | unset (chat unavailable) |
| `SECRET_KEY` | Flask session secret (admin chat mode) | dev default in code |
| `CHAT_ADMIN_PASSWORD` | Ask RideSafe admin unlock password | `RideSafe2026!` |
| `GEMINI_EMBED_MODEL` | Embedding model name | `gemini-embedding-001` |
| `GEMINI_CHAT_MODEL` | Chat model name | `gemini-flash-latest` |
| `GEMINI_CHAT_FALLBACKS` | Comma-separated fallbacks on 429/503 | `gemini-flash-lite-latest,gemini-3.5-flash-lite,gemini-3.1-flash-lite` |
| `DB_POOL_SIZE` | SQLAlchemy pool size (session mode only) | `2` |
| `DB_MAX_OVERFLOW` | SQLAlchemy max overflow | `2` |
| `DB_POOL_RECYCLE` | Recycle connections after N seconds | `300` |
| `WKHTMLTOPDF_PATH` | Path to wkhtmltopdf binary | Auto-detected |
| `WEB_CONCURRENCY` | Gunicorn worker count | `1` |
| `LOG_LEVEL` | Python log level | `INFO` |
| `FLASK_DEBUG` | Enable Flask debug mode (`1` to enable) | off |
| `EXCEL_FILE_PATH` | Path to xlsx for seeding | `traffic-incident.xlsx` |

Do not commit API keys; keep `.env` gitignored. See [`.env.example`](.env.example).

## Data updates

Runtime reads from the database, not the xlsx file. To refresh data:

1. Update `traffic-incident.xlsx`
2. Force re-seed:

   ```bash
   python -m scripts.seed_database --force
   ```

3. Rebuild the RAG corpus (Postgres + `GOOGLE_API_KEY` required):

   ```bash
   python -m scripts.build_rag_corpus --force
   ```

   On Render, run the same commands via the shell, or redeploy after clearing the relevant tables.

## Architecture

On startup the app: initializes the DB (ensures `vector` extension + tables + HNSW index on Postgres/Supabase) → seeds from xlsx (if empty) → loads the ML model → precomputes city-wide hourly averages → warms the dashboard HTML cache → builds the RAG corpus in the background if empty.

The homepage and barangay list are served from in-memory cache. API endpoints query Postgres/SQLite. PDF reports combine DB incident history with ML predictions. Chat retrieves embedded insight chunks via pgvector cosine search and may call allowlisted tools (incident rankings, offense breakdowns, monthly totals, barangay summaries, ML hour risk) — never free-form SQL — then answers with Gemini.

### Project structure

```
RideSafe/
├── app.py                        # Flask application & routes
├── traffic-incident.xlsx         # Source data for DB seeding
├── Dockerfile                    # Production image (wkhtmltopdf, GDAL, Gunicorn)
├── docker-compose.yml            # Local Postgres + web (always uses Compose DB)
├── render.yaml                   # Render Blueprint (web; DATABASE_URL → Supabase)
├── .env.example                  # Env template (Gemini; Supabase URL for Render)
├── requirements.txt
├── Procfile
│
├── scripts/
│   ├── db.py                     # SQLAlchemy models & session (incl. RAG tables)
│   ├── repository.py             # DB query helpers
│   ├── seed_database.py          # xlsx → DB import
│   ├── build_rag_corpus.py       # Insight docs + Gemini embeddings → pgvector
│   ├── rag.py                    # Embed, retrieve, answer (+ tool calling)
│   ├── chat_tools.py             # Allowlisted live DB/ML chat tools
│   ├── dashboard_insights.py     # City KPIs / rankings / barangay insight cards
│   ├── cache.py                  # Dashboard warmup cache
│   ├── model.py                  # Random Forest prediction model
│   ├── bar_graph.py              # Plotly trend charts
│   ├── heat_map.py               # Folium geographic visualization
│   ├── chart.py                  # Time-series charts
│   ├── barangay_list.py          # Barangay list from DB
│   ├── month_data.py             # Monthly statistics
│   └── summary_report.py         # PDF report data assembly
│
├── templates/
│   ├── index.html                # Sidebar dashboard shell
│   ├── chat.html                 # Legacy redirect helper
│   ├── partials/                 # chat_panel, admin_modal
│   └── pdf_template.html
│
└── static/
    ├── assets/
    ├── js/                       # index.js, chat.js
    └── style/
```

## API Endpoints

| Endpoint                       | Method | Description                                                       |
| ------------------------------ | ------ | ----------------------------------------------------------------- |
| `/health`                      | GET    | Health check (`{"status": "ok"}`)                               |
| `/`                            | GET    | Sidebar dashboard (Overview / Offense / Heatmap / Predictions / Ask); hashes `#overview` `#offense` `#heatmap` `#predict` `#ask` |
| `/chat`                        | GET    | Redirects to `/?view=ask` (Ask RideSafe view)                     |
| `/api/chat`                    | POST   | RAG + live tools (`message`); guest limit 3/hour; admin unlimited |
| `/api/chat/status`             | GET    | `{ admin, user_limit }` session status                            |
| `/api/chat/admin/login`        | POST   | Unlock admin (`password`)                                         |
| `/api/chat/admin/logout`       | POST   | Exit admin mode                                                   |
| `/api/dashboard/insights`      | GET    | Cached city KPIs, hotspot/peak-risk rankings, hour-risk series    |
| `/api/dashboard/barangay-insight/<barangay>` | GET | Compact barangay insight (`?hour=` optional)               |
| `/getMonthData`                | POST   | Monthly accident statistics (`year`, `month`)                     |
| `/predict`                     | POST   | ML accident probability (`barangay`, `hour`)                      |
| `/getBarangayList`             | GET    | List of barangays from incident data                              |
| `/getSummaryReport/<barangay>` | GET    | PDF summary report (`?hour=8` optional, highlights selected hour) |

Rate limits: `/` — 30/min; `/getSummaryReport` — 10/min; `/api/chat` — **3/hour** for guests, effectively unlimited for admin session.

## Machine Learning Model

The prediction model uses:

- **Algorithm**: Random Forest Classifier
- **Features**: Barangay, hour of day, peak hour indicator
- **Data balance**: SMOTE (Synthetic Minority Over-sampling Technique)
- **Training data**: Traffic incidents from 2022–2024
- **Artifacts**: `scripts/accident_prediction_model.pkl`, `scripts/barangay_encoder.pkl`

Retrain offline with `AccidentModel.train_and_save_model()` and redeploy the pickle files.

## License

This project is licensed under the MIT License — see the LICENSE file for details.

## Acknowledgments

- Traffic accident data from Imus City
- Built with Flask and Scikit-learn
- Interactive visualizations powered by Plotly and Folium
