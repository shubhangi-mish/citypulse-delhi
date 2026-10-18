from app.graph.client import GraphClient
from app.graph.model import now_ms, public_props
from app.graph.queries import Q, query_id


def list_warnings(graph: GraphClient, include_expired: bool = False, limit: int = 60) -> list[dict]:
    rows = graph.query(
        f"""
        MATCH (w:Warning)
        {"" if include_expired else "WHERE w.expires_at > $now"}
        OPTIONAL MATCH (w)-[:AFFECTS]->(n:Neighborhood)
        OPTIONAL MATCH (w)-[:MAY_IMPACT]->(e:Event)
        WITH w, count(DISTINCT n) AS nbhs, count(DISTINCT e) AS events
        RETURN properties(w) AS props, nbhs, events
        ORDER BY w.issued_at DESC LIMIT $limit
        """, {"now": now_ms(), "limit": limit}, readonly=True)
    return [{**public_props("Warning", r["props"]), "affected_neighborhood_count": r["nbhs"],
             "affected_event_count": r["events"], "active": r["props"]["expires_at"] > now_ms()} for r in rows]


def detail(graph: GraphClient, warning_id: str) -> dict | None:
    row = graph.one(
        """
        MATCH (w:Warning {warning_id:$id})
        OPTIONAL MATCH (w)-[:DERIVED_FROM]->(s:Source)
        RETURN properties(w) AS props, properties(s) AS source
        """, {"id": warning_id}, readonly=True)
    if not row:
        return None
    w = public_props("Warning", row["props"])
    w["description"] = row["props"].get("description")
    w["active"] = row["props"]["expires_at"] > now_ms()
    w["source"] = public_props("Source", row["source"]) if row["source"] else None
    w["affected_areas"] = graph.query(
        """
        MATCH (w:Warning {warning_id:$id})-[r:AFFECTS]->(a:AdministrativeArea)
        RETURN a.area_id AS area_id, a.name AS name, a.type AS type, r.basis AS basis
        """, {"id": warning_id}, readonly=True)
    w["affected_neighborhoods"] = graph.query(
        """
        MATCH (w:Warning {warning_id:$id})-[r:AFFECTS]->(n:Neighborhood)
        RETURN n.neighborhood_id AS neighborhood_id, n.name AS name, n.latitude AS latitude,
               n.longitude AS longitude, r.basis AS basis, r.via AS via
        ORDER BY n.name LIMIT 400
        """, {"id": warning_id}, readonly=True)
    impact = graph.query(Q("warning_impact"), {"warning_id": warning_id, "now_ms": now_ms()}, readonly=True)
    w["impact"] = {
        "query_id": query_id("warning_impact"),
        "events": [i for i in impact if i["impact_type"] == "event"],
        "issues": [i for i in impact if i["impact_type"] == "issue"],
        "assets": [i for i in impact if i["impact_type"] == "asset"][:60],
        "asset_total": sum(1 for i in impact if i["impact_type"] == "asset"),
    }
    w["opted_in_residents"] = (graph.one(
        """
        MATCH (w:Warning {warning_id:$id})-[:AFFECTS]->(n:Neighborhood)<-[:LIVES_IN]-(r:Resident)
        WHERE r.area_updates_opt_in = true
        RETURN count(DISTINCT r) AS c
        """, {"id": warning_id}, readonly=True) or {"c": 0})["c"]
    return w
