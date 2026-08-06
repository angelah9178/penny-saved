"""Top-level API router."""

from app.api.routes.auth import router as auth_router
from app.api.routes.entries import router as entries_router
from app.api.routes.health import router as health_router
from app.api.routes.opportunity_costs import router as opportunity_costs_router
from app.api.routes.statistics import router as statistics_router
from fastapi import APIRouter

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(entries_router)
api_router.include_router(statistics_router)
api_router.include_router(opportunity_costs_router)
