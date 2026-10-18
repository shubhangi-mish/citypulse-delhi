"""Graph endpoints. There is deliberately no endpoint that executes caller-supplied Cypher."""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agents.workflow import decision_detail
from app.api.deps import graph_dep
from app.graph.client import GraphClient
from app.graph.model import label_for_id
from app.schemas.requests import ImpactRequest
from app.services import explorer, issues, warnings

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/search")
def search(q: str = Query(min_length=2, max_length=80), graph: GraphClient = Depends(graph_dep)):
    return {"items": explorer.search(graph, q)}


@router.get("/stats")
def stats(graph: GraphClient = Depends(graph_dep)):
    return explorer.stats(graph)


@router.get("/path")
def path(a: str, b: str, graph: GraphClient = Depends(graph_dep)):
    res = explorer.shortest_path(graph, a, b)
    if res is None:
        raise HTTPException(400, detail={"error": "bad_ids"})
    return res


@router.get("/entities/{entity_id}")
def entity(entity_id: str, graph: GraphClient = Depends(graph_dep)):
    node = explorer.entity(graph, entity_id)
    if not node:
        raise HTTPException(404, detail={"error": "not_found"})
    return node


@router.get("/entities/{entity_id}/neighbors")
def neighbors(entity_id: str, types: str | None = None, limit: int = Query(60, le=150),
              graph: GraphClient = Depends(graph_dep)):
    res = explorer.neighbors(graph, entity_id, types.split(",") if types else None, limit)
    if not res:
        raise HTTPException(404, detail={"error": "not_found"})
    return res


@router.get("/explanations/{decision_id}")
def explanation(decision_id: str, graph: GraphClient = Depends(graph_dep)):
    d = decision_detail(graph, decision_id)
    if not d:
        raise HTTPException(404, detail={"error": "not_found"})
    return d


@router.post("/impact-analysis")
def impact(body: ImpactRequest, graph: GraphClient = Depends(graph_dep)):
    """Read-only graph impact for an issue or warning (no agent decisions are written)."""
    resolved = label_for_id(body.entity_id)
    if resolved and resolved[0] == "Warning":
        w = warnings.detail(graph, body.entity_id)
        if not w:
            raise HTTPException(404)
        return {"entity_id": body.entity_id, "impact": w["impact"]}
    if resolved and resolved[0] == "Issue":
        return {"entity_id": body.entity_id, "related": issues.related(graph, body.entity_id)}
    raise HTTPException(400, detail={"error": "unsupported_entity"})
