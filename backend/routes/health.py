"""
Network Health Score API routes for HomeSentinel.
2026-03-12: Endpoint for the gamification health score.
"""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/network", tags=["network"])

health_service = None


def set_health_service(service):
    global health_service
    health_service = service


@router.get("/health-score")
async def get_health_score() -> Dict[str, Any]:
    """Get composite network health score (0-100) with breakdown."""
    if health_service is None:
        raise HTTPException(status_code=500, detail="Health service not initialized")

    try:
        return health_service.compute_health_score()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
