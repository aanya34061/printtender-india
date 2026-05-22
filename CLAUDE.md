# PrintTender India

PrintTender India is a zero-cost government tender aggregator for the Indian printing press industry. It fetches printing-related tenders from free public Indian government sources every 6 hours, normalizes and deduplicates them into PostgreSQL on Supabase, exposes search and alert APIs through FastAPI on Render, and serves a React dashboard on Vercel with Resend email alerts.

## Architecture

Sources -> Fetcher -> Processor -> DB+API -> Frontend

- Sources: CPPP XML, GeM SPA, MP, UP, Maharashtra, Rajasthan, and TenderDekho public pages.
- Fetcher: httpx, BeautifulSoup, lxml, and Playwright collectors with printing keyword filtering.
- Processor: normalization, date parsing, tagging, deduplication, and persistence preparation.
- DB+API -> Frontend: Supabase Postgres plus FastAPI routes consumed by the Vite React dashboard.

## Directory Map

- `backend/app`: FastAPI application package.
- `backend/app/api`: REST routers for tenders, alerts, and stats.
- `backend/app/fetchers`: Source-specific tender collection logic.
- `backend/app/processing`: Normalization, deduplication, and keyword tagging.
- `backend/app/tasks`: Celery app and scheduled fetch jobs.
- `backend/app/alerts`: Resend email delivery helpers.
- `backend/migrations`: SQL schema bootstrap files for Supabase.
- `backend/tests`: Backend tests and parser fixtures.
- `frontend/src`: React dashboard source.
- `frontend/src/components`: Reusable search, filter, tender, alert, and stats UI.
- `frontend/src/hooks`: TanStack Query hooks for API reads.
- `frontend/src/store`: Zustand filter state.
- `frontend`: Vite, Tailwind, and Vercel configuration.

## Common Commands

- Run API: `cd backend && uvicorn app.main:app --reload`
- Run worker: `cd backend && celery -A app.tasks.celery_app.celery_app worker --beat --loglevel=info`
- Run tests: `cd backend && pytest`
- Manually trigger a fetch: `cd backend && python -c "import asyncio; from app.tasks.fetch_job import run_fetch_cycle; print(asyncio.run(run_fetch_cycle()))"`

## Required Env Vars

- `DATABASE_URL`
- `REDIS_URL`
- `RESEND_API_KEY`
- `APP_ENV`
- `FETCH_INTERVAL_HOURS`

## Rules Claude Must Always Follow

- Never hardcode env vars. Use `pydantic-settings`.
- All DB queries must be async SQLAlchemy 2.0 style.
- All scrapers must have random 2-4 second delay between requests.
- Never commit to main. Use feature branches.
- Run `pytest` before marking any task complete.
- Free tier limits: Supabase 500MB, Upstash 10k req/day, Resend 3k/month.
