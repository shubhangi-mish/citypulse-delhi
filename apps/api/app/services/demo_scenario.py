"""Guided demo scenario: "the headliner cancels".

SYNTHETIC DATA, clearly flagged: every node created here carries `demo = true`, the people are fictional personas
(email domain `demo.citypulse.invalid`), the events say "(demo scenario)" in their title, and `remove()` deletes
everything it created. It exists to demonstrate, with real graph writes and real agent actions, how connections
between people, professions, complaints, events and solutions play out. Hackathon rule 6 permits synthetic data.

Cast (neighbourhoods are real OpenStreetMap places already in the graph):
  Aarav Malhotra   indie singer-songwriter      Hauz Khas        headliner (will cancel)
  Naina Sethi      Hindustani classical vocalist Saket           available, same discipline, 3-4 km away
  Ishita Rao       live sketch artist / painter  Defence Colony  available, different discipline, ~5 km
  Kabir Anand      stand-up comedian             Lajpat Nagar    open to gigs but double-booked that evening
  Meher Chawla     community librarian           Chittaranjan Park  organiser, authorised agent autopilot
  Rohan Verma      software engineer             Green Park      attending, files the complaint
  Dr. Tanvi Bhatia paediatrician                 Karol Bagh      attending as a volunteer
"""

import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Notification
from app.graph.client import GraphClient
from app.graph.model import now_ms
from app.services import events as ev_svc
from app.services import issues as issue_svc
from app.services import notifications, residents, talent

IST = timezone(timedelta(hours=5, minutes=30))

PERSONAS = [
    dict(key="aarav", name="Aarav Malhotra", profession="Indie singer-songwriter", nbh="Hauz Khas", gigs=False),
    dict(key="naina", name="Naina Sethi", profession="Hindustani classical vocalist", nbh="Saket", gigs=True),
    dict(key="ishita", name="Ishita Rao", profession="Live sketch artist and painter", nbh="Defence Colony", gigs=True),
    dict(key="kabir", name="Kabir Anand", profession="Stand-up comedian", nbh="Lajpat Nagar", gigs=True),
    dict(key="meher", name="Meher Chawla", profession="Community librarian", nbh="Chittaranjan Park", gigs=False),
    dict(key="rohan", name="Rohan Verma", profession="Software engineer", nbh="Green Park", gigs=False),
    dict(key="tanvi", name="Dr. Tanvi Bhatia", profession="Paediatrician", nbh="Karol Bagh", gigs=False),
]
DEMO_NOTE = " This is a synthetic demo scenario created to demonstrate CityPulse; people and details are fictional."


def _nbh(graph: GraphClient, name: str) -> dict:
    row = graph.one("MATCH (n:Neighborhood {name:$n}) RETURN n.neighborhood_id AS id, n.latitude AS lat, "
                    "n.longitude AS lng LIMIT 1", {"n": name}, readonly=True)
    if not row:
        raise LookupError(f"neighbourhood {name} (load OpenStreetMap data first)")
    return row


def _persona_ids(graph: GraphClient) -> dict[str, str]:
    rows = graph.query("MATCH (r:Resident {demo:true}) RETURN r.demo_key AS k, r.resident_id AS id", readonly=True)
    return {r["k"]: r["id"] for r in rows}


def _main_event(graph: GraphClient) -> dict | None:
    return graph.one("MATCH (e:Event {demo_key:'main'}) RETURN e.event_id AS id", readonly=True)


def seed(graph: GraphClient) -> dict:
    ids = _persona_ids(graph)
    for p in PERSONAS:
        if p["key"] in ids:
            continue
        n = _nbh(graph, p["nbh"])
        created = residents.create(
            graph, name=p["name"], email=f"{p['key']}@demo.citypulse.invalid", address=f"{p['nbh']}, New Delhi (demo persona)",
            latitude=round(n["lat"] + 0.002, 5), longitude=round(n["lng"] + 0.002, 5), neighborhood_id=n["id"])
        rid = created["resident_id"]
        graph.query(
            """
            MATCH (r:Resident {resident_id:$id})
            SET r.demo = true, r.demo_key = $key, r.public_visibility = 'public', r.display_name_opt_in = true,
                r.discovery_opt_in = true, r.open_to_gigs = $gigs
            """, {"id": rid, "key": p["key"], "gigs": p["gigs"]})
        talent.set_profession(graph, rid, p["profession"])
        ids[p["key"]] = rid

    if not _main_event(graph):
        hk = _nbh(graph, "Hauz Khas")
        start_dt = (datetime.now(IST) + timedelta(days=3)).replace(hour=18, minute=30, second=0, microsecond=0)
        start = int(start_dt.timestamp() * 1000)
        main = ev_svc.create(
            graph, ids["meher"], title="Sunset Music Evening — Hauz Khas (demo scenario)",
            description="An open-air neighbourhood music evening to raise funds for a community library, headlined by a "
                        "local singer-songwriter." + DEMO_NOTE,
            category="concert", start_time=start, end_time=start + 3 * 3600_000, venue_name="Community courtyard, Hauz Khas",
            venue_address="Hauz Khas, New Delhi (demo)", latitude=hk["lat"], longitude=hk["lng"],
            organizer_name="Meher Chawla (demo persona)", organizer_contact="demo@demo.citypulse.invalid",
            organization_name=None, is_free=True, setting="outdoor", accessibility=None, registration_url=None,
            attestation=True)["event_id"]
        graph.query(
            """
            MATCH (e:Event {event_id:$eid})
            SET e.demo = true, e.demo_key = 'main', e.agent_autopilot = true, e.performer_gap = false
            WITH e MATCH (e)-[:HOSTED_AT]->(v:Venue) SET v.demo = true
            """, {"eid": main})
        graph.query(
            """
            MATCH (e:Event {event_id:$eid}), (a:Resident {resident_id:$aid})
            MERGE (e)-[f:FEATURES]->(a) SET f.status = 'confirmed', f.role = 'headliner', f.confirmed_at = $now
            """, {"eid": main, "aid": ids["aarav"], "now": now_ms()})
        ev_svc.participate(graph, main, ids["rohan"], "going")
        ev_svc.participate(graph, main, ids["tanvi"], "volunteer")

        lp = _nbh(graph, "Lajpat Nagar")
        clash = ev_svc.create(
            graph, ids["kabir"], title="Comedy Open Mic — Lajpat Nagar (demo scenario)",
            description="A weekly open-mic comedy night hosted by Kabir." + DEMO_NOTE, category="concert",
            start_time=start + 30 * 60_000, end_time=start + 150 * 60_000, venue_name="Cafe stage, Lajpat Nagar",
            venue_address="Lajpat Nagar, New Delhi (demo)", latitude=lp["lat"], longitude=lp["lng"],
            organizer_name="Kabir Anand (demo persona)", organizer_contact="demo@demo.citypulse.invalid",
            organization_name=None, is_free=False, setting="indoor", accessibility=None, registration_url=None,
            attestation=True)["event_id"]
        graph.query(
            """
            MATCH (e:Event {event_id:$eid}), (k:Resident {resident_id:$kid})
            SET e.demo = true, e.demo_key = 'clash'
            WITH e, k MATCH (e)-[:HOSTED_AT]->(v:Venue) SET v.demo = true
            WITH e, k
            MERGE (e)-[f:FEATURES]->(k) SET f.status = 'confirmed', f.role = 'headliner', f.confirmed_at = $now
            """, {"eid": clash, "kid": ids["kabir"], "now": now_ms()})
    return {"personas": len(ids), "event_id": _main_event(graph)["id"]}


def remove(graph: GraphClient, db: Session) -> dict:
    ids = list(_persona_ids(graph).values())
    graph.query("MATCH (d:Discussion)-[:ABOUT]->(x) WHERE x.demo = true DETACH DELETE d")
    graph.query("MATCH (m:AgentMemory)-[:SUMMARIZES]->(c:CoordinationCase) WHERE c.demo = true DETACH DELETE m")
    graph.query("MATCH (n) WHERE n.demo = true DETACH DELETE n")
    graph.query("MATCH (p:Profession) WHERE NOT ()-[:PRACTICES]->(p) DETACH DELETE p")
    graph.query("MATCH (rd:Road) WHERE rd.created_at IS NOT NULL AND NOT ()-[:ON_ROAD|ACCESSIBLE_VIA]->(rd) DETACH DELETE rd")
    if ids:
        db.execute(delete(Notification).where(Notification.resident_id.in_(ids)))
        db.commit()
    return {"removed_personas": len(ids)}


def cancel_main(graph: GraphClient, db: Session, reason: str = "Family emergency — can't make it, sorry!") -> dict:
    from app.agents import event_workflow

    ids, main = _persona_ids(graph), _main_event(graph)
    if not ids or not main:
        raise LookupError("scenario not seeded")
    talent.cancel_performance(graph, db, main["id"], ids["aarav"], reason)
    return event_workflow.handle_disruption(graph, db, main["id"])


def file_complaint(graph: GraphClient) -> dict:
    ids, main = _persona_ids(graph), _main_event(graph)
    if not ids or not main:
        raise LookupError("scenario not seeded")
    existing = graph.one("MATCH (i:Issue {demo:true}) RETURN i.issue_id AS id LIMIT 1", readonly=True)
    if existing:
        return {"issue_id": existing["id"], "already": True}
    e = graph.one("MATCH (e:Event {event_id:$id}) RETURN e.public_lat AS lat, e.public_lng AS lng", {"id": main["id"]},
                  readonly=True)
    created = issue_svc.create(
        graph, ids["rohan"], category="other", title="Headliner cancelled for Saturday's Sunset Music Evening",
        description="The booked singer has pulled out of the Hauz Khas music evening. Many of us were coming for the "
                    "performance and the library fundraiser depends on it. Can someone help find a replacement?"
                    + DEMO_NOTE,
        latitude=e["lat"], longitude=e["lng"], precision="approximate", anonymous=False)
    iid = created["issue_id"]
    now = now_ms()
    graph.query(
        """
        MATCH (i:Issue {issue_id:$iid}), (e:Event {event_id:$eid})
        SET i.demo = true
        MERGE (i)-[:ABOUT_EVENT {created_at:$now}]->(e)
        WITH i, e
        OPTIONAL MATCH (c:CoordinationCase {case_type:'event_disruption'})-[:ADDRESSES]->(e)
        WHERE c.status IN ['proposed', 'open', 'in_progress']
        FOREACH (_ IN CASE WHEN c IS NULL THEN [] ELSE [1] END |
            MERGE (c)-[:ADDRESSES {created_at:$now}]->(i)
            SET i.status = 'coordination_in_progress')
        """, {"iid": iid, "eid": main["id"], "now": now})
    attached = graph.one("MATCH (:CoordinationCase)-[:ADDRESSES]->(:Issue {issue_id:$id}) RETURN count(*) AS c",
                         {"id": iid}, readonly=True)["c"]
    issue_svc.record_history(graph, iid, "Linked to the event it is about"
                             + ("; a coordination case is already finding a replacement performer." if attached else "."),
                             "system")
    return {"issue_id": iid, "linked_to_case": bool(attached)}


def respond_as(graph: GraphClient, db: Session, key: str, accept: bool) -> dict:
    ids, main = _persona_ids(graph), _main_event(graph)
    if key not in ids or not main:
        raise LookupError("persona")
    return talent.respond(graph, db, main["id"], ids[key], accept)


def state(graph: GraphClient, db: Session) -> dict:
    ids = _persona_ids(graph)
    if not ids:
        return {"seeded": False, "personas": [], "steps": {}, "event": None, "decisions": [], "case": None,
                "complaint": None, "memory": []}
    main = _main_event(graph)
    eid = main["id"] if main else None
    people = graph.query(
        """
        MATCH (r:Resident {demo:true})
        OPTIONAL MATCH (r)-[:LIVES_IN]->(n:Neighborhood)
        OPTIONAL MATCH (r)-[:PRACTICES]->(p:Profession)
        RETURN r.resident_id AS resident_id, r.demo_key AS key, r.name AS name, r.profession AS profession,
               p.category AS category, r.open_to_gigs AS open_to_gigs, n.name AS neighborhood
        """, readonly=True)
    order = {p["key"]: i for i, p in enumerate(PERSONAS)}
    people.sort(key=lambda p: order.get(p["key"], 99))
    inbox_rows = db.scalars(select(Notification).where(Notification.resident_id.in_(list(ids.values())))
                            .order_by(Notification.created_at.desc())).all()
    inbox: dict[str, list] = {}
    for n in inbox_rows:
        inbox.setdefault(n.resident_id, []).append({"kind": n.kind, "message": n.message, "at": n.created_at.isoformat()})
    for p in people:
        p["inbox"] = inbox.get(p["resident_id"], [])[:4]
        p["unread"] = len(inbox.get(p["resident_id"], []))
    event = None
    if eid:
        event = ev_svc.detail(graph, eid, None)
        event["invites"] = graph.query(
            """
            MATCH (:Event {event_id:$id})-[i:INVITED]->(r:Resident)
            RETURN r.demo_key AS key, r.name AS name, r.profession AS profession, i.status AS status, i.score AS score,
                   i.reasons AS reasons
            ORDER BY i.score DESC
            """, {"id": eid}, readonly=True)
    runs = graph.query(
        """
        MATCH (d:AgentDecision {demo:true})
        RETURN d.decision_id AS decision_id, d.agent_name AS agent_name, d.decision_type AS decision_type,
               d.rationale AS rationale, d.review_status AS review_status, d.created_at AS created_at, d.run_id AS run_id
        ORDER BY d.created_at DESC, d.decision_type ASC LIMIT 16
        """, readonly=True)
    case = graph.one(
        """
        MATCH (c:CoordinationCase {demo:true})
        RETURN c.case_id AS case_id, c.title AS title, c.status AS status
        ORDER BY c.created_at DESC LIMIT 1
        """, readonly=True)
    complaint = graph.one("MATCH (i:Issue {demo:true}) RETURN i.issue_id AS issue_id, i.title AS title, i.status AS status",
                          readonly=True)
    memory = graph.query("MATCH (m:AgentMemory)-[:SUMMARIZES]->(c:CoordinationCase {demo:true}) "
                         "RETURN m.memory_id AS memory_id, m.summary AS summary ORDER BY m.created_at DESC", readonly=True)
    cancelled = bool(event and any(p["status"] == "cancelled" for p in event["performers"]))
    resolved = bool(event and any(p["status"] == "confirmed" and p["role"] == "replacement" for p in event["performers"]))
    return {
        "seeded": True, "personas": people, "event": event, "decisions": runs, "case": case, "complaint": complaint,
        "memory": memory, "steps": {"seeded": True, "cancelled": cancelled, "agents_acted": bool(case),
                                    "complaint": bool(complaint), "resolved": resolved},
    }
