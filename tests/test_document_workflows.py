from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.email_auth import aware, send_code
from app.models import EmailChallenge, SevereForecast, User
from app.schemas import RegisterRequest
from tests.conftest import csrf_headers, verify_and_login
from tests.test_backend_workflow import add_user

EMAIL = "novo@exemplo.com"
PASSWORD = "Abcde!"
POLYGON = {"type": "Polygon", "coordinates": [[[-47, -25], [-45, -25], [-45, -23], [-47, -25]]]}


def signup(client):
    return client.post(
        "/api/v1/auth/register", json={"name": "Novo Usuário", "email": EMAIL, "password": PASSWORD}
    )


def professional(client, db, role="METEOROLOGIST"):
    user = add_user(db, email="prof@exemplo.com", role_code=role, public_code="PROF-TEST")
    assert (
        client.post(
            "/api/v1/auth/login-professional", json={"email": user.email, "password": "Senha123!"}
        ).status_code
        == 200
    )
    return user


def forecast_payload():
    now = datetime.now(UTC)
    return {
        "area_name": "Baixada Santista",
        "severity": "HIGH",
        "description": "Possibilidade de tempestades severas.",
        "polygon": POLYGON,
        "issued_at": now.isoformat(),
        "valid_until": (now + timedelta(hours=6)).isoformat(),
    }


@pytest.mark.parametrize("password", ["ABCDE!", "Abcde!", "A!!!!1"])
def test_document_password_accepts_six_characters(password):
    assert RegisterRequest(name="Teste", email=EMAIL, password=password).password == password


@pytest.mark.parametrize("password", ["Abcd!", "abcdef!", "Abcdef", "Abcde "])
def test_document_password_rejects_missing_requirement(password):
    with pytest.raises(ValueError):
        RegisterRequest(name="Teste", email=EMAIL, password=password)


def test_verification_required_all_login_routes(client, mail_outbox, db):
    assert signup(client).status_code == 201
    assert not client.cookies.get("prevclima_access")
    for path in ["login", "login-mobile", "login-professional"]:
        assert (
            client.post(
                f"/api/v1/auth/{path}", json={"email": EMAIL, "password": PASSWORD}
            ).status_code
            == 403
        )
    challenge = db.scalar(select(EmailChallenge))
    assert challenge.token_hash != mail_outbox[-1][2]
    assert aware(challenge.expires_at) > datetime.now(UTC) + timedelta(hours=23)
    verify_and_login(client, mail_outbox, EMAIL, PASSWORD)
    response = client.post(
        "/api/v1/auth/verify-email",
        json={"email": EMAIL, "code": mail_outbox[-1][2]},
        headers=csrf_headers(client),
    )
    assert response.status_code == 400


def test_resend_invalidates_old_code_and_expired_code_fails(client, mail_outbox, db):
    signup(client)
    old = mail_outbox[-1][2]
    assert client.post("/api/v1/auth/resend-verification", json={"email": EMAIL}).status_code == 200
    new = mail_outbox[-1][2]
    if old != new:
        assert (
            client.post("/api/v1/auth/verify-email", json={"email": EMAIL, "code": old}).status_code
            == 400
        )
    challenge = db.scalar(select(EmailChallenge))
    challenge.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    assert (
        client.post("/api/v1/auth/verify-email", json={"email": EMAIL, "code": new}).status_code
        == 400
    )


def test_challenge_locks_after_five_failures(client, mail_outbox):
    signup(client)
    code = mail_outbox[-1][2]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert (
            client.post(
                "/api/v1/auth/verify-email", json={"email": EMAIL, "code": wrong}
            ).status_code
            == 400
        )
    assert (
        client.post("/api/v1/auth/verify-email", json={"email": EMAIL, "code": code}).status_code
        == 400
    )


def test_email_requests_are_limited_and_unknown_reset_is_generic(client):
    for _ in range(10):
        response = client.post("/api/v1/auth/forgot-password", json={"email": EMAIL})
        assert response.status_code == 200
    assert client.post("/api/v1/auth/forgot-password", json={"email": EMAIL}).status_code == 429


def test_smtp_failure_leaves_recoverable_pending_account(client, monkeypatch, db, mail_outbox):
    from app import email_auth

    deliver = email_auth.send_code

    def unavailable(*args):
        raise HTTPException(503, "SMTP indisponível")

    monkeypatch.setattr(email_auth, "send_code", unavailable)
    assert signup(client).status_code == 503
    assert db.scalar(select(User).where(User.email == EMAIL)).email_verified_at is None
    monkeypatch.setattr(email_auth, "send_code", deliver)
    assert client.post("/api/v1/auth/resend-verification", json={"email": EMAIL}).status_code == 200
    verify_and_login(client, mail_outbox, EMAIL, PASSWORD)


def test_password_reset_expires_and_revokes_sessions(client, db, mail_outbox):
    signup(client)
    verify_and_login(client, mail_outbox, EMAIL, PASSWORD)
    old_cookie = client.cookies.get("prevclima_access")
    headers = csrf_headers(client)
    assert (
        client.post(
            "/api/v1/auth/forgot-password", json={"email": EMAIL}, headers=headers
        ).status_code
        == 200
    )
    code = mail_outbox[-1][2]
    challenge = db.scalar(select(EmailChallenge).where(EmailChallenge.purpose == "reset"))
    assert (
        datetime.now(UTC) + timedelta(minutes=14)
        < aware(challenge.expires_at)
        < datetime.now(UTC) + timedelta(minutes=16)
    )
    payload = {"email": EMAIL, "code": code, "password": "NovaS!"}
    assert (
        client.post("/api/v1/auth/reset-password", json=payload, headers=headers).status_code == 200
    )
    assert client.get("/api/v1/users/me").status_code == 401
    assert (
        client.post("/api/v1/auth/reset-password", json=payload, headers=headers).status_code == 400
    )
    assert (
        client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code
        == 401
    )
    assert (
        client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "NovaS!"}).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {old_cookie}"}
        ).status_code
        == 401
    )


@pytest.mark.parametrize("role", ["METEOROLOGIST", "ADMIN"])
def test_professionals_publish_and_owner_inherits(client, db, role):
    professional(client, db, role)
    payload = forecast_payload()
    result = client.post("/api/v1/severe-forecasts", json=payload, headers=csrf_headers(client))
    assert result.status_code == 201, result.text
    record = result.json()
    assert record["description"] == payload["description"]
    assert record["id"] in [
        r["id"] for r in client.get("/api/v1/map-data").json()["severe_forecast_areas"]
    ]
    edited = client.patch(
        f"/api/v1/severe-forecasts/{record['id']}",
        json={**payload, "description": "Descrição corrigida da previsão."},
        headers=csrf_headers(client),
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["published_at"] == record["published_at"]
    assert (
        client.delete(
            f"/api/v1/severe-forecasts/{record['id']}", headers=csrf_headers(client)
        ).status_code
        == 200
    )


@pytest.mark.parametrize("seconds,expected", [(1799, 200), (1800, 409), (1801, 409)])
@pytest.mark.parametrize("operation", ["patch", "delete"])
def test_editing_deadline_enforced_atomically(
    client, db, monkeypatch, seconds, expected, operation
):
    from app.routers import severe_forecasts

    professional(client, db)
    payload = forecast_payload()
    record = client.post(
        "/api/v1/severe-forecasts", json=payload, headers=csrf_headers(client)
    ).json()
    item = db.get(SevereForecast, record["id"])
    instant = aware(item.published_at) + timedelta(seconds=seconds)
    monkeypatch.setattr(severe_forecasts, "now_utc", lambda: instant)
    kwargs = {"headers": csrf_headers(client)}
    if operation == "patch":
        kwargs["json"] = payload
    result = getattr(client, operation)(f"/api/v1/severe-forecasts/{record['id']}", **kwargs)
    assert result.status_code == expected, result.text


def test_regular_user_cannot_publish_or_manage(registered_client):
    c = registered_client
    assert (
        c.post(
            "/api/v1/severe-forecasts", json=forecast_payload(), headers=csrf_headers(c)
        ).status_code
        == 403
    )
    assert c.get("/api/v1/admin/users").status_code == 403


def test_meteorologist_manages_peers_but_cannot_modify_owner_or_self(client, db):
    professional_user = professional(client, db)
    owner = add_user(db, email="owner@exemplo.com", role_code="ADMIN", public_code="OWNER-TEST")
    h = csrf_headers(client)
    created = client.post(
        "/api/v1/admin/users",
        headers=h,
        json={
            "name": "Nova Profissional",
            "email": "newprof@exemplo.com",
            "password": "Abcde!",
            "role": "METEOROLOGIST",
        },
    )
    assert created.status_code == 201
    peer_id = created.json()["id"]
    assert (
        client.patch(
            f"/api/v1/admin/users/{peer_id}/role", headers=h, json={"role": "USER"}
        ).status_code
        == 200
    )
    assert client.delete(f"/api/v1/admin/users/{peer_id}", headers=h).status_code == 200
    for user in [owner, professional_user]:
        assert client.delete(f"/api/v1/admin/users/{user.id}", headers=h).status_code == 409
        assert (
            client.patch(
                f"/api/v1/admin/users/{user.id}/role", headers=h, json={"role": "USER"}
            ).status_code
            == 409
        )


def test_alert_types_instructions_and_immutability(client, db):
    professional(client, db)
    payload = {
        "title": "Tempestade severa",
        "message": "Risco de ventos fortes.",
        "event_type": "SEVERE_STORM",
        "severity": "HIGH",
        "area_name": "Litoral",
        "polygon": POLYGON,
        "valid_until": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    result = client.post("/api/v1/alerts", json=payload, headers=csrf_headers(client))
    assert result.status_code == 201
    assert result.json()["recommendations"]
    alert_id = result.json()["id"]
    for method in [client.patch, client.delete]:
        assert method(f"/api/v1/alerts/{alert_id}", headers=csrf_headers(client)).status_code == 405
    assert (
        client.post(
            "/api/v1/alerts",
            json={**payload, "event_type": "HEAVY_RAIN"},
            headers=csrf_headers(client),
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/severe-forecasts",
            json={**forecast_payload(), "polygon": {"type": "Point", "coordinates": [0, 0]}},
            headers=csrf_headers(client),
        ).status_code
        == 422
    )


def test_notifications_require_location_and_preferences(registered_client, db):
    user = db.scalar(select(User).where(User.email == "maria@exemplo.com"))
    user.city = None
    user.state = None
    db.commit()
    assert registered_client.get("/api/v1/notifications").json() == []
    user.latitude = -24.1008
    user.longitude = -46.6200
    db.commit()
    rows = registered_client.get("/api/v1/notifications").json()
    assert len(rows) == 1
    user.weather_notifications = False
    db.commit()
    assert registered_client.get("/api/v1/notifications").json() == []
    user.weather_notifications = True
    db.commit()
    registered_client.post(
        f"/api/v1/alerts/{rows[0]['id']}/read", headers=csrf_headers(registered_client)
    )
    assert registered_client.get("/api/v1/notifications").json() == []


def test_education_is_available_without_demo_data(db):
    from app.education_seed import ensure_education
    from app.models import EducationalContent

    ensure_education(db)
    db.commit()
    ensure_education(db)
    db.commit()
    rows = list(
        db.scalars(select(EducationalContent).where(EducationalContent.source_key.like("EDU-%")))
    )
    assert len(rows) == 5
    assert all(row.media_url.startswith("/assets/img/safety-") for row in rows)


def test_zero_area_polygon_rejected(client, db):
    professional(client, db)
    payload = forecast_payload()
    payload["polygon"] = {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [2, 2], [0, 0]]]}
    assert (
        client.post(
            "/api/v1/severe-forecasts", json=payload, headers=csrf_headers(client)
        ).status_code
        == 422
    )


@pytest.mark.parametrize("security", ["starttls", "ssl"])
def test_email_transport_uses_tls_and_explicit_message(monkeypatch, security):
    import ssl

    from app import email_auth
    from app.config import get_settings

    settings = get_settings()
    for key, value in {
        "smtp_host": "smtp.example.com",
        "smtp_from": "sender@example.com",
        "smtp_security": security,
        "smtp_username": "sender",
        "smtp_password": "test-only",
    }.items():
        monkeypatch.setattr(settings, key, value)
    calls = {}

    class Transport:
        def __init__(self, host, port, **kwargs):
            calls["connection"] = (host, port, kwargs)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self, context):
            calls["tls"] = context

        def login(self, username, password):
            calls["login"] = (username, password)

        def send_message(self, message):
            calls["message"] = message

    monkeypatch.setattr(email_auth.smtplib, "SMTP", Transport)
    monkeypatch.setattr(email_auth.smtplib, "SMTP_SSL", Transport)
    send_code(EMAIL, "reset", "123456")
    context = calls["tls"] if security == "starttls" else calls["connection"][2]["context"]
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname
    assert calls["message"]["To"] == EMAIL
    assert "123456" in calls["message"].get_content()
    assert "15 minutos" in calls["message"].get_content()
