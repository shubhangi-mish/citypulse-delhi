"""Graph-powered endpoints must fail loudly when FalkorDB is down — never compute a substitute answer."""

from fastapi.testclient import TestClient

from app.graph.client import GraphClient, set_graph


def test_graph_endpoints_return_503_when_falkordb_is_down(graph):
    from app.main import app

    dead = GraphClient("127.0.0.1", 6390, "citypulse_test")  # nothing listens here
    set_graph(dead)
    try:
        c = TestClient(app)
        c.headers.update({"X-CityPulse-Client": "web"})
        for path in ("/api/v1/nearby/activity", "/api/v1/issues", "/api/v1/events", "/api/v1/warnings",
                     "/api/v1/neighborhoods", "/api/v1/graph/search?q=metro"):
            r = c.get(path)
            assert r.status_code == 503, path
            assert r.json()["error"] == "graph_unavailable"
        r = c.post("/api/v1/profiles", json={"name": "N", "email": "n@example.com", "address": "Somewhere",
                                             "latitude": 28.63, "longitude": 77.21})
        assert r.status_code == 503
        assert c.get("/health").json() == {"status": "degraded", "falkordb": False}
    finally:
        set_graph(graph)
