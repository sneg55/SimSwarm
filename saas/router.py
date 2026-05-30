from fastapi import APIRouter
from saas.health import router as health_router
from saas.jobs.api import router as jobs_router
from saas.auth.api import router as auth_router
from saas.jobs.progress import router as progress_router
from saas.jobs.export import router as export_router
from saas.jobs.share import router as share_router
from saas.jobs.fetch import router as fetch_router
from saas.auth.profile import router as profile_router
from saas.jobs.ai import router as ai_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(jobs_router)
api_router.include_router(auth_router)
api_router.include_router(progress_router)
api_router.include_router(export_router)
api_router.include_router(share_router)
api_router.include_router(fetch_router)
api_router.include_router(profile_router)
api_router.include_router(ai_router)
