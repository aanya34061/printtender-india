# PrintTender India — Deployment Checklist

Step-by-step guide to deploy the full stack for free using Supabase + Upstash + Resend + Render + Vercel.

---

## Prerequisites

- GitHub account (repo pushed)
- Accounts on: Supabase, Upstash, Resend, Render, Vercel (all free tiers)

---

## 1 — External Services Setup

### Supabase (PostgreSQL)
- [ ] Go to https://supabase.com → New project
- [ ] Wait for project to provision (~2 min)
- [ ] Go to **Settings → Database → Connection string (URI)**
- [ ] Copy the `postgresql://...` URL
- [ ] If you use a pooler hostname (`*.pooler.supabase.com`), copy the full pooled connection string exactly as Supabase shows it, including the correct username format and port
- [ ] Add `?sslmode=require` to the end if not present
- [ ] Save as `DATABASE_URL`

### Upstash (Redis)
- [ ] Go to https://upstash.com → Create Database → Redis
- [ ] Choose the region closest to your Render region
- [ ] Copy **Redis URL** (starts with `rediss://`)
- [ ] Save as `REDIS_URL`

### Resend (Email)
- [ ] Go to https://resend.com → API Keys → Create API Key
- [ ] Optionally verify your sending domain (or use `onboarding@resend.dev` for testing)
- [ ] Copy API key (starts with `re_`)
- [ ] Save as `RESEND_API_KEY`

---

## 2 — Push Code to GitHub

- [ ] Create a new GitHub repository (public or private)
- [ ] Push code:
  ```bash
  git remote add origin https://github.com/YOUR_USERNAME/printtender-india.git
  git push origin main --tags
  ```

---

## 3 — Deploy Backend on Render

- [ ] Go to https://render.com → New → **Blueprint** → Connect your GitHub repo
- [ ] Render detects `render.yaml` automatically and shows 3 services
- [ ] Before deploying, create the **Environment Group**:
  - Go to **Environment → Environment Groups → New Group**
  - Name: `printtender-env`
  - Add variables:
    | Key | Value |
    |-----|-------|
    | `DATABASE_URL` | *(your Supabase URL)* |
    | `REDIS_URL` | *(your Upstash URL)* |
    | `RESEND_API_KEY` | *(your Resend key)* |
- [ ] Deploy all 3 services: `printtender-api`, `printtender-worker`, `printtender-scheduler`
- [ ] Wait for `printtender-api` build to complete (~5–10 min)

### Initialise the database
- [ ] Go to Render → `printtender-api` → **Shell**
- [ ] Run:
  ```bash
  python -c "import asyncio; from app.database import create_tables; asyncio.run(create_tables())"
  ```
- [ ] Confirm tables created with no errors

### Trigger first fetch
- [ ] In the same Render Shell, run:
  ```bash
  python -c "import asyncio; from app.tasks.fetch_job import run_fetch_cycle; print(asyncio.run(run_fetch_cycle()))"
  ```
- [ ] Confirm a positive number of tenders fetched

---

## 4 — Deploy Frontend on Vercel

- [ ] Go to https://vercel.com → New Project → Import from GitHub
- [ ] Select the `printtender-india` repo
- [ ] Set **Root Directory** to `frontend`
- [ ] Set **Framework Preset** to `Vite`
- [ ] Under **Environment Variables**, add:
  | Key | Value |
  |-----|-------|
  | `VITE_API_BASE_URL` | `https://printtender-api.onrender.com` |
- [ ] Click **Deploy** — build takes ~1 min
- [ ] Note your Vercel URL (e.g. `https://printtender-india.vercel.app`)

---

## 5 — Smoke Test

- [ ] Visit your Vercel URL
- [ ] Search for `"printing"` — tenders should appear
- [ ] Click a tender → **View Details** → apply steps should be visible
- [ ] Subscribe with a test email → check inbox for welcome email
- [ ] Visit `https://printtender-api.onrender.com/health` → `{"status":"ok","env":"production"}`
- [ ] Visit `https://printtender-api.onrender.com/docs` → Swagger UI loads

---

## 6 — Keep Render Free Tier Awake

Render free tier web services spin down after 15 minutes of inactivity.

- [ ] Go to https://uptimerobot.com → New Monitor
  - Monitor Type: HTTP(s)
  - URL: `https://printtender-api.onrender.com/health`
  - Monitoring Interval: **5 minutes**
- [ ] Save monitor — this keeps the API warm 24/7

---

## Free Tier Limits Reference

| Service | Free Limit | Notes |
|---------|-----------|-------|
| Supabase | 500 MB storage, 2 GB bandwidth | Pause after 1 week inactivity |
| Upstash Redis | 10,000 req/day | ~1,667 fetches/day |
| Resend | 3,000 emails/month | 100/day |
| Render Web | 750 hrs/month | Spins down after 15 min idle |
| Render Worker | 750 hrs/month | Always-on while active |
| Vercel | Unlimited for static | 100 GB bandwidth |

---

## Troubleshooting

**API returns 500 on startup**
→ Check Render logs; confirm `DATABASE_URL` is correct and DB is reachable.

**No tenders appearing**
→ Open Render Shell → run the fetch command manually → check `fetch_logs` table in Supabase.

**Emails not sending**
→ Verify `RESEND_API_KEY` is set and the sending domain is verified in Resend dashboard.

**Vercel build fails**
→ Ensure `VITE_API_BASE_URL` is set in Vercel environment variables.
