"""City Connections: privacy-safe subgraph exploration. Never loads the whole graph; every node passes through
the public property allowlist; residents appear only as "Resident (private)" unless they opted in."""

import secrets

from app.graph.client import GraphClient
from app.graph.model import ID_PROP, LABELS, display_label, label_for_id, public_props

# Relationship provenance class shown in the UI legend.
REL_CLASS = {
    "DERIVED_FROM": "verified", "CONTAINS": "verified", "AFFECTS": "verified", "OPERATED_BY": "community",
    "REPORTED": "community", "SUPPORTS": "community", "FOLLOWS": "community", "SUBMITTED": "community",
    "PARTICIPATES_IN": "community", "CONCERNS": "community", "COMMENTED_ON": "community", "ABOUT": "community",
    "ORGANIZED_BY": "community", "LIVES_IN": "community", "HOSTED_AT": "community",
    "LOCATED_IN": "inferred", "NEAR": "inferred", "ON_ROAD": "inferred", "ACCESSIBLE_VIA": "inferred",
    "POSSIBLY_DUPLICATES": "inferred", "MAY_IMPACT": "inferred",
    "ADDRESSES": "coordination", "PART_OF": "coordination", "APPROVED": "coordination",
    "CONSIDERED": "ai", "BASED_ON": "ai", "USED_MEMORY": "ai", "PRODUCED": "ai", "SUMMARIZES": "ai",
    "PRACTICES": "community", "FEATURES": "community", "ABOUT_EVENT": "community",
    "INVITED": "coordination", "AUTHORIZED": "coordination",
    "RECOMMENDED": "ai", "INFORMED": "ai", "RECORDS": "ai", "LEARNED_FROM": "ai",
}
REL_MEANING = {
    "LOCATED_IN": "is located in (nearest OSM place)", "CONTAINS": "contains (OSM boundary)",
    "REPORTED": "reported", "SUPPORTS": "is affected too", "FOLLOWS": "follows", "NEAR": "is near",
    "ON_ROAD": "is on road (OSM reverse geocode)", "CONCERNS": "concerns (reporter-selected)",
    "POSSIBLY_DUPLICATES": "may duplicate (graph heuristic)", "AFFECTS": "affects (official alert area)",
    "MAY_IMPACT": "may impact (time + place overlap)", "OPERATED_BY": "operated by (OSM operator tag)",
    "DERIVED_FROM": "derived from source", "ADDRESSES": "addresses", "PART_OF": "part of",
    "CONSIDERED": "agent considered", "BASED_ON": "agent decision based on", "USED_MEMORY": "agent used memory",
    "PRODUCED": "agent produced", "SUMMARIZES": "memory summarizes", "APPROVED": "approved",
    "HOSTED_AT": "hosted at", "ACCESSIBLE_VIA": "accessible via", "SUBMITTED": "submitted",
    "PARTICIPATES_IN": "participates in", "ORGANIZED_BY": "organized by", "LIVES_IN": "lives in",
    "COMMENTED_ON": "commented on", "ABOUT": "about", "RECOMMENDED": "recommended",
    "PRACTICES": "works as", "FEATURES": "features performer", "ABOUT_EVENT": "is about event",
    "INVITED": "invited to step in", "AUTHORIZED": "authorised (organiser autopilot)",
    "INFORMED": "handed off to (agent chain)", "RECORDS": "memory records action", "LEARNED_FROM": "memory learned from",
}
HIDDEN_FOR_PUBLIC = {"LIVES_IN", "COMMENTED_ON"}  # would reveal where a resident lives / what they wrote


def _node_id(label: str, props: dict) -> str | None:
    return props.get(ID_PROP.get(label, ""))


def _node(label: str, props: dict) -> dict:
    if label == "Resident" and not public_props(label, props)["display_name"]:
        # Private residents get a throwaway id per response: no expansion, no linking across views.
        return {"id": f"anon_{secrets.token_hex(4)}", "label": label, "name": "Resident (private)",
                "props": {}, "expandable": False}
    return {"id": _node_id(label, props), "label": label, "name": display_label(label, props),
            "props": public_props(label, props), "expandable": True}


def entity(graph: GraphClient, entity_id: str) -> dict | None:
    resolved = label_for_id(entity_id)
    if not resolved:
        return None
    label, prop = resolved
    row = graph.one(f"MATCH (n:{label} {{{prop}:$id}}) RETURN properties(n) AS p", {"id": entity_id}, readonly=True)
    if not row:
        return None
    node = _node(label, row["p"])
    return node if node["expandable"] else None


def neighbors(graph: GraphClient, entity_id: str, rel_types: list[str] | None = None, limit: int = 60,
              include_private_edges: bool = False) -> dict | None:
    resolved = label_for_id(entity_id)
    if not resolved:
        return None
    label, prop = resolved
    allowed = [t for t in (rel_types or list(REL_CLASS)) if t in REL_CLASS]
    if not include_private_edges:
        allowed = [t for t in allowed if t not in HIDDEN_FOR_PUBLIC]
    rows = graph.query(
        f"""
        MATCH (n:{label} {{{prop}:$id}})-[r]-(m)
        WHERE type(r) IN $types AND NOT m:Discussion
        RETURN labels(m)[0] AS label, properties(m) AS props, type(r) AS rel, properties(r) AS rprops,
               startNode(r) = n AS outgoing
        LIMIT $limit
        """, {"id": entity_id, "types": allowed, "limit": limit}, readonly=True)
    center = entity(graph, entity_id)
    if not center or not center.get("expandable"):
        return None
    nodes, edges = {center["id"]: center}, []
    for r in rows:
        if r["label"] not in {lbl for lbl, _ in LABELS.values()}:
            continue
        other = _node(r["label"], r["props"])
        if not other["id"]:
            continue
        nodes.setdefault(other["id"], other)
        src, dst = (center["id"], other["id"]) if r["outgoing"] else (other["id"], center["id"])
        rp = r["rprops"] or {}
        edges.append({
            "id": f"{src}-{r['rel']}-{dst}", "source": src, "target": dst, "type": r["rel"],
            "class": REL_CLASS.get(r["rel"], "community"), "meaning": REL_MEANING.get(r["rel"], r["rel"].lower()),
            "basis": rp.get("basis"), "verification_status": rp.get("verification_status"),
            "score": rp.get("score"), "reasons": rp.get("reasons"),
        })
    return {"center": center["id"], "nodes": list(nodes.values()), "edges": edges}


def shortest_path(graph: GraphClient, a: str, b: str, max_hops: int = 5) -> dict | None:
    ra, rb = label_for_id(a), label_for_id(b)
    if not ra or not rb:
        return None
    types = "|".join(t for t in REL_CLASS if t not in HIDDEN_FOR_PUBLIC)
    row = graph.one(
        f"""
        MATCH (x:{ra[0]} {{{ra[1]}:$a}}), (y:{rb[0]} {{{rb[1]}:$b}})
        WITH x, y
        MATCH p = shortestPath((x)-[:{types}*1..{int(max_hops)}]-(y))
        RETURN [n IN nodes(p) | {{label: labels(n)[0], props: properties(n)}}] AS ns,
               [r IN relationships(p) | type(r)] AS rels
        """, {"a": a, "b": b}, readonly=True)
    if not row:
        return {"found": False, "nodes": [], "rels": []}
    return {"found": True, "nodes": [_node(n["label"], n["props"]) for n in row["ns"]], "rels": row["rels"]}


def search(graph: GraphClient, q: str, limit: int = 12) -> list[dict]:
    """Name/title prefix search across public entity types (used by explorer & command pickers)."""
    term = q.strip().lower()
    if len(term) < 2:
        return []
    out = []
    for label, field in (("Issue", "title"), ("Event", "title"), ("Warning", "title"), ("Neighborhood", "name"),
                         ("InfrastructureAsset", "name"), ("Organization", "name"), ("AdministrativeArea", "name"),
                         ("CoordinationCase", "title")):
        rows = graph.query(
            f"MATCH (n:{label}) WHERE toLower(n.{field}) CONTAINS $q RETURN properties(n) AS p LIMIT $limit",
            {"q": term, "limit": limit}, readonly=True)
        out += [_node(label, r["p"]) for r in rows]
    out.sort(key=lambda n: (not n["name"].lower().startswith(term), len(n["name"])))
    return out[:limit]


def stats(graph: GraphClient) -> dict:
    labels = graph.query("MATCH (n) RETURN labels(n)[0] AS label, count(n) AS c", readonly=True)
    rels = graph.query("MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS c", readonly=True)
    return {"nodes": {r["label"]: r["c"] for r in labels}, "relationships": {r["type"]: r["c"] for r in rels}}
