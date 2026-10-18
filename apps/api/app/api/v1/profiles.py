from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import graph_dep
from app.db.session import get_db
from app.graph.client import GraphClient
from app.schemas.requests import ProfileCreate, ProfileUpdate
from app.security.auth import RESIDENT_COOKIE, end_resident_sessions, optional_resident, require_resident, \
    start_resident_session
from app.services import audit, notifications, residents

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.post("", status_code=201)
def create_profile(body: ProfileCreate, response: Response, db: Session = Depends(get_db),
                   graph: GraphClient = Depends(graph_dep)):
    """Quick profile. Always creates a NEW profile — an email address never unlocks an existing one."""
    profile = residents.create(graph, name=body.name, email=str(body.email), address=body.address,
                               latitude=body.latitude, longitude=body.longitude, neighborhood_id=body.neighborhood_id)
    start_resident_session(db, response, profile["resident_id"])
    return profile


@router.get("/me")
def me(resident_id: str | None = Depends(optional_resident), graph: GraphClient = Depends(graph_dep)):
    if not resident_id:
        return {"profile": None}
    profile = residents.get_owner_view(graph, resident_id)
    return {"profile": profile}


@router.patch("/me")
def update_me(body: ProfileUpdate, resident_id: str = Depends(require_resident),
              graph: GraphClient = Depends(graph_dep)):
    changes = body.model_dump(exclude_none=True)
    return residents.update(graph, resident_id, changes)


@router.delete("/me", status_code=204)
def delete_me(response: Response, resident_id: str = Depends(require_resident), db: Session = Depends(get_db),
              graph: GraphClient = Depends(graph_dep)):
    residents.delete(graph, resident_id)
    end_resident_sessions(db, resident_id)
    audit.record(db, "resident", resident_id, "profile_deleted")
    response.delete_cookie(RESIDENT_COOKIE, path="/")


@router.post("/me/sign-out", status_code=204)
def sign_out(response: Response):
    response.delete_cookie(RESIDENT_COOKIE, path="/")


@router.get("/me/activity")
def my_activity(resident_id: str = Depends(require_resident), graph: GraphClient = Depends(graph_dep)):
    return residents.activity(graph, resident_id)


@router.get("/me/notifications")
def my_notifications(resident_id: str = Depends(require_resident), db: Session = Depends(get_db)):
    items = notifications.list_for(db, resident_id)
    return {"items": items, "unread": sum(1 for i in items if not i["read"])}


@router.post("/me/notifications/read", status_code=204)
def read_notifications(resident_id: str = Depends(require_resident), db: Session = Depends(get_db)):
    notifications.mark_read(db, resident_id)


@router.get("/me/export")
def export_me(resident_id: str = Depends(require_resident), graph: GraphClient = Depends(graph_dep)):
    """Your own data, for transparency."""
    profile = residents.get_owner_view(graph, resident_id)
    if not profile:
        raise HTTPException(404)
    return {"profile": profile, "activity": residents.activity(graph, resident_id)}
