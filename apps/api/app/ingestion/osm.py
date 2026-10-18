"""OpenStreetMap ingestion (ODbL) via Overpass.

Creates:
  (:AdministrativeArea) for the NCT of Delhi and its OSM districts
  (:Neighborhood) for named place=suburb|neighbourhood|quarter nodes
  (AdministrativeArea)-[:CONTAINS]->(Neighborhood) from OSM boundary membership (computed by Overpass)
  (:InfrastructureAsset) metro stations, hospitals, police/fire stations, public toilets, named parks
  (InfrastructureAsset)-[:OPERATED_BY]->(Organization) only where OSM has an explicit operator tag
  (InfrastructureAsset)-[:LOCATED_IN]->(Neighborhood) nearest named place (rule-inferred, labelled so)
All nodes get DERIVED_FROM -> (:Source {source_id:'src_osm'}).
"""

import hashlib
import json
import logging
import math
import time

import httpx

from app.core.config import REPO_ROOT, get_settings
from app.graph.client import GraphClient
from app.graph.model import VerificationStatus, now_ms

log = logging.getLogger("citypulse.ingestion.osm")

OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter"]
CACHE = REPO_ROOT / "data" / "cache"
SRC = "src_osm"
AREA = 'area["name"="Delhi"]["admin_level"="4"]["boundary"="administrative"]->.d;'

Q_DELHI = '[out:json][timeout:60];rel["name"="Delhi"]["admin_level"="4"]["boundary"="administrative"];out tags center;'
Q_DISTRICTS = (f'[out:json][timeout:120];{AREA}rel(area.d)["boundary"="administrative"]["admin_level"="5"];'
               'foreach->.r(.r out tags center;.r map_to_area->.a;'
               'node(area.a)["place"~"^(suburb|neighbourhood|quarter)$"]["name"];out ids;);')
Q_PLACES = f'[out:json][timeout:120];{AREA}node(area.d)["place"~"^(suburb|neighbourhood|quarter)$"]["name"];out body;'
Q_ASSETS = (f'[out:json][timeout:180];{AREA}('
            'nwr["station"="subway"](area.d);nwr["railway"="station"]["subway"="yes"](area.d);'
            'nwr["amenity"="hospital"]["name"](area.d);nwr["amenity"="police"](area.d);'
            'nwr["amenity"="fire_station"](area.d);nwr["amenity"="toilets"](area.d);'
            'nwr["leisure"="park"]["name"](area.d););out tags center;')


def _fetch(name: str, query: str, use_cache: bool) -> list[dict]:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"osm_{name}.json"
    if use_cache and path.exists() and time.time() - path.stat().st_mtime < 7 * 86400:
        return json.loads(path.read_text(encoding="utf-8"))["elements"]
    last: Exception | None = None
    for attempt in range(9):
        url = OVERPASS[attempt % len(OVERPASS)]
        try:
            r = httpx.post(url, data={"data": query}, headers={"User-Agent": get_settings().user_agent}, timeout=240)
            r.raise_for_status()
            elements = r.json()["elements"]
            path.write_text(r.text, encoding="utf-8")
            return elements
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            last = exc
            log.warning("Overpass %s failed (%s), retrying", url, exc)
            time.sleep(min(10 * 2 ** attempt, 300))
    raise RuntimeError(f"Overpass unavailable: {last}")


def _coords(el: dict) -> tuple[float, float] | None:
    if "lat" in el:
        return el["lat"], el["lon"]
    if "center" in el:
        return el["center"]["lat"], el["center"]["lon"]
    return None


def _asset_type(tags: dict) -> str | None:
    if tags.get("station") == "subway" or tags.get("subway") == "yes":
        return "metro_station"
    amenity = tags.get("amenity")
    if amenity in ("hospital", "police", "fire_station"):
        return amenity
    if amenity == "toilets":
        return "public_toilet"
    if tags.get("leisure") == "park":
        return "park"
    return None


DEFAULT_NAMES = {"public_toilet": "Public toilet", "police": "Police station", "fire_station": "Fire station"}


def _org_id(name: str) -> str:
    return "org_osm_" + hashlib.sha1(name.lower().encode()).hexdigest()[:12]


def _batched(rows: list, n: int = 400):
    for i in range(0, len(rows), n):
        yield rows[i:i + n]


def _nearest(lat: float, lng: float, places: list[dict], max_m: float = 3000) -> str | None:
    best, best_d = None, max_m
    coslat = math.cos(math.radians(lat))
    for p in places:
        dx = (p["longitude"] - lng) * 111_320 * coslat
        dy = (p["latitude"] - lat) * 110_574
        d = math.hypot(dx, dy)
        if d < best_d:
            best, best_d = p["neighborhood_id"], d
    return best


def ingest(graph: GraphClient, use_cache: bool = True) -> dict:
    now = now_ms()
    stats = {"fetched": 0, "upserted": 0}

    # 1. NCT of Delhi
    delhi = _fetch("delhi", Q_DELHI, use_cache)
    stats["fetched"] += len(delhi)
    delhi_area_id = None
    for el in delhi:
        c = _coords(el) or (28.6139, 77.2090)
        delhi_area_id = f"area_osm_r{el['id']}"
        graph.query(
            """
            MERGE (a:AdministrativeArea {area_id:$id})
            SET a.name = $name, a.type = 'union_territory', a.boundary_source = 'OpenStreetMap relation',
                a.osm_ref = $ref, a.latitude = $lat, a.longitude = $lng, a.authority_reference = 'Government of NCT of Delhi',
                a.retrieved_at = $now
            WITH a MATCH (s:Source {source_id:$src}) MERGE (a)-[:DERIVED_FROM]->(s)
            """, {"id": delhi_area_id, "name": el["tags"].get("name:en", el["tags"].get("name")),
                  "ref": f"relation/{el['id']}", "lat": c[0], "lng": c[1], "now": now, "src": SRC})

    # 2. Neighbourhoods
    places_raw = _fetch("places", Q_PLACES, use_cache)
    stats["fetched"] += len(places_raw)
    places = [{
        "neighborhood_id": f"nbh_osm_n{el['id']}", "osm_ref": f"node/{el['id']}",
        "name": el["tags"].get("name:en") or el["tags"]["name"], "administrative_type": el["tags"]["place"],
        "latitude": el["lat"], "longitude": el["lon"],
    } for el in places_raw if "lat" in el]
    for batch in _batched(places):
        graph.query(
            """
            UNWIND $rows AS p
            MERGE (n:Neighborhood {neighborhood_id: p.neighborhood_id})
            SET n.name = p.name, n.administrative_type = p.administrative_type, n.osm_ref = p.osm_ref,
                n.latitude = p.latitude, n.longitude = p.longitude,
                n.location = point({latitude: p.latitude, longitude: p.longitude}),
                n.source = 'OpenStreetMap', n.source_id = $src, n.geometry_reference = p.osm_ref,
                n.retrieved_at = $now, n.verification_status = $vs
            WITH n MATCH (s:Source {source_id:$src}) MERGE (n)-[:DERIVED_FROM]->(s)
            """, {"rows": batch, "src": SRC, "now": now, "vs": VerificationStatus.SOURCE_VERIFIED})
    stats["upserted"] += len(places)

    # 3. Districts and containment (membership computed by Overpass from OSM boundaries)
    elements = _fetch("districts", Q_DISTRICTS, use_cache)
    stats["fetched"] += len(elements)
    current, membership = None, []
    for el in elements:
        if el["type"] == "relation":
            c = _coords(el) or (None, None)
            current = f"area_osm_r{el['id']}"
            graph.query(
                """
                MERGE (a:AdministrativeArea {area_id:$id})
                SET a.name = $name, a.type = 'district', a.boundary_source = 'OpenStreetMap relation',
                    a.osm_ref = $ref, a.latitude = $lat, a.longitude = $lng, a.retrieved_at = $now
                WITH a MATCH (s:Source {source_id:$src}) MERGE (a)-[:DERIVED_FROM]->(s)
                WITH a OPTIONAL MATCH (d:AdministrativeArea {area_id:$parent})
                FOREACH (_ IN CASE WHEN d IS NULL THEN [] ELSE [1] END |
                    MERGE (d)-[:CONTAINS {basis:'osm_boundary', source_id:$src}]->(a))
                """, {"id": current, "name": el["tags"].get("name:en", el["tags"].get("name")),
                      "ref": f"relation/{el['id']}", "lat": c[0], "lng": c[1], "now": now, "src": SRC,
                      "parent": delhi_area_id or ""})
        elif el["type"] == "node" and current:
            membership.append({"area": current, "nbh": f"nbh_osm_n{el['id']}"})
    for batch in _batched(membership):
        graph.query(
            """
            UNWIND $rows AS m
            MATCH (a:AdministrativeArea {area_id: m.area}), (n:Neighborhood {neighborhood_id: m.nbh})
            MERGE (a)-[c:CONTAINS]->(n)
            SET c.basis = 'osm_boundary', c.source_id = $src, c.verification_status = $vs
            """, {"rows": batch, "src": SRC, "vs": VerificationStatus.SOURCE_VERIFIED})
    stats["upserted"] += len(membership)

    # 4. Infrastructure assets + explicit operator tags
    assets_raw = _fetch("assets", Q_ASSETS, use_cache)
    stats["fetched"] += len(assets_raw)
    assets, operated, seen_metro = [], [], set()
    for el in assets_raw:
        tags = el.get("tags", {})
        kind, c = _asset_type(tags), _coords(el)
        if not kind or not c:
            continue
        name = tags.get("name:en") or tags.get("name") or DEFAULT_NAMES.get(kind)
        if not name:
            continue
        if kind == "metro_station":
            key = name.lower().replace(" metro station", "").strip()
            if key in seen_metro:
                continue
            seen_metro.add(key)
        aid = f"ast_osm_{el['type'][0]}{el['id']}"
        assets.append({"asset_id": aid, "asset_type": kind, "name": name, "latitude": c[0], "longitude": c[1],
                       "osm_ref": f"{el['type']}/{el['id']}",
                       "nbh": _nearest(c[0], c[1], places)})
        operator = (tags.get("operator") or "").strip()
        if operator:
            operated.append({"asset": aid, "org_id": _org_id(operator), "org": " ".join(operator.split())})
    for batch in _batched(assets):
        graph.query(
            """
            UNWIND $rows AS a
            MERGE (x:InfrastructureAsset {asset_id: a.asset_id})
            SET x.asset_type = a.asset_type, x.name = a.name, x.latitude = a.latitude, x.longitude = a.longitude,
                x.location = point({latitude: a.latitude, longitude: a.longitude}), x.osm_ref = a.osm_ref,
                x.source_id = $src, x.verification_status = $vs, x.retrieved_at = $now
            WITH x, a MATCH (s:Source {source_id:$src}) MERGE (x)-[:DERIVED_FROM]->(s)
            WITH x, a MATCH (n:Neighborhood {neighborhood_id: a.nbh})
            MERGE (x)-[r:LOCATED_IN]->(n)
            SET r.basis = 'nearest_osm_place', r.verification_status = $inferred
            """, {"rows": batch, "src": SRC, "now": now, "vs": VerificationStatus.SOURCE_VERIFIED,
                  "inferred": VerificationStatus.RULE_INFERRED})
    for batch in _batched(operated):
        graph.query(
            """
            UNWIND $rows AS o
            MERGE (org:Organization {organization_id: o.org_id})
            ON CREATE SET org.name = o.org, org.category = 'operator (per OpenStreetMap)',
                          org.verification_status = $cr
            WITH org, o MATCH (x:InfrastructureAsset {asset_id: o.asset})
            MERGE (x)-[r:OPERATED_BY]->(org)
            SET r.basis = 'OpenStreetMap operator tag', r.source_id = $src, r.verification_status = $cr
            """, {"rows": batch, "src": SRC, "cr": VerificationStatus.COMMUNITY_REPORTED})
    stats["upserted"] += len(assets) + len(operated)
    graph.query("MATCH (s:Source {source_id:$src}) SET s.retrieved_at = $now", {"src": SRC, "now": now})
    log.info("OSM ingest: %s neighbourhoods, %s containment edges, %s assets, %s operator edges",
             len(places), len(membership), len(assets), len(operated))
    return {**stats, "neighborhoods": len(places), "containment": len(membership), "assets": len(assets),
            "operator_edges": len(operated)}
