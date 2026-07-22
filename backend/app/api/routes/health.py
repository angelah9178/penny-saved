"""Application liveness route."""

from fastapi import APIRouter

from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    operation_id="get_health",
    response_model=HealthResponse,
    responses={500: {"description": "Internal server error"}},
)
async def get_health() -> HealthResponse:
    """Report process liveness without requiring a database connection."""
    return HealthResponse()
