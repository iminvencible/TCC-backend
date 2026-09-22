from sqlalchemy.orm import Session

from app.models import AuditEvent, User


def record_audit(
    db: Session,
    *,
    actor: User | None,
    action: str,
    target_type: str,
    target_id: int | str,
    details: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_id=actor.id if actor else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        details=details or {},
    )
    db.add(event)
    return event
