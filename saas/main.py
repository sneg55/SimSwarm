import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from saas.api.router import api_router
from saas.config import Settings
from saas.database import init_db
from saas.limiter import limiter
from saas.logging import setup_logging
from saas.middleware.error_tracking import log_error_event


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    log_format = os.getenv("LOG_FORMAT", "json")
    setup_logging(json_output=(log_format == "json"))

    app = FastAPI(title="SimSwarm", version="0.1.0")
    app.state.settings = settings
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    init_db(settings.DATABASE_URL)
    app.include_router(api_router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        await log_error_event(request, exc)
        raise exc

    return app
