"""
Deco API Routes
Endpoints for Deco node management and monitoring
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Create router for Deco endpoints
router = APIRouter(prefix="/api/deco", tags=["deco"])

# Global Deco service instance (injected from main.py)
deco_service = None


def set_deco_service(service):
    """
    Set the Deco service instance

    Args:
        service: DecoService instance
    """
    global deco_service
    deco_service = service


@router.get("/nodes")
async def get_deco_nodes() -> Dict[str, Any]:
    """
    Get list of Deco nodes with detailed status information

    Returns:
        JSON response containing:
        - nodes: List of node dictionaries with details
        - total: Total number of nodes
        - timestamp: API response timestamp
        - cache_info: Cache status and age

    Raises:
        401: Not authenticated with Deco API
        500: API error or service not initialized
    """
    if deco_service is None:
        raise HTTPException(status_code=500, detail="Deco service not initialized")

    try:
        nodes = deco_service.get_nodes_with_details()

        return {
            "nodes": nodes,
            "total": len(nodes),
            "timestamp": nodes[0]["last_updated"] if nodes else None,
            "cache_info": {
                "ttl_seconds": deco_service.CACHE_TTL,
                "cached": deco_service._nodes_cache is not None,
            },
        }

    except Exception as e:
        logger.error(f"Failed to fetch Deco nodes: {e}")
        if "401" in str(e) or "Unauthorized" in str(e):
            raise HTTPException(status_code=401, detail="Not authenticated with Deco API")
        raise HTTPException(status_code=500, detail=f"Failed to fetch nodes: {str(e)}")


@router.get("/nodes/{node_id}")
async def get_deco_node(node_id: str) -> Dict[str, Any]:
    """
    Get detailed information for a specific Deco node

    Args:
        node_id: Unique node identifier

    Returns:
        JSON response containing:
        - node: Node details dictionary
        - timestamp: API response timestamp

    Raises:
        404: Node not found
        401: Not authenticated with Deco API
        500: API error or service not initialized
    """
    if deco_service is None:
        raise HTTPException(status_code=500, detail="Deco service not initialized")

    try:
        node = deco_service.get_node_by_id(node_id)

        if not node:
            raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

        return {
            "node": node,
            "timestamp": node["last_updated"],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch node {node_id}: {e}")
        if "401" in str(e) or "Unauthorized" in str(e):
            raise HTTPException(status_code=401, detail="Not authenticated with Deco API")
        raise HTTPException(status_code=500, detail=f"Failed to fetch node: {str(e)}")


@router.post("/nodes/refresh")
async def refresh_deco_nodes() -> Dict[str, Any]:
    """
    Manually refresh Deco node list (bypass cache)

    Returns:
        JSON response containing:
        - success: Operation success status
        - nodes: List of refreshed node dictionaries
        - message: Operation message
        - timestamp: API response timestamp

    Raises:
        401: Not authenticated with Deco API
        500: API error or service not initialized
    """
    if deco_service is None:
        raise HTTPException(status_code=500, detail="Deco service not initialized")

    try:
        # Clear cache to force refresh
        deco_service.clear_cache()
        nodes = deco_service.get_nodes_with_details()

        return {
            "success": True,
            "nodes": nodes,
            "message": f"Refreshed {len(nodes)} nodes",
            "timestamp": nodes[0]["last_updated"] if nodes else None,
        }

    except Exception as e:
        logger.error(f"Failed to refresh Deco nodes: {e}")
        if "401" in str(e) or "Unauthorized" in str(e):
            raise HTTPException(status_code=401, detail="Not authenticated with Deco API")
        raise HTTPException(status_code=500, detail=f"Failed to refresh nodes: {str(e)}")
