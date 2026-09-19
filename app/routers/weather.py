from datetime import UTC, datetime
from math import asin, cos, radians, sin, sqrt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, desc, func, select
from sqlalchemy.exc import IntegrityError

from app.dependencies import CurrentUser, DbSession, optional_current_user, require_roles
from app.models import AlertRead, Forecast, User, WeatherAlert
from app.schemas import (
    AlertCreateRequest,
    AlertOut,
    ForecastOut,
    HomeOut,
    MapAlertOut,
    MapDataOut,
    MapForecastOut,
    MessageOut,
)

router = APIRouter(tags=["weather"])


def now_utc() -> datetime:
    return datetime.now(UTC)


def alert_out(alert: WeatherAlert, read_ids: set[int] | None = None) -> AlertOut:
    return AlertOut(
        id=alert.id,
        title=alert.title,
        message=alert.message,
        event_type=alert.event_type,
        severity=alert.severity,
        area_name=alert.area_name,
        recommendations=alert.recommendations,
        is_demo=alert.is_demo,
        issued_at=alert.issued_at,
        valid_until=alert.valid_until,
        is_read=bool(read_ids and alert.id in read_ids),
    )


def active_alerts(db: DbSession) -> list[WeatherAlert]:
    return list(
        db.scalars(
            select(WeatherAlert)
            .where(and_(WeatherAlert.issued_at <= now_utc(), WeatherAlert.valid_until > now_utc()))
            .order_by(desc(WeatherAlert.issued_at))
        )
    )


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(radians, (lat1, lon1, lat2, lon2))
    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad
    value = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    return 6371.0088 * 2 * asin(sqrt(value))


def ring_state(longitude: float, latitude: float, ring: list[list[float]]) -> int:
    inside = False
    for index in range(len(ring) - 1):
        x1, y1 = ring[index][:2]
        x2, y2 = ring[index + 1][:2]
        cross = (longitude - x1) * (y2 - y1) - (latitude - y1) * (x2 - x1)
        if (
            abs(cross) <= 1e-9
            and min(x1, x2) - 1e-9 <= longitude <= max(x1, x2) + 1e-9
            and min(y1, y2) - 1e-9 <= latitude <= max(y1, y2) + 1e-9
        ):
            return 2
        if (y1 > latitude) != (y2 > latitude):
            intersection = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
            if longitude < intersection:
                inside = not inside
    return 1 if inside else 0


def point_in_polygon(longitude: float, latitude: float, geometry: dict) -> bool:
    if geometry.get("type") != "Polygon":
        return False
    rings = geometry.get("coordinates")
    if not isinstance(rings, list) or not rings or len(rings[0]) < 4:
        return False
    outer = ring_state(longitude, latitude, rings[0])
    if outer == 0:
        return False
    if outer == 2:
        return True
    for hole in rings[1:]:
        state = ring_state(longitude, latitude, hole)
        if state == 2:
            return True
        if state == 1:
            return False
    return True


def alerts_for_location(
    alerts: list[WeatherAlert], latitude: float | None, longitude: float | None
) -> list[WeatherAlert]:
    if latitude is None or longitude is None:
        return alerts
    selected = []
    for alert in alerts:
        if alert.polygon:
            if point_in_polygon(longitude, latitude, alert.polygon):
                selected.append(alert)
            continue
        if alert.latitude is None or alert.longitude is None or alert.radius_km is None:
            selected.append(alert)
            continue
        if distance_km(latitude, longitude, float(alert.latitude), float(alert.longitude)) <= float(
            alert.radius_km
        ):
            selected.append(alert)
    return selected


def user_read_ids(db: DbSession, user: User | None, alert_ids: list[int]) -> set[int]:
    if not user or not alert_ids:
        return set()
    return set(
        db.scalars(
            select(AlertRead.alert_id).where(
                AlertRead.user_id == user.id, AlertRead.alert_id.in_(alert_ids)
            )
        )
    )


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(
    db: DbSession,
    user: Annotated[User | None, Depends(optional_current_user)],
    active: bool = Query(default=True),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
):
    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=422, detail="latitude and longitude must be supplied together"
        )
    query = select(WeatherAlert)
    if active:
        query = query.where(
            WeatherAlert.issued_at <= now_utc(), WeatherAlert.valid_until > now_utc()
        )
    alerts = list(db.scalars(query.order_by(desc(WeatherAlert.issued_at))))
    if user and latitude is None and user.latitude is not None and user.longitude is not None:
        latitude, longitude = float(user.latitude), float(user.longitude)
    alerts = alerts_for_location(alerts, latitude, longitude)
    read_ids = user_read_ids(db, user, [alert.id for alert in alerts])
    return [alert_out(alert, read_ids) for alert in alerts]


@router.post("/alerts", response_model=AlertOut, status_code=status.HTTP_201_CREATED)
def create_alert(
    payload: AlertCreateRequest,
    db: DbSession,
    user: Annotated[User, Depends(require_roles("METEOROLOGIST", "OWNER"))],
):
    alert = WeatherAlert(
        created_by=user.id,
        title=payload.title,
        message=payload.message,
        event_type=payload.event_type,
        severity=payload.severity,
        area_name=payload.area_name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        radius_km=payload.radius_km,
        polygon=payload.polygon,
        recommendations=payload.recommendations,
        issued_at=payload.issued_at,
        valid_until=payload.valid_until,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert_out(alert)


@router.post("/alerts/{alert_id}/read", response_model=MessageOut)
def mark_alert_read(alert_id: int, user: CurrentUser, db: DbSession):
    if not db.get(WeatherAlert, alert_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    exists = db.scalar(
        select(AlertRead.id).where(AlertRead.user_id == user.id, AlertRead.alert_id == alert_id)
    )
    if not exists:
        db.add(AlertRead(user_id=user.id, alert_id=alert_id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return MessageOut(message="Alert marked as read")


@router.get("/forecasts/current", response_model=ForecastOut)
def current_forecast(
    db: DbSession,
    city: str = Query(default="Mongagua", min_length=2, max_length=100),
    state: str = Query(default="SP", min_length=2, max_length=2),
):
    forecast = db.scalar(
        select(Forecast)
        .where(
            func.lower(Forecast.city) == city.strip().lower(),
            Forecast.state == state.upper(),
            Forecast.issued_at <= now_utc(),
            Forecast.valid_until > now_utc(),
        )
        .order_by(desc(Forecast.issued_at))
    )
    if not forecast:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No current forecast")
    return forecast


@router.get("/home", response_model=HomeOut)
def home(
    db: DbSession,
    user: Annotated[User | None, Depends(optional_current_user)],
    city: str = Query(default="Mongagua", min_length=2, max_length=100),
    state: str = Query(default="SP", min_length=2, max_length=2),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
):
    if (latitude is None) != (longitude is None):
        raise HTTPException(
            status_code=422, detail="latitude and longitude must be supplied together"
        )
    if user and user.city and user.state:
        city, state = user.city, user.state
    if user and latitude is None and user.latitude is not None and user.longitude is not None:
        latitude, longitude = float(user.latitude), float(user.longitude)
    forecast = None
    if latitude is not None and longitude is not None:
        area_forecasts = db.scalars(
            select(Forecast)
            .where(
                Forecast.issued_at <= now_utc(),
                Forecast.valid_until > now_utc(),
                Forecast.polygon.is_not(None),
            )
            .order_by(desc(Forecast.issued_at))
        )
        forecast = next(
            (
                item
                for item in area_forecasts
                if item.polygon and point_in_polygon(longitude, latitude, item.polygon)
            ),
            None,
        )
    if not forecast and (latitude is None or longitude is None):
        forecast = db.scalar(
            select(Forecast)
            .where(
                func.lower(Forecast.city) == city.strip().lower(),
                Forecast.state == state.upper(),
                Forecast.issued_at <= now_utc(),
                Forecast.valid_until > now_utc(),
            )
            .order_by(desc(Forecast.issued_at))
        )
    alerts = alerts_for_location(active_alerts(db), latitude, longitude)
    read_ids = user_read_ids(db, user, [alert.id for alert in alerts])
    rendered = [alert_out(alert, read_ids) for alert in alerts]
    return HomeOut(
        forecast=forecast,
        active_alerts=rendered,
        unread_alert_count=(
            sum(1 for alert in rendered if not alert.is_read)
            if not user or user.weather_notifications
            else 0
        ),
    )


@router.get("/map-data", response_model=MapDataOut)
def map_data(db: DbSession):
    alerts = [
        MapAlertOut(
            id=alert.id,
            title=alert.title,
            event_type=alert.event_type,
            severity=alert.severity,
            area_name=alert.area_name,
            latitude=alert.latitude,
            longitude=alert.longitude,
            radius_km=alert.radius_km,
            polygon=alert.polygon,
            is_demo=alert.is_demo,
            issued_at=alert.issued_at,
            valid_until=alert.valid_until,
        )
        for alert in active_alerts(db)
    ]
    forecasts = db.scalars(
        select(Forecast)
        .where(
            Forecast.issued_at <= now_utc(),
            Forecast.valid_until > now_utc(),
            Forecast.polygon.is_not(None),
        )
        .order_by(desc(Forecast.issued_at))
    )
    forecast_areas = [
        MapForecastOut(
            id=forecast.id,
            city=forecast.city,
            state=forecast.state,
            severity=forecast.severity,
            polygon=forecast.polygon,
            source_name=forecast.source_name,
            valid_until=forecast.valid_until,
        )
        for forecast in forecasts
        if forecast.polygon
    ]
    return MapDataOut(alerts=alerts, forecast_areas=forecast_areas, generated_at=now_utc())
