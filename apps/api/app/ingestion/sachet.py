"""NDMA SACHET CAP alerts -> (:Warning) nodes.

Only alerts whose RSS title/author or CAP sender/areaDesc mention Delhi are kept. Area matching:
  * a Delhi district named in areaDesc -> AFFECTS every neighbourhood that OSM places inside that district
  * a neighbourhood named in areaDesc  -> AFFECTS that neighbourhood
  * "Delhi"/"NCT" without a finer area  -> AFFECTS the NCT AdministrativeArea and all its neighbourhoods
Each AFFECTS edge records its basis. Alert text is treated strictly as data (never as instructions).
"""

import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime

import httpx

from app.core.config import get_settings
from app.graph.client import GraphClient
from app.graph.model import VerificationStatus, now_ms

log = logging.getLogger("citypulse.ingestion.sachet")

RSS_URL = "https://sachet.ndma.gov.in/cap_public_website/rss/rss_india.xml"
SRC = "src_ndma_sachet"
CAP_NS = {"cap": "urn:oasis:names:tc:emergency:cap:1.2"}
DELHI_PATTERN = re.compile(r"\b(delhi|ncr|nct|shahdara)\b", re.I)
SEVERITY_ORDER = {"Extreme": 4, "Severe": 3, "Moderate": 2, "Minor": 1, "Unknown": 0}


def _parse_time(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(datetime.fromisoformat(value.strip()).timestamp() * 1000)
    except ValueError:
        return None


def _text(el: ET.Element | None, path: str) -> str | None:
    if el is None:
        return None
    node = el.find(path, CAP_NS)
    return node.text.strip() if node is not None and node.text else None


def fetch_feed(client: httpx.Client) -> list[dict]:
    r = client.get(RSS_URL)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    items = []
    for it in root.iter("item"):
        items.append({
            "title": (it.findtext("title") or "").strip(),
            "link": (it.findtext("link") or "").strip(),
            "author": (it.findtext("author") or "").strip(),
            "guid": (it.findtext("guid") or "").strip(),
            "category": (it.findtext("category") or "").strip(),
        })
    return items


def parse_cap(xml_bytes: bytes) -> dict:
    root = ET.fromstring(xml_bytes)
    info = None
    for candidate in root.findall("cap:info", CAP_NS):
        lang = (_text(candidate, "cap:language") or "").lower()
        if info is None or lang.startswith("en"):
            info = candidate
    areas = [(_text(a, "cap:areaDesc") or "") for a in (info.findall("cap:area", CAP_NS) if info is not None else [])]
    return {
        "identifier": _text(root, "cap:identifier"), "sender": _text(root, "cap:sender"),
        "sent": _parse_time(_text(root, "cap:sent")), "status": _text(root, "cap:status"),
        "msg_type": _text(root, "cap:msgType"), "scope": _text(root, "cap:scope"),
        "event": _text(info, "cap:event"), "category": _text(info, "cap:category"),
        "urgency": _text(info, "cap:urgency"), "severity": _text(info, "cap:severity"),
        "certainty": _text(info, "cap:certainty"), "effective": _parse_time(_text(info, "cap:effective")),
        "onset": _parse_time(_text(info, "cap:onset")), "expires": _parse_time(_text(info, "cap:expires")),
        "headline": _text(info, "cap:headline"), "description": _text(info, "cap:description"),
        "instruction": _text(info, "cap:instruction"), "area_desc": "; ".join(a for a in areas if a),
    }


def is_delhi(item: dict, cap: dict | None = None) -> bool:
    hay = " ".join([item.get("title", ""), item.get("author", "")] +
                   ([cap.get("sender") or "", cap.get("area_desc") or ""] if cap else []))
    return bool(DELHI_PATTERN.search(hay))


def _norm(s: str) -> str:
    return re.sub(r"[^a-z ]", " ", s.lower()).strip()


def match_areas(graph: GraphClient, area_desc: str, headline: str) -> dict:
    """Resolve CAP area text to graph entities. Returns {'districts': [...], 'neighborhoods': [...], 'nct': bool}."""
    text = f" {_norm(area_desc)} {_norm(headline)} "
    districts = graph.query("MATCH (a:AdministrativeArea {type:'district'}) RETURN a.area_id AS id, a.name AS name",
                            readonly=True)
    hit_districts = [d["id"] for d in districts if d["name"] and f" {_norm(d['name'])} " in text]
    nbhs = graph.query("MATCH (n:Neighborhood) RETURN n.neighborhood_id AS id, n.name AS name", readonly=True)
    hit_nbhs = [n["id"] for n in nbhs if n["name"] and len(n["name"]) > 4 and f" {_norm(n['name'])} " in text]
    nct = not hit_districts and not hit_nbhs and bool(DELHI_PATTERN.search(text))
    return {"districts": hit_districts, "neighborhoods": hit_nbhs, "nct": nct}


def upsert_warning(graph: GraphClient, item: dict, cap: dict, areas: dict) -> str:
    ext = cap["identifier"] or item["guid"]
    wid = "wrn_sachet_" + hashlib.sha1(ext.encode()).hexdigest()[:14]
    now = now_ms()
    expires = cap["expires"] or ((cap["effective"] or cap["sent"] or now) + 6 * 3600 * 1000)
    graph.query(
        """
        MERGE (w:Warning {warning_id:$id})
        SET w.external_id = $ext, w.title = $title, w.warning_type = $event, w.category = $category,
            w.severity = $severity, w.severity_rank = $rank, w.urgency = $urgency, w.certainty = $certainty,
            w.issuing_authority = $authority, w.issued_at = $sent, w.effective_at = $effective,
            w.expires_at = $expires, w.area_description = $area, w.instruction = $instruction,
            w.description = $description, w.cap_status = $status, w.cap_msg_type = $msg_type,
            w.source_url = $link, w.source_name = 'NDMA SACHET (CAP Integrated Alert System)',
            w.source_type = 'official_alert', w.license = 'Public domain (declared by feed)',
            w.published_at = $sent, w.last_verified_at = $now,
            w.verification_status = CASE WHEN $expires < $now THEN $expired ELSE $official END
        SET w.ingested_at = coalesce(w.ingested_at, $now)
        WITH w MATCH (s:Source {source_id:$src}) MERGE (w)-[:DERIVED_FROM]->(s)
        """,
        {"id": wid, "ext": ext, "title": cap["headline"] or item["title"], "event": cap["event"],
         "category": cap["category"], "severity": cap["severity"], "rank": SEVERITY_ORDER.get(cap["severity"] or "", 0),
         "urgency": cap["urgency"], "certainty": cap["certainty"],
         "authority": cap["sender"] + (f" — {item['author'].split('(')[-1].rstrip(')')}" if "(" in item["author"] else ""),
         "sent": cap["sent"], "effective": cap["effective"] or cap["sent"], "expires": expires,
         "area": cap["area_desc"], "instruction": cap["instruction"], "description": cap["description"],
         "status": cap["status"], "msg_type": cap["msg_type"], "link": item["link"], "now": now,
         "expired": VerificationStatus.EXPIRED, "official": VerificationStatus.OFFICIAL_VERIFIED, "src": SRC},
    )
    if areas["districts"]:
        graph.query(
            """
            MATCH (w:Warning {warning_id:$id}), (a:AdministrativeArea)-[:CONTAINS]->(n:Neighborhood)
            WHERE a.area_id IN $districts
            MERGE (w)-[r:AFFECTS]->(n) SET r.basis = 'cap_areaDesc_district_match', r.via = a.name
            WITH DISTINCT w, a MERGE (w)-[r2:AFFECTS]->(a) SET r2.basis = 'cap_areaDesc_district_match'
            """, {"id": wid, "districts": areas["districts"]})
    if areas["neighborhoods"]:
        graph.query(
            """
            MATCH (w:Warning {warning_id:$id}), (n:Neighborhood) WHERE n.neighborhood_id IN $nbhs
            MERGE (w)-[r:AFFECTS]->(n) SET r.basis = 'cap_areaDesc_name_match'
            """, {"id": wid, "nbhs": areas["neighborhoods"]})
    if areas["nct"]:
        graph.query(
            """
            MATCH (w:Warning {warning_id:$id}), (a:AdministrativeArea {type:'union_territory'})
            MERGE (w)-[r:AFFECTS]->(a) SET r.basis = 'cap_areaDesc_mentions_delhi'
            WITH w, a MATCH (a)-[:CONTAINS]->(:AdministrativeArea)-[:CONTAINS]->(n:Neighborhood)
            MERGE (w)-[r2:AFFECTS]->(n) SET r2.basis = 'cap_areaDesc_mentions_delhi'
            """, {"id": wid})
    return wid


def ingest(graph: GraphClient, max_alerts: int = 40) -> dict:
    from app.services.events import link_warnings

    s = get_settings()
    stats = {"fetched": 0, "upserted": 0, "delhi_candidates": 0}
    with httpx.Client(headers={"User-Agent": s.user_agent}, timeout=20) as client:
        items = fetch_feed(client)
        stats["fetched"] = len(items)
        candidates = [i for i in items if is_delhi(i)][:max_alerts]
        stats["delhi_candidates"] = len(candidates)
        for item in candidates:
            try:
                r = client.get(item["link"])
                r.raise_for_status()
                cap = parse_cap(r.content)
            except Exception as exc:
                log.warning("CAP fetch failed for %s: %s", item["link"], exc)
                continue
            if cap["status"] != "Actual" or not is_delhi(item, cap):
                continue
            # The issuing office (e.g. IMD New Delhi) may cover neighbouring states: keep the alert only if its
            # *area* resolves to Delhi entities in the graph.
            areas = match_areas(graph, cap["area_desc"] or "", cap["headline"] or "")
            if not (areas["districts"] or areas["neighborhoods"] or areas["nct"]):
                continue
            upsert_warning(graph, item, cap, areas)
            stats["upserted"] += 1
    graph.query("MATCH (w:Warning) WHERE w.expires_at < $now SET w.verification_status = $expired",
                {"now": now_ms(), "expired": VerificationStatus.EXPIRED})
    graph.query("MATCH (s:Source {source_id:$src}) SET s.retrieved_at = $now", {"src": SRC, "now": now_ms()})
    stats["event_links"] = link_warnings(graph)
    return stats
