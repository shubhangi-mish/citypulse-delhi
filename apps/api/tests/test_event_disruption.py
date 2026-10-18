"""A booked performer cancels; the agents find replacements through the graph, act, and remember.

All data lives in the isolated test graph. The people here are test fixtures, never written to the real graph."""

import time

from tests.conftest import make_client, new_profile

HOUR = 3600_000


def _person(graph, name, profession, email, lat, lng, gigs=True):
    c = make_client(graph)
    p = new_profile(c, name=name, email=email, lat=lat, lng=lng)
    r = c.patch("/api/v1/profiles/me", json={"public_visibility": "public", "display_name_opt_in": True,
                                             "profession": profession, "open_to_gigs": gigs})
    assert r.status_code == 200, r.text
    return c, p["resident_id"]


def _event(c, title, start, venue="Fixture Hall"):
    r = c.post("/api/v1/events", json={
        "title": title, "description": "Fixture event used to test replacement matching in the graph.",
        "category": "concert", "start_time": start, "end_time": start + 3 * HOUR, "venue_name": venue,
        "venue_address": "Fixture address", "latitude": 28.6318, "longitude": 77.2171, "organizer_name": "Fixture Org",
        "organizer_contact": "org@example.com", "attestation": True})
    assert r.status_code == 201, r.text
    return r.json()["event_id"]


def _feature(graph, eid, rid, role="headliner"):
    graph.query("MATCH (e:Event {event_id:$e}), (r:Resident {resident_id:$r}) "
                "MERGE (e)-[f:FEATURES]->(r) SET f.status='confirmed', f.role=$role", {"e": eid, "r": rid, "role": role})


def test_cancellation_agents_invite_ranked_artists_and_close_the_loop(graph):
    start = int(time.time() * 1000) + 48 * HOUR
    org, org_id = _person(graph, "Org Fixture", "Community librarian", "org-d@example.com", 28.6330, 77.2150, gigs=False)
    singer, singer_id = _person(graph, "Singer Fixture", "Indie singer-songwriter", "sing-d@example.com", 28.6310, 77.2180, gigs=False)
    vocalist, vocalist_id = _person(graph, "Vocalist Fixture", "Classical vocalist", "voc-d@example.com", 28.6400, 77.2100)
    painter, painter_id = _person(graph, "Painter Fixture", "Live sketch artist", "pai-d@example.com", 28.6450, 77.2000)
    comedian, comedian_id = _person(graph, "Comedian Fixture", "Stand-up comedian", "com-d@example.com", 28.6350, 77.2200)
    dev, dev_id = _person(graph, "Dev Fixture", "Software engineer", "dev-d@example.com", 28.6320, 77.2160)  # not an artist

    eid = _event(org, "Fixture Music Evening", start)
    clash_eid = _event(comedian, "Fixture Comedy Night", start + HOUR, venue="Fixture Cafe")
    graph.query("MATCH (e:Event {event_id:$e}) SET e.agent_autopilot = true, e.performer_gap = false", {"e": eid})
    _feature(graph, eid, singer_id)
    _feature(graph, clash_eid, comedian_id)
    dev.post(f"/api/v1/events/{eid}/participate", json={"role": "going"})

    # 1. the performer cancels -> agents run and act (organiser authorised autopilot)
    res = org.post(f"/api/v1/events/{eid}/cancel-performance", json={"reason": "Family emergency"})
    assert res.status_code == 200, res.text
    run = res.json()
    assert run["autopilot"] and run["model_name"].startswith("deterministic")
    names = [c["name"] for c in run["candidates"]["eligible"]]
    assert names[0] == "Vocalist Fixture"                         # same discipline family + near, ranks first
    assert "Painter Fixture" in names and "Dev Fixture" not in names   # non-artists never matched
    excluded = {e["name"]: e["reason"] for e in run["candidates"]["excluded"]}
    assert "Fixture Comedy Night" in excluded["Comedian Fixture"]      # excluded via the FEATURES clash traversal
    assert {x["status"] for x in run["executed"]} == {"executed"}      # real actions without a coordinator click

    # real side effects: INVITED edges and in-app notifications
    invited = graph.query("MATCH (:Event {event_id:$e})-[i:INVITED]->(r:Resident) RETURN r.name AS n, i.status AS s",
                          {"e": eid})
    assert {i["n"] for i in invited} == {"Vocalist Fixture", "Painter Fixture"} and {i["s"] for i in invited} == {"pending"}
    assert any(n["kind"] == "replacement_invite" for n in vocalist.get("/api/v1/profiles/me/notifications").json()["items"])
    assert not any(n["kind"] == "replacement_invite" for n in comedian.get("/api/v1/profiles/me/notifications").json()["items"])
    kinds = [n["kind"] for n in dev.get("/api/v1/profiles/me/notifications").json()["items"]]
    assert "performer_cancelled" in kinds and "event_update" in kinds          # attendees were told by the agent
    detail = dev.get(f"/api/v1/events/{eid}").json()
    assert detail["performer_gap"] is True
    assert detail["coordination"][0]["actions"][0]["authorised_by"] == "organiser autopilot"

    # decision trace: four chained agent decisions
    chain = graph.one("MATCH (a:AgentDecision {decision_id:$a})-[:INFORMED]->()-[:INFORMED]->()-[:INFORMED]->(d:AgentDecision) "
                      "RETURN d.review_status AS s", {"a": run["decisions"]["context"]})
    assert chain["s"] == "auto_authorized"

    # 2. the vocalist steps in -> gap filled, everyone told, case resolved, memory written
    ok = vocalist.post(f"/api/v1/events/{eid}/invitation", json={"accept": True})
    assert ok.status_code == 200 and ok.json()["accepted"]
    after = dev.get(f"/api/v1/events/{eid}").json()
    assert after["performer_gap"] is False
    assert any(p["role"] == "replacement" and p["status"] == "confirmed" and p["display_name"] == "Vocalist Fixture"
               for p in after["performers"])
    assert any(n["kind"] == "replacement_confirmed" for n in dev.get("/api/v1/profiles/me/notifications").json()["items"])
    case = graph.one("MATCH (c:CoordinationCase {case_type:'event_disruption'})-[:ADDRESSES]->(:Event {event_id:$e}) "
                     "RETURN c.status AS s", {"e": eid})
    assert case["s"] == "resolved"
    mem = graph.one("MATCH (m:AgentMemory)-[:SUMMARIZES]->(:CoordinationCase)-[:ADDRESSES]->(:Event {event_id:$e}) "
                    "RETURN m.summary AS s", {"e": eid})
    assert "Vocalist Fixture" in mem["s"] and "organiser autopilot" in mem["s"]
    # a second invitee can no longer accept: the loop is closed
    assert painter.post(f"/api/v1/events/{eid}/invitation", json={"accept": True}).status_code == 404


def test_without_autopilot_agents_only_propose(graph):
    start = int(time.time() * 1000) + 72 * HOUR
    org, _ = _person(graph, "Org Two", "Teacher", "org-e@example.com", 28.6330, 77.2150, gigs=False)
    singer, singer_id = _person(graph, "Singer Two", "Folk singer", "sing-e@example.com", 28.6310, 77.2180, gigs=False)
    _person(graph, "Poet Two", "Poet", "poet-e@example.com", 28.6400, 77.2100)
    eid = _event(org, "Fixture Poetry Night", start)
    _feature(graph, eid, singer_id)
    run = org.post(f"/api/v1/events/{eid}/cancel-performance", json={"reason": "Ill"}).json()
    assert not run["autopilot"] and run["executed"] == []
    assert graph.one("MATCH (:Event {event_id:$e})-[i:INVITED]->() RETURN count(i) AS c", {"e": eid})["c"] == 0
    proposed = graph.query("MATCH (a:CoordinationAction {status:'proposed'})-[:PART_OF]->(:CoordinationCase)-[:ADDRESSES]->"
                           "(:Event {event_id:$e}) RETURN a.action_type AS t", {"e": eid})
    assert "invite_replacement" in {p["t"] for p in proposed}      # waits for a coordinator
