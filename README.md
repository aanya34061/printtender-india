# PrintTender India

> **Zero-cost government tender aggregator for the Indian printing press industry.**

Automatically fetches printing-related tenders from free public Indian government portals every 6 hours, normalises and deduplicates them into PostgreSQL, and serves a searchable React dashboard with email alerts — all on free-tier infrastructure.

---

## Architecture

```
Sources → Fetchers → Processor → DB → API → Frontend
```

| Layer | Technology |
|-------|-----------|
| **Sources** | CPPP (XML), GeM (Playwright SPA), MP · UP · Maharashtra · Rajasthan state portals |
| **Fetching** | httpx, BeautifulSoup4, lxml, Playwright Chromium |
| **Processing** | Normalisation, date parsing, keyword tagging, rapidfuzz deduplication |
| **Database** | Supabase PostgreSQL (async SQLAlchemy 2.0) |
| **API** | FastAPI + Celery + Redis |
| **Frontend** | React 18 + Vite + TailwindCSS 3 + TanStack Query 5 + Zustand 5 |
| **Email** | Resend (welcome, daily digest, urgent alerts) |
| **Deploy** | Render (API + Worker + Scheduler) · Vercel (Frontend) |

---

## Features

- Full-text search across all tenders (PostgreSQL `tsvector`)
- Filter by state (37 states/UTs), portal, category, and deadline window
- Deadline countdown badges (red/orange/green) and value formatting (₹ Lakh / Cr)
- Per-portal "How to Apply" step-by-step guide (CPPP / GeM / State portals)
- Email alert subscriptions with daily/weekly digest and urgent 72-hour alerts
- Automatic deduplication via fuzzy title matching
- Auto-fetch every 6 hours via Celery Beat

---

## Local Development

### Prerequisites
- Python 3.11+, Docker, Node 18+

### Quick Start (Docker)

```bash
git clone https://github.com/YOUR_USERNAME/printtender-india.git
cd printtender-india
bash scripts/setup.sh
docker compose up
```

API: http://localhost:8000
Docs: http://localhost:8000/docs

### Manual Setup

**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium --with-deps
cp .env.example .env          # fill in DATABASE_URL, REDIS_URL, RESEND_API_KEY
uvicorn app.main:app --reload
```

**Worker** (separate terminal)
```bash
cd backend
source .venv/bin/activate
celery -A app.tasks.celery_app.celery_app worker --beat --loglevel=info
```

**Frontend**
```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

**Trigger a manual fetch**
```bash
cd backend
python -c "import asyncio; from app.tasks.fetch_job import run_fetch_cycle; print(asyncio.run(run_fetch_cycle()))"
```

**Run tests**
```bash
cd backend
pytest tests/ -v
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string (asyncpg-compatible) |
| `REDIS_URL` | Yes | Redis connection string |
| `RESEND_API_KEY` | Yes | Resend.com API key for email alerts |
| `APP_ENV` | No | `development` or `production` (default: `development`) |
| `FETCH_INTERVAL_HOURS` | No | Hours between automatic fetches (default: `6`) |
| `MAX_TENDERS_PER_KEYWORD` | No | Cap per keyword per run (default: `100`) |
| `REQUEST_DELAY_SECONDS` | No | Polite delay between requests (default: `3`) |

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check + env |
| `GET` | `/tenders` | Search tenders (q, state, portal, category, days, page, limit) |
| `GET` | `/tenders/{id}` | Single tender + apply_steps |
| `GET` | `/tenders/count` | Count matching tenders |
| `GET` | `/stats` | Dashboard stats |
| `GET` | `/stats/portals/status` | Last fetch per portal |
| `POST` | `/alerts/subscribe` | Create email alert subscription |
| `DELETE` | `/alerts/{id}` | Unsubscribe (email must match) |

---

## Deployment

See [DEPLOY.md](./DEPLOY.md) for the full step-by-step deployment checklist.

**Quick summary:**
1. Local dev: use `backend/.env.example` defaults with Docker Compose Postgres + Redis
2. Production: Supabase → copy `DATABASE_URL`, Upstash → copy `REDIS_URL`, Resend → copy `RESEND_API_KEY`
3. Push to GitHub
4. Render → import `render.yaml` → set env vars → deploy 3 services
5. Vercel → import `frontend/` → set `VITE_API_BASE_URL` → deploy
6. UptimeRobot → monitor `/health` every 5 min

---

## Free Tier Limits

| Service | Limit |
|---------|-------|
| Supabase | 500 MB DB · 2 GB bandwidth |
| Upstash Redis | 10,000 req/day |
| Resend | 3,000 emails/month |
| Render | 750 hrs/month per service |
| Vercel | Unlimited static · 100 GB bandwidth |

---

## Project Structure

```
printtender-india/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers (tenders, alerts, stats)
│   │   ├── alerts/       # Resend email sender
│   │   ├── fetchers/     # CPPP, GeM, State portal scrapers
│   │   ├── processing/   # Normaliser, deduplicator, tagger
│   │   ├── tasks/        # Celery app + fetch job
│   │   ├── config.py     # pydantic-settings
│   │   ├── database.py   # SQLAlchemy async engine
│   │   ├── models.py     # ORM models
│   │   ├── schemas.py    # Pydantic schemas
│   │   └── main.py       # FastAPI app
│   ├── migrations/       # SQL bootstrap scripts
│   ├── tests/            # pytest test suite
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/   # React UI components
│   │   ├── hooks/        # TanStack Query hooks
│   │   └── store/        # Zustand filter store
│   ├── vercel.json
│   └── package.json
├── scripts/
│   └── setup.sh          # One-command local setup
├── docker-compose.yml
├── render.yaml
├── DEPLOY.md
└── README.md
```

---

## License

MIT — free to use, modify, and deploy.
