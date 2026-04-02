from unittest.mock import MagicMock

from saas.storage.minio_client import SimDataStorage, SIM_DATA_FILES


def test_sim_data_files_list():
    """All 8 expected files are defined."""
    assert len(SIM_DATA_FILES) == 8
    assert "market_curves.json" in SIM_DATA_FILES
    assert "posts.json" in SIM_DATA_FILES
    assert "agent_trajectories.json" in SIM_DATA_FILES


def test_generate_upload_urls_returns_dict():
    """generate_upload_urls returns a URL per file."""
    mock_client = MagicMock()
    mock_client.presigned_put_object.return_value = "https://minio.example.com/presigned-put"

    storage = SimDataStorage.__new__(SimDataStorage)
    storage._client = mock_client
    storage._bucket = "simswarm"
    storage._enabled = True

    urls = storage.generate_upload_urls(job_id=42)

    assert len(urls) == 8
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

    assert len(urls) == 8
    assert all(url == "https://minio.example.com/presigned-get" for url in urls.values())


def test_generate_upload_urls_disabled_when_no_endpoint():
    """Returns None when MinIO is not configured."""
    storage = SimDataStorage(endpoint="", access_key="", secret_key="", bucket="simswarm")
    result = storage.generate_upload_urls(job_id=1)
    assert result is None
