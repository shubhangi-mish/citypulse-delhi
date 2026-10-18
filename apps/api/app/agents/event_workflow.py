"""Event-disruption workflow (LangGraph): a booked performer cancels and the agents react.

  Context Agent      -> what is the event, who was booked, who is attending, is autopilot authorised?
  Impact Agent       -> who is affected (participants, volunteers, linked complaints, overlapping alerts) and which
                        replacement artists exist (Query G), including WHY some are excluded
  Memory Agent       -> earlier disruption cases and what resolved them (Query H)
  Coordination Agent -> decide and act: invite the best-matched artists, notify participants, or ask for a human

Actions taken by the agents are real: INVITED edges + in-app notifications to the candidate artists, an event update
and notifications to participants. They execute without a coordinator click ONLY when the organiser pre-authorised
autopilot on the event (recorded as an AUTHORIZED edge); otherwise they are proposed for coordinator approval.
"""

import json
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agents import llm
from app.graph.client import GraphClient
from app.graph.model import new_id, now_ms
from app.graph.queries import Q, query_id
from app.services import coordination, talent

MAX_INVITES = 2


class State(TypedDict, total=False):
    event_id: str
    run_id: str
    trace: list[dict]
    ctx: dict
    impact: dict
    memory: dict
    plan: list[dict]
    summary: str
    decisions: dict
    case_id: str
    action_ids: list[str]
    executed: list[dict]


def _t(state: State, agent: str, tool: str, qid: str, rows: int) -> list[dict]:
    return state.get("trace", []) + [{"agent": agent, "tool": tool, "query_id": qid, "rows": rows}]


def build(graph: GraphClient, db: Session):
    def context_agent(state: State) -> State:
        row = graph.one(
            """
            MATCH (e:Event {event_id:$id})
            OPTIONAL MATCH (e)-[f:FEATURES]->(p:Resident)
            OPTIONAL MATCH (p)-[:PRACTICES]->(pr:Profession)
            OPTIONAL MATCH (e)-[:HOSTED_AT]->(v:Venue)
            OPTIONAL MATCH (e)-[:LOCATED_IN]->(n:Neighborhood)
            OPTIONAL MATCH (org:Resident)-[:SUBMITTED]->(e)
            RETURN e.title AS title, e.start_time AS start_time, e.end_time AS end_time,
                   e.performer_gap AS gap, e.agent_autopilot AS autopilot, e.demo AS demo,
                   v.name AS venue, n.name AS neighborhood, org.resident_id AS organizer_id,
                   collect(DISTINCT {id: p.resident_id, status: f.status, role: f.role, profession: pr.name,
                                     name: CASE WHEN p.display_name_opt_in = true THEN p.name ELSE null END}) AS performers
            """, {"id": state["event_id"]}, readonly=True)
        if not row:
            raise LookupError("event")
        row["performers"] = [p for p in row["performers"] if p["id"]]
        row["hours_until"] = round((row["start_time"] - now_ms()) / 3_600_000, 1)
        return {"ctx": row, "trace": _t(state, "Context Agent", "event_context", "agents/event_workflow.py#context", 1)}

    def impact_agent(state: State) -> State:
        eid = state["event_id"]
        trace = state["trace"]
        parts = graph.query(
            "MATCH (r:Resident)-[p:PARTICIPATES_IN]->(:Event {event_id:$id}) RETURN p.role AS role, count(r) AS n",
            {"id": eid}, readonly=True)
        trace = trace + [{"agent": "Impact Agent", "tool": "participants", "query_id": "agents/event_workflow.py#participants", "rows": len(parts)}]
        complaints = graph.query(
            "MATCH (i:Issue)-[:ABOUT_EVENT]->(:Event {event_id:$id}) RETURN i.issue_id AS issue_id, i.title AS title",
            {"id": eid}, readonly=True)
        trace = trace + [{"agent": "Impact Agent", "tool": "linked_complaints", "query_id": "agents/event_workflow.py#complaints", "rows": len(complaints)}]
        alerts = graph.query(
            """
            MATCH (w:Warning)-[:MAY_IMPACT]->(:Event {event_id:$id})
            WHERE w.expires_at > $now
            RETURN w.warning_id AS warning_id, w.title AS title, w.issuing_authority AS authority
            """, {"id": eid, "now": now_ms()}, readonly=True)
        cand = talent.find_candidates(graph, eid)
        trace = trace + [{"agent": "Impact Agent", "tool": "replacement_candidates", "query_id": cand["query_id"],
                          "rows": len(cand["eligible"]) + len(cand["excluded"])}]
        counts = {p["role"] or "interested": p["n"] for p in parts}
        paths = []
        for p in state["ctx"]["performers"]:
            if p["status"] == "cancelled":
                for c in cand["eligible"][:MAX_INVITES]:
                    paths.append({"nodes": [{"label": "Resident", "name": p["name"] or "Cancelled performer"},
                                            {"label": "Profession", "name": p["profession"]},
                                            {"label": "Resident", "name": c["name"]}],
                                  "rels": ["PRACTICES", "PRACTICES"], "query_id": cand["query_id"],
                                  "meaning": f"{c['name']} {'shares the discipline' if 'same discipline' in ' '.join(c['reasons']) else 'is in the same artistic family' if 'same artistic family' in ' '.join(c['reasons']) else 'is another artist nearby'} ({c['profession']}), {c['distance']} away"})
        return {"impact": {"participants": counts, "participant_total": sum(counts.values()), "complaints": complaints,
                           "alerts": alerts, "candidates": cand, "paths": paths}, "trace": trace}

    def memory_agent(state: State) -> State:
        rows = graph.query(Q("event_disruption_memory"), {"event_id": state["event_id"]}, readonly=True)
        lessons = [{"prior_event": r["prior_event"], "summary": r["summary"], "outcome": r["outcome"],
                    "success": r["outcome_success"], "replacement_profession": r["replacement_profession"],
                    "memory_id": r["memory_id"]} for r in rows]
        return {"memory": {"prior": rows, "lessons": lessons},
                "trace": _t(state, "Memory Agent", "prior_disruptions", query_id("event_disruption_memory"), len(rows))}

    def coordination_agent(state: State) -> State:
        ctx, imp, mem = state["ctx"], state["impact"], state["memory"]
        cancelled = [p for p in ctx["performers"] if p["status"] == "cancelled"]
        eligible = imp["candidates"]["eligible"]
        plan: list[dict] = []
        if cancelled and eligible:
            chosen = eligible[:MAX_INVITES]
            lesson = next((l for l in mem["lessons"] if l["success"]), None)
            memo = (f" Memory: an earlier disruption (“{lesson['prior_event']}”) was resolved by a "
                    f"{lesson['replacement_profession']}." if lesson else "")
            names = ", ".join(f"{c['name']} ({c['profession']})" for c in chosen)
            plan.append({
                "action_type": "invite_replacement",
                "description": f"Invite {len(chosen)} nearby artist(s) to step in: {names}.",
                "payload": {"event_id": state["event_id"], "candidates": chosen,
                            "message": f"“{ctx['title']}” ({ctx['neighborhood']}) just lost its booked performer and has "
                                       f"{ctx['hours_until']:.0f} hours to go. You're a good match — can you step in? "
                                       "Open the event to accept or decline."},
                "rationale": "Graph match (Query G): " + "; ".join(
                    f"{c['name']} — score {c['score']}: " + ", ".join(c["reasons"][:4]) for c in chosen) + "." + memo,
            })
        elif cancelled:
            plan.append({
                "action_type": "publish_community_update",
                "description": "No matching artist is available nearby; post an open call to the community.",
                "payload": {"message": f"“{ctx['title']}” is looking for a replacement performer. If you perform and can "
                                       "help, please say so in the discussion."},
                "rationale": f"Query G returned no eligible candidates ({len(imp['candidates']['excluded'])} excluded).",
            })
        if imp["participant_total"]:
            plan.append({
                "action_type": "notify_attendees",
                "description": f"Tell {imp['participant_total']} participant(s) that a replacement is being arranged.",
                "payload": {"message": f"Update on “{ctx['title']}”: the booked performer has cancelled and CityPulse "
                                       "agents have already reached out to nearby artists. We'll confirm as soon as "
                                       "someone steps in."},
                "rationale": f"{imp['participant_total']} residents are going or volunteering and should not be left guessing.",
            })
        excl = imp["candidates"]["excluded"]
        summary = (
            f"“{ctx['title']}” in {ctx['neighborhood'] or 'Delhi'} lost its performer with {ctx['hours_until']:.0f} h to go. "
            f"{imp['participant_total']} participant(s) affected, {len(imp['complaints'])} linked complaint(s). "
            f"Graph search found {len(eligible)} eligible replacement artist(s)"
            + (f" and excluded {len(excl)}: " + "; ".join(f"{e['name']} ({e['reason']})" for e in excl) if excl else "") + "."
        )
        if llm.enabled():
            out = llm.complete_json("Rewrite this coordinator summary in max 70 words, neutral tone, no new facts. "
                                    'Return {"summary": str}.', {"summary": summary})
            if isinstance(out, dict) and isinstance(out.get("summary"), str) and len(out["summary"]) < 900:
                summary = out["summary"]
        return {"plan": plan, "summary": summary}

    def persist(state: State) -> State:
        eid, now, model = state["event_id"], now_ms(), llm.model_name()
        ctx, imp, mem, plan = state["ctx"], state["impact"], state["memory"], state["plan"]
        autopilot = bool(ctx.get("autopilot"))
        strength = "high" if len(imp["candidates"]["eligible"]) >= 2 else "medium" if imp["candidates"]["eligible"] else "low"

        def decision(agent: str, dtype: str, rationale: str, payload: dict[str, Any], review: str, mdl: str) -> str:
            did = new_id("dec")
            graph.query(
                """
                MATCH (e:Event {event_id:$eid})
                CREATE (d:AgentDecision {decision_id:$id, agent_name:$agent, decision_type:$type, rationale:$why,
                        created_at:$now, model_name:$model, evidence_strength:$strength, review_status:$review,
                        run_id:$run, trace:$trace, demo:$demo})
                CREATE (d)-[:CONSIDERED {role:'subject'}]->(e)
                """, {"eid": eid, "id": did, "agent": agent, "type": dtype, "why": rationale, "now": now, "model": mdl,
                      "strength": strength, "review": review, "run": state["run_id"], "demo": bool(ctx.get("demo")),
                      "trace": json.dumps(payload, default=str)})
            return did

        det = "deterministic graph tools"
        calls = lambda a: [t for t in state["trace"] if t["agent"] == a]  # noqa: E731
        d1 = decision("Context Agent", "event_context",
                      f"Event “{ctx['title']}” at {ctx['venue']} ({ctx['neighborhood']}), starts in {ctx['hours_until']:.0f} h; "
                      f"performers: {', '.join((p['name'] or 'performer') + ' [' + str(p['status']) + ']' for p in ctx['performers'])}; "
                      f"autopilot {'authorised by the organiser' if autopilot else 'not authorised'}.",
                      {"context": ctx, "tool_calls": calls("Context Agent")}, "informational", det)
        d2 = decision("Impact Agent", "impact_assessment",
                      f"{imp['participant_total']} participant(s), {len(imp['complaints'])} complaint(s), "
                      f"{len(imp['alerts'])} overlapping alert(s); {len(imp['candidates']['eligible'])} eligible and "
                      f"{len(imp['candidates']['excluded'])} excluded replacement artist(s).",
                      {"impact": imp, "paths": imp["paths"], "tool_calls": calls("Impact Agent")}, "informational", det)
        d3 = decision("Memory Agent", "memory_retrieval",
                      f"Retrieved {len(mem['lessons'])} earlier disruption case(s) from the graph.",
                      {"memory": mem, "tool_calls": calls("Memory Agent")}, "informational", det)
        review = ("auto_authorized" if autopilot else "pending_review") if plan else "no_action"
        d4 = decision("Coordination Agent", "coordination_recommendation", state["summary"],
                      {"plan": plan, "summary": state["summary"],
                       "uncertainty": "Scores are heuristic ranking scores from graph evidence, not probabilities of acceptance."},
                      review, model)
        graph.query(
            """
            MATCH (a:AgentDecision {decision_id:$a}), (b:AgentDecision {decision_id:$b}),
                  (c:AgentDecision {decision_id:$c}), (d:AgentDecision {decision_id:$d})
            CREATE (a)-[:INFORMED]->(b), (b)-[:INFORMED]->(c), (c)-[:INFORMED]->(d)
            """, {"a": d1, "b": d2, "c": d3, "d": d4})
        graph.query("MATCH (d:AgentDecision) WHERE d.decision_id IN $ds MATCH (s:Source {source_id:'citypulse_submission'}) "
                    "MERGE (d)-[:BASED_ON]->(s)", {"ds": [d1, d2, d4]})
        mem_ids = [l["memory_id"] for l in mem["lessons"]]
        if mem_ids:
            graph.query("MATCH (d:AgentDecision) WHERE d.decision_id IN $ds MATCH (m:AgentMemory) WHERE m.memory_id IN $ms "
                        "MERGE (d)-[:USED_MEMORY]->(m)", {"ds": [d3, d4], "ms": mem_ids})

        case_id, action_ids, executed = None, [], []
        if plan:
            case_id = (graph.one(
                """
                MATCH (c:CoordinationCase {case_type:'event_disruption'})-[:ADDRESSES]->(:Event {event_id:$id})
                WHERE c.status IN ['proposed', 'open', 'in_progress'] RETURN c.case_id AS id
                ORDER BY c.created_at DESC LIMIT 1
                """, {"id": eid}, readonly=True) or {}).get("id")
            if not case_id:
                case_id = coordination.create_case(
                    graph, title=f"Replace cancelled performer: {ctx['title']}"[:140], case_type="event_disruption",
                    issue_ids=[], event_ids=[eid], created_by="agent:Coordination Agent", initial_status="proposed")
                if ctx.get("demo"):
                    graph.query("MATCH (c:CoordinationCase {case_id:$id}) SET c.demo = true", {"id": case_id})
            for r in plan:
                aid = coordination.add_action(graph, case_id, action_type=r["action_type"], description=r["description"],
                                              proposed_by="agent:Coordination Agent",
                                              payload={**r["payload"], "rationale": r["rationale"]}, decision_id=d4)
                action_ids.append(aid)
                if ctx.get("demo"):
                    graph.query("MATCH (a:CoordinationAction {action_id:$id}) SET a.demo = true", {"id": aid})
                if autopilot:
                    executed.append(coordination.auto_execute(graph, db, aid, ctx.get("organizer_id")))
        return {"decisions": {"context": d1, "impact": d2, "memory": d3, "coordination": d4},
                "case_id": case_id, "action_ids": action_ids, "executed": executed}

    sg = StateGraph(State)
    for name, fn in (("context_agent", context_agent), ("impact_agent", impact_agent), ("memory_agent", memory_agent),
                     ("coordination_agent", coordination_agent), ("persist", persist)):
        sg.add_node(name, fn)
    sg.set_entry_point("context_agent")
    sg.add_edge("context_agent", "impact_agent")
    sg.add_edge("impact_agent", "memory_agent")
    sg.add_edge("memory_agent", "coordination_agent")
    sg.add_edge("coordination_agent", "persist")
    sg.add_edge("persist", END)
    return sg.compile()


def handle_disruption(graph: GraphClient, db: Session, event_id: str) -> dict:
    state = build(graph, db).invoke({"event_id": event_id, "run_id": new_id("dec").replace("dec_", "run_"), "trace": []})
    return {
        "run_id": state["run_id"], "event_id": event_id, "summary": state["summary"], "model_name": llm.model_name(),
        "autopilot": bool(state["ctx"].get("autopilot")), "candidates": state["impact"]["candidates"],
        "plan": state["plan"], "executed": state["executed"], "case_id": state.get("case_id"),
        "action_ids": state.get("action_ids", []), "decisions": state["decisions"], "tool_calls": state["trace"],
        "memory": state["memory"],
    }
