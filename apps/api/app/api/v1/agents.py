from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents import workflow
from app.api.deps import graph_dep
from app.db.session import get_db
from app.graph.client import GraphClient
from app.schemas.requests import AnalyzeEvent, AnalyzeIssue
from app.security.auth import require_operator
from app.services import audit, events, warnings

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/analyze-issue")
def analyze_issue(body: AnalyzeIssue, operator: str = Depends(require_operator), db: Session = Depends(get_db),
                  graph: GraphClient = Depends(graph_dep)):
    try:
        result = workflow.analyze_issue(graph, body.issue_id)
    except LookupError:
        raise HTTPException(404, detail={"error": "not_found"})
    audit.record(db, "operator", operator, "agent_analysis", body.issue_id, run_id=result["run_id"],
                 proposals=len(result["action_ids"]))
    return result


@router.post("/analyze-event")
def analyze_event(body: AnalyzeEvent, operator: str = Depends(require_operator),
                  graph: GraphClient = Depends(graph_dep)):
    """Event impact: official alerts linked by MAY_IMPACT and open reports near the venue (graph-only)."""
    ev = events.detail(graph, body.event_id, None)
    if not ev:
        raise HTTPException(404, detail={"error": "not_found"})
    linked = events.link_warnings(graph, body.event_id)
    ev = events.detail(graph, body.event_id, None)
    alerts = [warnings.detail(graph, w["warning_id"]) for w in ev["warnings"]]
    return {"event_id": body.event_id, "new_warning_links": linked, "warnings": ev["warnings"],
            "nearby_issues": ev["nearby_issues"],
            "alert_sources": [{"warning_id": a["warning_id"], "source_url": a["source_url"],
                               "issuing_authority": a["issuing_authority"]} for a in alerts if a],
            "summary": (f"{len(ev['warnings'])} official alert(s) overlap the event's place and time; "
                        f"{len(ev['nearby_issues'])} open community report(s) within 1 km of the venue.")}


@router.get("/decisions/{decision_id}")
def decision(decision_id: str, graph: GraphClient = Depends(graph_dep)):
    d = workflow.decision_detail(graph, decision_id)
    if not d:
        raise HTTPException(404, detail={"error": "not_found"})
    return d


@router.get("/issues/{issue_id}/decisions")
def issue_decisions(issue_id: str, graph: GraphClient = Depends(graph_dep)):
    return {"items": workflow.decisions_for_issue(graph, issue_id)}


@router.get("/memory/{case_id}")
def memory(case_id: str, operator: str = Depends(require_operator), graph: GraphClient = Depends(graph_dep)):
    rows = graph.query(
        """
        MATCH (m:AgentMemory)-[:SUMMARIZES]->(c:CoordinationCase {case_id:$id})
        OPTIONAL MATCH (m)-[:RECORDS]->(a:CoordinationAction)
        OPTIONAL MATCH (d:AgentDecision)-[:USED_MEMORY]->(m)
        RETURN m.memory_id AS memory_id, m.summary AS summary, m.memory_type AS memory_type,
               m.created_at AS created_at, m.valid_until AS valid_until,
               collect(DISTINCT {action_id: a.action_id, action_type: a.action_type, outcome: a.outcome}) AS actions,
               collect(DISTINCT {decision_id: d.decision_id, run_id: d.run_id, created_at: d.created_at}) AS reused_by
        ORDER BY m.created_at DESC
        """, {"id": case_id}, readonly=True)
    for r in rows:
        r["actions"] = [a for a in r["actions"] if a["action_id"]]
        r["reused_by"] = [d for d in r["reused_by"] if d["decision_id"]]
    return {"case_id": case_id, "memories": rows}


@router.get("/memory")
def all_memory(operator: str = Depends(require_operator), graph: GraphClient = Depends(graph_dep)):
    rows = graph.query(
        """
        MATCH (m:AgentMemory)-[:SUMMARIZES]->(c:CoordinationCase)
        OPTIONAL MATCH (d:AgentDecision)-[:USED_MEMORY]->(m)
        RETURN m.memory_id AS memory_id, m.summary AS summary, m.created_at AS created_at,
               c.case_id AS case_id, c.title AS case_title, count(DISTINCT d) AS times_reused
        ORDER BY m.created_at DESC LIMIT 100
        """, readonly=True)
    return {"items": rows}


@router.get("/activity")
def agent_activity(operator: str = Depends(require_operator), graph: GraphClient = Depends(graph_dep)):
    rows = graph.query(
        """
        MATCH (d:AgentDecision)-[:CONSIDERED {role:'subject'}]->(i)
        RETURN d.decision_id AS decision_id, d.agent_name AS agent_name, d.decision_type AS decision_type,
               d.rationale AS rationale, d.created_at AS created_at, d.run_id AS run_id, d.model_name AS model_name,
               d.review_status AS review_status, coalesce(i.issue_id, i.event_id) AS issue_id, i.title AS issue_title,
               labels(i)[0] AS subject_type
        ORDER BY d.created_at DESC LIMIT 120
        """, readonly=True)
    return {"items": rows}
