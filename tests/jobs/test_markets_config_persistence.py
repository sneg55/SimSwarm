"""Unit tests for markets_config persistence."""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text

import saas.jobs.persistence_sync_progress as persistence_mod


@pytest.fixture
def tmp_engine(monkeypatch, tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE TABLE simulation_jobs ("
            " id INTEGER PRIMARY KEY,"
            " markets_config TEXT"
            ")"
        ))
        conn.execute(text("INSERT INTO simulation_jobs (id) VALUES (1)"))
        conn.commit()

    def _stub_engine():
        return engine

    monkeypatch.setattr(persistence_mod, "_get_sync_engine", _stub_engine)
    yield engine
    engine.dispose()


class TestUpdateMarketsConfigSync:
    def test_persists_markets_list_as_json(self, tmp_engine):
        markets = [{"question": "Will X?", "initial_price_yes": 0.6, "rationale": "because Y"}]
        persistence_mod._update_markets_config_sync(1, markets)
        with tmp_engine.connect() as conn:
            row = conn.execute(text("SELECT markets_config FROM simulation_jobs WHERE id=1")).first()
        assert json.loads(row[0]) == markets

    def test_none_becomes_sql_null(self, tmp_engine):
        persistence_mod._update_markets_config_sync(1, None)
        with tmp_engine.connect() as conn:
            row = conn.execute(text("SELECT markets_config FROM simulation_jobs WHERE id=1")).first()
        assert row[0] is None

    def test_missing_job_id_is_swallowed(self, tmp_engine, caplog):
        # Should not raise — mirrors the silent-fail pattern in _update_enrichment_sync.
        persistence_mod._update_markets_config_sync(9999, [{"question": "Q", "initial_price_yes": 0.5}])
