"""Professions, performers and replacement matching.

Graph shape:
  (Resident)-[:PRACTICES]->(Profession {category})        who does what
  (Event)-[:FEATURES {status, role}]->(Resident)          who is booked to perform
  (Event)-[:INVITED {status, score, reasons}]->(Resident) agent/coordinator invitations to step in

A performer cancelling flips the FEATURES edge to `cancelled`, sets `Event.performer_gap`, notifies participants,
and (see agents/event_workflow.py) wakes the agents. Replacement candidates come from Query G.
"""

import hashlib

from sqlalchemy.orm import Session

from app.graph.client import GraphClient
from app.graph.model import new_id, now_ms
from app.graph.queries import Q, query_id
from app.services import notifications

ARTIST_WORDS = ("singer", "musician", "vocalist", "guitarist", "drummer", "pianist", "painter", "sketch", "dancer",
                "poet", "comedian", "actor", "photographer", "artist", "performer", "storyteller", "dj", "sitarist",
                "tabla", "illustrator")
FAMILIES = {
    "music": ("singer", "musician", "vocalist", "guitarist", "drummer", "pianist", "sitarist", "tabla", "dj", "composer"),
    "visual": ("painter", "sketch", "illustrator", "photographer", "sculptor", "muralist"),
    "performance": ("comedian", "actor", "poet", "storyteller", "dancer", "performer", "magician"),
}
SEARCH_RADIUS_M = 15_000
MIN_SCORE = 0.3


def category_for(profession: str) -> str:
    p = profession.lower()
    return "artist" if any(w in p for w in ARTIST_WORDS) else "professional"


def family_for(profession: str) -> str | None:
    p = profession.lower()
    for fam, words in FAMILIES.items():
        if any(w in p for w in words):
            return fam
    return None


def set_profession(graph: GraphClient, resident_id: str, profession: str) -> None:
    name = " ".join(profession.split())
    graph.query("MATCH (r:Resident {resident_id:$rid})-[old:PRACTICES]->() DELETE old", {"rid": resident_id})
    if not name:
        graph.query("MATCH (r:Resident {resident_id:$rid}) REMOVE r.profession", {"rid": resident_id})
        return
    pid = "prof_" + hashlib.sha1(name.lower().encode()).hexdigest()[:12]
    graph.query(
        """
        MATCH (r:Resident {resident_id:$rid})
        MERGE (p:Profession {profession_id:$pid})
        ON CREATE SET p.name = $name, p.category = $cat, p.family = $fam
        MERGE (r)-[:PRACTICES]->(p)
        SET r.profession = $name
        """, {"rid": resident_id, "pid": pid, "name": name, "cat": category_for(name), "fam": family_for(name)})


def _km_bucket(meters: float) -> str:
    km = max(0.5, round(meters / 500) * 0.5)
    return f"~{km:g} km"


def find_candidates(graph: GraphClient, event_id: str, radius_m: int = SEARCH_RADIUS_M) -> dict:
    """Rank replacement candidates and explain every inclusion/exclusion. Returns eligible + excluded lists."""
    rows = graph.query(Q("replacement_candidates"), {"event_id": event_id, "radius_m": radius_m}, readonly=True)
    eligible, excluded = [], []
    for r in rows:
        who = r["display_name"] or "A local artist (private)"
        base = {"resident_id": r["resident_id"], "name": who, "profession": r["profession"],
                "neighborhood": r["neighborhood"], "distance": _km_bucket(r["distance_m"])}
        if r["clashes"]:
            c = r["clashes"][0]
            excluded.append({**base, "reason": f"already booked at “{c['title']}” during the same time"})
            continue
        score = 0.2
        reasons = ["opted in to fill-in gigs", f"works as {r['profession']}"]
        if r["same_discipline"]:
            score += 0.5
            reasons.append("same discipline as the performer who cancelled")
        elif r["same_family"]:
            score += 0.35
            reasons.append(f"same artistic family ({r['family']}) as the performer who cancelled")
        prox = max(0.0, 1 - r["distance_m"] / radius_m)
        score += 0.3 * prox
        reasons.append(f"lives {_km_bucket(r['distance_m'])} from the venue")
        reasons.append("no overlapping booking (checked via FEATURES edges)")
        eligible.append({**base, "score": round(score, 2), "reasons": reasons})
    eligible.sort(key=lambda c: -c["score"])
    return {"eligible": [c for c in eligible if c["score"] >= MIN_SCORE], "excluded": excluded,
            "query_id": query_id("replacement_candidates")}


def invite(graph: GraphClient, db: Session, event_id: str, candidates: list[dict], action_id: str,
           message: str) -> int:
    """Real side effects: INVITED edges in the graph + in-app notifications to each candidate."""
    sent = 0
    now = now_ms()
    for c in candidates:
        graph.query(
            """
            MATCH (e:Event {event_id:$eid}), (r:Resident {resident_id:$rid})
            MERGE (e)-[i:INVITED]->(r)
            ON CREATE SET i.status = 'pending', i.created_at = $now, i.action_id = $aid, i.score = $score,
                          i.reasons = $reasons
            """, {"eid": event_id, "rid": c["resident_id"], "now": now, "aid": action_id, "score": c.get("score"),
                  "reasons": c.get("reasons", [])})
        sent += notifications.notify(db, [c["resident_id"]], kind="replacement_invite", entity_id=event_id,
                                     message=message, dedupe_key=f"invite:{event_id}:{c['resident_id']}")
    return sent


def _event_row(graph: GraphClient, event_id: str) -> dict | None:
    return graph.one(
        """
        MATCH (e:Event {event_id:$id})
        OPTIONAL MATCH (o:Resident)-[:SUBMITTED]->(e)
        RETURN e.title AS title, e.performer_gap AS gap, o.resident_id AS organizer_id
        """, {"id": event_id}, readonly=True)


def cancel_performance(graph: GraphClient, db: Session, event_id: str, resident_id: str, reason: str) -> dict:
    now = now_ms()
    row = graph.one(
        """
        MATCH (e:Event {event_id:$eid})-[f:FEATURES {status:'confirmed'}]->(r:Resident {resident_id:$rid})
        SET f.status = 'cancelled', f.cancelled_at = $now, f.reason = $reason, e.performer_gap = true,
            e.updated_at = $now
        RETURN e.title AS title, r.name AS name, r.display_name_opt_in AS named, r.profession AS profession
        """, {"eid": event_id, "rid": resident_id, "now": now, "reason": reason})
    if not row:
        raise LookupError("confirmed performance")
    who = row["name"] if row["named"] else "A booked performer"
    graph.query(
        """
        MATCH (e:Event {event_id:$eid})
        CREATE (d:Discussion {discussion_id:$did, body:$body, created_at:$now, visibility:'public',
                              kind:'history', actor:'system'})-[:ABOUT]->(e)
        """, {"eid": event_id, "did": new_id("dis"), "now": now,
              "body": f"{who} ({row['profession'] or 'performer'}) can no longer perform. Reason given: {reason}"})
    audience = notifications.event_audience(graph, event_id)
    notifications.notify(db, audience, kind="performer_cancelled", entity_id=event_id,
                         message=f"“{row['title']}”: {who} has cancelled. CityPulse is looking for a replacement.",
                         dedupe_key=f"cancel:{event_id}:{resident_id}", exclude=resident_id)
    return {"event_id": event_id, "performer": who, "title": row["title"]}


def respond(graph: GraphClient, db: Session, event_id: str, resident_id: str, accept: bool) -> dict:
    """An invited artist says yes/no. Yes closes the loop: they are booked, the gap is filled, participants and the
    organiser are told, the coordination case is resolved and the Memory Agent records what worked."""
    now = now_ms()
    inv = graph.one(
        """
        MATCH (e:Event {event_id:$eid})-[i:INVITED {status:'pending'}]->(r:Resident {resident_id:$rid})
        RETURN i.action_id AS action_id, e.title AS title, r.name AS name, r.display_name_opt_in AS named,
               r.profession AS profession
        """, {"eid": event_id, "rid": resident_id}, readonly=True)
    if not inv:
        raise LookupError("pending invitation")
    who = inv["name"] if inv["named"] else "A local artist"
    if not accept:
        graph.query("MATCH (:Event {event_id:$eid})-[i:INVITED]->(:Resident {resident_id:$rid}) "
                    "SET i.status='declined', i.responded_at=$now", {"eid": event_id, "rid": resident_id, "now": now})
        pending = graph.one("MATCH (:Event {event_id:$eid})-[i:INVITED {status:'pending'}]->() RETURN count(i) AS c",
                            {"eid": event_id}, readonly=True)["c"]
        return {"accepted": False, "pending_left": pending, "who": who}

    graph.query(
        """
        MATCH (e:Event {event_id:$eid})-[i:INVITED {status:'pending'}]->(r:Resident {resident_id:$rid})
        SET i.status = 'accepted', i.responded_at = $now
        MERGE (e)-[f:FEATURES]->(r)
        SET f.status = 'confirmed', f.role = 'replacement', f.confirmed_at = $now
        SET e.performer_gap = false, e.updated_at = $now
        """, {"eid": event_id, "rid": resident_id, "now": now})
    others = graph.query(
        """
        MATCH (:Event {event_id:$eid})-[i:INVITED {status:'pending'}]->(r:Resident)
        SET i.status = 'closed', i.responded_at = $now
        RETURN r.resident_id AS rid
        """, {"eid": event_id, "now": now})
    notifications.notify(db, [o["rid"] for o in others], kind="replacement_filled", entity_id=event_id,
                         message=f"“{inv['title']}” has found its replacement performer. Thank you for being available!",
                         dedupe_key=f"filled:{event_id}:closed")
    graph.query(
        """
        MATCH (e:Event {event_id:$eid})
        CREATE (d:Discussion {discussion_id:$did, body:$body, created_at:$now, visibility:'public',
                              kind:'history', actor:'system'})-[:ABOUT]->(e)
        """, {"eid": event_id, "did": new_id("dis"), "now": now,
              "body": f"{who} ({inv['profession']}) stepped in as the replacement performer."})
    audience = notifications.event_audience(graph, event_id)
    notifications.notify(db, audience, kind="replacement_confirmed", entity_id=event_id,
                         message=f"Good news: {who} ({inv['profession']}) will perform at “{inv['title']}”.",
                         dedupe_key=f"confirmed:{event_id}:{resident_id}", exclude=resident_id)
    _close_case(graph, event_id, inv["action_id"], who, inv["profession"])
    return {"accepted": True, "who": who, "profession": inv["profession"]}


def _close_case(graph: GraphClient, event_id: str, action_id: str | None, who: str, profession: str) -> None:
    """Resolve the coordination case, record the outcome on the invite action and let the Memory Agent learn."""
    from app.agents.memory import write_case_memory

    now = now_ms()
    outcome = f"{who} ({profession}) accepted the invitation and is now booked as the replacement performer."
    case = graph.one(
        """
        MATCH (c:CoordinationCase {case_type:'event_disruption'})-[:ADDRESSES]->(:Event {event_id:$eid})
        WHERE c.status IN ['open', 'in_progress', 'proposed']
        RETURN c.case_id AS id ORDER BY c.created_at DESC LIMIT 1
        """, {"eid": event_id}, readonly=True)
    if not case:
        return
    if action_id:
        graph.query(
            """
            MATCH (a:CoordinationAction {action_id:$aid})
            SET a.status = 'completed', a.outcome = $outcome, a.outcome_success = true, a.outcome_by = 'system',
                a.completed_at = $now
            """, {"aid": action_id, "outcome": outcome, "now": now})
    graph.query("MATCH (c:CoordinationCase {case_id:$id}) SET c.status = 'resolved', c.updated_at = $now",
                {"id": case["id"], "now": now})
    # close complaints attached to the case
    graph.query(
        """
        MATCH (c:CoordinationCase {case_id:$id})-[:ADDRESSES]->(i:Issue)
        WHERE i.status <> 'closed'
        SET i.status = 'closed', i.updated_at = $now
        WITH i
        CREATE (d:Discussion {discussion_id: 'dis_' + i.issue_id + '_closed', body:$body, created_at:$now,
                              visibility:'public', kind:'history', actor:'system'})-[:ABOUT]->(i)
        """, {"id": case["id"], "now": now,
              "body": "Resolved: a replacement performer has been confirmed for the event."})
    write_case_memory(graph, case["id"], trigger_action_id=action_id)
