from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import graph_dep
from app.db.session import get_db
from app.graph.client import GraphClient
from app.schemas.requests import ActionCreate, ActionOutcome, ActionReject, CaseCreate, CaseStatus
from app.security.auth import optional_operator, require_operator, require_resident
from app.services import audit, coordination

router = APIRouter(prefix="/coordination", tags=["coordination"])


@router.get("/cases")
def list_cases(status: str | None = None, operator: str | None = Depends(optional_operator),
               graph: GraphClient = Depends(graph_dep)):
    items = coordination.list_cases(graph, status)
    if not operator:  # residents never see agent proposals that no coordinator has approved
        items = [c for c in items if c["status"] != "proposed"]
    return {"items": items}


@router.post("/cases", status_code=201)
def create_case(body: CaseCreate, operator: str = Depends(require_operator), db: Session = Depends(get_db),
                graph: GraphClient = Depends(graph_dep)):
    cid = coordination.create_case(graph, title=body.title, case_type=body.case_type, issue_ids=body.issue_ids,
                                   created_by=f"coordinator:{operator}")
    audit.record(db, "operator", operator, "case_created", cid, issues=body.issue_ids)
    return {"case_id": cid}


@router.get("/cases/{case_id}")
def get_case(case_id: str, operator: str | None = Depends(optional_operator), graph: GraphClient = Depends(graph_dep)):
    case = coordination.case_detail(graph, case_id, operator=bool(operator))
    if not case or (case["status"] == "proposed" and not operator):
        raise HTTPException(404, detail={"error": "not_found"})
    if not operator:
        case["actions"] = [a for a in case["actions"] if a["status"] != "proposed"]
    return case


@router.post("/cases/{case_id}/status")
def case_status(case_id: str, body: CaseStatus, operator: str = Depends(require_operator),
                db: Session = Depends(get_db), graph: GraphClient = Depends(graph_dep)):
    coordination.set_case_status(graph, case_id, body.status)
    audit.record(db, "operator", operator, "case_status", case_id, status=body.status)
    return {"status": body.status}


@router.post("/cases/{case_id}/actions", status_code=201)
def add_action(case_id: str, body: ActionCreate, operator: str = Depends(require_operator),
               db: Session = Depends(get_db), graph: GraphClient = Depends(graph_dep)):
    if body.action_type not in coordination.ACTION_TYPES:
        raise HTTPException(422, detail={"error": "unknown_action_type"})
    try:
        aid = coordination.add_action(graph, case_id, action_type=body.action_type, description=body.description,
                                      proposed_by=f"coordinator:{operator}", payload=body.payload)
    except LookupError:
        raise HTTPException(404, detail={"error": "not_found"})
    audit.record(db, "operator", operator, "action_proposed", aid, case_id=case_id, type=body.action_type)
    return {"action_id": aid}


@router.post("/cases/{case_id}/join")
def join(case_id: str, resident_id: str = Depends(require_resident), graph: GraphClient = Depends(graph_dep)):
    coordination.join_case(graph, case_id, resident_id)
    return {"joined": True}


@router.post("/actions/{action_id}/approve")
def approve(action_id: str, operator: str = Depends(require_operator), db: Session = Depends(get_db),
            graph: GraphClient = Depends(graph_dep)):
    try:
        result = coordination.approve(graph, db, action_id, operator)
    except LookupError:
        raise HTTPException(404, detail={"error": "not_found"})
    except ValueError as exc:
        raise HTTPException(409, detail={"error": "conflict", "message": str(exc)})
    audit.record(db, "operator", operator, "action_approved", action_id, execution=result["execution"])
    return result


@router.post("/actions/{action_id}/reject")
def reject(action_id: str, body: ActionReject, operator: str = Depends(require_operator),
           db: Session = Depends(get_db), graph: GraphClient = Depends(graph_dep)):
    coordination.reject(graph, action_id, operator, body.reason)
    audit.record(db, "operator", operator, "action_rejected", action_id, reason=body.reason)
    return {"status": "rejected"}


@router.post("/actions/{action_id}/outcome")
def outcome(action_id: str, body: ActionOutcome, operator: str = Depends(require_operator),
            db: Session = Depends(get_db), graph: GraphClient = Depends(graph_dep)):
    try:
        result = coordination.record_outcome(graph, action_id, operator, body.outcome, body.success)
    except LookupError:
        raise HTTPException(404, detail={"error": "not_found"})
    audit.record(db, "operator", operator, "action_outcome", action_id, success=body.success,
                 memory_id=result["memory_id"])
    return result
