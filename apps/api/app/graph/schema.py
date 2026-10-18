"""Graph schema bootstrap: indexes for stable IDs, status/time filters and geospatial point properties.

FalkorDB (verified on 4.x) supports `CREATE INDEX FOR (n:Label) ON (n.prop)` range indexes, including on
point properties, which `distance()` filters use. Re-running is safe: "already indexed" errors are ignored.
"""

import logging

from app.graph.client import GraphClient, GraphQueryError
from app.graph.model import LABELS

log = logging.getLogger("citypulse.graph.schema")

EXTRA_INDEXES: list[tuple[str, str]] = [
    ("Issue", "status"), ("Issue", "created_at"), ("Issue", "location"), ("Issue", "category"),
    ("Event", "status"), ("Event", "start_time"), ("Event", "location"),
    ("Warning", "expires_at"), ("Warning", "external_id"),
    ("Neighborhood", "location"), ("InfrastructureAsset", "location"), ("Venue", "location"),
    ("Resident", "location"), ("CoordinationCase", "status"), ("CoordinationAction", "status"),
    ("Road", "osm_ref"), ("InfrastructureAsset", "osm_ref"), ("Neighborhood", "osm_ref"),
    ("Organization", "name"), ("Profession", "category"), ("Resident", "open_to_gigs"),
]


def index_statements() -> list[str]:
    stmts = [f"CREATE INDEX FOR (n:{label}) ON (n.{prop})" for label, prop in LABELS.values()]
    stmts += [f"CREATE INDEX FOR (n:{label}) ON (n.{prop})" for label, prop in EXTRA_INDEXES]
    return stmts


def ensure_schema(graph: GraphClient) -> int:
    created = 0
    for stmt in index_statements():
        try:
            graph.query(stmt)
            created += 1
        except GraphQueryError as exc:
            if "already indexed" not in str(exc).lower():
                raise
    log.info("graph schema ensured (%d new indexes)", created)
    return created
