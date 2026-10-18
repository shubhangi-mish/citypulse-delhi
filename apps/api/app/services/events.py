"""Events: genuine resident/organizer submissions (labelled as such) and source-backed events."""

from app.graph.client import GraphClient
from app.graph.model import VerificationStatus, new_id, now_ms, public_props
from app.services import geo, places

CATEGORIES = {
    "cultural": "Cultural festivals", "concert": "Concerts", "exhibition": "Exhibitions",
    "educational": "Educational events", "community_meeting": "Community meetings",
    "cleanup": "Neighbourhood cleanups", "workshop": "Workshops", "market": "Markets",
    "volunteering": "Volunteering", "sports": "Sports and recreation",
}


def create(graph: GraphClient, resident_id: str, *, title: str, description: str, category: str,
           start_time: int, end_time: int, venue_name: str, venue_address: str, latitude: float, longitude: float,
           organizer_name: str, organizer_contact: str, organization_name: str | None, is_free: bool,
           setting: str, accessibility: str | None, registration_url: str | None, attestation: bool) -> dict:
    eid, vid = new_id("evt"), new_id("ven")
    now = now_ms()
    plat, plng = geo.generalise(latitude, longitude, "approximate")
    graph.query(
        """
        MATCH (r:Resident {resident_id:$rid})
        CREATE (v:Venue {venue_id:$vid, name:$venue_name, address:$venue_address, latitude:$lat, longitude:$lng,
                         location: point({latitude:$lat, longitude:$lng}), source_id:'citypulse_submission',
                         created_at:$now})
        CREATE (e:Event {event_id:$eid, title:$title, description:$description, category:$category,
                         start_time:$start, end_time:$end, status:'scheduled', venue_id:$vid,
                         location: point({latitude:$lat, longitude:$lng}), public_lat:$plat, public_lng:$plng,
                         organizer_name:$org_name, organizer_contact:$contact, is_free:$free, setting:$setting,
                         accessibility:$access, registration_url:$reg, source_type:'user_submitted',
                         source_id:'citypulse_submission', organizer_attestation:$attest,
                         verification_status:$vs, created_at:$now, updated_at:$now})
        CREATE (e)-[:HOSTED_AT {created_at:$now}]->(v)
        CREATE (r)-[:SUBMITTED {created_at:$now}]->(e)
        """,
        {"rid": resident_id, "vid": vid, "eid": eid, "venue_name": venue_name, "venue_address": venue_address,
         "lat": latitude, "lng": longitude, "plat": plat, "plng": plng, "now": now, "title": title,
         "description": description, "category": category, "start": start_time, "end": end_time,
         "org_name": organizer_name, "contact": organizer_contact, "free": is_free, "setting": setting,
         "access": accessibility, "reg": registration_url, "attest": attestation,
         "vs": VerificationStatus.COMMUNITY_REPORTED},
    )
    if organization_name:
        graph.query(
            """
            MATCH (e:Event {event_id:$eid})
            MERGE (o:Organization {name:$name})
            ON CREATE SET o.organization_id = $oid, o.category = 'community', o.verification_status = $vs,
                          o.created_at = $now
            CREATE (e)-[:ORGANIZED_BY {basis:'organizer_attestation', created_at:$now}]->(o)
            """,
            {"eid": eid, "name": organization_name.strip(), "oid": new_id("org"), "now": now,
             "vs": VerificationStatus.COMMUNITY_REPORTED},
        )
    nbh = places.nearest_neighborhood(graph, latitude, longitude)
    if nbh:
        places.link_neighborhood(graph, "Event", eid, nbh["neighborhood_id"], "nearest_osm_place")
        places.link_neighborhood(graph, "Venue", vid, nbh["neighborhood_id"], "nearest_osm_place")
    places.link_road(graph, "Venue", vid, "ACCESSIBLE_VIA", latitude, longitude)
    link_warnings(graph, eid)
    return {"event_id": eid}


def link_warnings(graph: GraphClient, event_id: str | None = None) -> int:
    """MAY_IMPACT: active warning affects the event's neighbourhood or venue road during the event window."""
    where = "WHERE e.event_id = $eid AND " if event_id else "WHERE "
    rows = graph.query(
        f"""
        MATCH (w:Warning)-[:AFFECTS]->(x)<-[:LOCATED_IN|ACCESSIBLE_VIA|HOSTED_AT*1..2]-(e:Event)
        {where} w.effective_at <= e.end_time AND w.expires_at >= e.start_time AND e.status <> 'cancelled'
        MERGE (w)-[m:MAY_IMPACT]->(e)
        ON CREATE SET m.basis = 'spatiotemporal_overlap', m.verification_status = $vs, m.created_at = $now,
                      m.via = coalesce(x.name, x.neighborhood_id)
        RETURN count(m) AS c
        """, {"eid": event_id, "vs": VerificationStatus.RULE_INFERRED, "now": now_ms()})
    return rows[0]["c"] if rows else 0


def list_events(graph: GraphClient, *, category: str | None, neighborhood_id: str | None, from_ms: int | None,
                to_ms: int | None, is_free: bool | None, setting: str | None, lat: float | None, lng: float | None,
                radius_m: int | None, include_past: bool = False, limit: int = 60) -> list[dict]:
    where, params = [], {"limit": limit, "now": now_ms()}
    if not include_past:
        where.append("e.end_time >= $now")
    if category:
        where.append("e.category = $category"); params["category"] = category
    if from_ms:
        where.append("e.end_time >= $from"); params["from"] = from_ms
    if to_ms:
        where.append("e.start_time <= $to"); params["to"] = to_ms
    if is_free is not None:
        where.append("e.is_free = $free"); params["free"] = is_free
    if setting:
        where.append("e.setting = $setting"); params["setting"] = setting
    if lat is not None and lng is not None and radius_m:
        where.append("distance(e.location, point({latitude:$lat, longitude:$lng})) < $radius")
        params.update(lat=lat, lng=lng, radius=radius_m)
    match = "MATCH (e:Event)"
    if neighborhood_id:
        match = "MATCH (e:Event)-[:LOCATED_IN]->(:Neighborhood {neighborhood_id:$nid})"
        params["nid"] = neighborhood_id
    rows = graph.query(
        f"""
        {match}
        {"WHERE " + " AND ".join(where) if where else ""}
        OPTIONAL MATCH (e)-[:HOSTED_AT]->(v:Venue)
        OPTIONAL MATCH (e)-[:LOCATED_IN]->(n:Neighborhood)
        OPTIONAL MATCH (p:Resident)-[:PARTICIPATES_IN]->(e)
        OPTIONAL MATCH (w:Warning)-[:MAY_IMPACT]->(e)
        WITH e, v, n, count(DISTINCT p) AS participants, count(DISTINCT w) AS warnings
        RETURN properties(e) AS props, v.name AS venue, n.name AS neighborhood, participants, warnings
        ORDER BY e.start_time ASC LIMIT $limit
        """, params, readonly=True)
    return [{**public_props("Event", r["props"]), "venue": r["venue"], "neighborhood": r["neighborhood"],
             "participant_count": r["participants"], "warning_count": r["warnings"]} for r in rows]


def detail(graph: GraphClient, event_id: str, viewer_id: str | None) -> dict | None:
    row = graph.one(
        """
        MATCH (e:Event {event_id:$id})
        OPTIONAL MATCH (e)-[:HOSTED_AT]->(v:Venue)
        OPTIONAL MATCH (v)-[:ACCESSIBLE_VIA]->(rd:Road)
        OPTIONAL MATCH (e)-[:LOCATED_IN]->(n:Neighborhood)
        OPTIONAL MATCH (e)-[:ORGANIZED_BY]->(o:Organization)
        OPTIONAL MATCH (sub:Resident)-[:SUBMITTED]->(e)
        RETURN properties(e) AS props, properties(v) AS venue, rd.road_id AS road_id, rd.name AS road,
               n.neighborhood_id AS neighborhood_id, n.name AS neighborhood,
               properties(o) AS org, sub.resident_id = $viewer AS is_organizer
        """, {"id": event_id, "viewer": viewer_id or ""}, readonly=True)
    if not row:
        return None
    ev = public_props("Event", row["props"])
    is_organizer = bool(row["is_organizer"])
    ev.update(
        venue=public_props("Venue", row["venue"]) if row["venue"] else None, road_id=row["road_id"],
        road=row["road"], neighborhood_id=row["neighborhood_id"], neighborhood=row["neighborhood"],
        organization=public_props("Organization", row["org"]) if row["org"] else None,
        is_organizer=is_organizer,
    )
    if is_organizer:
        ev["organizer_contact"] = row["props"].get("organizer_contact")
    parts = graph.query(
        """
        MATCH (r:Resident)-[p:PARTICIPATES_IN]->(e:Event {event_id:$id})
        RETURN properties(r) AS r, p.role AS role, r.resident_id = $viewer AS me
        """, {"id": event_id, "viewer": viewer_id or ""}, readonly=True)
    ev["participant_count"] = len(parts)
    ev["participant_roles"] = {role: sum(1 for p in parts if p["role"] == role)
                               for role in ("interested", "going", "volunteer")}
    ev["named_participants"] = [n for n in (public_props("Resident", p["r"])["display_name"] for p in parts) if n]
    ev["attendees"] = [{"name": pub["display_name"], "profession": pub["profession"], "role": p["role"]}
                       for p in parts for pub in [public_props("Resident", p["r"])] if pub["display_name"]]
    mine = next((p for p in parts if p["me"]), None)
    ev["viewer"] = {"participating": bool(mine), "role": mine["role"] if mine else None}
    ev["warnings"] = graph.query(
        """
        MATCH (w:Warning)-[m:MAY_IMPACT]->(e:Event {event_id:$id})
        RETURN w.warning_id AS warning_id, w.title AS title, w.severity AS severity,
               w.issuing_authority AS issuing_authority, m.via AS via, m.basis AS basis,
               m.verification_status AS verification_status
        """, {"id": event_id}, readonly=True)
    ev["nearby_issues"] = graph.query(
        """
        MATCH (e:Event {event_id:$id}), (i:Issue)
        WHERE i.status <> 'closed' AND distance(i.location, e.location) < 1000
        RETURN i.issue_id AS issue_id, i.title AS title, i.category AS category, i.status AS status,
               round(distance(i.location, e.location)) AS distance_m
        ORDER BY distance_m ASC LIMIT 6
        """, {"id": event_id}, readonly=True)
    ev["updates"] = graph.query(
        """
        MATCH (d:Discussion)-[:ABOUT]->(e:Event {event_id:$id})
        OPTIONAL MATCH (a:Resident)-[:COMMENTED_ON]->(d)
        RETURN properties(d) AS d, properties(a) AS a
        ORDER BY d.created_at ASC
        """, {"id": event_id}, readonly=True)
    ev["updates"] = [{**public_props("Discussion", u["d"]),
                      "actor": u["d"].get("actor"),
                      "author": public_props("Resident", u["a"])["display_name"] if u["a"] else None}
                     for u in ev["updates"]]
    perf = graph.query(
        """
        MATCH (:Event {event_id:$id})-[f:FEATURES]->(p:Resident)
        RETURN properties(p) AS p, f.status AS status, f.role AS role, f.confirmed_at AS confirmed_at
        ORDER BY confirmed_at ASC
        """, {"id": event_id}, readonly=True)
    ev["performers"] = [{**{k: v for k, v in public_props("Resident", x["p"]).items() if k != "demo"},
                         "status": x["status"], "role": x["role"]} for x in perf]
    inv = (graph.one(
        "MATCH (:Event {event_id:$id})-[i:INVITED]->(:Resident {resident_id:$rid}) RETURN i.status AS status",
        {"id": event_id, "rid": viewer_id or ""}, readonly=True) or {}).get("status")
    ev["viewer_invitation"] = inv
    cases = graph.query(
        """
        MATCH (c:CoordinationCase)-[:ADDRESSES]->(:Event {event_id:$id})
        WHERE c.status <> 'proposed'
        OPTIONAL MATCH (a:CoordinationAction)-[:PART_OF]->(c)
        WHERE a.status IN ['approved', 'executed', 'completed']
        RETURN c.case_id AS case_id, c.title AS title, c.status AS status, c.created_at AS created,
               collect(DISTINCT {action_type: a.action_type, description: a.description, status: a.status,
                                 outcome: a.outcome, proposed_by: a.proposed_by, authorised_by: a.approved_by,
                                 note: a.execution_note}) AS actions
        ORDER BY created DESC
        """, {"id": event_id}, readonly=True)
    ev["coordination"] = [{k: v for k, v in c.items() if k != "created"} | {"actions": [a for a in c["actions"] if a["action_type"]]}
                          for c in cases]
    return ev


def participate(graph: GraphClient, event_id: str, resident_id: str, role: str | None) -> None:
    if role is None:
        graph.query("MATCH (r:Resident {resident_id:$rid})-[p:PARTICIPATES_IN]->(e:Event {event_id:$id}) DELETE p",
                    {"id": event_id, "rid": resident_id})
        return
    graph.query(
        """
        MATCH (e:Event {event_id:$id}), (r:Resident {resident_id:$rid})
        MERGE (r)-[p:PARTICIPATES_IN]->(e)
        ON CREATE SET p.created_at = $now
        SET p.role = $role
        """, {"id": event_id, "rid": resident_id, "role": role, "now": now_ms()})


def organizer_of(graph: GraphClient, event_id: str) -> str | None:
    row = graph.one("MATCH (r:Resident)-[:SUBMITTED]->(e:Event {event_id:$id}) RETURN r.resident_id AS rid",
                    {"id": event_id}, readonly=True)
    return row["rid"] if row else None
