"""MinIO object storage client for rich simulation data."""
from __future__ import annotations

import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

SIM_DATA_FILES = [
    "market_curves.json",
    "agent_trajectories.json",
    "engagement_summary.json",
    "top_posts.json",
    "posts.json",
    "trades.json",
    "social_graph.json",
    "profiles.json",
]

UPLOAD_EXPIRY = timedelta(hours=2)
DOWNLOAD_EXPIRY = timedelta(hours=1)


class SimDataStorage:
    """Generate presigned URLs for simulation data upload/download."""

    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool = True):
        self._bucket = bucket
        self._enabled = bool(endpoint)
        if self._enabled:
            from minio import Minio
            self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        else:
            self._client = None

    def _object_path(self, job_id: int, filename: str) -> str:
        return f"sim-data/{job_id}/{filename}"

    def generate_upload_urls(self, job_id: int) -> dict[str, str] | None:
        """Generate presigned PUT URLs for all sim data files. Returns None if MinIO not configured."""
        if not self._enabled:
            return None
        urls = {}
        for filename in SIM_DATA_FILES:
            obj = self._object_path(job_id, filename)
            urls[filename] = self._client.presigned_put_object(self._bucket, obj, expires=UPLOAD_EXPIRY)
        return urls

    def generate_download_urls(self, job_id: int) -> dict[str, str] | None:
        """Generate presigned GET URLs for all sim data files. Returns None if MinIO not configured."""
        if not self._enabled:
            return None
        urls = {}
        for filename in SIM_DATA_FILES:
            obj = self._object_path(job_id, filename)
            urls[filename] = self._client.presigned_get_object(self._bucket, obj, expires=DOWNLOAD_EXPIRY)
        return urls
