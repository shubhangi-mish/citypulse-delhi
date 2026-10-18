"""Integration tests run against a REAL FalkorDB, in an isolated graph (never the production graph), and a
temporary SQLite database for session/audit tables.

Fixture geography below exists only inside the test graph. It is never written to the production graph.
"""

import os
import tempfile

import pytest

os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ["INGEST_SCHEDULE"] = "false"
os.environ["LLM_PROVIDER"] = "none"
os.environ["RATE_LIMIT_WRITES_PER_MINUTE"] = "100000"
_db_file = os.path.join(tempfile.mkdtemp(), "citypulse_test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file}"

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

from fastapi.testclient import TestClient  # noqa: E402

from app.db import session as db_session  # noqa: E402
from app.graph.client import GraphClient, set_graph  # noqa: E402
from app.graph.schema import ensure_schema  # noqa: E402
from app.ingestion.sources import ensure_source_nodes  # noqa: E402
from app.security.auth import hash_password  # noqa: E402
from app.services import geo  # noqa: E402

TEST_GRAPH = "citypulse_test"
OPERATOR_PASSWORD = "test-operator-password"

# Test-only fixture places (coordinates near real Delhi localities so geo validation passes).
FIXTURE_PLACES = [
    ("nbh_test_cp", "Fixture Place A", 28.6315, 77.2167),
    ("nbh_test_kb", "Fixture Place B", 28.6519, 77.1909),
    ("nbh_test_far", "Fixture Place Far", 28.5355, 77.3910),
]


def _seed_fixture_geography(g: GraphClient) -> None:
    g.query("CREATE (:AdministrativeArea {area_id:'area_test_d', name:'Fixture District', type:'district'})")
    for nid, name, lat, lng in FIXTURE_PLACES:
        g.query(
            """
            MATCH (d:AdministrativeArea {area_id:'area_test_d'})
            CREATE (n:Neighborhood {neighborhood_id:$id, name:$name, latitude:$lat, longitude:$lng,
                    location: point({latitude:$lat, longitude:$lng}), source_id:'src_osm'})
            CREATE (d)-[:CONTAINS]->(n)
            """, {"id": nid, "name": name, "lat": lat, "lng": lng})
    g.query(
        """
        MATCH (n:Neighborhood {neighborhood_id:'nbh_test_cp'})
        CREATE (a:InfrastructureAsset {asset_id:'ast_test_1', name:'Fixture Metro', asset_type:'metro_station',
                latitude:28.6328, longitude:77.2197, location: point({latitude:28.6328, longitude:77.2197})})
        CREATE (a)-[:LOCATED_IN]->(n)
        CREATE (o:Organization {organization_id:'org_test_1', name:'Fixture Operator'})
        CREATE (a)-[:OPERATED_BY {basis:'OpenStreetMap operator tag', source_id:'src_osm',
                verification_status:'COMMUNITY_REPORTED'}]->(o)
        """)


@pytest.fixture(scope="session")
def graph():
    s = get_settings()
    g = GraphClient(s.falkordb_host, s.falkordb_port, TEST_GRAPH)
    if not g.ping():
        pytest.skip("FalkorDB not reachable; start it with `docker compose up -d falkordb`")
    g.drop()
    ensure_schema(g)
    ensure_source_nodes(g)
    _seed_fixture_geography(g)
    set_graph(g)
    yield g
    g.drop()


@pytest.fixture(scope="session", autouse=True)
def _db():
    os.environ["OPERATOR_ACCOUNTS"] = f"coord:{hash_password(OPERATOR_PASSWORD, iterations=1000)}"
    get_settings.cache_clear()
    db_session.configure(os.environ["DATABASE_URL"])
    db_session.create_tables()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Deterministic road lookup instead of calling Nominatim."""
    def fake_road(lat, lng):
        if lat > 28.6:
            return {"osm_ref": "way/test-1", "name": "Fixture Marg", "road_class": "primary"}
        return {"osm_ref": "way/test-2", "name": "Fixture Road South", "road_class": "secondary"}
    monkeypatch.setattr(geo, "reverse_road", fake_road)


def make_client(graph) -> TestClient:
    from app.main import app

    set_graph(graph)
    c = TestClient(app)
    c.headers.update({"X-CityPulse-Client": "web"})
    return c


@pytest.fixture
def client(graph):
    return make_client(graph)


@pytest.fixture
def client2(graph):
    return make_client(graph)


@pytest.fixture
def operator(graph):
    c = make_client(graph)
    r = c.post("/api/v1/operator/login", json={"username": "coord", "password": OPERATOR_PASSWORD})
    assert r.status_code == 200, r.text
    return c


def new_profile(c: TestClient, name="Test Resident", email="a@example.com", lat=28.6320, lng=77.2180, **extra):
    r = c.post("/api/v1/profiles", json={"name": name, "email": email, "address": "Fixture address",
                                         "latitude": lat, "longitude": lng, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def new_issue(c: TestClient, title="Deep waterlogging at the crossing", lat=28.6322, lng=77.2190,
              category="waterlogging", **extra):
    r = c.post("/api/v1/issues", json={"category": category, "title": title,
                                       "description": "Water has been standing here since morning, about knee deep.",
                                       "latitude": lat, "longitude": lng, **extra})
    assert r.status_code == 201, r.text
    return r.json()["issue_id"]
