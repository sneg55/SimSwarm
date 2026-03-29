"""Endpoint to fetch and extract text from a URL for seed input."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl
import httpx
import re

from saas.auth.dependencies import get_current_user

router = APIRouter(prefix="/fetch", tags=["fetch"])

MAX_CONTENT_LENGTH = 5_000_000  # 5MB max download
TIMEOUT_SECONDS = 15


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
