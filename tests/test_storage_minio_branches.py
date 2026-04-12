"""Branch coverage for saas.storage.minio_client."""
from unittest.mock import MagicMock, patch

from saas.storage.minio_client import SimDataStorage


def test_constructor_instantiates_minio_when_endpoint_provided():
    with patch("minio.Minio") as mock_minio:
        mock_client = MagicMock()
        mock_minio.return_value = mock_client
        storage = SimDataStorage(
            endpoint="minio.example.com:9000",
            access_key="ak",
            secret_key="sk",
            bucket="simswarm",
            secure=False,
        )
    assert storage._enabled is True
    assert storage._client is mock_client
    mock_minio.assert_called_once_with(
        "minio.example.com:9000",
        access_key="ak",
        secret_key="sk",
        secure=False,
    )


def test_generate_download_urls_disabled_returns_none():
    storage = SimDataStorage(endpoint="", access_key="", secret_key="", bucket="b")
    assert storage.generate_download_urls(1) is None


def test_generate_download_urls_with_proxy_rewrites_url():
    mock_client = MagicMock()
    mock_client.presigned_get_object.return_value = (
        "http://minio.internal:9000/simswarm/sim-data/1/posts.json?X-Amz-Sig=abc"
    )

    storage = SimDataStorage.__new__(SimDataStorage)
    storage._client = mock_client
    storage._bucket = "simswarm"
    storage._enabled = True
    storage._proxy_base = "https://simswarm.xyz/minio"

    urls = storage.generate_download_urls(job_id=1)

    assert all(url.startswith("https://simswarm.xyz/minio/") for url in urls.values())
    assert "?X-Amz-Sig=abc" in urls["posts.json"]


def test_object_path_format():
    storage = SimDataStorage.__new__(SimDataStorage)
    assert storage._object_path(42, "posts.json") == "sim-data/42/posts.json"
