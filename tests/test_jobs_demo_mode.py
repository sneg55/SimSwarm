import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from saas.config import Settings
from saas.database import get_session
from saas.main import create_app

DEMO_SETTINGS = Settings(
    DATABASE_URL="sqlite+aiosqlite://", SECRET_KEY="test-secret",
    LLM_API_KEY="k", NEO4J_PASSWORD="p", DEMO_MODE=True,
)


@pytest.fixture
async def demo_client(db_engine):
    app = create_app(DEMO_SETTINGS)
    sf = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
        async with sf() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_create_job_blocked_in_demo_mode(demo_client, client, seeded_routing):
    # Register + get token on the full-mode client (shares db_engine).
    reg = await client.post("/api/auth/register",
                            json={"email": "demo@example.com", "password": "password123"})
    token = reg.json()["token"]
    resp = await demo_client.post(
        "/api/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={"seed_text": "hello world", "goal": "predict", "tier": "small",
              "enrich_web": False, "forecast_days": 30},
    )
    assert resp.status_code == 403


async def test_launch_draft_blocked_in_demo_mode(demo_client, client):
    # Register via the full-mode client (shares db_engine + SECRET_KEY).
    reg = await client.post(
        "/api/auth/register",
        json={"email": "demo2@example.com", "password": "password123"},
    )
    token = reg.json()["token"]

    # The DEMO_MODE gate in launch_draft fires before _get_user_draft,
    # so any job_id returns 403 without reaching the 404 ownership check.
    resp = await demo_client.post(
        "/api/jobs/draft/99999/launch",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
