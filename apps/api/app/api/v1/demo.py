"""Operator-only controls for the synthetic "headliner cancels" demo scenario (see services/demo_scenario.py).
Every endpoint acts only on nodes flagged `demo = true`; none can touch real residents."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import graph_dep
from app.db.session import get_db
from app.graph.client import GraphClient
from app.security.auth import require_operator
from app.services import audit, demo_scenario

router = APIRouter(prefix="/demo", tags=["demo"])


class Respond(BaseModel):
    persona_key: str
    accept: bool


@router.get("/state")
def get_state(operator: str = Depends(require_operator), db: Session = Depends(get_db),
              graph: GraphClient = Depends(graph_dep)):
    return demo_scenario.state(graph, db)


@router.post("/seed")
def seed(operator: str = Depends(require_operator), db: Session = Depends(get_db),
         graph: GraphClient = Depends(graph_dep)):
    try:
        res = demo_scenario.seed(graph)
    except LookupError as exc:
        raise HTTPException(409, detail={"error": "missing_geography", "message": str(exc)})
    audit.record(db, "operator", operator, "demo_seed")
    return res


@router.post("/reset")
def reset(operator: str = Depends(require_operator), db: Session = Depends(get_db),
          graph: GraphClient = Depends(graph_dep)):
    demo_scenario.remove(graph, db)
    res = demo_scenario.seed(graph)
    audit.record(db, "operator", operator, "demo_reset")
    return res


@router.delete("")
def remove(operator: str = Depends(require_operator), db: Session = Depends(get_db),
           graph: GraphClient = Depends(graph_dep)):
    res = demo_scenario.remove(graph, db)
    audit.record(db, "operator", operator, "demo_remove")
    return res


@router.post("/cancel-artist")
def cancel_artist(operator: str = Depends(require_operator), db: Session = Depends(get_db),
                  graph: GraphClient = Depends(graph_dep)):
    try:
        res = demo_scenario.cancel_main(graph, db)
    except LookupError:
        raise HTTPException(409, detail={"error": "not_ready", "message": "Seed the scenario first (or the performer already cancelled)."})
    audit.record(db, "operator", operator, "demo_cancel_artist", res["event_id"], run_id=res["run_id"])
    return res


@router.post("/file-complaint")
def file_complaint(operator: str = Depends(require_operator), db: Session = Depends(get_db),
                   graph: GraphClient = Depends(graph_dep)):
    try:
        res = demo_scenario.file_complaint(graph)
    except LookupError:
        raise HTTPException(409, detail={"error": "not_ready", "message": "Seed the scenario first."})
    audit.record(db, "operator", operator, "demo_file_complaint", res["issue_id"])
    return res


@router.post("/respond")
def respond(body: Respond, operator: str = Depends(require_operator), db: Session = Depends(get_db),
            graph: GraphClient = Depends(graph_dep)):
    try:
        res = demo_scenario.respond_as(graph, db, body.persona_key, body.accept)
    except LookupError:
        raise HTTPException(409, detail={"error": "no_pending_invitation", "message": "That persona has no pending invitation."})
    audit.record(db, "operator", operator, "demo_respond", body.persona_key, accept=body.accept)
    return res
