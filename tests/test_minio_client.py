from datetime import timedelta
from unittest.mock import MagicMock

from saas.constants.tiers import TIER_TIMEOUTS
from saas.storage.minio_client import SimDataStorage, SIM_DATA_FILES, UPLOAD_EXPIRY


def test_upload_expiry_covers_largest_tier():
    """Presigned upload URLs must outlive the longest possible sim.

    Sim 123 (medium tier, 5 h) completed at ~4 h 53 m and every upload was
    rejected because the 2 h expiry had already lapsed. URLs are minted at
    sim-creation time and the pod PUTs right after the pipeline ends, so the
    window has to cover tier timeout + provisioning + some slack.
    """
    max_tier_s = max(TIER_TIMEOUTS.values())
    assert UPLOAD_EXPIRY >= timedelta(seconds=max_tier_s + 3600), (
        f"UPLOAD_EXPIRY={UPLOAD_EXPIRY} is too short for largest tier "
        f"({max_tier_s}s) plus a 1 h safety buffer."
    )


def test_sim_data_files_list():
    """All expected files are defined, including chat_log.json for the
    external-LLM report task and relations.json for post-mortem diagnostics."""
    assert len(SIM_DATA_FILES) == 10
    assert "market_curves.json" in SIM_DATA_FILES
    assert "posts.json" in SIM_DATA_FILES
    assert "agent_trajectories.json" in SIM_DATA_FILES
    assert "chat_log.json" in SIM_DATA_FILES
    assert "relations.json" in SIM_DATA_FILES


def test_generate_upload_urls_returns_dict():
    """generate_upload_urls returns a URL per file."""
    mock_client = MagicMock()
    mock_client.presigned_put_object.return_value = "https://minio.example.com/presigned-put"

    storage = SimDataStorage.__new__(SimDataStorage)
    storage._client = mock_client
    storage._bucket = "simswarm"
    storage._enabled = True

    urls = storage.generate_upload_urls(job_id=42)

    assert len(urls) == 10
    assert all(url == "https://minio.example.com/presigned-put" for url in urls.values())
    assert "market_curves.json" in urls
    calls = mock_client.presigned_put_object.call_args_list
    first_call_args = calls[0]
    assert first_call_args[0][0] == "simswarm"
    assert "sim-data/42/" in first_call_args[0][1]


def test_generate_download_urls_returns_dict():
    """generate_download_urls returns a URL per file."""
    mock_client = MagicMock()
    mock_client.presigned_get_object.return_value = "https://minio.example.com/presigned-get"

    storage = SimDataStorage.__new__(SimDataStorage)
    storage._client = mock_client
    storage._bucket = "simswarm"
    storage._enabled = True
    storage._proxy_base = ""

    urls = storage.generate_download_urls(job_id=42)

    assert len(urls) == 10
    assert all(url == "https://minio.example.com/presigned-get" for url in urls.values())


def test_generate_upload_urls_disabled_when_no_endpoint():
    """Returns None when MinIO is not configured."""
    storage = SimDataStorage(endpoint="", access_key="", secret_key="", bucket="simswarm")
    result = storage.generate_upload_urls(job_id=1)
    assert result is None
