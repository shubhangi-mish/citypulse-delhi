"""Agent analysis, human approval, and persistent memory that survives a restart."""

from app.graph.client import GraphClient
from tests.conftest import TEST_GRAPH, make_client, new_issue, new_profile


def test_coordination_requires_operator(graph, client):
    assert client.post("/api/v1/agents/analyze-issue", json={"issue_id": "iss_x"}).status_code == 401
    assert client.post("/api/v1/coordination/actions/act_x/approve", json={}).status_code == 401


def test_analysis_approval_memory_survives_restart(graph, operator):
    # 1. genuine-style flow inside the test graph: a report and an operator analysis
    r1 = make_client(graph)
    new_profile(r1, email="m1@example.com")
    first = new_issue(r1, title="Waterlogging after every rain at the crossing", lat=28.6325, lng=77.2185)

    res = operator.post("/api/v1/agents/analyze-issue", json={"issue_id": first}).json()
    assert res["model_name"].startswith("deterministic")
    assert set(res["decisions"]) == {"context", "impact", "memory", "coordination"}
    assert res["action_ids"], "expected proposals (e.g. request community verification)"
    # proposals are hidden from the public until approved
    assert make_client(graph).get(f"/api/v1/coordination/cases/{res['case_id']}").status_code == 404

    # hand-off chain is in the graph
    chain = graph.one(
        """
        MATCH (a:AgentDecision {decision_id:$a})-[:INFORMED]->(b)-[:INFORMED]->(c)-[:INFORMED]->(d:AgentDecision)
        RETURN d.decision_id AS d
        """, {"a": res["decisions"]["context"]})
    assert chain["d"] == res["decisions"]["coordination"]

    # 2. coordinator approves and records an outcome -> Memory Agent writes memory
    action = res["action_ids"][0]
    ap = operator.post(f"/api/v1/coordination/actions/{action}/approve", json={})
    assert ap.status_code == 200 and ap.json()["status"] == "executed"
    out = operator.post(f"/api/v1/coordination/actions/{action}/outcome",
                        json={"outcome": "Six neighbours confirmed; group formed to track drainage.", "success": True})
    memory_id = out.json()["memory_id"]
    assert memory_id

    # 3. "restart": brand-new graph connection and app client
    fresh = GraphClient(graph.host, graph.port, TEST_GRAPH)
    op2 = make_client(fresh)
    from tests.conftest import OPERATOR_PASSWORD
    op2.post("/api/v1/operator/login", json={"username": "coord", "password": OPERATOR_PASSWORD})
    assert any(m["memory_id"] == memory_id for m in op2.get(f"/api/v1/agents/memory/{res['case_id']}").json()["memories"])

    # 4. a NEW related report: the agents retrieve the prior case through the graph and it changes the output
    r2 = make_client(fresh)
    new_profile(r2, email="m2@example.com")
    second = new_issue(r2, title="Crossing flooded again today", lat=28.6327, lng=77.2186)
    res2 = op2.post("/api/v1/agents/analyze-issue", json={"issue_id": second}).json()
    priors = res2["memory"]["prior_cases"]
    assert any(p["case_id"] == res["case_id"] for p in priors)
    assert any(r.get("from_memory") and "Memory:" in r["rationale"] for r in res2["recommendations"])
    used = fresh.one("MATCH (d:AgentDecision {decision_id:$d})-[:USED_MEMORY]->(m:AgentMemory) RETURN m.memory_id AS m",
                     {"d": res2["decisions"]["coordination"]})
    assert used["m"] == memory_id

    # explanation endpoint exposes query ids, paths and sources
    exp = op2.get(f"/api/v1/graph/explanations/{res2['decisions']['impact']}").json()
    assert exp["trace"]["paths"] and all(p["query_id"] for p in exp["trace"]["paths"])
    assert exp["handoff"]["next_agent"] == "Memory Agent"
