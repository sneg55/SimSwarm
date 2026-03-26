from fastapi import FastAPI
from saas.api.router import api_router
from saas.config import Settings
from saas.database import init_db

# Module-level reference updated each time create_app is called
_app_settings: Settings | None = None


def create_app(settings: Settings | None = None) -> FastAPI:
    global _app_settings
    if settings is None:
        settings = Settings()
    _app_settings = settings

    app = FastAPI(title="FishCloud", version="0.1.0")
    init_db(settings.DATABASE_URL)
    app.include_router(api_router)
    return app
