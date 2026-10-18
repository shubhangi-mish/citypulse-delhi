"""CLI: uv run python -m app.ingestion.run [osm|sachet|all] [--refresh]"""

import logging
import sys

from app.db.session import SessionLocal, create_tables
from app.graph.client import get_graph
from app.graph.schema import ensure_schema
from app.ingestion import osm, sachet, sources

RUNNERS = {"src_osm": lambda g, refresh: osm.ingest(g, use_cache=not refresh),
           "src_ndma_sachet": lambda g, refresh: sachet.ingest(g)}
ALIASES = {"osm": "src_osm", "sachet": "src_ndma_sachet"}


def run(source_id: str, refresh: bool = False) -> dict:
    graph = get_graph()
    ensure_schema(graph)
    sources.ensure_source_nodes(graph)
    db = SessionLocal()
    try:
        with sources.run_record(db, source_id) as rec:
            stats = RUNNERS[source_id](graph, refresh)
            rec.records_fetched = stats.get("fetched", 0)
            rec.records_upserted = stats.get("upserted", 0)
        return stats
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    create_tables()
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    refresh = "--refresh" in sys.argv
    ids = list(RUNNERS) if target == "all" else [ALIASES.get(target, target)]
    for sid in ids:
        print(sid, run(sid, refresh))
