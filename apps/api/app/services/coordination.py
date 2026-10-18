"""Coordination cases and actions.

Lifecycle of an action: proposed (by agent or coordinator) -> approved (by an authenticated coordinator,
recorded as (Coordinator)-[:APPROVED]->(CoordinationAction)) -> executed (side effects inside CityPulse only)
-> completed with an outcome. Recording an outcome triggers the Memory Agent, which writes an AgentMemory
node that later analyses retrieve through the graph (Query F).

No action contacts any government body: CityPulse is an independent community platform.
"""

import json

from sqlalchemy.orm import Session

from app.graph.client import GraphClient
from app.graph.model import new_id, now_ms, public_props
from app.services import issues as issue_svc
from app.services import notifications

ACTION_TYPES = {
    "assign_coordinator": "Assign to a CityPulse coordinator",
    "request_more_info": "Request additional information from the reporter",
    "publish_community_update": "Publish a community update",
    "link_related_reports": "Link related reports",
    "request_community_verification": "Request community verification",
    "contact_organizer": "Contact a participating event organizer (in-app)",
    "mark_completed": "Mark coordination completed",
    "invite_replacement": "Invite replacement performers (in-app)",
    "notify_attendees": "Notify event participants",
}
CASE_STATUSES = ("proposed", "open", "in_progress", "resolved", "closed")


def ensure_coordinator(graph: GraphClient, username: str) -> str:
    cid = f"crd_{username}"
    graph.query(
        """
        MERGE (c:Coordinator {coordinator_id:$id})
        ON CREATE SET c.display_name = $name, c.created_at = $now
        """, {"id": cid, "name": username, "now": now_ms()})
    return cid


def create_case(graph: GraphClient, *, title: str, case_type: str, issue_ids: list[str], created_by: str,
                initial_status: str = "open", event_ids: list[str] | None = None) -> str:
    """initial_status='proposed' is used by the Coordination Agent: the case exists to hold proposals but does not
    change any issue's public status until a coordinator approves an action."""
    cid = new_id("case")
    now = now_ms()
    graph.query(
        """
        CREATE (c:CoordinationCase {case_id:$id, title:$title, case_type:$type, status:$status,
                created_at:$now, updated_at:$now, created_by:$by})
        WITH c
        MATCH (i:Issue) WHERE i.issue_id IN $issues
        MERGE (c)-[:ADDRESSES {created_at:$now}]->(i)
        """, {"id": cid, "title": title, "type": case_type, "now": now, "by": created_by, "issues": issue_ids,
              "status": initial_status})
    if event_ids:
        graph.query(
            """
            MATCH (c:CoordinationCase {case_id:$id}), (e:Event) WHERE e.event_id IN $events
            MERGE (c)-[:ADDRESSES {created_at:$now}]->(e)
            """, {"id": cid, "events": event_ids, "now": now})
    if initial_status == "open":
        _activate_issues(graph, cid, f"Coordination case opened on CityPulse: {title}", created_by)
    return cid


def _activate_issues(graph: GraphClient, case_id: str, note: str, actor: str) -> None:
    rows = graph.query(
        """
        MATCH (c:CoordinationCase {case_id:$id})-[:ADDRESSES]->(i:Issue)
        WHERE i.status IN ['submitted', 'community_corroborated', 'under_review']
        SET i.status = 'coordination_in_progress', i.updated_at = $now
        RETURN i.issue_id AS id
        """, {"id": case_id, "now": now_ms()})
    for r in rows:
        issue_svc.record_history(graph, r["id"], note, actor)


def case_for_issue(graph: GraphClient, issue_id: str) -> str | None:
    row = graph.one(
        """
        MATCH (c:CoordinationCase)-[:ADDRESSES]->(:Issue {issue_id:$id})
        WHERE c.status IN ['proposed', 'open', 'in_progress']
        RETURN c.case_id AS id ORDER BY c.created_at DESC LIMIT 1
        """, {"id": issue_id}, readonly=True)
    return row["id"] if row else None


def list_cases(graph: GraphClient, status: str | None = None) -> list[dict]:
    rows = graph.query(
        f"""
        MATCH (c:CoordinationCase)
        {"WHERE c.status = $status" if status else ""}
        OPTIONAL MATCH (c)-[:ADDRESSES]->(i:Issue)
        OPTIONAL MATCH (c)-[:ADDRESSES]->(ev:Event)
        OPTIONAL MATCH (a:CoordinationAction)-[:PART_OF]->(c)
        WITH c, collect(DISTINCT {{issue_id: i.issue_id, title: i.title}}) AS issues,
             collect(DISTINCT {{event_id: ev.event_id, title: ev.title}}) AS events,
             count(DISTINCT a) AS actions,
             count(DISTINCT CASE WHEN a.status = 'proposed' THEN a END) AS pending
        RETURN properties(c) AS props, issues, events, actions, pending
        ORDER BY c.updated_at DESC
        """, {"status": status}, readonly=True)
    return [{**public_props("CoordinationCase", r["props"]),
             "issues": [i for i in r["issues"] if i["issue_id"]],
             "events": [e for e in r["events"] if e["event_id"]], "action_count": r["actions"],
             "pending_actions": r["pending"]} for r in rows]


def case_detail(graph: GraphClient, case_id: str, *, operator: bool = False) -> dict | None:
    row = graph.one("MATCH (c:CoordinationCase {case_id:$id}) RETURN properties(c) AS p", {"id": case_id},
                    readonly=True)
    if not row:
        return None
    case = public_props("CoordinationCase", row["p"])
    case["assigned_to"] = row["p"].get("assigned_to")
    case["issues"] = graph.query(
        """
        MATCH (c:CoordinationCase {case_id:$id})-[:ADDRESSES]->(i:Issue)
        OPTIONAL MATCH (i)-[:LOCATED_IN]->(n:Neighborhood)
        RETURN i.issue_id AS issue_id, i.title AS title, i.status AS status, i.category AS category,
               i.support_count AS support_count, n.name AS neighborhood
        """, {"id": case_id}, readonly=True)
    case["events"] = graph.query(
        """
        MATCH (c:CoordinationCase {case_id:$id})-[:ADDRESSES]->(e:Event)
        OPTIONAL MATCH (e)-[:LOCATED_IN]->(n:Neighborhood)
        RETURN e.event_id AS event_id, e.title AS title, e.start_time AS start_time, e.performer_gap AS performer_gap,
               n.name AS neighborhood
        """, {"id": case_id}, readonly=True)
    actions = graph.query(
        """
        MATCH (a:CoordinationAction)-[:PART_OF]->(c:CoordinationCase {case_id:$id})
        OPTIONAL MATCH (d:AgentDecision)-[:PRODUCED]->(a)
        OPTIONAL MATCH (crd:Coordinator)-[:APPROVED]->(a)
        RETURN properties(a) AS a, d.decision_id AS decision_id,
               coalesce(crd.display_name, a.approved_by) AS approved_by
        ORDER BY a.created_at ASC
        """, {"id": case_id}, readonly=True)
    case["actions"] = [{**public_props("CoordinationAction", x["a"]), "decision_id": x["decision_id"],
                        "approved_by": x["approved_by"], "payload": json.loads(x["a"].get("payload") or "{}")
                        if operator else None} for x in actions]
    case["memories"] = graph.query(
        """
        MATCH (m:AgentMemory)-[:SUMMARIZES]->(c:CoordinationCase {case_id:$id})
        RETURN m.memory_id AS memory_id, m.summary AS summary, m.memory_type AS memory_type,
               m.created_at AS created_at
        ORDER BY m.created_at DESC
        """, {"id": case_id}, readonly=True)
    case["decisions"] = graph.query(
        """
        MATCH (d:AgentDecision)-[:CONSIDERED]->(x)<-[:ADDRESSES]-(c:CoordinationCase {case_id:$id})
        RETURN DISTINCT d.decision_id AS decision_id, d.agent_name AS agent_name, d.decision_type AS decision_type,
               d.rationale AS rationale, d.created_at AS created_at, d.model_name AS model_name,
               d.review_status AS review_status
        ORDER BY d.created_at DESC LIMIT 20
        """, {"id": case_id}, readonly=True)
    case["participant_count"] = (graph.one(
        "MATCH (r:Resident)-[:PARTICIPATES_IN]->(c:CoordinationCase {case_id:$id}) RETURN count(r) AS c",
        {"id": case_id}, readonly=True) or {"c": 0})["c"]
    return case


def add_action(graph: GraphClient, case_id: str, *, action_type: str, description: str, proposed_by: str,
               payload: dict | None = None, decision_id: str | None = None) -> str:
    aid = new_id("act")
    now = now_ms()
    row = graph.one(
        """
        MATCH (c:CoordinationCase {case_id:$case})
        CREATE (a:CoordinationAction {action_id:$id, action_type:$type, description:$desc, status:'proposed',
                proposed_by:$by, payload:$payload, created_at:$now})-[:PART_OF]->(c)
        SET c.updated_at = $now
        RETURN a.action_id AS id
        """, {"case": case_id, "id": aid, "type": action_type, "desc": description, "by": proposed_by,
              "payload": json.dumps(payload or {}), "now": now})
    if not row:
        raise LookupError("case")
    if decision_id:
        graph.query(
            """
            MATCH (d:AgentDecision {decision_id:$d}), (a:CoordinationAction {action_id:$a})
            MERGE (d)-[:PRODUCED]->(a)
            """, {"d": decision_id, "a": aid})
    return aid


def _action(graph: GraphClient, action_id: str) -> dict | None:
    return graph.one(
        """
        MATCH (a:CoordinationAction {action_id:$id})-[:PART_OF]->(c:CoordinationCase)
        RETURN properties(a) AS a, c.case_id AS case_id, c.title AS case_title
        """, {"id": action_id}, readonly=True)


def approve(graph: GraphClient, db: Session, action_id: str, username: str) -> dict:
    row = _action(graph, action_id)
    if not row:
        raise LookupError("action")
    if row["a"]["status"] != "proposed":
        raise ValueError(f"Action is already {row['a']['status']}.")
    crd = ensure_coordinator(graph, username)
    now = now_ms()
    graph.query(
        """
        MATCH (a:CoordinationAction {action_id:$id}), (crd:Coordinator {coordinator_id:$crd})
        SET a.status = 'approved', a.approved_by = $user, a.approved_at = $now
        MERGE (crd)-[:APPROVED {at:$now}]->(a)
        WITH a MATCH (a)-[:PART_OF]->(c:CoordinationCase)
        SET c.status = CASE WHEN c.status IN ['proposed', 'open'] THEN 'in_progress' ELSE c.status END,
            c.updated_at = $now
        """, {"id": action_id, "crd": crd, "user": username, "now": now})
    _activate_issues(graph, row["case_id"], f"A CityPulse coordinator approved coordination: {row['case_title']}",
                     f"coordinator:{username}")
    graph.query(
        """
        MATCH (a:CoordinationAction {action_id:$id})<-[:PRODUCED]-(d:AgentDecision)
        SET d.review_status = 'approved'
        """, {"id": action_id})
    result = execute(graph, db, action_id, row["case_id"], row["a"], username)
    graph.query("MATCH (a:CoordinationAction {action_id:$id}) SET a.status = 'executed', a.executed_at = $now,"
                " a.execution_note = $note", {"id": action_id, "now": now_ms(), "note": result})
    return {"action_id": action_id, "status": "executed", "execution": result}


def reject(graph: GraphClient, action_id: str, username: str, reason: str) -> None:
    graph.query(
        """
        MATCH (a:CoordinationAction {action_id:$id}) WHERE a.status = 'proposed'
        SET a.status = 'rejected', a.rejected_by = $user, a.outcome = $reason, a.executed_at = $now
        WITH a OPTIONAL MATCH (a)<-[:PRODUCED]-(d:AgentDecision) SET d.review_status = 'rejected'
        """, {"id": action_id, "user": username, "reason": reason, "now": now_ms()})


def execute(graph: GraphClient, db: Session, action_id: str, case_id: str, action: dict, username: str) -> str:
    """Side effects happen only inside CityPulse (graph updates + in-app notifications)."""
    kind = action["action_type"]
    payload = json.loads(action.get("payload") or "{}")
    issue_ids = [r["issue_id"] for r in graph.query(
        "MATCH (c:CoordinationCase {case_id:$id})-[:ADDRESSES]->(i:Issue) RETURN i.issue_id AS issue_id",
        {"id": case_id}, readonly=True)]
    event_ids = [r["event_id"] for r in graph.query(
        "MATCH (c:CoordinationCase {case_id:$id})-[:ADDRESSES]->(e:Event) RETURN e.event_id AS event_id",
        {"id": case_id}, readonly=True)]
    message = payload.get("message") or action.get("description") or ""
    if kind == "invite_replacement":
        from app.services import talent
        ev = payload.get("event_id") or (event_ids[0] if event_ids else None)
        candidates = payload.get("candidates", [])
        if not ev or not candidates:
            return "No candidates to invite."
        sent = talent.invite(graph, db, ev, candidates, action_id, message)
        return f"Invited {len(candidates)} artist(s) to step in; {sent} in-app notification(s) sent."
    if kind == "notify_attendees":
        total = 0
        for ev in ([payload["event_id"]] if payload.get("event_id") else event_ids):
            total += _event_post(graph, db, ev, message, action_id, "event_update", username)
        return f"Event participants and organiser notified ({total} in-app notification(s))."
    if kind == "link_related_reports":
        pairs = payload.get("pairs", [])
        for a, b in pairs:
            graph.query(
                """
                MATCH (x:Issue {issue_id:$a}), (y:Issue {issue_id:$b})
                MERGE (x)-[d:POSSIBLY_DUPLICATES]->(y)
                ON CREATE SET d.basis = 'coordinator_linked', d.created_at = $now
                SET d.confirmed = true, d.confirmed_by = $user
                WITH y MATCH (c:CoordinationCase {case_id:$case}) MERGE (c)-[:ADDRESSES]->(y)
                """, {"a": a, "b": b, "now": now_ms(), "user": username, "case": case_id})
        return f"Linked {len(pairs)} report pair(s) and attached them to the case."
    if kind in ("publish_community_update", "request_community_verification", "request_more_info"):
        label = {"publish_community_update": "Community update", "request_community_verification":
                 "Verification request", "request_more_info": "Coordinator question"}[kind]
        audience: list[str] = []
        for iid in issue_ids:
            issue_svc.record_history(graph, iid, f"{label} from CityPulse coordination: {message}", f"coordinator:{username}")
            if kind == "request_more_info":
                rep = issue_svc.reporter_of(graph, iid)
                audience += [rep] if rep else []
            else:
                audience += notifications.issue_audience(graph, iid)
        sent = notifications.notify(db, audience, kind=kind, entity_id=issue_ids[0] if issue_ids else case_id,
                                    message=f"{label}: {message}"[:500], dedupe_key=f"{kind}:{action_id}")
        if kind == "publish_community_update":
            for ev in event_ids:
                sent += _event_post(graph, db, ev, message, action_id, "event_update", username)
        return f"Posted to {len(issue_ids) + len(event_ids)} item(s); {sent} in-app notification(s) sent."
    if kind == "assign_coordinator":
        assignee = payload.get("assignee") or username
        graph.query("MATCH (c:CoordinationCase {case_id:$id}) SET c.assigned_to = $u", {"id": case_id, "u": assignee})
        return f"Case assigned to coordinator {assignee}."
    if kind == "contact_organizer":
        event_id = payload.get("event_id")
        from app.services.events import organizer_of
        org = organizer_of(graph, event_id) if event_id else None
        if not org:
            return "No organizer with a CityPulse profile found for this event; nothing sent."
        notifications.notify(db, [org], kind="organizer_contact", entity_id=event_id,
                             message=f"CityPulse coordination: {message}"[:500], dedupe_key=f"org:{action_id}")
        return "Organizer notified in-app."
    if kind == "mark_completed":
        graph.query("MATCH (c:CoordinationCase {case_id:$id}) SET c.status = 'resolved', c.updated_at = $now",
                    {"id": case_id, "now": now_ms()})
        return "Case marked resolved."
    return "Recorded."


def _event_post(graph: GraphClient, db: Session, event_id: str, message: str, action_id: str, kind: str,
                actor: str) -> int:
    graph.query(
        """
        MATCH (e:Event {event_id:$eid})
        CREATE (d:Discussion {discussion_id:$did, body:$body, created_at:$now, visibility:'public',
                              kind:'history', actor:$actor})-[:ABOUT]->(e)
        """, {"eid": event_id, "did": new_id("dis"), "now": now_ms(), "actor": actor, "body": message})
    return notifications.notify(db, notifications.event_audience(graph, event_id), kind=kind, entity_id=event_id,
                                message=message[:500], dedupe_key=f"{kind}:{action_id}:{event_id}")


def auto_execute(graph: GraphClient, db: Session, action_id: str, authorizer_id: str | None) -> dict:
    """Execute an agent-proposed action WITHOUT a coordinator click, only because the event's organiser explicitly
    pre-authorised autopilot for this event. Recorded as (Resident)-[:AUTHORIZED {basis:'event_autopilot'}]->(Action)."""
    row = _action(graph, action_id)
    if not row:
        raise LookupError("action")
    now = now_ms()
    graph.query(
        """
        MATCH (a:CoordinationAction {action_id:$id})
        SET a.status = 'approved', a.approved_by = 'organiser autopilot', a.approved_at = $now,
            a.authorization = 'event_autopilot'
        WITH a MATCH (a)-[:PART_OF]->(c:CoordinationCase)
        SET c.status = CASE WHEN c.status IN ['proposed', 'open'] THEN 'in_progress' ELSE c.status END,
            c.updated_at = $now
        WITH a OPTIONAL MATCH (o:Resident {resident_id:$org})
        FOREACH (_ IN CASE WHEN o IS NULL THEN [] ELSE [1] END | MERGE (o)-[:AUTHORIZED {at:$now, basis:'event_autopilot'}]->(a))
        WITH a OPTIONAL MATCH (a)<-[:PRODUCED]-(d:AgentDecision)
        SET d.review_status = 'auto_authorized'
        """, {"id": action_id, "now": now, "org": authorizer_id or ""})
    result = execute(graph, db, action_id, row["case_id"], row["a"], "CityPulse agent (organiser-authorised)")
    graph.query("MATCH (a:CoordinationAction {action_id:$id}) SET a.status = 'executed', a.executed_at = $now,"
                " a.execution_note = $note", {"id": action_id, "now": now_ms(), "note": result})
    return {"action_id": action_id, "status": "executed", "execution": result}


def record_outcome(graph: GraphClient, action_id: str, username: str, outcome: str, success: bool) -> dict:
    row = _action(graph, action_id)
    if not row:
        raise LookupError("action")
    graph.query(
        """
        MATCH (a:CoordinationAction {action_id:$id})
        SET a.status = 'completed', a.outcome = $outcome, a.outcome_success = $ok, a.outcome_by = $user,
            a.completed_at = $now
        """, {"id": action_id, "outcome": outcome, "ok": success, "user": username, "now": now_ms()})
    from app.agents.memory import write_case_memory
    memory_id = write_case_memory(graph, row["case_id"], trigger_action_id=action_id)
    return {"action_id": action_id, "memory_id": memory_id}


def set_case_status(graph: GraphClient, case_id: str, status: str) -> None:
    graph.query("MATCH (c:CoordinationCase {case_id:$id}) SET c.status = $s, c.updated_at = $now",
                {"id": case_id, "s": status, "now": now_ms()})


def join_case(graph: GraphClient, case_id: str, resident_id: str) -> None:
    graph.query(
        """
        MATCH (c:CoordinationCase {case_id:$id}), (r:Resident {resident_id:$rid})
        MERGE (r)-[p:PARTICIPATES_IN]->(c) ON CREATE SET p.created_at = $now, p.role = 'volunteer'
        """, {"id": case_id, "rid": resident_id, "now": now_ms()})
