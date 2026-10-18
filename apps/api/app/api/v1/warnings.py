from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import graph_dep
from app.graph.client import GraphClient
from app.services import warnings

router = APIRouter(prefix="/warnings", tags=["warnings"])


@router.get("")
def list_warnings(include_expired: bool = False, graph: GraphClient = Depends(graph_dep)):
    return {"items": warnings.list_warnings(graph, include_expired=include_expired)}


@router.get("/{warning_id}")
def get_warning(warning_id: str, graph: GraphClient = Depends(graph_dep)):
    w = warnings.detail(graph, warning_id)
    if not w:
        raise HTTPException(404, detail={"error": "not_found"})
    return w
