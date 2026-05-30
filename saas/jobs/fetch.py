"""Endpoint to fetch and extract text from a URL for seed input."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
import httpx
import ipaddress
import re
import socket

from saas.auth.dependencies import get_current_user

router = APIRouter(prefix="/fetch", tags=["fetch"])

MAX_CONTENT_LENGTH = 5_000_000  # 5MB max download
TIMEOUT_SECONDS = 15

# Blocked hostnames (cloud metadata endpoints)
_BLOCKED_HOSTS = {"metadata.google.internal", "metadata.goog", "169.254.169.254"}


def _is_private_ip(host: str) -> bool:
    """Check if a hostname resolves to a private/reserved IP address."""
    try:
        addr = ipaddress.ip_address(host)
        return addr.is_private or addr.is_reserved or addr.is_loopback or addr.is_link_local
    except ValueError:
        pass
    # Resolve hostname to IP
    try:
        for info in socket.getaddrinfo(host, None):
            addr = ipaddress.ip_address(info[4][0])
            if addr.is_private or addr.is_reserved or addr.is_loopback or addr.is_link_local:
                return True
    except socket.gaierror:
        pass
    return False


def _validate_url(url: str) -> None:
    """Reject URLs targeting internal/private resources (SSRF protection)."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = parsed.hostname or ""
    scheme = parsed.scheme.lower()

    if scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Only http/https URLs are allowed")
    if not host:
        raise HTTPException(status_code=400, detail="Invalid URL")
    if host.lower() in _BLOCKED_HOSTS:
        raise HTTPException(status_code=400, detail="This URL is not allowed")
    if _is_private_ip(host):
        raise HTTPException(status_code=400, detail="URLs targeting private/internal networks are not allowed")


class FetchRequest(BaseModel):
    url: HttpUrl


class FetchResponse(BaseModel):
    text: str
    char_count: int
    source_url: str


def _html_to_text(html: str) -> str:
    """Strip HTML tags and extract readable text."""
    # Remove script/style blocks
    html = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # Remove tags
    text = re.sub(r'<[^>]+>', ' ', html)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Decode common entities
    for entity, char in [('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'),
                         ('&quot;', '"'), ('&#39;', "'"), ('&nbsp;', ' ')]:
        text = text.replace(entity, char)
    return text


@router.post("", response_model=FetchResponse)
async def fetch_url(
    body: FetchRequest,
    current_user: dict = Depends(get_current_user),
):
    url = str(body.url)
    _validate_url(url)
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS,
            follow_redirects=True,
            max_redirects=5,
        ) as client:
            resp = await client.get(url, headers={
                "User-Agent": "SimSwarm/1.0 (seed-fetcher)",
                "Accept": "text/html,text/plain,application/json",
            })
            resp.raise_for_status()

            if len(resp.content) > MAX_CONTENT_LENGTH:
                raise HTTPException(status_code=400, detail="Content too large (max 5MB)")

            content_type = resp.headers.get("content-type", "")
            raw = resp.text

            if "text/html" in content_type:
                text = _html_to_text(raw)
            elif "application/json" in content_type:
                text = raw
            else:
                text = raw

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"URL returned HTTP {e.response.status_code}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=400, detail="URL fetch timed out")
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"Could not reach URL: {e}")

    if not text.strip():
        raise HTTPException(status_code=400, detail="No text content found at URL")

    return FetchResponse(text=text, char_count=len(text), source_url=url)
