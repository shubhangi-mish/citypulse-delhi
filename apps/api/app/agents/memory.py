"""Memory Agent — persistence side. Writes AgentMemory nodes that summarise coordination cases and their
outcomes, connected to the case, the actions it records and the decisions that produced them."""

from app.graph.client import GraphClient
from app.graph.model import new_id, now_ms

MEMORY_TTL_MS = 365 * 86400 * 1000


def write_case_memory(graph: GraphClient, case_id: str, trigger_action_id: str | None = None) -> str | None:
    row = graph.one(
        """
        MATCH (c:CoordinationCase {case_id:$id})
        OPTIONAL MATCH (c)-[:ADDRESSES]->(i:Issue)
        OPTIONAL MATCH (i)-[:ON_ROAD]->(rd:Road)
        OPTIONAL MATCH (i)-[:LOCATED_IN]->(n:Neighborhood)
        OPTIONAL MATCH (c)-[:ADDRESSES]->(ev:Event)
        OPTIONAL MATCH (ev)-[:LOCATED_IN]->(n2:Neighborhood)
        WITH c, collect(DISTINCT i.title) + collect(DISTINCT ev.title) AS titles,
             collect(DISTINCT i.category) + collect(DISTINCT c.case_type) AS cats,
             collect(DISTINCT rd.name) AS roads, collect(DISTINCT n.name) + collect(DISTINCT n2.name) AS nbhs
        OPTIONAL MATCH (a:CoordinationAction)-[:PART_OF]->(c)
        WHERE a.status IN ['executed', 'completed']
        OPTIONAL MATCH (crd:Coordinator)-[:APPROVED]->(a)
        RETURN c.title AS title, titles, cats, roads, nbhs,
               collect(DISTINCT {id: a.action_id, type: a.action_type, status: a.status, outcome: a.outcome,
                                 ok: a.outcome_success, by: coalesce(crd.display_name, a.approved_by)}) AS actions
        """, {"id": case_id}, readonly=True)
    if not row:
        return None
    actions = [a for a in row["actions"] if a["id"]]
    parts = []
    for a in actions:
        res = a["outcome"] or "no outcome recorded yet"
        verdict = {True: "worked", False: "did not work"}.get(a["ok"], "outcome pending")
        parts.append(f"{a['type'].replace('_', ' ')} (authorised by {a["by"] or "a coordinator"}) — {verdict}: {res}")
    where = ", ".join([x for x in row["roads"] if x][:2] + [x for x in row["nbhs"] if x][:2]) or "unknown location"
    summary = (f"Case '{row['title']}' about {', '.join(c.replace('_', ' ') for c in row['cats'] if c) or 'reports'} at {where}. "
               + ("Actions: " + "; ".join(parts) + "." if parts else "No executed actions yet."))
    mid = new_id("mem")
    now = now_ms()
    graph.query(
        """
        MATCH (c:CoordinationCase {case_id:$case})
        CREATE (m:AgentMemory {memory_id:$id, memory_type:'case_outcome', summary:$summary, created_at:$now,
                               valid_until:$until, source_reference:$case, written_by:'Memory Agent'})
        CREATE (m)-[:SUMMARIZES {created_at:$now}]->(c)
        WITH m
        MATCH (a:CoordinationAction) WHERE a.action_id IN $actions
        MERGE (m)-[:RECORDS]->(a)
        WITH DISTINCT m
        OPTIONAL MATCH (m)-[:RECORDS]->(:CoordinationAction)<-[:PRODUCED]-(d:AgentDecision)
        FOREACH (_ IN CASE WHEN d IS NULL THEN [] ELSE [1] END | MERGE (m)-[:LEARNED_FROM]->(d))
        """, {"case": case_id, "id": mid, "summary": summary, "now": now, "until": now + MEMORY_TTL_MS,
              "actions": [a["id"] for a in actions]})
    return mid
