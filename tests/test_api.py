from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select

from app.models import AlertRead, Forecast, Role, User, WeatherReport
from app.routers.weather import point_in_polygon
from app.schemas import AlertCreateRequest
from app.security import hash_password
from tests.conftest import csrf_headers


def test_health_and_static_page(client: TestClient):
    assert client.get("/api/health").json() == {"status": "ok"}
    page = client.get("/")
    assert page.status_code == 200
    assert "PrevClima" in page.text
    for path in (
        "/localizacao.html",
        "/mapa.html",
        "/informacoes.html",
        "/relato.html",
    ):
        assert client.get(path).status_code == 200


def test_register_login_and_profile(client: TestClient):
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Maria Teste",
            "email": "Maria@Example.com",
            "password": "Senha123!",
            "city": "Mongagua",
            "state": "sp",
        },
    )
    assert registration.status_code == 201
    body = registration.json()
    assert body["user"]["email"] == "maria@example.com"
    assert body["user"]["role"] == "USER"
    assert body["user"]["state"] == "SP"
    assert "prevclima_access" in client.cookies

    assert client.post("/api/v1/auth/logout").status_code == 403
    assert client.post("/api/v1/auth/logout", headers=csrf_headers(client)).status_code == 200
    assert client.get("/api/v1/users/me").status_code == 401

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "MARIA@example.com", "password": "Senha123!"},
    )
    assert login.status_code == 200
    profile = client.get("/api/v1/users/me")
    assert profile.status_code == 200
    assert profile.json()["name"] == "Maria Teste"


def test_registration_rejects_weak_and_duplicate_password(client: TestClient):
    weak = client.post(
        "/api/v1/auth/register",
        json={"name": "Weak User", "email": "weak@example.com", "password": "password"},
    )
    assert weak.status_code == 422

    payload = {"name": "First User", "email": "same@example.com", "password": "Senha123!"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    duplicate = client.post(
        "/api/v1/auth/register",
        json={**payload, "email": "SAME@example.com"},
    )
    assert duplicate.status_code == 409

    role_spoof = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Role Spoof",
            "email": "spoof@example.com",
            "password": "Senha123!",
            "role": "OWNER",
        },
    )
    assert role_spoof.status_code == 422


def test_password_is_hashed(client: TestClient, db):
    client.post(
        "/api/v1/auth/register",
        json={"name": "Hash Test", "email": "hash@example.com", "password": "Senha123!"},
    )
    user = db.scalar(select(User).where(User.email == "hash@example.com"))
    assert user.password_hash != "Senha123!"
    assert user.password_hash.startswith("$argon2")


def test_profile_update_requires_csrf(registered_client: TestClient):
    denied = registered_client.patch("/api/v1/users/me", json={"city": "Santos", "state": "SP"})
    assert denied.status_code == 403

    updated = registered_client.patch(
        "/api/v1/users/me",
        json={"city": "Santos", "state": "sp", "weather_notifications": False},
        headers=csrf_headers(registered_client),
    )
    assert updated.status_code == 200
    assert updated.json()["city"] == "Santos"
    assert updated.json()["state"] == "SP"
    assert updated.json()["weather_notifications"] is False

    for invalid in (
        {"weather_notifications": None},
        {"latitude": None, "longitude": 1},
        {"city": "Santos"},
    ):
        response = registered_client.patch(
            "/api/v1/users/me", json=invalid, headers=csrf_headers(registered_client)
        )
        assert response.status_code == 422


def test_city_change_clears_stale_coordinates(registered_client: TestClient):
    headers = csrf_headers(registered_client)
    positioned = registered_client.patch(
        "/api/v1/users/me",
        json={"latitude": -24.1, "longitude": -46.62},
        headers=headers,
    )
    assert positioned.status_code == 200
    changed = registered_client.patch(
        "/api/v1/users/me",
        json={"city": "Santos", "state": "SP"},
        headers=headers,
    )
    assert changed.status_code == 200
    assert changed.json()["latitude"] is None
    assert changed.json()["longitude"] is None


def test_public_home_and_alerts_use_database(client: TestClient):
    home = client.get("/api/v1/home?city=Mongagua&state=SP")
    assert home.status_code == 200
    assert home.json()["forecast"]["source_name"] == "TEST DATA"
    assert home.json()["forecast"]["issued_at"].endswith("Z")
    assert home.json()["unread_alert_count"] == 1

    alerts = client.get("/api/v1/alerts")
    assert alerts.status_code == 200
    assert alerts.json()[0]["title"] == "Tempestade severa"
    assert alerts.json()[0]["is_demo"] is True


def test_map_data_exposes_active_geometry(client: TestClient):
    response = client.get("/api/v1/map-data")
    assert response.status_code == 200
    body = response.json()
    assert body["generated_at"].endswith("Z")
    assert body["alerts"][0]["radius_km"] == "30.00"
    assert body["alerts"][0]["is_demo"] is True
    assert body["forecast_areas"][0]["polygon"]["type"] == "Polygon"


def test_scheduled_forecast_is_not_exposed(client: TestClient, db):
    now = datetime.now(UTC)
    db.add(
        Forecast(
            source_key="TEST-FUTURE-FORECAST",
            city="Mongagua",
            state="SP",
            condition="Previsao futura",
            temperature_c=Decimal("31"),
            minimum_c=Decimal("25"),
            maximum_c=Decimal("33"),
            humidity=50,
            wind_kmh=Decimal("10"),
            rain_probability=20,
            severity="MODERATE",
            polygon={
                "type": "Polygon",
                "coordinates": [[[-47, -25], [-46, -25], [-46, -23], [-47, -23], [-47, -25]]],
            },
            source_name="SCHEDULED TEST DATA",
            issued_at=now + timedelta(hours=1),
            valid_until=now + timedelta(hours=3),
        )
    )
    db.commit()
    assert client.get("/api/v1/home").json()["forecast"]["source_name"] == "TEST DATA"
    assert client.get("/api/v1/forecasts/current").json()["source_name"] == "TEST DATA"
    sources = [
        item["source_name"] for item in client.get("/api/v1/map-data").json()["forecast_areas"]
    ]
    assert "SCHEDULED TEST DATA" not in sources


def test_education_hides_scheduled_content(client: TestClient):
    response = client.get("/api/v1/education")
    assert response.status_code == 200
    assert [item["title"] for item in response.json()] == ["Seguranca em tempestades"]


def test_report_submission_is_authenticated_owned_and_validated(
    client: TestClient, registered_client: TestClient, db
):
    payload = {
        "description": "Granizo observado perto da avenida principal.",
        "occurred_at": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
        "latitude": -24.1,
        "longitude": -46.62,
        "image_url": "https://example.com/granizo.jpg",
    }
    with TestClient(client.app) as anonymous:
        assert anonymous.post("/api/v1/reports", json=payload).status_code == 401
    assert registered_client.post("/api/v1/reports", json=payload).status_code == 403
    created = registered_client.post(
        "/api/v1/reports", json=payload, headers=csrf_headers(registered_client)
    )
    assert created.status_code == 201
    assert created.json()["status"] == "PENDING"
    own = registered_client.get("/api/v1/reports/me")
    assert own.status_code == 200
    assert [item["id"] for item in own.json()] == [created.json()["id"]]
    report = db.get(WeatherReport, created.json()["id"])
    user = db.scalar(select(User).where(User.email == "maria@example.com"))
    assert report.reporter_id == user.id

    future = registered_client.post(
        "/api/v1/reports",
        json={**payload, "occurred_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()},
        headers=csrf_headers(registered_client),
    )
    assert future.status_code == 422
    unsafe_url = registered_client.post(
        "/api/v1/reports",
        json={**payload, "image_url": "javascript:alert(1)"},
        headers=csrf_headers(registered_client),
    )
    assert unsafe_url.status_code == 422
    blank_description = registered_client.post(
        "/api/v1/reports",
        json={**payload, "description": "          "},
        headers=csrf_headers(registered_client),
    )
    assert blank_description.status_code == 422


def test_alert_polygon_validation_rejects_malformed_geometry():
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        AlertCreateRequest(
            title="Poligono invalido",
            message="Esta geometria nao possui um anel fechado.",
            event_type="HEAVY_RAIN",
            severity="HIGH",
            area_name="Area de teste",
            polygon={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]},
            recommendations=["Procure abrigo"],
            issued_at=now,
            valid_until=now + timedelta(hours=1),
        )


def test_mark_alert_read_is_idempotent(registered_client: TestClient, db):
    alert_id = registered_client.get("/api/v1/alerts").json()[0]["id"]
    headers = csrf_headers(registered_client)
    assert (
        registered_client.post(f"/api/v1/alerts/{alert_id}/read", headers=headers).status_code
        == 200
    )
    assert (
        registered_client.post(f"/api/v1/alerts/{alert_id}/read", headers=headers).status_code
        == 200
    )
    assert db.scalar(select(func.count(AlertRead.id))) == 1
    assert registered_client.get("/api/v1/alerts").json()[0]["is_read"] is True


def test_alerts_are_filtered_by_authenticated_location(registered_client: TestClient):
    headers = csrf_headers(registered_client)
    response = registered_client.patch(
        "/api/v1/users/me",
        json={"latitude": 0, "longitude": 0},
        headers=headers,
    )
    assert response.status_code == 200
    assert registered_client.get("/api/v1/alerts").json() == []
    home = registered_client.get("/api/v1/home").json()
    assert home["unread_alert_count"] == 0
    assert home["forecast"] is None


def test_professional_login_rejects_regular_user(registered_client: TestClient):
    response = registered_client.post(
        "/api/v1/auth/login-professional",
        json={"email": "maria@example.com", "password": "Senha123!"},
    )
    assert response.status_code == 403


def test_professional_accounts_cannot_be_self_created(client: TestClient):
    response = client.post(
        "/api/v1/auth/register-meteorologist",
        json={
            "name": "Attacker",
            "email": "attacker@example.com",
            "password": "Senha123!",
            "access_code": "PREV-ADMIN",
        },
    )
    assert response.status_code in {404, 405}


def test_polygon_targeting_includes_boundary_and_excludes_holes():
    polygon = {
        "type": "Polygon",
        "coordinates": [
            [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
            [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]],
        ],
    }
    assert point_in_polygon(2, 2, polygon)
    assert point_in_polygon(0, 5, polygon)
    assert not point_in_polygon(5, 5, polygon)
    assert point_in_polygon(4, 5, polygon)
    assert not point_in_polygon(12, 5, polygon)


def test_only_owner_can_create_professional_accounts(registered_client: TestClient, db):
    payload = {
        "name": "Meteorologista Teste",
        "email": "meteo@example.com",
        "password": "Meteo123!",
        "role": "METEOROLOGIST",
        "city": "Santos",
        "state": "SP",
    }
    denied = registered_client.post(
        "/api/v1/admin/users", json=payload, headers=csrf_headers(registered_client)
    )
    assert denied.status_code == 403

    owner_role = db.scalar(select(Role).where(Role.code == "OWNER"))
    db.add(
        User(
            public_code="TEST-OWNER",
            name="Owner Test",
            email="owner-test@example.com",
            password_hash=hash_password("Owner123!"),
            role_id=owner_role.id,
        )
    )
    db.commit()
    registered_client.cookies.clear()
    login = registered_client.post(
        "/api/v1/auth/login",
        json={"email": "owner-test@example.com", "password": "Owner123!"},
    )
    assert login.status_code == 200
    created = registered_client.post(
        "/api/v1/admin/users", json=payload, headers=csrf_headers(registered_client)
    )
    assert created.status_code == 201
    assert created.json()["role"] == "METEOROLOGIST"

    registered_client.cookies.clear()
    professional_login = registered_client.post(
        "/api/v1/auth/login-professional",
        json={"email": "meteo@example.com", "password": "Meteo123!"},
    )
    assert professional_login.status_code == 200
    now = datetime.now(UTC)
    alert = registered_client.post(
        "/api/v1/alerts",
        headers=csrf_headers(registered_client),
        json={
            "title": "Alerta profissional",
            "message": "Mensagem validada pelo meteorologista.",
            "event_type": "HEAVY_RAIN",
            "severity": "HIGH",
            "area_name": "Santos",
            "latitude": -23.96,
            "longitude": -46.33,
            "radius_km": 20,
            "recommendations": ["Evite areas alagadas"],
            "issued_at": now.isoformat(),
            "valid_until": (now + timedelta(hours=2)).isoformat(),
        },
    )
    assert alert.status_code == 201
    assert alert.json()["is_demo"] is False
