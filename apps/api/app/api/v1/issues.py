from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import graph_dep
from app.db.session import get_db
from app.graph.client import GraphClient
from app.schemas.requests import CommentCreate, FollowRequest, IssueCreate, IssueStatusUpdate, SupportRequest
from app.security.auth import optional_operator, optional_resident, require_resident
from app.services import audit, issues, notifications, places

router = APIRouter(prefix="/issues", tags=["issues"])


@router.get("/meta")
def meta():
    return {"categories": issues.CATEGORIES, "statuses": issues.STATUSES}


@router.get("/assets-near")
def assets_near(lat: float, lng: float, graph: GraphClient = Depends(graph_dep)):
    """Known OSM infrastructure near a point — lets reporters say which asset their report concerns."""
    return {"items": places.assets_near(graph, lat, lng)}


@router.post("", status_code=201)
def create_issue(body: IssueCreate, resident_id: str = Depends(require_resident),
                 graph: GraphClient = Depends(graph_dep)):
    created = issues.create(graph, resident_id, category=body.category, title=body.title,
                            description=body.description, latitude=body.latitude, longitude=body.longitude,
                            precision=body.precision, anonymous=body.anonymous,
                            concerns_asset_id=body.concerns_asset_id)
    return {**created, "message": "Submitted to the CityPulse community. This does not file a complaint with any "
                                  "government department."}


@router.get("")
def list_issues(status: str | None = None, category: str | None = None, neighborhood_id: str | None = None,
                lat: float | None = None, lng: float | None = None, radius_km: int | None = None,
                limit: int = 50, graph: GraphClient = Depends(graph_dep)):
    return {"items": issues.list_issues(graph, status=status, category=category, neighborhood_id=neighborhood_id,
                                        lat=lat, lng=lng, radius_m=radius_km * 1000 if radius_km else None,
                                        limit=min(limit, 200))}


@router.get("/{issue_id}")
def get_issue(issue_id: str, viewer: str | None = Depends(optional_resident),
              operator: str | None = Depends(optional_operator), graph: GraphClient = Depends(graph_dep)):
    issue = issues.detail(graph, issue_id, viewer)
    if not issue:
        raise HTTPException(404, detail={"error": "not_found"})
    if not operator and issue.get("network"):
        # agent proposals stay internal until a coordinator approves them
        issue["network"]["cases"] = [
            {**c, "actions": [a for a in c["actions"] if a["status"] not in ("proposed", "rejected")]}
            for c in issue["network"]["cases"] if c["status"] != "proposed"]
    return issue


@router.post("/{issue_id}/support")
def support(issue_id: str, body: SupportRequest = SupportRequest(), resident_id: str = Depends(require_resident),
            db: Session = Depends(get_db), graph: GraphClient = Depends(graph_dep)):
    if not body.affected:
        return issues.unsupport(graph, issue_id, resident_id)
    result = issues.support(graph, issue_id, resident_id)
    if result["newly_supported"]:
        reporter = issues.reporter_of(graph, issue_id)
        if reporter:
            notifications.notify(db, [reporter], kind="support", entity_id=issue_id,
                                 message=f"Another resident is affected by your report ({result['support_count']} total).",
                                 dedupe_key=f"support:{issue_id}:{result['support_count']}", exclude=resident_id)
    return result


@router.post("/{issue_id}/follow")
def follow(issue_id: str, body: FollowRequest = FollowRequest(), resident_id: str = Depends(require_resident),
           graph: GraphClient = Depends(graph_dep)):
    issues.set_follow(graph, issue_id, resident_id, body.follow)
    return {"following": body.follow}


@router.post("/{issue_id}/comments", status_code=201)
def comment(issue_id: str, body: CommentCreate, resident_id: str = Depends(require_resident),
            db: Session = Depends(get_db), graph: GraphClient = Depends(graph_dep)):
    try:
        created = issues.comment(graph, "Issue", issue_id, resident_id, body.body)
    except LookupError:
        raise HTTPException(404, detail={"error": "not_found"})
    notifications.notify(db, notifications.issue_audience(graph, issue_id), kind="comment", entity_id=issue_id,
                         message="New comment on a report you follow.",
                         dedupe_key=f"comment:{created['discussion_id']}", exclude=resident_id)
    return created


@router.post("/{issue_id}/status")
def set_status(issue_id: str, body: IssueStatusUpdate, resident_id: str | None = Depends(optional_resident),
               operator: str | None = Depends(optional_operator), db: Session = Depends(get_db),
               graph: GraphClient = Depends(graph_dep)):
    """Reporters may confirm resolution of their own report; other changes require a coordinator."""
    is_reporter = resident_id and issues.reporter_of(graph, issue_id) == resident_id
    if operator:
        actor = f"coordinator:{operator}"
    elif is_reporter and body.status in ("resolved_reporter_confirmed", "submitted"):
        actor = "reporter"
    else:
        raise HTTPException(403, detail={"error": "forbidden", "message": "Not allowed to set this status."})
    issues.set_status(graph, issue_id, body.status, actor)
    audit.record(db, "operator" if operator else "resident", operator or resident_id or "", "issue_status",
                 issue_id, status=body.status)
    notifications.notify(db, notifications.issue_audience(graph, issue_id), kind="status", entity_id=issue_id,
                         message=f"Status update: {issues.STATUSES[body.status]}",
                         dedupe_key=f"status:{issue_id}:{body.status}", exclude=resident_id)
    return {"status": body.status}
