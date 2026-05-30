import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from saas.config import Settings
from saas.database import get_session
from saas.main import create_app

DEMO_SETTINGS = Settings(
    DATABASE_URL="sqlite+aiosqlite://", SECRET_KEY="t",
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


async def test_register_blocked_in_demo_mode(demo_client):
    resp = await demo_client.post(
        "/api/auth/register",
        json={"email": "x@example.com", "password": "password123"},
    )
    assert resp.status_code == 403


async def test_register_allowed_by_default(client):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "ok@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
