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
    "chat_log.json",  # required by the external-LLM report task (saas/jobs/report.py)
    "relations.json",  # LLM-extracted typed graph edges; useful for post-mortems
]

UPLOAD_EXPIRY = timedelta(hours=2)
DOWNLOAD_EXPIRY = timedelta(hours=1)


class SimDataStorage:
    """Generate presigned URLs for simulation data upload/download."""

    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool = True, proxy_base: str = ""):
        self._bucket = bucket
        self._enabled = bool(endpoint)
        self._proxy_base = proxy_base  # e.g. "https://simswarm.xyz/minio" — rewrites download URLs
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
        """Generate presigned GET URLs for all sim data files. Returns None if MinIO not configured.

        If proxy_base is set, rewrites URLs to route through the HTTPS reverse proxy
        (avoids mixed-content browser blocks when the page is HTTPS but MinIO is HTTP).
        """
        if not self._enabled:
            return None
        urls = {}
        for filename in SIM_DATA_FILES:
            obj = self._object_path(job_id, filename)
            url = self._client.presigned_get_object(self._bucket, obj, expires=DOWNLOAD_EXPIRY)
            if self._proxy_base:
                # Rewrite http://minio-host:9000/bucket/path?sig → proxy_base/bucket/path?sig
                from urllib.parse import urlparse
                parsed = urlparse(url)
                url = f"{self._proxy_base}{parsed.path}?{parsed.query}"
            urls[filename] = url
        return urls
