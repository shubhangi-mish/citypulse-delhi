"""Resident profiles live in FalkorDB. Private fields (email, address, exact location) are only read here,
for the owner, and never by public queries."""

from app.graph.client import GraphClient
from app.graph.model import new_id, now_ms
from app.services import places

OWNER_PROJECTION = """
  r.resident_id AS resident_id, r.name AS name, r.email AS email, r.address AS address,
  r.latitude AS latitude, r.longitude AS longitude, r.public_visibility AS public_visibility,
  r.display_name_opt_in AS display_name_opt_in, r.discovery_opt_in AS discovery_opt_in,
  r.profession AS profession, r.open_to_gigs AS open_to_gigs, r.demo AS demo,
  r.area_updates_opt_in AS area_updates_opt_in, r.created_at AS created_at, r.updated_at AS updated_at
"""


def create(graph: GraphClient, *, name: str, email: str, address: str, latitude: float, longitude: float,
           neighborhood_id: str | None) -> dict:
    rid = new_id("res")
    now = now_ms()
    nbh = places.get_neighborhood(graph, neighborhood_id) if neighborhood_id else None
    basis = "resident_selected"
    if not nbh:
        nbh = places.nearest_neighborhood(graph, latitude, longitude)
        basis = "nearest_osm_place"
    graph.query(
        """
        CREATE (r:Resident {resident_id:$id, name:$name, email:$email, address:$address,
                latitude:$lat, longitude:$lng, location: point({latitude:$lat, longitude:$lng}),
                neighborhood_id:$nid, public_visibility:'private', display_name_opt_in:false,
                discovery_opt_in:false, area_updates_opt_in:true, created_at:$now, updated_at:$now})
        """,
        {"id": rid, "name": name, "email": email, "address": address, "lat": latitude, "lng": longitude,
         "nid": nbh["neighborhood_id"] if nbh else None, "now": now},
    )
    if nbh:
        graph.query(
            """
            MATCH (r:Resident {resident_id:$id}), (n:Neighborhood {neighborhood_id:$nid})
            CREATE (r)-[:LIVES_IN {basis:$basis, created_at:$now}]->(n)
            """,
            {"id": rid, "nid": nbh["neighborhood_id"], "basis": basis, "now": now},
        )
    return get_owner_view(graph, rid)  # type: ignore[return-value]


def get_owner_view(graph: GraphClient, resident_id: str) -> dict | None:
    row = graph.one(
        f"""
        MATCH (r:Resident {{resident_id:$id}})
        OPTIONAL MATCH (r)-[:LIVES_IN]->(n:Neighborhood)
        RETURN {OWNER_PROJECTION}, n.neighborhood_id AS neighborhood_id, n.name AS neighborhood_name,
               n.latitude AS neighborhood_latitude, n.longitude AS neighborhood_longitude
        """,
        {"id": resident_id}, readonly=True,
    )
    return row


def home_point(graph: GraphClient, resident_id: str) -> tuple[float, float] | None:
    row = graph.one("MATCH (r:Resident {resident_id:$id}) RETURN r.latitude AS lat, r.longitude AS lng",
                    {"id": resident_id}, readonly=True)
    return (row["lat"], row["lng"]) if row else None


def update(graph: GraphClient, resident_id: str, changes: dict) -> dict | None:
    allowed = {"name", "public_visibility", "display_name_opt_in", "discovery_opt_in", "area_updates_opt_in",
               "open_to_gigs"}
    profession = changes.get("profession")
    sets = {k: v for k, v in changes.items() if k in allowed and v is not None}
    loc = changes.get("location")
    if profession is not None:
        from app.services import talent
        talent.set_profession(graph, resident_id, profession)
    if sets:
        assignments = ", ".join(f"r.{k} = ${k}" for k in sets)
        graph.query(f"MATCH (r:Resident {{resident_id:$id}}) SET {assignments}, r.updated_at = $now",
                    {"id": resident_id, "now": now_ms(), **sets})
    if loc:
        graph.query(
            """
            MATCH (r:Resident {resident_id:$id})
            SET r.address = $address, r.latitude = $lat, r.longitude = $lng,
                r.location = point({latitude:$lat, longitude:$lng}), r.updated_at = $now
            WITH r OPTIONAL MATCH (r)-[l:LIVES_IN]->() DELETE l
            """,
            {"id": resident_id, "address": loc["address"], "lat": loc["latitude"], "lng": loc["longitude"],
             "now": now_ms()},
        )
        nbh = (places.get_neighborhood(graph, loc["neighborhood_id"]) if loc.get("neighborhood_id")
               else places.nearest_neighborhood(graph, loc["latitude"], loc["longitude"]))
        if nbh:
            graph.query(
                """
                MATCH (r:Resident {resident_id:$id}), (n:Neighborhood {neighborhood_id:$nid})
                SET r.neighborhood_id = $nid
                CREATE (r)-[:LIVES_IN {basis:$basis, created_at:$now}]->(n)
                """,
                {"id": resident_id, "nid": nbh["neighborhood_id"], "now": now_ms(),
                 "basis": "resident_selected" if loc.get("neighborhood_id") else "nearest_osm_place"},
            )
    return get_owner_view(graph, resident_id)


def delete(graph: GraphClient, resident_id: str) -> None:
    """Remove the resident and their comments. Reports they filed stay public (civic record) but lose any
    link back to them."""
    graph.query(
        """
        MATCH (r:Resident {resident_id:$id})
        OPTIONAL MATCH (r)-[:COMMENTED_ON]->(d:Discussion)
        DETACH DELETE d
        """,
        {"id": resident_id},
    )
    graph.query("MATCH (r:Resident {resident_id:$id}) DETACH DELETE r", {"id": resident_id})


def activity(graph: GraphClient, resident_id: str) -> dict:
    reported = graph.query(
        """
        MATCH (r:Resident {resident_id:$id})-[:REPORTED]->(i:Issue)
        RETURN i.issue_id AS issue_id, i.title AS title, i.status AS status, i.category AS category,
               i.support_count AS support_count, i.created_at AS created_at
        ORDER BY i.created_at DESC
        """, {"id": resident_id}, readonly=True)
    following = graph.query(
        """
        MATCH (r:Resident {resident_id:$id})-[rel:FOLLOWS|SUPPORTS]->(i:Issue)
        WHERE NOT (r)-[:REPORTED]->(i)
        RETURN i.issue_id AS issue_id, i.title AS title, i.status AS status, i.category AS category,
               i.support_count AS support_count, collect(DISTINCT type(rel)) AS relation, i.created_at AS created_at
        ORDER BY i.created_at DESC
        """, {"id": resident_id}, readonly=True)
    events = graph.query(
        """
        MATCH (r:Resident {resident_id:$id})-[rel:PARTICIPATES_IN|SUBMITTED]->(e:Event)
        RETURN e.event_id AS event_id, e.title AS title, e.start_time AS start_time, e.status AS status,
               collect(DISTINCT type(rel)) AS relation
        ORDER BY e.start_time ASC
        """, {"id": resident_id}, readonly=True)
    cases = graph.query(
        """
        MATCH (r:Resident {resident_id:$id})-[:PARTICIPATES_IN]->(c:CoordinationCase)
        RETURN c.case_id AS case_id, c.title AS title, c.status AS status
        """, {"id": resident_id}, readonly=True)
    return {"reported": reported, "following": following, "events": events, "cases": cases}
