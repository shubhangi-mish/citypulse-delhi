"""Sources, geocoding, operator auth, command overview, meta."""

import threading

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import graph_dep
from app.core.config import get_settings
from app.db.session import get_db
from app.graph.client import GraphClient, GraphUnavailable
from app.graph.model import now_ms
from app.ingestion import run as ingestion_run
from app.ingestion import sources
from app.schemas.requests import OperatorLogin
from app.security.auth import operator_login, operator_logout, optional_operator, require_operator
from app.services import audit, explorer, geo

router = APIRouter(tags=["system"])


@router.get("/sources")
def list_sources():
    return {"items": [{k: v for k, v in s.items()} for s in sources.manifest()]}


@router.get("/sources/status")
def sources_status(db: Session = Depends(get_db), graph: GraphClient = Depends(graph_dep)):
    try:
        items = sources.status(db, graph)
        graph_ok = True
    except GraphUnavailable:
        items, graph_ok = sources.status(db, None), False
    return {"items": items, "graph_available": graph_ok}


@router.post("/sources/{source_id}/refresh", status_code=202)
def refresh_source(source_id: str, operator: str = Depends(require_operator), db: Session = Depends(get_db)):
    if source_id not in ingestion_run.RUNNERS:
        raise HTTPException(404, detail={"error": "not_ingestible"})
    audit.record(db, "operator", operator, "source_refresh", source_id)
    threading.Thread(target=ingestion_run.run, args=(source_id, True), daemon=True).start()
    return {"started": True}


@router.get("/geo/config")
def geo_config():
    s = get_settings()
    return {"provider": "mapbox" if s.geocoding_token else "nominatim", "radii_km": list(geo.RADII_KM),
            "center": {"latitude": geo.DELHI_CENTER[0], "longitude": geo.DELHI_CENTER[1]}, "bbox": geo.DELHI_BBOX}


@router.get("/geo/search")
def geo_search(q: str = Query(min_length=3, max_length=200)):
    try:
        return geo.search(q)
    except Exception:
        raise HTTPException(502, detail={"error": "geocoder_unavailable",
                                         "message": "Address search is unavailable right now. Drop a pin on the map instead."})


@router.get("/neighborhoods")
def neighborhoods(q: str | None = None, lat: float | None = None, lng: float | None = None,
                  graph: GraphClient = Depends(graph_dep)):
    if lat is not None and lng is not None:
        rows = graph.query(
            """
            MATCH (n:Neighborhood)
            WHERE distance(n.location, point({latitude:$lat, longitude:$lng})) < 5000
            OPTIONAL MATCH (a:AdministrativeArea)-[:CONTAINS]->(n)
            RETURN n.neighborhood_id AS neighborhood_id, n.name AS name, a.name AS district,
                   n.latitude AS latitude, n.longitude AS longitude,
                   round(distance(n.location, point({latitude:$lat, longitude:$lng}))) AS distance_m
            ORDER BY distance_m ASC LIMIT 8
            """, {"lat": lat, "lng": lng}, readonly=True)
    else:
        rows = graph.query(
            """
            MATCH (n:Neighborhood)
            WHERE $q IS NULL OR toLower(n.name) CONTAINS toLower($q)
            OPTIONAL MATCH (a:AdministrativeArea)-[:CONTAINS]->(n)
            RETURN n.neighborhood_id AS neighborhood_id, n.name AS name, a.name AS district,
                   n.latitude AS latitude, n.longitude AS longitude
            ORDER BY n.name ASC LIMIT 40
            """, {"q": q}, readonly=True)
    return {"items": rows, "attribution": "© OpenStreetMap contributors (ODbL)"}


@router.get("/neighborhoods/{neighborhood_id}")
def neighborhood(neighborhood_id: str, graph: GraphClient = Depends(graph_dep)):
    row = graph.one(
        """
        MATCH (n:Neighborhood {neighborhood_id:$id})
        OPTIONAL MATCH (a:AdministrativeArea)-[:CONTAINS]->(n)
        OPTIONAL MATCH (i:Issue)-[:LOCATED_IN]->(n) WHERE i.status <> 'closed'
        WITH n, a, count(DISTINCT i) AS open_issues
        OPTIONAL MATCH (e:Event)-[:LOCATED_IN]->(n) WHERE e.end_time >= $now
        WITH n, a, open_issues, count(DISTINCT e) AS upcoming_events
        OPTIONAL MATCH (x:InfrastructureAsset)-[:LOCATED_IN]->(n)
        RETURN n.neighborhood_id AS neighborhood_id, n.name AS name, n.administrative_type AS type,
               n.latitude AS latitude, n.longitude AS longitude, n.osm_ref AS osm_ref, a.name AS district,
               open_issues, upcoming_events, count(DISTINCT x) AS assets
        """, {"id": neighborhood_id, "now": now_ms()}, readonly=True)
    if not row:
        raise HTTPException(404)
    return row


@router.get("/map/layers")
def map_layers(layers: str = "issues,events,warnings", min_lat: float = 28.40, min_lng: float = 76.83,
               max_lat: float = 28.89, max_lng: float = 77.35, graph: GraphClient = Depends(graph_dep)):
    """GeoJSON for the Explore map, limited to the viewport. Only public coordinates are returned."""
    want = set(layers.split(","))
    feats = []
    box = {"a": min_lat, "b": max_lat, "c": min_lng, "d": max_lng}
    if "issues" in want:
        for r in graph.query(
            """
            MATCH (i:Issue) WHERE i.status <> 'closed' AND i.public_lat >= $a AND i.public_lat <= $b
              AND i.public_lng >= $c AND i.public_lng <= $d
            RETURN i.issue_id AS id, i.title AS title, i.category AS category, i.status AS status,
                   i.public_lat AS lat, i.public_lng AS lng, i.support_count AS support
            LIMIT 2000
            """, box, readonly=True):
            feats.append(_feature("issue", r))
    if "events" in want:
        for r in graph.query(
            """
            MATCH (e:Event) WHERE e.end_time >= $now AND e.public_lat >= $a AND e.public_lat <= $b
              AND e.public_lng >= $c AND e.public_lng <= $d
            RETURN e.event_id AS id, e.title AS title, e.category AS category, e.start_time AS start,
                   e.public_lat AS lat, e.public_lng AS lng
            LIMIT 1000
            """, {**box, "now": now_ms()}, readonly=True):
            feats.append(_feature("event", r))
    if "warnings" in want:
        for r in graph.query(
            """
            MATCH (w:Warning)-[:AFFECTS]->(n:Neighborhood) WHERE w.expires_at > $now
              AND n.latitude >= $a AND n.latitude <= $b AND n.longitude >= $c AND n.longitude <= $d
            RETURN w.warning_id AS id, w.title AS title, w.severity AS severity, n.name AS area,
                   n.latitude AS lat, n.longitude AS lng
            LIMIT 3000
            """, {**box, "now": now_ms()}, readonly=True):
            feats.append(_feature("warning", r))
    if "infrastructure" in want:
        for r in graph.query(
            """
            MATCH (a:InfrastructureAsset) WHERE a.latitude >= $a AND a.latitude <= $b
              AND a.longitude >= $c AND a.longitude <= $d
            RETURN a.asset_id AS id, a.name AS title, a.asset_type AS category, a.latitude AS lat, a.longitude AS lng
            LIMIT 4000
            """, box, readonly=True):
            feats.append(_feature("infrastructure", r))
    if "neighborhoods" in want:
        for r in graph.query(
            """
            MATCH (n:Neighborhood) WHERE n.latitude >= $a AND n.latitude <= $b AND n.longitude >= $c
              AND n.longitude <= $d
            RETURN n.neighborhood_id AS id, n.name AS title, n.administrative_type AS category,
                   n.latitude AS lat, n.longitude AS lng
            LIMIT 2000
            """, box, readonly=True):
            feats.append(_feature("neighborhood", r))
    return {"type": "FeatureCollection", "features": feats,
            "attribution": "© OpenStreetMap contributors (ODbL); alerts: NDMA SACHET"}


def _feature(kind: str, r: dict) -> dict:
    props = {k: v for k, v in r.items() if k not in ("lat", "lng")}
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [r["lng"], r["lat"]]},
            "properties": {"kind": kind, **props}}


# ---------- operator auth ----------

@router.post("/operator/login")
def login(body: OperatorLogin, response: Response, db: Session = Depends(get_db)):
    if not get_settings().operators:
        raise HTTPException(503, detail={"error": "no_operators",
                                         "message": "No coordinator accounts are configured (OPERATOR_ACCOUNTS)."})
    if not operator_login(db, response, body.username, body.password):
        audit.record(db, "operator", body.username, "login_failed")
        raise HTTPException(401, detail={"error": "invalid_credentials", "message": "Invalid username or password."})
    audit.record(db, "operator", body.username, "login")
    return {"username": body.username}


@router.post("/operator/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    operator_logout(db, request, response)


@router.get("/operator/me")
def operator_me(operator: str | None = Depends(optional_operator)):
    return {"username": operator}


@router.get("/command/overview")
def overview(operator: str = Depends(require_operator), graph: GraphClient = Depends(graph_dep)):
    row = graph.one(
        """
        OPTIONAL MATCH (i:Issue) WHERE i.status <> 'closed' AND i.status <> 'resolved_reporter_confirmed'
        WITH count(i) AS open_reports
        OPTIONAL MATCH (i2:Issue) WHERE i2.status IN ['submitted', 'community_corroborated']
          AND NOT (i2)<-[:ADDRESSES]-(:CoordinationCase)
        WITH open_reports, count(i2) AS awaiting_review
        OPTIONAL MATCH (w:Warning) WHERE w.expires_at > $now
        WITH open_reports, awaiting_review, count(w) AS active_warnings
        OPTIONAL MATCH (e:Event) WHERE e.end_time >= $now
        WITH open_reports, awaiting_review, active_warnings, count(e) AS upcoming_events
        OPTIONAL MATCH (c:CoordinationCase) WHERE c.status IN ['open', 'in_progress']
        WITH open_reports, awaiting_review, active_warnings, upcoming_events, count(c) AS open_cases
        OPTIONAL MATCH (a:CoordinationAction {status:'proposed'})
        RETURN open_reports, awaiting_review, active_warnings, upcoming_events, open_cases,
               count(a) AS pending_recommendations
        """, {"now": now_ms()}, readonly=True)
    return {**row, "graph": explorer.stats(graph)}


@router.get("/command/audit")
def audit_log(operator: str = Depends(require_operator), db: Session = Depends(get_db)):
    return {"items": audit.recent(db)}
