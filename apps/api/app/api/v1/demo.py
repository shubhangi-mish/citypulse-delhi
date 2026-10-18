"""Operator-only controls for the synthetic "headliner cancels" demo scenario (see services/demo_scenario.py).
Every endpoint acts only on nodes flagged `demo = true`; none can touch real residents."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import graph_dep
from app.db.session import get_db
from app.graph.client import GraphClient
from app.security.auth import RESIDENT_COOKIE, _set_cookie, require_operator, start_resident_session
from app.services import audit, demo_scenario

router = APIRouter(prefix="/demo", tags=["demo"])


BACKUP_COOKIE = "cp_session_backup"


class Impersonate(BaseModel):
    persona_key: str


class Respond(BaseModel):
    persona_key: str
    accept: bool


@router.post("/impersonate")
def impersonate(body: Impersonate, request: Request, response: Response, operator: str = Depends(require_operator),
                db: Session = Depends(get_db), graph: GraphClient = Depends(graph_dep)):
    """Open the resident app AS a synthetic demo persona (demo=true only). The coordinator's own resident session, if
    any, is kept in a backup cookie so "Back to my account" restores it instead of losing it."""
    ids = demo_scenario._persona_ids(graph)
    rid = ids.get(body.persona_key)
    if not rid:
        raise HTTPException(404, detail={"error": "not_found", "message": "Unknown demo persona."})
    existing = request.cookies.get(RESIDENT_COOKIE)
    if existing and not request.cookies.get(BACKUP_COOKIE):
        _set_cookie(response, BACKUP_COOKIE, existing, 60 * 60 * 12)
    start_resident_session(db, response, rid)
    audit.record(db, "operator", operator, "demo_impersonate", rid)
    main = demo_scenario._main_event(graph)
    return {"resident_id": rid, "event_id": main["id"] if main else None}


@router.post("/restore-session", status_code=204)
def restore_session(request: Request, response: Response):
    """Leave a demo persona and go back to the browser's own resident session (or none)."""
    backup = request.cookies.get(BACKUP_COOKIE)
    if backup:
        _set_cookie(response, RESIDENT_COOKIE, backup, 60 * 60 * 24 * 180)
        response.delete_cookie(BACKUP_COOKIE, path="/")
    else:
        response.delete_cookie(RESIDENT_COOKIE, path="/")


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
