import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from saas.config import Settings
from saas.models.base import Base
from saas.billing.models import CreditEntry, CreditPack  # noqa: F401 — registers table in metadata
from saas.auth.models import User  # noqa: F401 — registers table in metadata
from saas.jobs.models import SimulationJob, ModelRouting  # noqa: F401 — registers table in metadata
from saas.database import get_session


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset the shared in-memory rate-limiter before every test to prevent
    counters from leaking across test cases."""
    from saas.limiter import limiter
    limiter.reset()
    yield
    limiter.reset()

_FORWARD_IMPORTS_OK = True

TEST_DATABASE_URL = "sqlite+aiosqlite://"

test_settings = Settings(
    DATABASE_URL=TEST_DATABASE_URL,
    SECRET_KEY="test-secret",
    LLM_API_KEY="test-key",
    LLM_BASE_URL="http://localhost:8000/v1",
    LLM_MODEL_NAME="test-model",
    NEO4J_PASSWORD="test-neo4j",
)


@pytest.fixture
async def db_engine():
    if not _FORWARD_IMPORTS_OK:
        pytest.skip("saas.models.base not yet available (Task 3)")
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    if not _FORWARD_IMPORTS_OK:
        pytest.skip("saas.models.base not yet available (Task 3)")
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client(db_engine):
    if not _FORWARD_IMPORTS_OK:
        pytest.skip("saas.models.base not yet available (Task 3)")
    from saas.main import create_app

    app = create_app(test_settings)

    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_headers(client):
    """Register a test user and return auth headers."""
    resp = await client.post("/api/auth/register", json={"email": "testuser@example.com", "password": "testpass123"})
    data = resp.json()
    token = data["token"]
    user_id = str(data["user"]["id"])
    return {"Authorization": f"Bearer {token}", "_user_id": user_id}


@pytest.fixture
async def funded_user(db_session, auth_headers):
    from saas.billing.ledger import CreditLedger
    user_id = auth_headers["_user_id"]
    ledger = CreditLedger(db_session)
    await ledger.credit(user_id, amount=10000, description="Test credits")
    await db_session.commit()


@pytest.fixture
async def seeded_routing(db_session):
    """Seed ModelRouting rows required for job creation endpoint."""
    rows = [
        ModelRouting(
            sim_tier="small",
            model_id="Qwen/Qwen3-14B",
            gpu_type="NVIDIA L40S",
            max_rounds=25,
            target_agents=10,
            vllm_args="--max-model-len 16384 --enable-auto-tool-choice --tool-call-parser hermes",
        ),
        ModelRouting(
            sim_tier="medium",
            model_id="Qwen/Qwen3-14B",
            gpu_type="NVIDIA L40S",
            max_rounds=100,
            target_agents=20,
            vllm_args="--max-model-len 16384 --enable-auto-tool-choice --tool-call-parser hermes",
        ),
        ModelRouting(
            sim_tier="large",
            model_id="Qwen/Qwen3-14B",
            gpu_type="NVIDIA L40S",
            max_rounds=200,
            target_agents=35,
            vllm_args="--max-model-len 16384 --enable-auto-tool-choice --tool-call-parser hermes",
        ),
    ]
    for row in rows:
        db_session.add(row)
    await db_session.commit()
