# CubsEdge — Deployment Guide

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌───────────────┐
│  cubsstats.live  │────→│   Vercel / CDN   │     │  MLB Stats API│
│   (browser)      │     │   (static SPA)   │     │  (free, no key)│
└────────┬────────┘     └──────────────────┘     └───────┬───────┘
         │ /api/*                                         │
         ▼                                                │
┌──────────────────┐     ┌──────────────────┐            │
│  Railway / Render│     │   Scheduler      │────────────┘
│  FastAPI + Gunicorn     │   (APScheduler)  │
│  :8000           │     │   cron jobs      │
└────────┬────────┘     └──────────────────┘
         │
         ▼
┌──────────────────┐     ┌──────────────────┐
│   SQLite DB      │     │  ML Models       │
│   /app/data/     │     │  /app/models/    │
└──────────────────┘     └──────────────────┘
```

## Quick Start (Local)

```bash
# Backend
cd backend
pip install -r requirements.txt
python -m scripts.seed_historical    # One-time: load 2024-2025 data
python -m scripts.seed_benchmarks    # One-time: compute benchmarks
uvicorn app.main:app --reload        # API on :8000

# Frontend
cd frontend
npm install
npm run dev                          # Dev server on :5173

# Scheduler (optional — runs cron jobs locally)
cd backend
python -m scripts.scheduler
```

## Quick Start (Docker)

```bash
# Build and run API + scheduler
docker compose up -d

# First time: seed historical data
docker compose --profile seed run seed

# View logs
docker compose logs -f api
docker compose logs -f scheduler
```

## Deploy to Railway

### Backend API
1. Create a new Railway project
2. Connect your Git repo, set root directory to `backend/`
3. Railway auto-detects the Dockerfile
4. Set environment variables:
   ```
   DATABASE_URL=sqlite:////app/data/cubsedge.db
   ENVIRONMENT=production
   CORS_ORIGINS=https://cubsstats.live
   ANTHROPIC_API_KEY=sk-ant-...
   ```
5. Add a persistent volume mounted at `/app/data`
6. Deploy — Railway uses `railway.toml` for config

### Scheduler Worker
1. In the same Railway project, add a new service
2. Same repo + Dockerfile
3. Override start command: `python -m scripts.scheduler`
4. Same env vars + same volume mount at `/app/data`

### Seed Data (one-time)
```bash
railway run python -m scripts.seed_historical
railway run python -m scripts.seed_benchmarks
```

## Deploy to Render

```bash
# Uses render.yaml blueprint
render blueprint launch
```

Or manually:
1. Create Web Service → Docker → `backend/Dockerfile`
2. Create Worker → Docker → cmd: `python -m scripts.scheduler`
3. Create Static Site → `frontend/` → build: `npm run build` → publish: `dist/`
4. Add persistent disk to API + Worker (mount `/app/data`)

## Deploy Frontend to Vercel

```bash
cd frontend
npx vercel --prod
```

Or connect Git repo:
1. Import repo in Vercel, set root directory to `frontend/`
2. Framework: Vite
3. Build command: `npm run build`
4. Output: `dist/`
5. Add rewrite rule: `/api/:path*` → `https://YOUR-BACKEND-URL/api/:path*`

### Domain Setup (cubsstats.live)
1. In Vercel: Settings → Domains → Add `cubsstats.live`
2. In your DNS provider, add:
   - `A` record: `76.76.21.21` (Vercel)
   - `CNAME` for `www`: `cname.vercel-dns.com`
3. Vercel auto-provisions SSL

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | SQLite path (production: `sqlite:////app/data/cubsedge.db`) |
| `ENVIRONMENT` | Yes | `development` or `production` |
| `CORS_ORIGINS` | Yes | Comma-separated allowed origins |
| `ANTHROPIC_API_KEY` | No | Claude API key for editorial generation (falls back to data-driven text) |
| `VITE_API_URL` | No | Frontend: backend URL (empty = use Vercel rewrites) |

## Cron Schedule (all times Central)

| Job | Schedule | What it does |
|-----|----------|-------------|
| Game Watcher | Every 15 min, 4PM-1AM | Polls MLB API, triggers post-game pipeline on Final |
| Daily Pass 2 | 10:00 AM | Statcast + FanGraphs refresh |
| Statcast Backfill | 10:30 AM | Fill gaps for games missing pitch data |
| Weekly Refresh | Sunday midnight | Full league benchmarks + ML retrain + editorials |

## Pipeline Flow (post-game)

```
Game goes Final (detected by game_watcher_tick)
  → Fetch box score from MLB Stats API
  → Parse pitcher + hitter game stats
  → Update team season aggregates
  → Refresh Cubs player percentile ranks
  → Generate Daily Takeaway editorial
  → All API endpoints reflect new data
```

## E2E Test

```bash
cd backend
python -m scripts.test_pipeline
```

Tests the full pipeline: game detection → box score → team stats → benchmarks → divergence → editorial → all API endpoints.

## Monitoring

- `GET /health` — Backend health check
- `GET /api/predictions/model-status` — ML model training status
- `GET /api/editorials/latest` — Most recent editorial (confirms pipeline ran)
- Docker: `docker compose logs -f scheduler` for cron job output
