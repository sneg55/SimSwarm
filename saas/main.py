from fastapi import FastAPI
from saas.api.router import api_router
from saas.config import Settings
from saas.database import init_db


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    app = FastAPI(title="FishCloud", version="0.1.0")
    init_db(settings.DATABASE_URL)
    app.include_router(api_router)
    return app
