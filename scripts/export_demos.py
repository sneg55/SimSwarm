"""Export the curated public demos from a live SimSwarm instance to static
files for the Cloudflare Pages build. Run BEFORE decommissioning servers.

Usage:
    python scripts/export_demos.py --base-url https://simswarm.xyz

Writes:
    frontend/public/demos/index.json        # gallery list
    frontend/public/demos/<token>.json       # one per demo (full payload)
    frontend/public/demos/<token>.og.html    # static OG preview page
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import pathlib

import httpx

OUT_DIR = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "public" / "demos"


def _og_description(payload: dict) -> str:
    """Mirror saas/jobs/share.py OG logic using only the public share payload."""
    structured = payload.get("structured") or {}
    brief = structured.get("brief") or structured.get("executive_brief")
    if isinstance(brief, str) and brief.strip():
        return brief.strip()[:200]
    report = payload.get("report") or ""
    for line in report.split("\n"):
        s = line.strip()
        if s and not s.startswith("#") and len(s) > 30:
            return s[:200]
    return f"AI swarm simulation: {payload.get('goal', '')}"[:200]


def _og_html(token: str, payload: dict) -> str:
    title = html_mod.escape(payload.get("goal") or "SimSwarm Simulation")
    desc = html_mod.escape(_og_description(payload))
    canonical = f"https://simswarm.xyz/s/{token}"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — SimSwarm</title>
<meta name="description" content="{desc}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="SimSwarm">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta http-equiv="refresh" content="0;url=/s/{token}">
</head>
<body><p>Redirecting to <a href="/s/{token}">SimSwarm results</a>...</p></body>
</html>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="https://simswarm.xyz")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=30) as client:
        demos = client.get(f"{base}/api/share/demos").raise_for_status().json()
        (OUT_DIR / "index.json").write_text(json.dumps(demos, indent=2))
        print(f"wrote index.json ({len(demos)} demos)")

        for demo in demos:
            token = demo["share_token"]
            payload = client.get(f"{base}/api/share/{token}").raise_for_status().json()
            # Compact (no indent) — these carry full chat replays and can be MBs.
            (OUT_DIR / f"{token}.json").write_text(json.dumps(payload, separators=(",", ":")))
            (OUT_DIR / f"{token}.og.html").write_text(_og_html(token, payload))
            print(f"wrote {token}.json + {token}.og.html")


if __name__ == "__main__":
    main()
