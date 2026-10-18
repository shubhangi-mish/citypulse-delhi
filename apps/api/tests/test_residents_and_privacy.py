import json

from tests.conftest import make_client, new_issue, new_profile

PRIVATE_KEYS = {"email", "address", "latitude", "longitude", "location"}


def _walk(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k, v
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def test_profile_persisted_in_graph(client, graph):
    p = new_profile(client, email="owner@example.com")
    row = graph.one("MATCH (r:Resident {resident_id:$id})-[:LIVES_IN]->(n:Neighborhood) RETURN r.email AS e, n.name AS n",
                    {"id": p["resident_id"]})
    assert row == {"e": "owner@example.com", "n": "Fixture Place A"}
    me = client.get("/api/v1/profiles/me").json()["profile"]
    assert me["resident_id"] == p["resident_id"] and me["public_visibility"] == "private"


def test_email_does_not_unlock_existing_profile(graph):
    a, b = make_client(graph), make_client(graph)
    pa = new_profile(a, name="Alice", email="same@example.com")
    pb = new_profile(b, name="Mallory", email="same@example.com")
    assert pa["resident_id"] != pb["resident_id"]
    me_b = b.get("/api/v1/profiles/me").json()["profile"]
    assert me_b["resident_id"] == pb["resident_id"] and me_b["name"] == "Mallory"
    anon = make_client(graph)
    assert anon.get("/api/v1/profiles/me").json() == {"profile": None}


def test_nearby_contributors_never_leak_private_fields(graph):
    a = make_client(graph)
    pa = new_profile(a, name="Public Pat", email="pat@example.com")
    a.patch("/api/v1/profiles/me", json={"public_visibility": "public", "display_name_opt_in": True})
    iid = new_issue(a, title="Broken streetlight near the gate", category="streetlights")
    b = make_client(graph)
    new_profile(b, name="Private Priya", email="priya@example.com", lat=28.6330, lng=77.2175)
    b.post(f"/api/v1/issues/{iid}/support", json={"affected": True})

    r = b.get("/api/v1/nearby/contributors", params={"radius_km": 1})
    body = r.json()
    names = [c["display_name"] for c in body["contributors"]]
    assert "Public Pat" in names and "Private Priya" not in names
    text = json.dumps(body)
    assert "pat@example.com" not in text and "priya@example.com" not in text and "Fixture address" not in text
    assert not any(k in PRIVATE_KEYS for k, _ in _walk(body["contributors"]))
    # centre derived from the viewer's home is generalised, never the home point
    assert body["center"]["mode"] == "home"
    assert (body["center"]["latitude"], body["center"]["longitude"]) != (28.6330, 77.2175)


def test_issue_detail_and_explorer_hide_private_residents(graph):
    a = make_client(graph)
    pa = new_profile(a, name="Hidden Harsh", email="harsh@example.com")
    iid = new_issue(a, title="Overflowing garbage bins", category="garbage")
    detail = make_client(graph).get(f"/api/v1/issues/{iid}").json()
    assert detail["reported_by"] is None
    assert "harsh@example.com" not in json.dumps(detail) and "Hidden Harsh" not in json.dumps(detail)
    assert not any(k in PRIVATE_KEYS for k, _ in _walk(detail))

    nb = make_client(graph).get(f"/api/v1/graph/entities/{iid}/neighbors").json()
    residents = [n for n in nb["nodes"] if n["label"] == "Resident"]
    assert residents and all(n["name"] == "Resident (private)" and n["id"].startswith("anon_") for n in residents)
    assert pa["resident_id"] not in json.dumps(nb)
    # private resident cannot be expanded by id
    assert make_client(graph).get(f"/api/v1/graph/entities/{pa['resident_id']}/neighbors").status_code == 404


def test_anonymous_report_not_attributed_even_for_public_profile(graph):
    a = make_client(graph)
    new_profile(a, name="Open Olu", email="olu@example.com")
    a.patch("/api/v1/profiles/me", json={"public_visibility": "public", "display_name_opt_in": True})
    iid = new_issue(a, title="Pothole outside the school", category="roads_potholes", anonymous=True)
    assert make_client(graph).get(f"/api/v1/issues/{iid}").json()["reported_by"] is None


def test_profile_deletion_removes_resident(graph):
    a = make_client(graph)
    p = new_profile(a, email="gone@example.com")
    iid = new_issue(a, title="Missing manhole cover", category="public_infrastructure")
    assert a.delete("/api/v1/profiles/me").status_code == 204
    assert graph.one("MATCH (r:Resident {resident_id:$id}) RETURN r", {"id": p["resident_id"]}) is None
    assert make_client(graph).get(f"/api/v1/issues/{iid}").status_code == 200  # civic record stays, unattributed


def test_csrf_header_required(graph):
    c = make_client(graph)
    c.headers.pop("X-CityPulse-Client")
    r = c.post("/api/v1/profiles", json={})
    assert r.status_code == 403 and r.json()["error"] == "csrf"


def test_outside_delhi_rejected(client):
    r = client.post("/api/v1/profiles", json={"name": "X", "email": "x@example.com", "address": "Mumbai",
                                              "latitude": 19.07, "longitude": 72.87})
    assert r.status_code == 422
