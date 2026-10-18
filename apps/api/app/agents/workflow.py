"""Issue analysis workflow (LangGraph): Context -> Impact -> Memory -> Coordination -> persist.

Each agent reads FalkorDB through typed tools, hands its structured output to the next agent, and is recorded
as an (:AgentDecision) with INFORMED edges between agents (the hand-off chain), CONSIDERED edges to the issues
it looked at, BASED_ON edges to sources, USED_MEMORY edges to prior memories and PRODUCED edges to proposed
coordination actions. Nothing is executed until a coordinator approves it.
"""

import json
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from app.agents import llm, tools
from app.graph.client import GraphClient
from app.graph.model import new_id, now_ms
from app.services import coordination

AGENTS = {
    "context": "Context Agent",
    "impact": "Impact Agent",
    "memory": "Memory Agent",
    "coordination": "Coordination Agent",
}


class AgentState(TypedDict, total=False):
    issue_id: str
    run_id: str
    trace: list[dict]
    context: dict
    clarifications: list[str]
    impact: dict
    memory: dict
    recommendations: list[dict]
    summary: str
    evidence_strength: str
    decisions: dict
    case_id: str
    action_ids: list[str]


def _log(state: AgentState, agent: str, result: tools.ToolResult) -> list[dict]:
    return state.get("trace", []) + [{"agent": AGENTS[agent], "tool": result.tool, "query_id": result.query_id,
                                      "rows": len(result.rows)}]


def _n(id_: str | None, label: str, name: str | None) -> dict:
    return {"id": id_, "label": label, "name": name}


def build(graph: GraphClient):
    # ---------------- Context Agent ----------------
    def context_agent(state: AgentState) -> AgentState:
        res = tools.issue_context(graph, state["issue_id"])
        if not res.rows:
            raise LookupError("issue")
        ctx = res.rows[0]
        clar = []
        if not ctx["neighborhood_id"]:
            clar.append("The report is not within 4 km of any named OpenStreetMap place; location context is limited.")
        if not ctx["road_id"]:
            clar.append("No OSM road could be resolved for this location; ask the reporter for the street name.")
        if len((ctx.get("description") or "").strip()) < 40:
            clar.append("The description is short; more detail (since when, how severe) would help others.")
        return {"context": ctx, "clarifications": clar, "trace": _log(state, "context", res)}

    # ---------------- Impact Agent ----------------
    def impact_agent(state: AgentState) -> AgentState:
        ctx, iid = state["context"], state["issue_id"]
        trace = state.get("trace", [])
        rel = tools.related_issues(graph, iid); trace = _log({"trace": trace}, "impact", rel)
        warn = tools.active_warnings(graph, iid); trace = _log({"trace": trace}, "impact", warn)
        evts = tools.upcoming_events_nearby(graph, iid); trace = _log({"trace": trace}, "impact", evts)
        orgs = tools.responsible_organizations(graph, [a["asset_id"] for a in ctx["assets"]])
        trace = _log({"trace": trace}, "impact", orgs)
        net = tools.coordination_network(graph, iid); trace = _log({"trace": trace}, "impact", net)

        issue_node = _n(iid, "Issue", ctx["title"])
        paths = []
        for r in rel.rows[:8]:
            other = _n(r["issue_id"], "Issue", r["title"])
            for road in r["shared_roads"]:
                paths.append({"nodes": [issue_node, _n(road["id"], "Road", road["name"]), other],
                              "rels": ["ON_ROAD", "ON_ROAD"], "query_id": rel.query_id,
                              "meaning": f"Both reports are on {road['name']}"})
            for a in r["shared_assets"]:
                paths.append({"nodes": [issue_node, _n(a["id"], "InfrastructureAsset", a["name"]), other],
                              "rels": ["NEAR", "NEAR"], "query_id": rel.query_id,
                              "meaning": f"Both reports are near {a['name']}"})
            if not r["shared_roads"] and not r["shared_assets"]:
                for nb in r["shared_neighborhoods"]:
                    paths.append({"nodes": [issue_node, _n(nb["id"], "Neighborhood", nb["name"]), other],
                                  "rels": ["LOCATED_IN", "LOCATED_IN"], "query_id": rel.query_id,
                                  "meaning": f"Both reports are in {nb['name']}"})
        for w in warn.rows:
            paths.append({"nodes": [_n(w["warning_id"], "Warning", w["title"]),
                                    _n(ctx["neighborhood_id"], "Neighborhood", w["via"]), issue_node],
                          "rels": ["AFFECTS", "LOCATED_IN"], "query_id": warn.query_id,
                          "meaning": f"Official alert from {w['issuing_authority']} covers {w['via']}"})
        for e in evts.rows:
            paths.append({"nodes": [issue_node, _n(e["event_id"], "Event", e["title"])], "rels": ["WITHIN_2KM"],
                          "query_id": evts.query_id,
                          "meaning": f"Upcoming event {int(e['distance_m'])} m away"
                                     + (f", sharing {e['shared_road']}" if e["shared_road"] else "")})
        for o in orgs.rows:
            asset = next((a for a in ctx["assets"] if a["asset_id"] == o["asset_id"]), {})
            paths.append({"nodes": [issue_node, _n(o["asset_id"], "InfrastructureAsset", asset.get("name")),
                                    _n(o["organization_id"], "Organization", o["organization"])],
                          "rels": [asset.get("relationship", "NEAR"), o["relationship"]], "query_id": orgs.query_id,
                          "meaning": f"{asset.get('name')} is operated by {o['organization']} ({o['basis']})"})
        impact = {"related": rel.rows, "warnings": warn.rows, "events": evts.rows, "organizations": orgs.rows,
                  "network": net.rows[0] if net.rows else {}, "paths": paths}
        return {"impact": impact, "trace": trace}

    # ---------------- Memory Agent (retrieval) ----------------
    def memory_agent(state: AgentState) -> AgentState:
        iid = state["issue_id"]
        prior = tools.prior_memory(graph, iid)
        trace = _log(state, "memory", prior)
        rec = tools.recurrence(graph, iid)
        trace = _log({"trace": trace}, "memory", rec)
        lessons = []
        for p in prior.rows:
            for a in p["actions"]:
                if a.get("outcome"):
                    lessons.append({"prior_issue_id": p["prior_issue_id"], "prior_title": p["prior_title"],
                                    "case_id": p["case_id"], "action_type": a["action_type"],
                                    "outcome": a["outcome"], "approved_by": a.get("approved_by"),
                                    "via": p["routes"][0]["via"] if p["routes"] else []})
        return {"memory": {"prior_cases": prior.rows, "recurrence": rec.rows[0] if rec.rows else {},
                           "lessons": lessons}, "trace": trace}

    # ---------------- Coordination Agent ----------------
    def coordination_agent(state: AgentState) -> AgentState:
        ctx, impact, memory = state["context"], state["impact"], state["memory"]
        recs: list[dict] = []
        dups = [r for r in impact["related"] if r["same_category"] and r["score"] >= 0.65]
        if dups:
            recs.append({
                "action_type": "link_related_reports",
                "description": f"Link {len(dups)} likely duplicate report(s) so residents coordinate in one place.",
                "payload": {"pairs": [[state["issue_id"], d["issue_id"]] for d in dups]},
                "rationale": "Graph overlap: " + "; ".join(
                    f"'{d['title']}' (score {d['score']:.2f}: same category"
                    + (f", same road {d['shared_roads'][0]['name']}" if d["shared_roads"] else "")
                    + (f", near {d['shared_assets'][0]['name']}" if d["shared_assets"] else "") + ")" for d in dups[:3]),
            })
        if (ctx.get("support_count") or 0) < 2 and ctx["status"] == "submitted":
            recs.append({
                "action_type": "request_community_verification",
                "description": "Ask followers and nearby residents to confirm whether they are affected.",
                "payload": {"message": f"Are you affected by '{ctx['title']}'"
                                       f"{' near ' + ctx['road'] if ctx.get('road') else ''}? Tap 'I'm affected too' "
                                       "or add details."},
                "rationale": f"Only {ctx.get('support_count') or 0} resident(s) have corroborated this report so far.",
            })
        if state.get("clarifications") and any("description" in c or "street" in c for c in state["clarifications"]):
            recs.append({
                "action_type": "request_more_info",
                "description": "Ask the reporter for more detail.",
                "payload": {"message": " ".join(c for c in state["clarifications"] if "description" in c or "street" in c)},
                "rationale": "Context Agent flagged missing information.",
            })
        for w in impact["warnings"][:1]:
            recs.append({
                "action_type": "publish_community_update",
                "description": "Publish an update pointing residents to the official alert.",
                "payload": {"message": f"An official alert from {w['issuing_authority']} currently covers {w['via']}: "
                                       f"\"{w['title']}\". See the official source: {w['source_url']}",
                            "warning_id": w["warning_id"]},
                "rationale": f"Active official alert affects {w['via']} (graph path Warning-AFFECTS->Neighborhood<-LOCATED_IN-Issue).",
            })
        for e in impact["events"][:2]:
            recs.append({
                "action_type": "contact_organizer",
                "description": f"Let the organizer of '{e['title']}' know about this report nearby.",
                "payload": {"event_id": e["event_id"],
                            "message": f"A community report '{ctx['title']}' is {int(e['distance_m'])} m from your "
                                       f"event venue. Consider informing participants."},
                "rationale": f"Event starts soon, {int(e['distance_m'])} m away"
                             + (f" on the same road ({e['shared_road']})" if e["shared_road"] else "") + ".",
            })
        # Memory changes the recommendation: reuse what worked, avoid what did not.
        worked = [l for l in memory["lessons"] if l["outcome"]]
        for lesson in worked[:2]:
            already = next((r for r in recs if r["action_type"] == lesson["action_type"]), None)
            note = (f"Prior case on '{lesson['prior_title']}' (connected via {' → '.join(lesson['via'])}) used "
                    f"{lesson['action_type'].replace('_', ' ')}; recorded outcome: \"{lesson['outcome']}\".")
            if already:
                already["rationale"] += " Memory: " + note
                already["from_memory"] = True
            elif lesson["action_type"] not in ("link_related_reports", "mark_completed", "contact_organizer"):
                recs.append({"action_type": lesson["action_type"],
                             "description": f"Repeat the approach from the earlier case ({lesson['action_type'].replace('_', ' ')}).",
                             "payload": {"message": f"Follow-up on '{ctx['title']}', similar to an earlier case."},
                             "rationale": "Memory: " + note, "from_memory": True})
        rec_row = memory.get("recurrence") or {}
        recurring = (rec_row.get("same_road") or 0) + (rec_row.get("same_neighborhood") or 0)

        routes = len({p["query_id"] for p in impact["paths"]}) + (1 if memory["lessons"] else 0)
        strength = "high" if routes >= 3 else "medium" if routes >= 1 else "low"
        summary = (
            f"'{ctx['title']}' ({ctx['category'].replace('_', ' ')}) in {ctx.get('neighborhood') or 'an unmapped area'}"
            f"{' on ' + ctx['road'] if ctx.get('road') else ''}. "
            f"{len(impact['related'])} related report(s), {len(impact['warnings'])} active official alert(s), "
            f"{len(impact['events'])} upcoming event(s) within 2 km, {len(memory['prior_cases'])} prior coordination "
            f"case(s) reachable in the graph."
            + (f" This looks recurring: {recurring} earlier report(s) of the same category nearby in the past year." if recurring else "")
        )
        if llm.enabled():
            out = llm.complete_json(
                "Write a concise, neutral summary (max 80 words) of the situation for a CityPulse coordinator, "
                "and improve each recommendation's 'message' for residents (max 50 words each, no promises, "
                "no claims about government action). Return {\"summary\": str, \"messages\": [str, ...]} with "
                "messages in the same order as DATA.recommendations.",
                {"issue": {k: ctx[k] for k in ("title", "description", "category", "neighborhood", "road")},
                 "graph_findings": summary, "recommendations": [{"action_type": r["action_type"],
                                                                  "message": r["payload"].get("message")} for r in recs]})
            if isinstance(out, dict):
                if isinstance(out.get("summary"), str) and len(out["summary"]) < 1200:
                    summary = out["summary"]
                msgs = out.get("messages")
                if isinstance(msgs, list) and len(msgs) == len(recs):
                    for r, m in zip(recs, msgs):
                        if isinstance(m, str) and "message" in r["payload"] and len(m) < 600:
                            r["payload"]["message"] = m
        return {"recommendations": recs, "summary": summary, "evidence_strength": strength}

    # ---------------- Persist decisions (graph memory of the run) ----------------
    def persist(state: AgentState) -> AgentState:
        iid, run_id, now = state["issue_id"], state["run_id"], now_ms()
        model = llm.model_name()
        trace = state["trace"]
        ctx, impact, memory = state["context"], state["impact"], state["memory"]
        sources = set(ctx.get("sources", [])) | {"citypulse_submission"}
        if impact["warnings"]:
            sources.add("src_ndma_sachet")
        if ctx.get("neighborhood_id") or ctx.get("road_id"):
            sources.add("src_osm")

        def decision(agent: str, dtype: str, rationale: str, payload: dict[str, Any], review: str) -> str:
            did = new_id("dec")
            graph.query(
                """
                MATCH (i:Issue {issue_id:$iid})
                CREATE (d:AgentDecision {decision_id:$id, agent_name:$agent, decision_type:$type, rationale:$why,
                        created_at:$now, model_name:$model, evidence_strength:$strength, review_status:$review,
                        run_id:$run, trace:$trace})
                CREATE (d)-[:CONSIDERED {role:'subject'}]->(i)
                """, {"iid": iid, "id": did, "agent": AGENTS[agent], "type": dtype, "why": rationale, "now": now,
                      "model": model if agent == "coordination" else "deterministic graph tools",
                      "strength": state["evidence_strength"], "review": review, "run": run_id,
                      "trace": json.dumps(payload, default=str)})
            return did

        d_ctx = decision("context", "context_resolution",
                         f"Resolved {ctx['title']!r} to {ctx.get('neighborhood') or 'no named place'}"
                         f"{', ' + ctx['district'] if ctx.get('district') else ''}"
                         f"{', road ' + ctx['road'] if ctx.get('road') else ''}; {len(ctx['assets'])} nearby asset(s).",
                         {"context": ctx, "clarifications": state["clarifications"],
                          "tool_calls": [t for t in trace if t["agent"] == AGENTS["context"]]}, "informational")
        d_imp = decision("impact", "impact_assessment",
                         f"{len(impact['paths'])} explanation path(s): {len(impact['related'])} related report(s), "
                         f"{len(impact['warnings'])} alert(s), {len(impact['events'])} event(s), "
                         f"{len(impact['organizations'])} operator link(s).",
                         {"paths": impact["paths"], "tool_calls": [t for t in trace if t["agent"] == AGENTS["impact"]]},
                         "informational")
        d_mem = decision("memory", "memory_retrieval",
                         f"Retrieved {len(memory['prior_cases'])} prior case(s) and {len(memory['lessons'])} recorded "
                         "outcome(s) through graph routes.",
                         {"prior_cases": memory["prior_cases"], "recurrence": memory["recurrence"],
                          "tool_calls": [t for t in trace if t["agent"] == AGENTS["memory"]]}, "informational")
        d_crd = decision("coordination", "coordination_recommendation", state["summary"],
                         {"recommendations": state["recommendations"], "summary": state["summary"],
                          "uncertainty": "Evidence strength is a count of independent graph routes, not a calibrated "
                                         "probability. Recommendations are proposals and require coordinator approval.",
                          "clarifications": state["clarifications"]},
                         "pending_review" if state["recommendations"] else "no_action")
        graph.query(
            """
            MATCH (a:AgentDecision {decision_id:$a}), (b:AgentDecision {decision_id:$b}),
                  (c:AgentDecision {decision_id:$c}), (d:AgentDecision {decision_id:$d})
            CREATE (a)-[:INFORMED]->(b), (b)-[:INFORMED]->(c), (c)-[:INFORMED]->(d)
            """, {"a": d_ctx, "b": d_imp, "c": d_mem, "d": d_crd})
        graph.query(
            """
            MATCH (d:AgentDecision) WHERE d.decision_id IN $ds
            MATCH (s:Source) WHERE s.source_id IN $sources
            MERGE (d)-[:BASED_ON]->(s)
            """, {"ds": [d_ctx, d_imp, d_crd], "sources": sorted(sources)})
        related_ids = [r["issue_id"] for r in impact["related"]]
        if related_ids:
            graph.query(
                """
                MATCH (d:AgentDecision {decision_id:$d}), (i:Issue) WHERE i.issue_id IN $ids
                MERGE (d)-[:CONSIDERED {role:'related'}]->(i)
                """, {"d": d_imp, "ids": related_ids})
        if impact["warnings"] or impact["events"]:
            graph.query(
                """
                MATCH (d:AgentDecision {decision_id:$d})
                OPTIONAL MATCH (w:Warning) WHERE w.warning_id IN $ws
                OPTIONAL MATCH (e:Event) WHERE e.event_id IN $es
                FOREACH (_ IN CASE WHEN w IS NULL THEN [] ELSE [1] END | MERGE (d)-[:CONSIDERED {role:'warning'}]->(w))
                FOREACH (_ IN CASE WHEN e IS NULL THEN [] ELSE [1] END | MERGE (d)-[:CONSIDERED {role:'event'}]->(e))
                """, {"d": d_imp, "ws": [w["warning_id"] for w in impact["warnings"]],
                      "es": [e["event_id"] for e in impact["events"]]})
        mem_ids = [m["memory_id"] for p in memory["prior_cases"] for m in p["memories"]]
        if mem_ids:
            graph.query(
                """
                MATCH (d:AgentDecision) WHERE d.decision_id IN $ds
                MATCH (m:AgentMemory) WHERE m.memory_id IN $ms
                MERGE (d)-[:USED_MEMORY]->(m)
                """, {"ds": [d_mem, d_crd], "ms": mem_ids})

        case_id, action_ids = None, []
        if state["recommendations"]:
            case_id = coordination.case_for_issue(graph, iid) or coordination.create_case(
                graph, title=f"Coordination: {ctx['title']}"[:120], case_type=ctx["category"], issue_ids=[iid],
                created_by="agent:Coordination Agent", initial_status="proposed")
            for r in state["recommendations"]:
                action_ids.append(coordination.add_action(
                    graph, case_id, action_type=r["action_type"], description=r["description"],
                    proposed_by="agent:Coordination Agent", payload={**r["payload"], "rationale": r["rationale"]},
                    decision_id=d_crd))
        return {"decisions": {"context": d_ctx, "impact": d_imp, "memory": d_mem, "coordination": d_crd},
                "case_id": case_id, "action_ids": action_ids}

    sg = StateGraph(AgentState)
    sg.add_node("context_agent", context_agent)
    sg.add_node("impact_agent", impact_agent)
    sg.add_node("memory_agent", memory_agent)
    sg.add_node("coordination_agent", coordination_agent)
    sg.add_node("persist", persist)
    sg.set_entry_point("context_agent")
    sg.add_edge("context_agent", "impact_agent")
    sg.add_edge("impact_agent", "memory_agent")
    sg.add_edge("memory_agent", "coordination_agent")
    sg.add_edge("coordination_agent", "persist")
    sg.add_edge("persist", END)
    return sg.compile()


def analyze_issue(graph: GraphClient, issue_id: str) -> dict:
    app = build(graph)
    state = app.invoke({"issue_id": issue_id, "run_id": new_id("dec").replace("dec_", "run_"), "trace": []})
    return {
        "run_id": state["run_id"], "issue_id": issue_id, "summary": state["summary"],
        "evidence_strength": state["evidence_strength"], "model_name": llm.model_name(),
        "clarifications": state["clarifications"], "recommendations": state["recommendations"],
        "paths": state["impact"]["paths"], "memory": state["memory"], "tool_calls": state["trace"],
        "decisions": state["decisions"], "case_id": state.get("case_id"), "action_ids": state.get("action_ids", []),
    }


def decision_detail(graph: GraphClient, decision_id: str) -> dict | None:
    row = graph.one(
        """
        MATCH (d:AgentDecision {decision_id:$id})
        OPTIONAL MATCH (d)-[c:CONSIDERED]->(x)
        OPTIONAL MATCH (d)-[:BASED_ON]->(s:Source)
        OPTIONAL MATCH (d)-[:USED_MEMORY]->(m:AgentMemory)
        OPTIONAL MATCH (d)-[:PRODUCED]->(a:CoordinationAction)
        OPTIONAL MATCH (prev:AgentDecision)-[:INFORMED]->(d)
        OPTIONAL MATCH (d)-[:INFORMED]->(next:AgentDecision)
        RETURN properties(d) AS d,
               collect(DISTINCT {id: coalesce(x.issue_id, x.warning_id, x.event_id), label: labels(x)[0],
                                 name: coalesce(x.title, x.name), role: c.role}) AS considered,
               collect(DISTINCT {source_id: s.source_id, name: s.name, url: s.url, license: s.license}) AS sources,
               collect(DISTINCT {memory_id: m.memory_id, summary: m.summary}) AS memories,
               collect(DISTINCT {action_id: a.action_id, action_type: a.action_type, status: a.status}) AS actions,
               prev.decision_id AS previous, prev.agent_name AS previous_agent,
               next.decision_id AS next, next.agent_name AS next_agent
        """, {"id": decision_id}, readonly=True)
    if not row:
        return None
    d = row["d"]
    return {
        "decision_id": d["decision_id"], "agent_name": d["agent_name"], "decision_type": d["decision_type"],
        "rationale": d["rationale"], "created_at": d["created_at"], "model_name": d["model_name"],
        "evidence_strength": d.get("evidence_strength"), "review_status": d["review_status"], "run_id": d["run_id"],
        "trace": json.loads(d.get("trace") or "{}"),
        "considered": [x for x in row["considered"] if x["id"]],
        "sources": [x for x in row["sources"] if x["source_id"]],
        "memories": [x for x in row["memories"] if x["memory_id"]],
        "actions": [x for x in row["actions"] if x["action_id"]],
        "handoff": {"previous": row["previous"], "previous_agent": row["previous_agent"], "next": row["next"],
                    "next_agent": row["next_agent"]},
    }


def decisions_for_issue(graph: GraphClient, issue_id: str) -> list[dict]:
    return graph.query(
        """
        MATCH (d:AgentDecision)-[:CONSIDERED {role:'subject'}]->(:Issue {issue_id:$id})
        RETURN d.decision_id AS decision_id, d.agent_name AS agent_name, d.decision_type AS decision_type,
               d.rationale AS rationale, d.created_at AS created_at, d.run_id AS run_id,
               d.review_status AS review_status, d.model_name AS model_name, d.evidence_strength AS evidence_strength
        ORDER BY d.created_at DESC, d.decision_type ASC
        """, {"id": issue_id}, readonly=True)
