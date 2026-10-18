"""Loads the canonical Cypher queries from /graph/queries so documentation and runtime never drift apart."""

from functools import lru_cache
from pathlib import Path

from app.core.config import REPO_ROOT

QUERY_DIR = REPO_ROOT / "graph" / "queries"
if not QUERY_DIR.exists():  # container layout: queries copied next to the app
    QUERY_DIR = Path(__file__).resolve().parents[2] / "graph_queries"

QUERY_IDS = {
    "nearby_contributors": "A_nearby_contributors",
    "related_issues": "B_related_issues",
    "warning_impact": "C_warning_impact",
    "responsible_organization": "D_responsible_organization",
    "coordination_network": "E_coordination_network",
    "agent_memory": "F_agent_memory",
    "replacement_candidates": "G_replacement_candidates",
    "event_disruption_memory": "H_event_disruption_memory",
}


@lru_cache
def Q(name: str) -> str:
    return (QUERY_DIR / f"{QUERY_IDS[name]}.cypher").read_text(encoding="utf-8")


def query_id(name: str) -> str:
    return f"graph/queries/{QUERY_IDS[name]}.cypher"
