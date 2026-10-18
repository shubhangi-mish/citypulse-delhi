"""Radius-based community discovery.

Candidate selection is geographic (FalkorDB point index + distance()), then every item is enriched by graph
traversal: reporter attribution, corroboration, the viewer's own relationships, coordination cases, affected
neighbourhoods for warnings. When the centre is the resident's home, it is resolved server-side and never
returned; distances are bucketed.
"""

from app.graph.client import GraphClient
from app.graph.model import public_props
from app.graph.queries import Q, query_id
from app.services import geo, places, residents
from app.graph.model import now_ms


def resolve_center(graph: GraphClient, *, viewer_id: str | None, lat: float | None, lng: float | None,
                   neighborhood_id: str | None) -> dict:
    """Returns {lat, lng, label, display_lat, display_lng}. display_* is safe to show; lat/lng may be private."""
    if neighborhood_id:
        n = places.get_neighborhood(graph, neighborhood_id)
        if n:
            return {"lat": n["latitude"], "lng": n["longitude"], "label": n["name"],
                    "display_lat": n["latitude"], "display_lng": n["longitude"], "mode": "neighborhood"}
    if lat is not None and lng is not None:
        return {"lat": lat, "lng": lng, "label": "Selected point", "display_lat": lat, "display_lng": lng,
                "mode": "point"}
    if viewer_id:
        home = residents.home_point(graph, viewer_id)
        if home:
            n = places.nearest_neighborhood(graph, *home)
            dlat, dlng = (n["latitude"], n["longitude"]) if n else geo.generalise(*home, "neighborhood")
            return {"lat": home[0], "lng": home[1], "label": n["name"] if n else "Your area",
                    "display_lat": dlat, "display_lng": dlng, "mode": "home"}
    return {"lat": geo.DELHI_CENTER[0], "lng": geo.DELHI_CENTER[1], "label": "Central Delhi",
            "display_lat": geo.DELHI_CENTER[0], "display_lng": geo.DELHI_CENTER[1], "mode": "default"}


def issues(graph: GraphClient, lat: float, lng: float, radius_m: int, viewer_id: str | None,
           following_only: bool = False, limit: int = 60) -> list[dict]:
    rows = graph.query(
        """
        MATCH (i:Issue)
        WHERE distance(i.location, point({latitude:$lat, longitude:$lng})) < $radius AND i.status <> 'closed'
        OPTIONAL MATCH (rep:Resident)-[rr:REPORTED]->(i)
        OPTIONAL MATCH (i)-[:LOCATED_IN]->(n:Neighborhood)
        OPTIONAL MATCH (c:Discussion {kind:'comment'})-[:ABOUT]->(i)
        OPTIONAL MATCH (case:CoordinationCase)-[:ADDRESSES]->(i)
        OPTIONAL MATCH (v:Resident {resident_id:$viewer})
        WITH i, rep, rr, n, count(DISTINCT c) AS comments, collect(DISTINCT case.status) AS case_statuses, v
        WITH i, rep, rr, n, comments, case_statuses,
             v IS NOT NULL AND size([(v)-[:SUPPORTS]->(i) | 1]) > 0 AS supported,
             v IS NOT NULL AND size([(v)-[:FOLLOWS]->(i) | 1]) > 0 AS following,
             rep.resident_id = $viewer AS mine
        WHERE NOT $following_only OR following OR mine
        RETURN properties(i) AS props, properties(rep) AS rep, properties(rr) AS rr, n.name AS neighborhood,
               comments, case_statuses, supported, following, mine,
               distance(i.location, point({latitude:$lat, longitude:$lng})) AS d
        ORDER BY i.created_at DESC LIMIT $limit
        """,
        {"lat": lat, "lng": lng, "radius": radius_m, "viewer": viewer_id or "", "following_only": following_only,
         "limit": limit}, readonly=True)
    out = []
    for r in rows:
        item = public_props("Issue", r["props"])
        show_name = r["rep"] and not (r["rr"] or {}).get("anonymous")
        item.update(
            kind="issue", neighborhood=r["neighborhood"], comment_count=r["comments"],
            reported_by=public_props("Resident", r["rep"])["display_name"] if show_name else None,
            in_coordination=any(s in ("open", "in_progress") for s in r["case_statuses"] if s),
            viewer={"supported": bool(r["supported"]), "following": bool(r["following"]), "mine": bool(r["mine"])},
            distance=geo.distance_bucket(r["d"]), sort_at=item.get("created_at"),
        )
        out.append(item)
    return out


def events(graph: GraphClient, lat: float, lng: float, radius_m: int, viewer_id: str | None,
           limit: int = 40) -> list[dict]:
    rows = graph.query(
        """
        MATCH (e:Event)
        WHERE e.end_time >= $now AND e.status <> 'cancelled'
          AND distance(e.location, point({latitude:$lat, longitude:$lng})) < $radius
        OPTIONAL MATCH (e)-[:HOSTED_AT]->(v:Venue)
        OPTIONAL MATCH (e)-[:LOCATED_IN]->(n:Neighborhood)
        OPTIONAL MATCH (p:Resident)-[:PARTICIPATES_IN]->(e)
        OPTIONAL MATCH (w:Warning)-[:MAY_IMPACT]->(e)
        WITH e, v, n, count(DISTINCT p) AS participants, count(DISTINCT w) AS warnings
        OPTIONAL MATCH (me:Resident {resident_id:$viewer})
        RETURN properties(e) AS props, v.name AS venue, n.name AS neighborhood, participants, warnings,
               me IS NOT NULL AND size([(me)-[:PARTICIPATES_IN]->(e) | 1]) > 0 AS participating,
               distance(e.location, point({latitude:$lat, longitude:$lng})) AS d
        ORDER BY e.start_time ASC LIMIT $limit
        """,
        {"lat": lat, "lng": lng, "radius": radius_m, "now": now_ms(), "viewer": viewer_id or "", "limit": limit},
        readonly=True)
    return [{**public_props("Event", r["props"]), "kind": "event", "venue": r["venue"],
             "neighborhood": r["neighborhood"], "participant_count": r["participants"],
             "warning_count": r["warnings"], "viewer": {"participating": bool(r["participating"])},
             "distance": geo.distance_bucket(r["d"]), "sort_at": r["props"].get("created_at")} for r in rows]


def warnings(graph: GraphClient, lat: float, lng: float, radius_m: int) -> list[dict]:
    rows = graph.query(
        """
        MATCH (w:Warning)-[:AFFECTS]->(n:Neighborhood)
        WHERE w.expires_at > $now AND distance(n.location, point({latitude:$lat, longitude:$lng})) < $radius
        WITH w, collect(DISTINCT n.name) AS areas
        RETURN properties(w) AS props, areas
        ORDER BY w.issued_at DESC
        """, {"lat": lat, "lng": lng, "radius": radius_m, "now": now_ms()}, readonly=True)
    return [{**public_props("Warning", r["props"]), "kind": "warning", "affected_neighborhoods": r["areas"][:8],
             "affected_count": len(r["areas"]), "sort_at": r["props"].get("issued_at")} for r in rows]


def contributors(graph: GraphClient, lat: float, lng: float, radius_m: int) -> dict:
    rows = graph.query(Q("nearby_contributors"), {"lat": lat, "lng": lng, "radius_m": radius_m}, readonly=True)
    people: dict[str, dict] = {}
    for r in rows:
        p = people.setdefault(r["resident_id"], {"resident_id": r["resident_id"], "display_name": r["display_name"],
                                                  "neighborhood": r["neighborhood"], "contributions": []})
        p["contributions"].append({"type": r["contribution"], "kind": r["kind"], "entity_id": r["entity_id"],
                                   "title": r["title"]})
    ranked = sorted(people.values(), key=lambda p: -len(p["contributions"]))
    return {"contributors": ranked, "query_id": query_id("nearby_contributors")}


def coordination(graph: GraphClient, lat: float, lng: float, radius_m: int) -> list[dict]:
    rows = graph.query(
        """
        MATCH (c:CoordinationCase)-[:ADDRESSES]->(i:Issue)
        WHERE c.status IN ['open', 'in_progress']
          AND distance(i.location, point({latitude:$lat, longitude:$lng})) < $radius
        OPTIONAL MATCH (p:Resident)-[:PARTICIPATES_IN]->(c)
        WITH c, collect(DISTINCT {issue_id: i.issue_id, title: i.title}) AS issues, count(DISTINCT p) AS participants
        RETURN properties(c) AS props, issues, participants
        ORDER BY c.updated_at DESC LIMIT 20
        """, {"lat": lat, "lng": lng, "radius": radius_m}, readonly=True)
    return [{**public_props("CoordinationCase", r["props"]), "kind": "coordination", "issues": r["issues"],
             "participant_count": r["participants"], "sort_at": r["props"].get("updated_at")} for r in rows]


def activity(graph: GraphClient, lat: float, lng: float, radius_m: int, viewer_id: str | None,
             kind: str = "all") -> list[dict]:
    items: list[dict] = []
    if kind in ("all", "complaints", "following"):
        items += issues(graph, lat, lng, radius_m, viewer_id, following_only=kind == "following")
    if kind in ("all", "events"):
        items += events(graph, lat, lng, radius_m, viewer_id)
    if kind in ("all", "warnings"):
        items += warnings(graph, lat, lng, radius_m)
    if kind in ("all", "community"):
        items += coordination(graph, lat, lng, radius_m)
    return sorted(items, key=lambda x: x.get("sort_at") or 0, reverse=True)
