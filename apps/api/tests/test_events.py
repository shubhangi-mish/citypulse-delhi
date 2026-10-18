import time

from tests.conftest import make_client, new_profile


def _event(c, **extra):
    start = int(time.time() * 1000) + 2 * 86400_000
    body = {"title": "Neighbourhood cleanup drive", "description": "Bring gloves; we clean the park and lanes together.",
            "category": "cleanup", "start_time": start, "end_time": start + 3 * 3600_000,
            "venue_name": "Fixture Park", "venue_address": "Near the fixture metro", "latitude": 28.6318,
            "longitude": 77.2171, "organizer_name": "Test Organizer", "organizer_contact": "organizer@example.com",
            "attestation": True, **extra}
    return c.post("/api/v1/events", json=body)


def test_event_requires_attestation(client):
    new_profile(client, email="e0@example.com")
    assert _event(client, attestation=False).status_code == 422


def test_event_graph_participation_and_privacy(graph):
    org, res = make_client(graph), make_client(graph)
    new_profile(org, email="org@example.com")
    r = _event(org, organization_name="Fixture RWA")
    assert r.status_code == 201
    eid = r.json()["event_id"]
    row = graph.one(
        """
        MATCH (:Resident)-[:SUBMITTED]->(e:Event {event_id:$id})-[:HOSTED_AT]->(v:Venue)-[:ACCESSIBLE_VIA]->(rd:Road)
        MATCH (e)-[:LOCATED_IN]->(n:Neighborhood), (e)-[:ORGANIZED_BY]->(o:Organization)
        RETURN e.verification_status AS vs, e.source_type AS st, rd.name AS road, n.name AS n, o.name AS o
        """, {"id": eid})
    assert row == {"vs": "COMMUNITY_REPORTED", "st": "user_submitted", "road": "Fixture Marg", "n": "Fixture Place A",
                   "o": "Fixture RWA"}
    new_profile(res, email="att@example.com")
    assert res.post(f"/api/v1/events/{eid}/participate", json={"role": "volunteer"}).status_code == 200
    public = res.get(f"/api/v1/events/{eid}").json()
    assert public["participant_roles"]["volunteer"] == 1
    assert "organizer_contact" not in public          # contact visible to the organizer only
    assert org.get(f"/api/v1/events/{eid}").json()["organizer_contact"] == "organizer@example.com"
    assert res.post(f"/api/v1/events/{eid}/updates", json={"body": "Hi"}).status_code in (403, 422)
    assert org.post(f"/api/v1/events/{eid}/updates", json={"body": "Meet at gate 2."}).status_code == 201
    assert any(n["kind"] == "organizer_update" for n in res.get("/api/v1/profiles/me/notifications").json()["items"])
