import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/postgres")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("RESEND_API_KEY", "re_test")

from fastapi.testclient import TestClient

from app.main import app


def test_health_check() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
