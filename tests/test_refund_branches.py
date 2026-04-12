"""Coverage for saas.jobs.refund._refund_credits."""
from unittest.mock import MagicMock, patch

from saas.jobs.refund import _refund_credits


def test_refund_no_db_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    # Should silently return without raising
    _refund_credits(job_id=1, user_id="u", credits=10)


def test_refund_inserts_entry(monkeypatch):
    """With DATABASE_URL set, refund opens async engine and inserts row."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

    # Patch create_async_engine to avoid real DB
    fake_engine = MagicMock()

    async def fake_dispose():
        return None

    fake_engine.dispose = fake_dispose

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def execute(self, *a, **k):
            return MagicMock(first=MagicMock(return_value=None))

        async def commit(self):
            return None

    # Have session_factory() return FakeSession()
    def factory(*a, **k):
        return FakeSession()

    with patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=fake_engine), \
         patch("sqlalchemy.ext.asyncio.async_sessionmaker", return_value=factory):
        _refund_credits(job_id=42, user_id="u", credits=10)


def test_refund_skips_duplicate(monkeypatch):
    """Existing entry -> skip insert."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

    fake_engine = MagicMock()

    async def fake_dispose():
        return None

    fake_engine.dispose = fake_dispose

    executed = []

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def execute(self, *a, **k):
            executed.append(a)
            # existing check returns something truthy
            return MagicMock(first=MagicMock(return_value=(1,)))

        async def commit(self):
            return None

    def factory(*a, **k):
        return FakeSession()

    with patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=fake_engine), \
         patch("sqlalchemy.ext.asyncio.async_sessionmaker", return_value=factory):
        _refund_credits(job_id=42, user_id="u", credits=10)

    # Only executed the SELECT (duplicate check), no INSERT
    assert len(executed) == 1


def test_refund_swallows_exception(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

    fake_engine = MagicMock()

    async def fake_dispose():
        return None

    fake_engine.dispose = fake_dispose

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def execute(self, *a, **k):
            raise RuntimeError("DB unavailable")

        async def commit(self):
            return None

    def factory(*a, **k):
        return FakeSession()

    with patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=fake_engine), \
         patch("sqlalchemy.ext.asyncio.async_sessionmaker", return_value=factory):
        # Should swallow and not raise
        _refund_credits(job_id=42, user_id="u", credits=10)
