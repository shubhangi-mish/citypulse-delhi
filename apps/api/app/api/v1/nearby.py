from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import AfterValidator

from app.api.deps import graph_dep
from app.graph.client import GraphClient
from app.security.auth import optional_resident
from app.services import nearby

router = APIRouter(prefix="/nearby", tags=["nearby"])


def _radius(v: int) -> int:
    if v not in (1, 3, 5, 10):
        raise ValueError("radius_km must be 1, 3, 5 or 10")
    return v


Radius = Annotated[int, AfterValidator(_radius)]


def _center(graph, viewer, lat, lng, neighborhood_id):
    return nearby.resolve_center(graph, viewer_id=viewer, lat=lat, lng=lng, neighborhood_id=neighborhood_id)


def _public_center(c: dict, radius_km: int) -> dict:
    return {"label": c["label"], "mode": c["mode"], "latitude": c["display_lat"], "longitude": c["display_lng"],
            "radius_km": radius_km}


@router.get("/activity")
def activity(radius_km: Radius = 3, kind: Literal["all", "complaints", "events", "community", "warnings",
                                                  "following"] = "all",
             lat: float | None = Query(None, ge=-90, le=90), lng: float | None = Query(None, ge=-180, le=180),
             neighborhood_id: str | None = None, viewer: str | None = Depends(optional_resident),
             graph: GraphClient = Depends(graph_dep)):
    c = _center(graph, viewer, lat, lng, neighborhood_id)
    items = nearby.activity(graph, c["lat"], c["lng"], radius_km * 1000, viewer, kind)
    return {"center": _public_center(c, radius_km), "items": items}


@router.get("/issues")
def issues(radius_km: Radius = 3, lat: float | None = None, lng: float | None = None,
           neighborhood_id: str | None = None, viewer: str | None = Depends(optional_resident),
           graph: GraphClient = Depends(graph_dep)):
    c = _center(graph, viewer, lat, lng, neighborhood_id)
    return {"center": _public_center(c, radius_km),
            "items": nearby.issues(graph, c["lat"], c["lng"], radius_km * 1000, viewer)}


@router.get("/events")
def events(radius_km: Radius = 3, lat: float | None = None, lng: float | None = None,
           neighborhood_id: str | None = None, viewer: str | None = Depends(optional_resident),
           graph: GraphClient = Depends(graph_dep)):
    c = _center(graph, viewer, lat, lng, neighborhood_id)
    return {"center": _public_center(c, radius_km),
            "items": nearby.events(graph, c["lat"], c["lng"], radius_km * 1000, viewer)}


@router.get("/warnings")
def warnings(radius_km: Radius = 3, lat: float | None = None, lng: float | None = None,
             neighborhood_id: str | None = None, viewer: str | None = Depends(optional_resident),
             graph: GraphClient = Depends(graph_dep)):
    c = _center(graph, viewer, lat, lng, neighborhood_id)
    return {"center": _public_center(c, radius_km),
            "items": nearby.warnings(graph, c["lat"], c["lng"], radius_km * 1000)}


@router.get("/contributors")
def contributors(radius_km: Radius = 3, lat: float | None = None, lng: float | None = None,
                 neighborhood_id: str | None = None, viewer: str | None = Depends(optional_resident),
                 graph: GraphClient = Depends(graph_dep)):
    c = _center(graph, viewer, lat, lng, neighborhood_id)
    return {"center": _public_center(c, radius_km), **nearby.contributors(graph, c["lat"], c["lng"], radius_km * 1000)}
