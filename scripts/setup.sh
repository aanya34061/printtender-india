#!/usr/bin/env bash
# PrintTender India — one-command local setup
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
COMPOSE="docker compose"

echo "==> PrintTender India — Local Setup"
echo ""

# 1. Copy .env if not present
if [ ! -f "$BACKEND_DIR/.env" ]; then
  echo "[1/5] Creating backend/.env from .env.example ..."
  cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  echo "      ✓ Edit backend/.env and add your DATABASE_URL, REDIS_URL, RESEND_API_KEY"
  echo ""
else
  echo "[1/5] backend/.env already exists — skipping copy."
fi

# 2. Start postgres + redis
echo "[2/5] Starting db and redis containers ..."
cd "$REPO_ROOT"
$COMPOSE up -d db redis
echo "      Waiting for postgres to be ready ..."
until $COMPOSE exec db pg_isready -U printtender -q 2>/dev/null; do
  sleep 1
done
echo "      ✓ postgres is ready."
echo ""

# 3. Build backend image
echo "[3/5] Building backend Docker image ..."
$COMPOSE build api
echo "      ✓ Image built."
echo ""

# 4. Run migrations (create tables)
echo "[4/5] Running database migrations ..."
$COMPOSE run --rm api python -c \
  "import asyncio; from app.database import create_tables; asyncio.run(create_tables())"
echo "      ✓ Tables created."
echo ""

# 5. Trigger first fetch
echo "[5/5] Triggering initial tender fetch ..."
$COMPOSE run --rm api python -c \
  "import asyncio; from app.tasks.fetch_job import run_fetch_cycle; n = asyncio.run(run_fetch_cycle()); print(f'      ✓ Fetched {n} tenders.')"
echo ""

echo "==========================================="
echo "  Setup complete!"
echo ""
echo "  Start the full stack:   docker compose up"
echo "  API:                    http://localhost:8000"
echo "  API docs:               http://localhost:8000/docs"
echo ""
echo "  For the frontend:"
echo "    cd frontend && npm install && npm run dev"
echo "    Open: http://localhost:5173"
echo "==========================================="
