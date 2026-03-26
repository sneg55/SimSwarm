from fastapi import APIRouter
from saas.api.health import router as health_router
from saas.api.jobs import router as jobs_router
from saas.api.billing import router as billing_router
from saas.api.auth import router as auth_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(jobs_router)
api_router.include_router(billing_router)
api_router.include_router(auth_router)
