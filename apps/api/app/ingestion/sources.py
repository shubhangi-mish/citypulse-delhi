"""Source registry: the manifest of evaluated sources, mirrored as Source nodes, plus run health from Postgres."""

import json
import logging
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT
from app.db.models import SourceRun, utcnow
from app.graph.client import GraphClient
from app.graph.model import now_ms

log = logging.getLogger("citypulse.ingestion")

MANIFEST = REPO_ROOT / "data" / "manifests" / "sources.json"
if not MANIFEST.exists():
    MANIFEST = Path(__file__).resolve().parents[2] / "data_manifests" / "sources.json"


@lru_cache
def manifest() -> list[dict]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["sources"]


def ensure_source_nodes(graph: GraphClient) -> None:
    rows = [{k: s.get(k) for k in ("source_id", "name", "url", "license", "source_type", "verification_status",
                                   "access_method", "ingestion")} for s in manifest()]
    graph.query(
        """
        UNWIND $rows AS s
        MERGE (n:Source {source_id: s.source_id})
        SET n.name = s.name, n.url = s.url, n.license = s.license, n.source_type = s.source_type,
            n.verification_status = s.verification_status, n.access_method = s.access_method,
            n.ingestion = s.ingestion
        """, {"rows": rows})


@contextmanager
def run_record(db: Session, source_id: str):
    run = SourceRun(source_id=source_id)
    db.add(run)
    db.commit()
    try:
        yield run
        run.status = "ok"
    except Exception as exc:
        run.status = "error"
        run.error = f"{type(exc).__name__}: {exc}"[:2000]
        log.exception("ingestion %s failed", source_id)
        raise
    finally:
        run.finished_at = utcnow()
        db.commit()


def mark_retrieved(graph: GraphClient, source_id: str) -> None:
    graph.query("MATCH (s:Source {source_id:$id}) SET s.retrieved_at = $now", {"id": source_id, "now": now_ms()})


def status(db: Session, graph: GraphClient | None) -> list[dict]:
    out = []
    counts: dict[str, int] = {}
    if graph is not None:
        for r in graph.query(
            """
            MATCH (x)-[:DERIVED_FROM]->(s:Source)
            RETURN s.source_id AS id, count(x) AS c
            """, readonly=True):
            counts[r["id"]] = r["c"]
    for s in manifest():
        last = db.scalars(select(SourceRun).where(SourceRun.source_id == s["source_id"])
                          .order_by(SourceRun.started_at.desc()).limit(1)).first()
        last_ok = db.scalars(select(SourceRun).where(SourceRun.source_id == s["source_id"], SourceRun.status == "ok")
                             .order_by(SourceRun.started_at.desc()).limit(1)).first()
        out.append({
            **{k: v for k, v in s.items() if not k.startswith("_")},
            "graph_records": counts.get(s["source_id"]),
            "last_run": None if not last else {
                "status": last.status, "started_at": last.started_at.isoformat(),
                "finished_at": last.finished_at.isoformat() if last.finished_at else None,
                "records_fetched": last.records_fetched, "records_upserted": last.records_upserted,
                "error": last.error},
            "last_success_at": last_ok.finished_at.isoformat() if last_ok and last_ok.finished_at else None,
        })
    return out
