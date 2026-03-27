import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from saas.api.router import api_router
from saas.config import Settings
from saas.database import init_db
from saas.limiter import limiter
from saas.logging import setup_logging

# Module-level reference updated each time create_app is called
_app_settings: Settings | None = None


def create_app(settings: Settings | None = None) -> FastAPI:
    global _app_settings
    if settings is None:
        settings = Settings()
    _app_settings = settings

    log_format = os.getenv("LOG_FORMAT", "json")
    setup_logging(json_output=(log_format == "json"))

    app = FastAPI(title="SimSwarm", version="0.1.0")
    app.state.settings = settings
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    init_db(settings.DATABASE_URL)
    app.include_router(api_router)

    # Serve demo JSON files at /demos/
    demos_dir = Path(__file__).parent.parent / "demos"
    if demos_dir.exists():
        app.mount("/demos", StaticFiles(directory=str(demos_dir)), name="demos")

    return app
