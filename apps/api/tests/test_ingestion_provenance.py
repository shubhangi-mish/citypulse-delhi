"""CAP parsing and provenance. The CAP document below mirrors the structure of real SACHET alerts
(urn:oasis:names:tc:emergency:cap:1.2); it is parsed into the TEST graph only."""

import time
from datetime import datetime, timedelta, timezone

from app.ingestion import sachet
from tests.conftest import make_client, new_profile

IST = timezone(timedelta(hours=5, minutes=30))


def _cap(area: str, hours: int = 3) -> bytes:
    now = datetime.now(IST)
    return f"""<cap:alert xmlns:cap="urn:oasis:names:tc:emergency:cap:1.2">
<cap:identifier>TEST-{time.time_ns()}</cap:identifier><cap:sender>Test-Sender</cap:sender>
<cap:sent>{now.isoformat()}</cap:sent><cap:status>Actual</cap:status><cap:msgType>Alert</cap:msgType>
<cap:scope>Public</cap:scope>
<cap:info><cap:language>en-IN</cap:language><cap:category>Met</cap:category><cap:event>Thunderstorm</cap:event>
<cap:urgency>Expected</cap:urgency><cap:severity>Moderate</cap:severity><cap:certainty>Likely</cap:certainty>
<cap:effective>{now.isoformat()}</cap:effective><cap:expires>{(now + timedelta(hours=hours)).isoformat()}</cap:expires>
<cap:headline>Test thunderstorm alert</cap:headline><cap:instruction>Follow official guidance.</cap:instruction>
<cap:area><cap:areaDesc>{area}</cap:areaDesc></cap:area></cap:info></cap:alert>""".encode()


def test_cap_parse_and_district_match(graph):
    cap = sachet.parse_cap(_cap("Fixture District"))
    assert cap["status"] == "Actual" and cap["severity"] == "Moderate" and cap["expires"] > cap["effective"]
    areas = sachet.match_areas(graph, cap["area_desc"], cap["headline"])
    assert areas["districts"] == ["area_test_d"]


def test_warning_has_full_provenance_and_affects_graph(graph):
    item = {"title": "Test alert", "link": "https://sachet.ndma.gov.in/cap_public_website/FetchXMLFile?identifier=T",
            "author": "controlroom@ndma.gov.in (IMD New Delhi)", "guid": "T", "category": "Met"}
    cap = sachet.parse_cap(_cap("Fixture District"))
    wid = sachet.upsert_warning(graph, item, cap, sachet.match_areas(graph, cap["area_desc"], cap["headline"]))
    w = graph.one(
        """
        MATCH (w:Warning {warning_id:$id})-[:DERIVED_FROM]->(s:Source {source_id:'src_ndma_sachet'})
        RETURN w.source_url AS url, w.source_name AS name, w.license AS license, w.published_at AS pub,
               w.ingested_at AS ing, w.last_verified_at AS ver, w.verification_status AS vs, w.expires_at AS exp
        """, {"id": wid})
    assert all(w[k] for k in ("url", "name", "license", "pub", "ing", "ver", "exp"))
    assert w["vs"] == "OFFICIAL_VERIFIED"
    affected = graph.one("MATCH (:Warning {warning_id:$id})-[:AFFECTS]->(n:Neighborhood) RETURN count(n) AS c",
                         {"id": wid})
    assert affected["c"] == 3

    # resident nearby sees it; warning impact query returns paths
    c = make_client(graph)
    new_profile(c, email="w@example.com")
    assert any(i.get("warning_id") == wid for i in c.get("/api/v1/nearby/warnings", params={"radius_km": 3}).json()["items"])
    detail = c.get(f"/api/v1/warnings/{wid}").json()
    assert detail["impact"]["query_id"].endswith("C_warning_impact.cypher")
    assert detail["impact"]["assets"][0]["path_rels"] == ["AFFECTS", "LOCATED_IN"]


def test_non_delhi_alert_is_rejected(graph):
    cap = sachet.parse_cap(_cap("Chamoli, Rudraprayag"))
    item = {"title": cap["headline"], "author": "controlroom@ndma.gov.in (IMD Dehradun)"}
    assert not sachet.is_delhi(item, cap)


def test_every_warning_and_event_has_source(graph):
    missing = graph.one(
        """
        OPTIONAL MATCH (w:Warning) WHERE NOT (w)-[:DERIVED_FROM]->(:Source) OR w.source_url IS NULL
        WITH count(w) AS bad_w
        OPTIONAL MATCH (e:Event) WHERE e.source_type IS NULL OR e.verification_status IS NULL
        RETURN bad_w, count(e) AS bad_e
        """)
    assert missing == {"bad_w": 0, "bad_e": 0}
