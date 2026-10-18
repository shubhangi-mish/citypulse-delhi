"""Citizen reports. The issue, its reporter, place, road, nearby assets, duplicates, supporters, followers,
comments and coordination all live as nodes/edges in FalkorDB."""

from app.graph.client import GraphClient
from app.graph.model import VerificationStatus, new_id, now_ms, public_props
from app.graph.queries import Q, query_id
from app.services import geo, places

CATEGORIES = {
    "waterlogging": "Waterlogging", "roads_potholes": "Roads and potholes", "streetlights": "Streetlights",
    "garbage": "Garbage", "water_supply": "Water supply", "sanitation": "Public sanitation",
    "traffic_obstruction": "Traffic obstruction", "public_infrastructure": "Public infrastructure",
    "accessibility": "Accessibility", "other": "Other",
}
STATUSES = {
    "submitted": "Submitted", "community_corroborated": "Community corroborated",
    "under_review": "Under community review", "coordination_in_progress": "Coordination in progress",
    "resolved_reporter_confirmed": "Resolved by reporter confirmation", "closed": "Closed",
}
CORROBORATION_THRESHOLD = 3
DUPLICATE_THRESHOLD = 0.65
RELATED_WINDOW_MS = 120 * 24 * 3600 * 1000


def create(graph: GraphClient, resident_id: str, *, category: str, title: str, description: str,
           latitude: float, longitude: float, precision: str, anonymous: bool,
           concerns_asset_id: str | None = None, event_id: str | None = None) -> dict:
    iid = new_id("iss")
    now = now_ms()
    nbh = places.nearest_neighborhood(graph, latitude, longitude)
    if precision == "neighborhood" and nbh:
        plat, plng = round(nbh["latitude"], 4), round(nbh["longitude"], 4)
    else:
        plat, plng = geo.generalise(latitude, longitude, precision)
    graph.query(
        """
        MATCH (r:Resident {resident_id:$rid})
        CREATE (i:Issue {issue_id:$id, title:$title, description:$description, category:$category,
                status:'submitted', latitude:$lat, longitude:$lng,
                location: point({latitude:$lat, longitude:$lng}), public_lat:$plat, public_lng:$plng,
                public_location_precision:$precision, created_at:$now, updated_at:$now,
                verification_status:$vs, support_count:0, source_type:'citypulse_submission'})
        CREATE (r)-[:REPORTED {created_at:$now, anonymous:$anon}]->(i)
        """,
        {"rid": resident_id, "id": iid, "title": title, "description": description, "category": category,
         "lat": latitude, "lng": longitude, "plat": plat, "plng": plng, "precision": precision, "now": now,
         "vs": VerificationStatus.COMMUNITY_REPORTED, "anon": anonymous},
    )
    if nbh:
        places.link_neighborhood(graph, "Issue", iid, nbh["neighborhood_id"], "nearest_osm_place")
    places.link_road(graph, "Issue", iid, "ON_ROAD", latitude, longitude)
    places.link_nearby_assets(graph, "Issue", iid, latitude, longitude)
    if concerns_asset_id:
        graph.query(
            """
            MATCH (i:Issue {issue_id:$id}), (a:InfrastructureAsset {asset_id:$aid})
            MERGE (i)-[c:CONCERNS]->(a)
            ON CREATE SET c.created_at = $now, c.basis = 'reporter_selected', c.verification_status = $vs
            """,
            {"id": iid, "aid": concerns_asset_id, "now": now, "vs": VerificationStatus.COMMUNITY_REPORTED},
        )
    record_history(graph, iid, "Report submitted to the CityPulse community.")
    link_duplicates(graph, iid)
    if event_id:
        link_event(graph, iid, event_id)
    return {"issue_id": iid}


def link_event(graph: GraphClient, issue_id: str, event_id: str) -> None:
    """A complaint about an event: (Issue)-[:ABOUT_EVENT]->(Event), and if agents/coordinators are already working on
    that event (an open disruption case) the complaint joins the case."""
    now = now_ms()
    row = graph.one("MATCH (i:Issue {issue_id:$i}), (e:Event {event_id:$e}) MERGE (i)-[:ABOUT_EVENT {created_at:$now}]->(e) "
                    "RETURN e.title AS title", {"i": issue_id, "e": event_id, "now": now})
    if not row:
        return
    joined = graph.one(
        """
        MATCH (i:Issue {issue_id:$i}), (e:Event {event_id:$e})
        MATCH (c:CoordinationCase)-[:ADDRESSES]->(e) WHERE c.status IN ['open', 'in_progress']
        MERGE (c)-[:ADDRESSES {created_at:$now}]->(i)
        SET i.status = 'coordination_in_progress', i.updated_at = $now
        RETURN c.title AS title
        """, {"i": issue_id, "e": event_id, "now": now})
    record_history(graph, issue_id, f"Linked to the event “{row['title']}”"
                   + (f" and added to the coordination case “{joined['title']}”." if joined else "."))


def related(graph: GraphClient, issue_id: str, radius_m: int = 1500) -> list[dict]:
    return graph.query(Q("related_issues"),
                       {"issue_id": issue_id, "radius_m": radius_m, "since_ms": now_ms() - RELATED_WINDOW_MS},
                       readonly=True)


def link_duplicates(graph: GraphClient, issue_id: str) -> list[dict]:
    candidates = [r for r in related(graph, issue_id) if r["same_category"] and r["score"] >= DUPLICATE_THRESHOLD]
    for c in candidates:
        reasons = ["same category"]
        reasons += [f"same road: {x['name']}" for x in c["shared_roads"]]
        reasons += [f"near the same asset: {x['name']}" for x in c["shared_assets"]]
        reasons += [f"same neighbourhood: {x['name']}" for x in c["shared_neighborhoods"]]
        if c["distance_m"] < 250:
            reasons.append(f"{int(c['distance_m'])} m apart")
        graph.query(
            """
            MATCH (a:Issue {issue_id:$a}), (b:Issue {issue_id:$b})
            MERGE (a)-[d:POSSIBLY_DUPLICATES]->(b)
            ON CREATE SET d.score = $score, d.reasons = $reasons, d.basis = 'graph_heuristic',
                          d.query_id = $qid, d.verification_status = $vs, d.created_at = $now
            """,
            {"a": issue_id, "b": c["issue_id"], "score": round(c["score"], 2), "reasons": reasons,
             "qid": query_id("related_issues"), "vs": VerificationStatus.RULE_INFERRED, "now": now_ms()},
        )
    return candidates


def record_history(graph: GraphClient, issue_id: str, text: str, actor: str = "system") -> None:
    graph.query(
        """
        MATCH (i:Issue {issue_id:$id})
        CREATE (d:Discussion {discussion_id:$did, body:$body, created_at:$now, visibility:'public',
                              kind:'history', actor:$actor})-[:ABOUT]->(i)
        """,
        {"id": issue_id, "did": new_id("dis"), "body": text, "now": now_ms(), "actor": actor},
    )


def _attribution(rep_props: dict | None, rel_props: dict | None) -> str | None:
    if not rep_props or (rel_props or {}).get("anonymous"):
        return None
    return public_props("Resident", rep_props)["display_name"]


def list_issues(graph: GraphClient, *, status: str | None = None, category: str | None = None,
                neighborhood_id: str | None = None, lat: float | None = None, lng: float | None = None,
                radius_m: int | None = None, limit: int = 50) -> list[dict]:
    where, params = [], {"limit": limit}
    if status:
        where.append("i.status = $status"); params["status"] = status
    if category:
        where.append("i.category = $category"); params["category"] = category
    if lat is not None and lng is not None and radius_m:
        where.append("distance(i.location, point({latitude:$lat, longitude:$lng})) < $radius")
        params.update(lat=lat, lng=lng, radius=radius_m)
    match = "MATCH (i:Issue)"
    if neighborhood_id:
        match = "MATCH (i:Issue)-[:LOCATED_IN]->(:Neighborhood {neighborhood_id:$nid})"
        params["nid"] = neighborhood_id
    rows = graph.query(
        f"""
        {match}
        {"WHERE " + " AND ".join(where) if where else ""}
        OPTIONAL MATCH (i)-[:LOCATED_IN]->(n:Neighborhood)
        OPTIONAL MATCH (rep:Resident)-[rr:REPORTED]->(i)
        OPTIONAL MATCH (c:Discussion {{kind:'comment'}})-[:ABOUT]->(i)
        WITH i, n, rep, rr, count(c) AS comments
        RETURN properties(i) AS props, n.name AS neighborhood, properties(rep) AS rep, properties(rr) AS rr,
               comments
        ORDER BY i.created_at DESC LIMIT $limit
        """, params, readonly=True)
    return [_card(r) for r in rows]


def _card(r: dict) -> dict:
    out = public_props("Issue", r["props"])
    out.update(neighborhood=r.get("neighborhood"), comment_count=r.get("comments", 0),
               reported_by=_attribution(r.get("rep"), r.get("rr")))
    return out


def detail(graph: GraphClient, issue_id: str, viewer_id: str | None) -> dict | None:
    row = graph.one(
        """
        MATCH (i:Issue {issue_id:$id})
        OPTIONAL MATCH (rep:Resident)-[rr:REPORTED]->(i)
        OPTIONAL MATCH (i)-[:LOCATED_IN]->(n:Neighborhood)
        OPTIONAL MATCH (area:AdministrativeArea)-[:CONTAINS]->(n)
        OPTIONAL MATCH (i)-[:ON_ROAD]->(rd:Road)
        RETURN properties(i) AS props, properties(rep) AS rep, properties(rr) AS rr,
               rep.resident_id = $viewer AS is_mine,
               n.neighborhood_id AS neighborhood_id, n.name AS neighborhood, area.name AS district,
               rd.road_id AS road_id, rd.name AS road
        """, {"id": issue_id, "viewer": viewer_id or ""}, readonly=True)
    if not row:
        return None
    issue = public_props("Issue", row["props"])
    issue.update(
        reported_by=_attribution(row["rep"], row["rr"]), is_mine=bool(row["is_mine"]),
        neighborhood_id=row["neighborhood_id"], neighborhood=row["neighborhood"], district=row["district"],
        road_id=row["road_id"], road=row["road"], case_reference=f"CP-{issue_id[4:12].upper()}",
    )
    lat, lng = row["props"]["latitude"], row["props"]["longitude"]

    issue["assets"] = graph.query(
        """
        MATCH (i:Issue {issue_id:$id})-[r:NEAR|CONCERNS]->(a:InfrastructureAsset)
        OPTIONAL MATCH (a)-[o:MAINTAINED_BY|OPERATED_BY|RESPONSIBLE_FOR]->(org:Organization)
        RETURN a.asset_id AS asset_id, a.name AS name, a.asset_type AS asset_type, type(r) AS relationship,
               r.distance_m AS distance_m, r.verification_status AS verification_status,
               collect(DISTINCT {name: org.name, relationship: type(o), basis: o.basis}) AS organizations
        """, {"id": issue_id}, readonly=True)
    for a in issue["assets"]:
        a["organizations"] = [o for o in a["organizations"] if o["name"]]

    viewer = {"supported": False, "following": False}
    if viewer_id:
        v = graph.one(
            """
            MATCH (i:Issue {issue_id:$id}), (r:Resident {resident_id:$rid})
            RETURN size([(r)-[:SUPPORTS]->(i) | 1]) > 0 AS supported, size([(r)-[:FOLLOWS]->(i) | 1]) > 0 AS following
            """, {"id": issue_id, "rid": viewer_id}, readonly=True)
        viewer = v or viewer
    issue["viewer"] = viewer

    issue["discussion"] = graph.query(
        """
        MATCH (d:Discussion)-[:ABOUT]->(i:Issue {issue_id:$id})
        OPTIONAL MATCH (author:Resident)-[:COMMENTED_ON]->(d)
        RETURN properties(d) AS d, properties(author) AS author, author.resident_id = $viewer AS mine
        ORDER BY d.created_at ASC
        """, {"id": issue_id, "viewer": viewer_id or ""}, readonly=True)
    issue["discussion"] = [
        {**public_props("Discussion", x["d"]),
         "author": (public_props("Resident", x["author"])["display_name"] if x["author"] else None),
         "mine": bool(x["mine"])}
        for x in issue["discussion"]
    ]

    issue["about_event"] = graph.one(
        "MATCH (:Issue {issue_id:$id})-[:ABOUT_EVENT]->(e:Event) RETURN e.event_id AS event_id, e.title AS title",
        {"id": issue_id}, readonly=True)
    issue["related"] = related(graph, issue_id)
    issue["related_query_id"] = query_id("related_issues")
    issue["network"] = graph.one(Q("coordination_network"), {"issue_id": issue_id}, readonly=True)

    issue["warnings"] = graph.query(
        """
        MATCH (i:Issue {issue_id:$id})-[:LOCATED_IN]->(n:Neighborhood)<-[:AFFECTS]-(w:Warning)
        WHERE w.expires_at > $now
        RETURN DISTINCT w.warning_id AS warning_id, w.title AS title, w.severity AS severity,
               w.issuing_authority AS issuing_authority, w.expires_at AS expires_at
        """, {"id": issue_id, "now": now_ms()}, readonly=True)
    issue["nearby_events"] = graph.query(
        """
        MATCH (e:Event)
        WHERE e.end_time >= $now AND distance(e.location, point({latitude:$lat, longitude:$lng})) < 2000
        RETURN e.event_id AS event_id, e.title AS title, e.start_time AS start_time,
               round(distance(e.location, point({latitude:$lat, longitude:$lng}))) AS distance_m
        ORDER BY e.start_time ASC LIMIT 5
        """, {"now": now_ms(), "lat": lat, "lng": lng}, readonly=True)
    return issue


def support(graph: GraphClient, issue_id: str, resident_id: str) -> dict:
    row = graph.one(
        """
        MATCH (i:Issue {issue_id:$id}), (r:Resident {resident_id:$rid})
        OPTIONAL MATCH (r)-[mine:REPORTED]->(i)
        RETURN mine IS NOT NULL AS is_reporter, size([(r)-[:SUPPORTS]->(i) | 1]) > 0 AS already
        """, {"id": issue_id, "rid": resident_id}, readonly=True)
    if not row:
        raise LookupError("issue")
    if row["is_reporter"]:
        raise PermissionError("Reporters cannot corroborate their own report.")
    graph.query(
        """
        MATCH (i:Issue {issue_id:$id}), (r:Resident {resident_id:$rid})
        MERGE (r)-[s:SUPPORTS]->(i)
        ON CREATE SET s.created_at = $now
        MERGE (r)-[f:FOLLOWS]->(i)
        ON CREATE SET f.created_at = $now
        WITH i
        MATCH (i)<-[:SUPPORTS]-(x:Resident)
        WITH i, count(DISTINCT x) AS c
        SET i.support_count = c, i.updated_at = $now
        RETURN c
        """, {"id": issue_id, "rid": resident_id, "now": now_ms()})
    upgraded = graph.one(
        """
        MATCH (i:Issue {issue_id:$id})
        WHERE i.status = 'submitted' AND i.support_count >= $threshold
        SET i.status = 'community_corroborated', i.verification_status = $vs
        RETURN i.issue_id AS id
        """, {"id": issue_id, "threshold": CORROBORATION_THRESHOLD,
              "vs": VerificationStatus.COMMUNITY_CORROBORATED})
    if upgraded:
        record_history(graph, issue_id,
                       f"Corroborated by {CORROBORATION_THRESHOLD}+ residents — status is now Community corroborated.")
    count = graph.one("MATCH (i:Issue {issue_id:$id}) RETURN i.support_count AS c, i.status AS s",
                      {"id": issue_id}, readonly=True)
    return {"support_count": count["c"], "status": count["s"], "newly_supported": not row["already"]}


def unsupport(graph: GraphClient, issue_id: str, resident_id: str) -> dict:
    graph.query(
        """
        MATCH (r:Resident {resident_id:$rid})-[s:SUPPORTS]->(i:Issue {issue_id:$id}) DELETE s
        """, {"id": issue_id, "rid": resident_id})
    row = graph.one(
        """
        MATCH (i:Issue {issue_id:$id})
        OPTIONAL MATCH (i)<-[:SUPPORTS]-(x:Resident)
        WITH i, count(DISTINCT x) AS c
        SET i.support_count = c
        RETURN c
        """, {"id": issue_id})
    return {"support_count": row["c"] if row else 0}


def set_follow(graph: GraphClient, issue_id: str, resident_id: str, follow: bool) -> None:
    if follow:
        graph.query(
            """
            MATCH (i:Issue {issue_id:$id}), (r:Resident {resident_id:$rid})
            MERGE (r)-[f:FOLLOWS]->(i) ON CREATE SET f.created_at = $now
            """, {"id": issue_id, "rid": resident_id, "now": now_ms()})
    else:
        graph.query("MATCH (r:Resident {resident_id:$rid})-[f:FOLLOWS]->(i:Issue {issue_id:$id}) DELETE f",
                    {"id": issue_id, "rid": resident_id})


def comment(graph: GraphClient, label: str, entity_id: str, resident_id: str, body: str,
            kind: str = "comment") -> dict:
    id_prop = {"Issue": "issue_id", "Event": "event_id", "CoordinationCase": "case_id"}[label]
    did = new_id("dis")
    row = graph.one(
        f"""
        MATCH (e:{label} {{{id_prop}:$id}}), (r:Resident {{resident_id:$rid}})
        CREATE (r)-[:COMMENTED_ON {{created_at:$now}}]->(d:Discussion {{discussion_id:$did, body:$body,
               created_at:$now, visibility:'public', kind:$kind}})-[:ABOUT]->(e)
        RETURN d.discussion_id AS discussion_id
        """, {"id": entity_id, "rid": resident_id, "did": did, "body": body, "now": now_ms(), "kind": kind})
    if not row:
        raise LookupError(label)
    return row


def set_status(graph: GraphClient, issue_id: str, status: str, actor: str) -> None:
    graph.query("MATCH (i:Issue {issue_id:$id}) SET i.status = $s, i.updated_at = $now",
                {"id": issue_id, "s": status, "now": now_ms()})
    record_history(graph, issue_id, f"Status changed to {STATUSES[status]}.", actor)


def reporter_of(graph: GraphClient, issue_id: str) -> str | None:
    row = graph.one("MATCH (r:Resident)-[:REPORTED]->(i:Issue {issue_id:$id}) RETURN r.resident_id AS rid",
                    {"id": issue_id}, readonly=True)
    return row["rid"] if row else None
