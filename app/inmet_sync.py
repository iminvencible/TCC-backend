from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.integrations.inmet import InmetClient, InmetError
from app.models import User, WeatherAlert


def cached_active_inmet_count(db: Session) -> int:
    now = datetime.now(UTC)
    return int(
        db.scalar(
            select(func.count(WeatherAlert.id)).where(
                WeatherAlert.origin == "INMET",
                WeatherAlert.validation_status == "ACTIVE",
                WeatherAlert.issued_at <= now,
                WeatherAlert.valid_until > now,
            )
        )
        or 0
    )


def sync_inmet_warnings(
    db: Session,
    *,
    actor: User | None,
    client: InmetClient | None = None,
) -> tuple[int, int]:
    warnings = (client or InmetClient()).fetch_warnings()
    imported = 0
    skipped = 0
    for warning in warnings:
        replacement_status = (
            "FALSE_ALARM" if warning.message_type == "CANCEL" else "NEEDS_CORRECTION"
        )
        referenced_keys = warning.referenced_source_keys
        if warning.message_type == "CANCEL" and not referenced_keys:
            referenced_keys = (warning.source_key,)

        def supersede_references() -> None:
            for source_key in referenced_keys:
                previous = db.scalar(
                    select(WeatherAlert).where(WeatherAlert.source_key == source_key)
                )
                if previous and previous.validation_status == "ACTIVE":
                    previous.validation_status = replacement_status
                    previous.status_reason = (
                        "Cancelado pelo INMET"
                        if warning.message_type == "CANCEL"
                        else "Substituído por atualização do INMET"
                    )
                    previous.status_changed_by = actor.id if actor else None
                    previous.status_changed_at = datetime.now(UTC)

        if warning.message_type == "CANCEL":
            supersede_references()
            skipped += 1
            continue
        if db.scalar(select(WeatherAlert.id).where(WeatherAlert.source_key == warning.source_key)):
            skipped += 1
            continue
        if not warning.polygon:
            skipped += 1
            continue
        if warning.message_type == "UPDATE":
            supersede_references()
        db.add(
            WeatherAlert(
                source_key=warning.source_key,
                is_demo=False,
                created_by=actor.id if actor else None,
                origin="INMET",
                source_name="Instituto Nacional de Meteorologia (INMET)",
                source_url=warning.source_url,
                validation_status="ACTIVE",
                title=warning.title,
                message=warning.message,
                event_type=warning.event_type,
                severity=warning.severity,
                area_name=warning.area_name,
                polygon=warning.polygon,
                recommendations=warning.recommendations,
                issued_at=warning.issued_at,
                valid_until=warning.valid_until,
            )
        )
        imported += 1
    record_audit(
        db,
        actor=actor,
        action="INMET_WARNINGS_SYNCED",
        target_type="integration",
        target_id="INMET",
        details={"imported": imported, "skipped": skipped},
    )
    db.commit()
    return imported, skipped


__all__ = ["InmetError", "cached_active_inmet_count", "sync_inmet_warnings"]
