"""In-app notifications (PostgreSQL). Recipients are resolved through the graph; delivery is stored here and
deduplicated with (resident_id, dedupe_key). No email/SMS is sent."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Notification, utcnow
from app.graph.client import GraphClient


def notify(db: Session, resident_ids: list[str], *, kind: str, entity_id: str, message: str, dedupe_key: str,
           exclude: str | None = None) -> int:
    sent = 0
    for rid in set(resident_ids) - {exclude}:
        if not rid:
            continue
        db.add(Notification(resident_id=rid, kind=kind, entity_id=entity_id, message=message,
                            dedupe_key=dedupe_key))
        try:
            db.commit()
            sent += 1
        except IntegrityError:
            db.rollback()
    return sent


def issue_audience(graph: GraphClient, issue_id: str) -> list[str]:
    rows = graph.query(
        """
        MATCH (i:Issue {issue_id:$id})<-[:REPORTED|FOLLOWS]-(r:Resident)
        RETURN DISTINCT r.resident_id AS rid
        """, {"id": issue_id}, readonly=True)
    return [r["rid"] for r in rows]


def event_audience(graph: GraphClient, event_id: str) -> list[str]:
    rows = graph.query(
        """
        MATCH (e:Event {event_id:$id})<-[:PARTICIPATES_IN|SUBMITTED]-(r:Resident)
        RETURN DISTINCT r.resident_id AS rid
        """, {"id": event_id}, readonly=True)
    return [r["rid"] for r in rows]


def list_for(db: Session, resident_id: str, limit: int = 50) -> list[dict]:
    rows = db.scalars(select(Notification).where(Notification.resident_id == resident_id)
                      .order_by(Notification.created_at.desc()).limit(limit)).all()
    return [{"id": n.id, "kind": n.kind, "entity_id": n.entity_id, "message": n.message,
             "created_at": n.created_at.isoformat(), "read": n.read_at is not None} for n in rows]


def mark_read(db: Session, resident_id: str) -> None:
    for n in db.scalars(select(Notification).where(Notification.resident_id == resident_id,
                                                   Notification.read_at.is_(None))):
        n.read_at = utcnow()
    db.commit()
