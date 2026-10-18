from tests.conftest import make_client, new_issue, new_profile


def test_report_is_graph_connected(client, graph):
    new_profile(client, email="rep@example.com")
    iid = new_issue(client, title="Waterlogged underpass near metro", concerns_asset_id="ast_test_1")
    row = graph.one(
        """
        MATCH (r:Resident)-[:REPORTED]->(i:Issue {issue_id:$id})-[:LOCATED_IN]->(n:Neighborhood)
        MATCH (i)-[:ON_ROAD]->(rd:Road)
        MATCH (i)-[:CONCERNS]->(a:InfrastructureAsset)
        RETURN n.name AS n, rd.name AS road, a.name AS asset, i.verification_status AS vs
        """, {"id": iid})
    assert row == {"n": "Fixture Place A", "road": "Fixture Marg", "asset": "Fixture Metro",
                   "vs": "COMMUNITY_REPORTED"}
    detail = client.get(f"/api/v1/issues/{iid}").json()
    assert detail["assets"][0]["organizations"][0]["name"] == "Fixture Operator"
    assert detail["case_reference"].startswith("CP-")


def test_second_session_discovers_report_within_radius_only(graph):
    a, b, far = make_client(graph), make_client(graph), make_client(graph)
    new_profile(a, email="a1@example.com")
    iid = new_issue(a, title="Streetlights out along the lane", category="streetlights")
    new_profile(b, email="b1@example.com", lat=28.6400, lng=77.2100)        # ~1.2 km away
    new_profile(far, email="far@example.com", lat=28.5355, lng=77.3910)     # ~20 km away

    ids_1km = [i.get("issue_id") for i in b.get("/api/v1/nearby/activity", params={"radius_km": 1}).json()["items"]]
    ids_3km = [i.get("issue_id") for i in b.get("/api/v1/nearby/activity", params={"radius_km": 3}).json()["items"]]
    ids_far = [i.get("issue_id") for i in far.get("/api/v1/nearby/activity", params={"radius_km": 10}).json()["items"]]
    assert iid not in ids_1km and iid in ids_3km and iid not in ids_far


def test_support_is_idempotent_and_corroborates(graph):
    rep = make_client(graph)
    new_profile(rep, email="r@example.com")
    iid = new_issue(rep, title="Garbage dumped on footpath", category="garbage")
    assert rep.post(f"/api/v1/issues/{iid}/support", json={}).status_code == 403  # reporter can't self-corroborate

    supporters = [make_client(graph) for _ in range(3)]
    for i, s in enumerate(supporters):
        new_profile(s, email=f"s{i}@example.com")
        s.post(f"/api/v1/issues/{iid}/support", json={})
    supporters[0].post(f"/api/v1/issues/{iid}/support", json={})  # duplicate click
    edges = graph.one("MATCH (:Resident)-[s:SUPPORTS]->(:Issue {issue_id:$id}) RETURN count(s) AS c", {"id": iid})
    assert edges["c"] == 3
    detail = rep.get(f"/api/v1/issues/{iid}").json()
    assert detail["support_count"] == 3 and detail["status"] == "community_corroborated"
    # reporter got an in-app notification
    assert rep.get("/api/v1/profiles/me/notifications").json()["unread"] >= 1


def test_duplicate_detection_uses_shared_road(graph):
    a, b = make_client(graph), make_client(graph)
    new_profile(a, email="d1@example.com")
    first = new_issue(a, title="Huge pothole on the main road", category="roads_potholes", lat=28.6500, lng=77.1900)
    new_profile(b, email="d2@example.com")
    second = new_issue(b, title="Pothole damaging scooters", category="roads_potholes", lat=28.6505, lng=77.1905)
    edge = graph.one(
        "MATCH (:Issue {issue_id:$a})-[d:POSSIBLY_DUPLICATES]->(:Issue {issue_id:$b}) RETURN d.score AS s, d.reasons AS r",
        {"a": second, "b": first})
    assert edge and edge["s"] >= 0.65 and any("Fixture Marg" in r for r in edge["r"])
    related = a.get(f"/api/v1/issues/{first}").json()["related"]
    assert related[0]["issue_id"] == second and related[0]["shared_roads"][0]["name"] == "Fixture Marg"


def test_follow_and_comment_notify(graph):
    a, b = make_client(graph), make_client(graph)
    new_profile(a, email="f1@example.com")
    iid = new_issue(a, title="No water supply since two days", category="water_supply")
    new_profile(b, email="f2@example.com")
    assert b.post(f"/api/v1/issues/{iid}/follow", json={"follow": True}).json() == {"following": True}
    assert b.post(f"/api/v1/issues/{iid}/comments", json={"body": "Same in our block."}).status_code == 201
    disc = a.get(f"/api/v1/issues/{iid}").json()["discussion"]
    assert any(d["body"] == "Same in our block." for d in disc)
    kinds = [n["kind"] for n in a.get("/api/v1/profiles/me/notifications").json()["items"]]
    assert "comment" in kinds
    assert any(i["issue_id"] == iid for i in b.get("/api/v1/profiles/me/activity").json()["following"])
