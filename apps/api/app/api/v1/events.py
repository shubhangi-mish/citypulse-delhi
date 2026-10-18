from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import graph_dep
from app.db.session import get_db
from app.graph.client import GraphClient
from app.schemas.requests import CommentCreate, EventCreate, EventUpdateCreate, ParticipateRequest
from app.security.auth import optional_resident, require_resident
from app.services import events, issues, notifications, talent
from app.agents import event_workflow
from pydantic import BaseModel, Field

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/meta")
def meta():
    return {"categories": events.CATEGORIES}


@router.get("")
def list_events(category: str | None = None, neighborhood_id: str | None = None, from_ms: int | None = None,
                to_ms: int | None = None, is_free: bool | None = None, setting: str | None = None,
                lat: float | None = None, lng: float | None = None, radius_km: int | None = None,
                include_past: bool = False, graph: GraphClient = Depends(graph_dep)):
    return {"items": events.list_events(graph, category=category, neighborhood_id=neighborhood_id, from_ms=from_ms,
                                        to_ms=to_ms, is_free=is_free, setting=setting, lat=lat, lng=lng,
                                        radius_m=radius_km * 1000 if radius_km else None, include_past=include_past)}


@router.post("", status_code=201)
def create_event(body: EventCreate, resident_id: str = Depends(require_resident),
                 graph: GraphClient = Depends(graph_dep)):
    created = events.create(
        graph, resident_id, title=body.title, description=body.description, category=body.category,
        start_time=body.start_time, end_time=body.end_time, venue_name=body.venue_name,
        venue_address=body.venue_address, latitude=body.latitude, longitude=body.longitude,
        organizer_name=body.organizer_name, organizer_contact=body.organizer_contact,
        organization_name=body.organization_name, is_free=body.is_free, setting=body.setting,
        accessibility=body.accessibility, registration_url=str(body.registration_url) if body.registration_url else None,
        attestation=body.attestation)
    return {**created, "message": "Published as a community-submitted event (not officially verified)."}


@router.get("/{event_id}")
def get_event(event_id: str, viewer: str | None = Depends(optional_resident), graph: GraphClient = Depends(graph_dep)):
    ev = events.detail(graph, event_id, viewer)
    if not ev:
        raise HTTPException(404, detail={"error": "not_found"})
    return ev


@router.post("/{event_id}/participate")
def participate(event_id: str, body: ParticipateRequest, resident_id: str = Depends(require_resident),
                db: Session = Depends(get_db), graph: GraphClient = Depends(graph_dep)):
    events.participate(graph, event_id, resident_id, body.role)
    org = events.organizer_of(graph, event_id)
    if body.role and org:
        notifications.notify(db, [org], kind="participation", entity_id=event_id,
                             message=f"A resident marked '{body.role}' for your event.",
                             dedupe_key=f"part:{event_id}:{resident_id}:{body.role}", exclude=resident_id)
    return {"role": body.role}


class CancelPerformance(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


class InvitationResponse(BaseModel):
    accept: bool


class Autopilot(BaseModel):
    enabled: bool


@router.post("/{event_id}/autopilot")
def set_autopilot(event_id: str, body: Autopilot, resident_id: str = Depends(require_resident),
                  graph: GraphClient = Depends(graph_dep)):
    """Organiser-only. When on, CityPulse agents may act for you (e.g. invite replacement performers) without waiting
    for a coordinator; every such action is recorded as an AUTHORIZED edge from you."""
    if events.organizer_of(graph, event_id) != resident_id:
        raise HTTPException(403, detail={"error": "forbidden", "message": "Only the organiser can change this."})
    events.set_autopilot(graph, event_id, body.enabled)
    return {"agent_autopilot": body.enabled}


@router.post("/{event_id}/cancel-performance")
def cancel_performance(event_id: str, body: CancelPerformance, resident_id: str = Depends(require_resident),
                       db: Session = Depends(get_db), graph: GraphClient = Depends(graph_dep)):
    """A booked performer (or the organiser, on their behalf) reports that the performance is off. This wakes the
    event-disruption agents, which act immediately if the organiser authorised autopilot."""
    organizer = events.organizer_of(graph, event_id)
    performer_id = resident_id
    if organizer == resident_id:
        row = graph.one("MATCH (:Event {event_id:$id})-[:FEATURES {status:'confirmed'}]->(r:Resident) "
                        "RETURN r.resident_id AS rid LIMIT 1", {"id": event_id}, readonly=True)
        performer_id = row["rid"] if row else resident_id
    try:
        talent.cancel_performance(graph, db, event_id, performer_id, body.reason)
    except LookupError:
        raise HTTPException(404, detail={"error": "not_found", "message": "No confirmed performance to cancel."})
    return event_workflow.handle_disruption(graph, db, event_id)


@router.post("/{event_id}/invitation")
def respond_invitation(event_id: str, body: InvitationResponse, resident_id: str = Depends(require_resident),
                       db: Session = Depends(get_db), graph: GraphClient = Depends(graph_dep)):
    try:
        result = talent.respond(graph, db, event_id, resident_id, body.accept)
    except LookupError:
        raise HTTPException(404, detail={"error": "not_found", "message": "No pending invitation."})
    if not body.accept and result["pending_left"] == 0 and graph.one(
            "MATCH (e:Event {event_id:$id}) WHERE e.performer_gap = true RETURN e.event_id AS id", {"id": event_id},
            readonly=True):
        result["agents"] = event_workflow.handle_disruption(graph, db, event_id)  # look for the next candidates
    return result


@router.post("/{event_id}/comments", status_code=201)
def comment(event_id: str, body: CommentCreate, resident_id: str = Depends(require_resident),
            graph: GraphClient = Depends(graph_dep)):
    try:
        return issues.comment(graph, "Event", event_id, resident_id, body.body)
    except LookupError:
        raise HTTPException(404, detail={"error": "not_found"})


@router.post("/{event_id}/updates", status_code=201)
def organizer_update(event_id: str, body: EventUpdateCreate, resident_id: str = Depends(require_resident),
                     db: Session = Depends(get_db), graph: GraphClient = Depends(graph_dep)):
    if events.organizer_of(graph, event_id) != resident_id:
        raise HTTPException(403, detail={"error": "forbidden", "message": "Only the organizer can post updates."})
    created = issues.comment(graph, "Event", event_id, resident_id, body.body, kind="organizer_update")
    notifications.notify(db, notifications.event_audience(graph, event_id), kind="organizer_update",
                         entity_id=event_id, message="The organizer posted an update.",
                         dedupe_key=f"evupd:{created['discussion_id']}", exclude=resident_id)
    return created
