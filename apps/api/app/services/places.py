"""Connect new entities to the sourced geography already in the graph (OSM neighbourhoods, roads, assets)."""

from app.graph.client import GraphClient
from app.graph.model import ID_PROP, VerificationStatus, now_ms
from app.services import geo

OSM_SOURCE_ID = "src_osm"


def nearest_neighborhood(graph: GraphClient, lat: float, lng: float, max_m: int = 4000) -> dict | None:
    return graph.one(
        """
        MATCH (n:Neighborhood)
        WHERE distance(n.location, point({latitude:$lat, longitude:$lng})) < $max
        WITH n, distance(n.location, point({latitude:$lat, longitude:$lng})) AS d
        ORDER BY d ASC LIMIT 1
        RETURN n.neighborhood_id AS neighborhood_id, n.name AS name, n.latitude AS latitude,
               n.longitude AS longitude, d AS distance_m
        """,
        {"lat": lat, "lng": lng, "max": max_m}, readonly=True,
    )


def get_neighborhood(graph: GraphClient, neighborhood_id: str) -> dict | None:
    return graph.one(
        "MATCH (n:Neighborhood {neighborhood_id:$id}) RETURN n.neighborhood_id AS neighborhood_id, n.name AS name,"
        " n.latitude AS latitude, n.longitude AS longitude", {"id": neighborhood_id}, readonly=True)


def link_neighborhood(graph: GraphClient, label: str, entity_id: str, neighborhood_id: str, basis: str) -> None:
    graph.query(
        f"""
        MATCH (e:{label} {{{ID_PROP[label]}:$id}}), (n:Neighborhood {{neighborhood_id:$nid}})
        MERGE (e)-[r:LOCATED_IN]->(n)
        ON CREATE SET r.basis = $basis, r.created_at = $now, r.verification_status = $vs
        """,
        {"id": entity_id, "nid": neighborhood_id, "basis": basis, "now": now_ms(),
         "vs": VerificationStatus.RULE_INFERRED},
    )


def link_road(graph: GraphClient, label: str, entity_id: str, rel: str, lat: float, lng: float) -> dict | None:
    road = geo.reverse_road(lat, lng)
    if not road:
        return None
    row = graph.one(
        f"""
        MATCH (e:{label} {{{ID_PROP[label]}:$id}})
        MERGE (rd:Road {{osm_ref:$ref}})
        ON CREATE SET rd.road_id = $road_id, rd.name = $name, rd.road_class = $cls, rd.source_id = $src,
                      rd.created_at = $now
        MERGE (e)-[r:{rel}]->(rd)
        ON CREATE SET r.basis = 'osm_nominatim_reverse', r.created_at = $now, r.verification_status = $vs
        WITH rd
        MATCH (s:Source {{source_id:$src}})
        MERGE (rd)-[:DERIVED_FROM]->(s)
        RETURN rd.road_id AS road_id, rd.name AS name
        """,
        {"id": entity_id, "ref": road["osm_ref"], "road_id": "road_" + _slug(road["osm_ref"]), "name": road["name"],
         "cls": road["road_class"], "src": OSM_SOURCE_ID, "now": now_ms(), "vs": VerificationStatus.RULE_INFERRED},
    )
    return row


def link_nearby_assets(graph: GraphClient, label: str, entity_id: str, lat: float, lng: float,
                       max_m: int = 300, limit: int = 3) -> list[dict]:
    return graph.query(
        f"""
        MATCH (e:{label} {{{ID_PROP[label]}:$id}})
        MATCH (a:InfrastructureAsset)
        WHERE distance(a.location, point({{latitude:$lat, longitude:$lng}})) < $max
        WITH e, a, distance(a.location, point({{latitude:$lat, longitude:$lng}})) AS d
        ORDER BY d ASC LIMIT $limit
        MERGE (e)-[r:NEAR]->(a)
        ON CREATE SET r.distance_m = round(d), r.basis = 'geo_proximity', r.created_at = $now,
                      r.verification_status = $vs
        RETURN a.asset_id AS asset_id, a.name AS name, a.asset_type AS asset_type, round(d) AS distance_m
        """,
        {"id": entity_id, "lat": lat, "lng": lng, "max": max_m, "limit": limit, "now": now_ms(),
         "vs": VerificationStatus.RULE_INFERRED},
    )


def assets_near(graph: GraphClient, lat: float, lng: float, max_m: int = 400, limit: int = 10) -> list[dict]:
    return graph.query(
        """
        MATCH (a:InfrastructureAsset)
        WHERE distance(a.location, point({latitude:$lat, longitude:$lng})) < $max
        WITH a, distance(a.location, point({latitude:$lat, longitude:$lng})) AS d
        ORDER BY d ASC LIMIT $limit
        RETURN a.asset_id AS asset_id, a.name AS name, a.asset_type AS asset_type, round(d) AS distance_m
        """,
        {"lat": lat, "lng": lng, "max": max_m, "limit": limit}, readonly=True,
    )


def _slug(ref: str) -> str:
    import hashlib

    return hashlib.sha1(ref.encode()).hexdigest()[:16]
