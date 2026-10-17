"""
Daily Digest API routes for HomeSentinel.
2026-03-12: Endpoint for retrieving daily summary statistics.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/digest", tags=["digest"])

digest_service = None


def set_digest_service(service):
    global digest_service
    digest_service = service


@router.get("/daily")
async def get_daily_digest(date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format, defaults to yesterday")) -> Dict[str, Any]:
    """Get daily digest summary for a given date (defaults to yesterday)."""
    if digest_service is None:
        raise HTTPException(status_code=500, detail="Digest service not initialized")

    try:
        return digest_service.compute_daily_digest(date=date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
