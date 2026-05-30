"""MinIO artifact download helper used by the report task.

Reads sim-data/{job_id}/{filename} via the Minio SDK. Returns bytes.
Separate from the presigned-URL path because the report task runs server-side
and doesn't need URL signing.
"""
from __future__ import annotations

import io
import logging
import os

logger = logging.getLogger(__name__)


class ArtifactMissingError(Exception):
    """Raised when an expected MinIO artifact is absent."""


def fetch_artifact(job_id: int, filename: str) -> bytes:
    """Fetch a single artifact by (job_id, filename).

    Uses MINIO_* env vars (identical set to SimDataStorage). Raises
    ArtifactMissingError on 404.
    """
    endpoint = os.getenv("MINIO_ENDPOINT", "")
    if not endpoint:
        raise ArtifactMissingError(
            f"MINIO_ENDPOINT not set; cannot fetch {filename} for job {job_id}"
        )
    from minio import Minio
    from minio.error import S3Error

    client = Minio(
        endpoint,
        access_key=os.getenv("MINIO_ACCESS_KEY", ""),
        secret_key=os.getenv("MINIO_SECRET_KEY", ""),
        secure=os.getenv("MINIO_SECURE", "true").lower() == "true",
    )
    bucket = os.getenv("MINIO_BUCKET", "simswarm")
    obj = f"sim-data/{job_id}/{filename}"

    try:
        resp = client.get_object(bucket, obj)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()
    except S3Error as exc:
        if exc.code == "NoSuchKey":
            raise ArtifactMissingError(f"{obj} missing in bucket {bucket}") from exc
        raise


def put_report_md(job_id: int, markdown: str) -> None:
    """Upload report.md to sim-data/{job_id}/report.md for downstream consumers."""
    endpoint = os.getenv("MINIO_ENDPOINT", "")
    if not endpoint:
        logger.warning("MINIO_ENDPOINT not set; skipping report.md upload for job %d", job_id)
        return
    from minio import Minio

    client = Minio(
        endpoint,
        access_key=os.getenv("MINIO_ACCESS_KEY", ""),
        secret_key=os.getenv("MINIO_SECRET_KEY", ""),
        secure=os.getenv("MINIO_SECURE", "true").lower() == "true",
    )
    bucket = os.getenv("MINIO_BUCKET", "simswarm")
    obj = f"sim-data/{job_id}/report.md"
    body = markdown.encode("utf-8")
    client.put_object(
        bucket, obj, data=io.BytesIO(body), length=len(body),
        content_type="text/markdown",
    )
