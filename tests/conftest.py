import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from saas.config import Settings
from saas.models.base import Base
from saas.models import CreditEntry  # noqa: F401 — registers table in metadata
from saas.models import User  # noqa: F401 — registers table in metadata
from saas.database import get_session

_FORWARD_IMPORTS_OK = True

TEST_DATABASE_URL = "sqlite+aiosqlite://"

test_settings = Settings(
    DATABASE_URL=TEST_DATABASE_URL,
    SECRET_KEY="test-secret",
    LLM_API_KEY="test-key",
    LLM_BASE_URL="http://localhost:8000/v1",
    LLM_MODEL_NAME="test-model",
    ZEP_API_KEY="test-zep",
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
async def funded_user(db_session):
    from saas.billing.ledger import CreditLedger
    ledger = CreditLedger(db_session)
    await ledger.credit("user-123", amount=10000, description="Test credits")
    await ledger.credit("user-456", amount=10000, description="Test credits")
    await ledger.credit("integration-test-user", amount=10000, description="Test credits")
    await ledger.credit("tier-test-user", amount=10000, description="Test credits")
    await db_session.commit()
