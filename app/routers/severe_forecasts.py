from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select, update

from app.audit import record_audit
from app.dependencies import DbSession, require_roles
from app.email_auth import aware
from app.models import SevereForecast, User
from app.schemas import MessageOut, SevereForecastOut, SevereForecastRequest

router = APIRouter(prefix="/severe-forecasts", tags=["previsões de tempo severo"])
Professional = Annotated[User, Depends(require_roles("METEOROLOGIST"))]


def now_utc():
    return datetime.now(UTC)


def forecast_out(item: SevereForecast) -> SevereForecastOut:
    return SevereForecastOut(
        id=item.id,
        created_by=item.created_by,
        area_name=item.area_name,
        severity=item.severity,
        description=item.description,
        polygon=item.polygon,
        issued_at=aware(item.issued_at),
        valid_until=aware(item.valid_until),
        published_at=aware(item.published_at),
        editable_until=aware(item.published_at) + timedelta(minutes=30),
    )


@router.get("", response_model=list[SevereForecastOut])
def list_forecasts(db: DbSession, limit: int = Query(100, ge=1, le=200)):
    rows = db.scalars(
        select(SevereForecast)
        .where(SevereForecast.issued_at <= now_utc(), SevereForecast.valid_until > now_utc())
        .order_by(SevereForecast.published_at.desc())
        .limit(limit)
    )
    return [forecast_out(item) for item in rows]


@router.post("", response_model=SevereForecastOut, status_code=201)
def create_forecast(payload: SevereForecastRequest, db: DbSession, user: Professional):
    item = SevereForecast(**payload.model_dump(), created_by=user.id, published_at=now_utc())
    db.add(item)
    db.flush()
    record_audit(
        db,
        actor=user,
        action="SEVERE_FORECAST_CREATED",
        target_type="severe_forecast",
        target_id=item.id,
    )
    db.commit()
    return forecast_out(item)


def editable(db: DbSession, forecast_id: int):
    item = db.get(SevereForecast, forecast_id)
    if not item:
        raise HTTPException(404, "Previsão não encontrada")
    if now_utc() >= aware(item.published_at) + timedelta(minutes=30):
        raise HTTPException(
            409,
            "Já se passaram 30 minutos desde a publicação. A previsão não pode mais ser alterada.",
        )
    return item


@router.patch("/{forecast_id}", response_model=SevereForecastOut)
def update_forecast(
    forecast_id: int, payload: SevereForecastRequest, db: DbSession, user: Professional
):
    item = editable(db, forecast_id)
    result = db.execute(
        update(SevereForecast)
        .execution_options(synchronize_session=False)
        .where(
            SevereForecast.id == forecast_id,
            SevereForecast.published_at > now_utc() - timedelta(minutes=30),
        )
        .values(**payload.model_dump())
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "O prazo de edição terminou. Atualize a página.")
    record_audit(
        db,
        actor=user,
        action="SEVERE_FORECAST_UPDATED",
        target_type="severe_forecast",
        target_id=item.id,
    )
    db.commit()
    db.refresh(item)
    return forecast_out(item)


@router.delete("/{forecast_id}", response_model=MessageOut)
def delete_forecast(forecast_id: int, db: DbSession, user: Professional):
    item = editable(db, forecast_id)
    record_audit(
        db,
        actor=user,
        action="SEVERE_FORECAST_DELETED",
        target_type="severe_forecast",
        target_id=item.id,
    )
    result = db.execute(
        delete(SevereForecast)
        .execution_options(synchronize_session=False)
        .where(
            SevereForecast.id == forecast_id,
            SevereForecast.published_at > now_utc() - timedelta(minutes=30),
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "O prazo de exclusão terminou. Atualize a página.")
    db.commit()
    return MessageOut(message="Previsão excluída")
