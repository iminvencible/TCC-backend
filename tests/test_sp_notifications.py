from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.geography import point_in_sao_paulo, sao_paulo_geometry
from app.models import User, WeatherAlert


@pytest.mark.parametrize(
    "longitude,latitude,expected",
    [
        (-46.6333, -23.5505, True),  # São Paulo capital
        (-47.06, -22.91, True),  # Campinas
        (-45.36, -23.78, True),  # Ilhabela (separate polygon)
        (-46.56, -21.79, False),  # Poços de Caldas: inside SP bbox, but in MG
        (-49.27, -25.43, False),  # Curitiba
        (-46.62, -24.1008, False),  # Offshore is not silently assigned to SP
    ],
)
def test_state_boundary_is_not_a_bounding_rectangle(longitude, latitude, expected):
    assert point_in_sao_paulo(longitude, latitude) is expected


def test_state_boundary_point_is_included():
    longitude, latitude = sao_paulo_geometry()["coordinates"][0][0][0]
    assert point_in_sao_paulo(longitude, latitude)


def add_warning(db, key, polygon=None, **kwargs):
    now = datetime.now(UTC)
    alert = WeatherAlert(
        source_key=key,
        origin="INMET",
        title=key,
        message="Aviso de teste",
        event_type="SEVERE_STORM",
        severity="HIGH",
        area_name="São Paulo",  # A label alone must never imply geographic coverage.
        polygon=polygon,
        issued_at=now - timedelta(minutes=1),
        valid_until=now + timedelta(hours=1),
        recommendations=[],
        **kwargs,
    )
    db.add(alert)
    db.commit()
    return alert


def rectangle(west, south, east, north):
    return {
        "type": "Polygon",
        "coordinates": [[[west, south], [east, south], [east, north],
                         [west, north], [west, south]]],
    }


def position_user(db, longitude, latitude):
    user = db.scalar(select(User).where(User.email == "maria@exemplo.com"))
    user.longitude, user.latitude = longitude, latitude
    db.commit()
    return user


def test_only_warning_covering_sp_recipient_is_delivered(registered_client, db):
    position_user(db, -46.6333, -23.5505)
    local = add_warning(db, "LOCAL", rectangle(-46.8, -23.7, -46.4, -23.4))
    add_warning(db, "REMOTE", rectangle(-48, -23, -47, -22))
    add_warning(db, "UNKNOWN")
    response = registered_client.get("/api/v1/notifications")
    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [local.id]


def test_warning_covering_other_state_cannot_notify_sp_labelled_user(registered_client, db):
    # User's stored state says SP; actual resolved coordinate takes precedence.
    position_user(db, -46.56, -21.79)
    add_warning(db, "MG", rectangle(-46.8, -22, -46.3, -21.5))
    assert registered_client.get("/api/v1/notifications").json() == []


def test_cross_border_warning_can_notify_inside_sp(registered_client, db):
    position_user(db, -46.6333, -23.5505)
    spanning = add_warning(db, "CROSS-BORDER", rectangle(-50, -25, -43, -20))
    assert [row["id"] for row in registered_client.get("/api/v1/notifications").json()] == [
        spanning.id
    ]


def test_radius_warning_uses_affected_area_not_center_state(registered_client, db):
    position_user(db, -46.6333, -23.5505)
    # Circle centered in MG still covers the recipient in SP.
    alert = add_warning(db, "RADIUS", latitude=-21.79, longitude=-46.56, radius_km=300)
    assert [row["id"] for row in registered_client.get("/api/v1/notifications").json()] == [
        alert.id
    ]


def test_geocoded_out_of_state_location_is_suppressed(registered_client, db, monkeypatch):
    from types import SimpleNamespace

    from app.routers import weather

    position_user(db, None, None)
    monkeypatch.setattr(
        weather, "get_open_meteo_or_fallback",
        lambda *args, **kwargs: (SimpleNamespace(latitude=-21.79, longitude=-46.56), False),
    )
    add_warning(db, "MG-GEOCODED", rectangle(-46.8, -22, -46.3, -21.5))
    assert registered_client.get("/api/v1/notifications").json() == []
