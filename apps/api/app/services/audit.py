from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditLog


def record(db: Session, actor_type: str, actor_id: str, action: str, target_id: str | None = None,
           **detail) -> None:
    db.add(AuditLog(actor_type=actor_type, actor_id=actor_id, action=action, target_id=target_id, detail=detail))
    db.commit()


def recent(db: Session, limit: int = 100) -> list[dict]:
    rows = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return [{"actor_type": a.actor_type, "actor_id": a.actor_id, "action": a.action, "target_id": a.target_id,
             "detail": a.detail, "created_at": a.created_at.isoformat()} for a in rows]
