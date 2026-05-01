# PrintTender India

PrintTender India aggregates Indian government printing tenders into a searchable dashboard with email alerts.

## Stack

- Backend: FastAPI, async SQLAlchemy 2.0, PostgreSQL, Celery, Redis
- Scraping: httpx, Playwright Chromium, BeautifulSoup4, lxml
- Processing: pandas, rapidfuzz, dateparser
- Frontend: React 18, Vite 5, TailwindCSS 3, TanStack Query 5, Zustand 5
- Deploy: Render, Vercel, Supabase, Upstash, Resend

## Local Backend

```bash
cd backend
cp .env.example .env
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload
```

## Local Frontend

```bash
cd frontend
npm install
npm run dev
```

## Fetch Tenders

```bash
cd backend
celery -A app.tasks.celery_app.celery_app worker --beat --loglevel=info
```
