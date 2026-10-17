"""
Speed Test API routes for HomeSentinel.

2026-03-11: Endpoints for running speed tests on Chester router via SSH,
viewing results/history, and accessing AI-driven insights.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/speedtest", tags=["speedtest"])

speedtest_service = None
speedtest_scheduler = None


def set_speedtest_service(service):
    global speedtest_service
    speedtest_service = service


def set_speedtest_scheduler(scheduler):
    global speedtest_scheduler
    speedtest_scheduler = scheduler


@router.post("/run")
async def run_speedtest() -> Dict[str, Any]:
    """Manually trigger a speed test on the Chester router via SSH.

    2026-03-11: SSHs into Chester and runs `speedtest --format=json`.
    Also captures cellular signal data and generates insights after completion.
    """
    if speedtest_service is None:
        raise HTTPException(status_code=500, detail="Speed test service not initialized")

    import asyncio
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, speedtest_service.run_speedtest)

        # Generate insights after manual test too
        if not result.get("error"):
            try:
                await loop.run_in_executor(None, speedtest_service.generate_insights)
            except Exception:
                pass

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/latest")
async def get_latest_speedtest() -> Dict[str, Any]:
    """Get the most recent speed test result with % change from previous."""
    if speedtest_service is None:
        raise HTTPException(status_code=500, detail="Speed test service not initialized")

    return speedtest_service.get_latest_with_change()


@router.get("/history")
async def get_speedtest_history(hours: int = 24) -> Dict[str, Any]:
    """Get speed test history for the last N hours (default 24).

    Returns time-series data suitable for charting.
    """
    if speedtest_service is None:
        raise HTTPException(status_code=500, detail="Speed test service not initialized")

    history = speedtest_service.get_history(hours=hours)
    stats = speedtest_service.get_stats(hours=hours)

    return {
        "hours": hours,
        "tests": history,
        "stats": stats,
        "total": len(history),
    }


@router.get("/hourly-averages")
async def get_hourly_averages(days: int = 7) -> Dict[str, Any]:
    """Get average speeds by hour of day over the last N days.

    Used for identifying peak/off-peak patterns.
    """
    if speedtest_service is None:
        raise HTTPException(status_code=500, detail="Speed test service not initialized")

    return {
        "days": days,
        "hourly": speedtest_service.get_hourly_averages(days=days),
    }


@router.get("/insights")
async def get_speed_insights() -> Dict[str, Any]:
    """Get AI-generated insights about speed test patterns."""
    if speedtest_service is None:
        raise HTTPException(status_code=500, detail="Speed test service not initialized")

    insights = speedtest_service.get_insights()
    return {
        "insights": insights,
        "total": len(insights),
    }


@router.post("/insights/generate")
async def generate_insights() -> Dict[str, Any]:
    """Manually trigger insight generation from accumulated test data."""
    if speedtest_service is None:
        raise HTTPException(status_code=500, detail="Speed test service not initialized")

    import asyncio
    loop = asyncio.get_event_loop()
    insights = await loop.run_in_executor(None, speedtest_service.generate_insights)
    return {
        "generated": len(insights),
        "insights": insights,
    }


@router.get("/scheduler/status")
async def get_scheduler_status() -> Dict[str, Any]:
    """Get the speed test scheduler status."""
    if speedtest_scheduler is None:
        return {"is_running": False, "error": "Scheduler not initialized"}

    return speedtest_scheduler.get_status()


@router.post("/scheduler/interval")
async def set_scheduler_interval(interval: int) -> Dict[str, Any]:
    """Update the speed test scheduler interval (in seconds, minimum 60)."""
    if speedtest_scheduler is None:
        raise HTTPException(status_code=500, detail="Scheduler not initialized")

    try:
        speedtest_scheduler.set_interval(interval)
        return {
            "success": True,
            "interval_seconds": interval,
            "message": f"Speed test interval updated to {interval} seconds",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
