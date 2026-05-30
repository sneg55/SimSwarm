"""Dump the FastAPI OpenAPI schema to docs-site/openapi.json.

Run from repo root:  python scripts/dump_openapi.py
Output path override: OPENAPI_OUT=/tmp/spec.json python scripts/dump_openapi.py
"""
import json
import os

# Dummy values so Settings construction never touches real infra; openapi()
# only introspects routes, it does not connect to the DB/Redis.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "dev-only-not-a-secret")
os.environ.setdefault("LLM_API_KEY", "dev-only-not-a-secret")
os.environ.setdefault("NEO4J_PASSWORD", "dev-only-not-a-secret")

from saas.main import create_app  # noqa: E402

OUT = os.environ.get("OPENAPI_OUT", "docs-site/openapi.json")


def main() -> None:
    app = create_app()
    schema = app.openapi()
    with open(OUT, "w") as fh:
        json.dump(schema, fh, indent=2)
        fh.write("\n")
    print(f"wrote {OUT}: {len(schema.get('paths', {}))} paths")


if __name__ == "__main__":
    main()
