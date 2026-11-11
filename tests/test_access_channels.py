import pytest

from app.security import create_access_token, decode_access_token
from tests.conftest import csrf_headers
from tests.test_backend_workflow import add_user


@pytest.mark.parametrize("role", ["USER", "ADMIN", "METEOROLOGIST"])
@pytest.mark.parametrize("endpoint", ["login", "login-professional", "login-mobile"])
def test_login_channel_role_matrix(client, db, role, endpoint):
    user = add_user(db, email="channel@example.com", role_code=role, public_code="CHANNEL")
    allowed = (role == "USER") == (endpoint == "login-mobile")
    response = client.post(
        f"/api/v1/auth/{endpoint}", json={"email": user.email, "password": "Senha123!"}
    )
    assert response.status_code == (200 if allowed else 403)
    if not allowed:
        assert "prevclima_access" not in client.cookies
        return
    payload = decode_access_token(client.cookies.get("prevclima_access"))
    assert payload["aud"] == ("prevclima-mobile" if role == "USER" else "prevclima-web")
    assert client.get("/api/v1/auth/mobile-session").status_code == (200 if role == "USER" else 403)
    assert client.get("/api/v1/auth/professional-session").status_code == (
        403 if role == "USER" else 200
    )


@pytest.mark.parametrize("role", ["USER", "ADMIN", "METEOROLOGIST"])
def test_legacy_or_wrong_audience_token_cannot_bypass_role_split(client, db, role):
    user = add_user(db, email="legacy@example.com", role_code=role, public_code="LEGACY")
    audience = "prevclima-web" if role == "USER" else "prevclima-mobile"
    token = create_access_token(user.id, user.token_version, audience=audience)
    # Both accepted token transport mechanisms must enforce the audience/role pair.
    for cookie in [True, False]:
        client.cookies.clear()
        if cookie:
            client.cookies.set("prevclima_access", token)
        headers = {} if cookie else {"Authorization": f"Bearer {token}"}
        assert client.get("/api/v1/users/me", headers=headers).status_code == 401
        assert client.get("/api/v1/dashboard", headers=headers).status_code == 401
        assert client.get("/api/v1/auth/professional-session", headers=headers).status_code == 401
        assert client.get("/api/v1/auth/mobile-session", headers=headers).status_code == 403


def test_mobile_user_can_use_user_apis_but_not_professional_apis(registered_client):
    client = registered_client
    mobile_page = client.get("/mobile/inicio.html", follow_redirects=False)
    assert mobile_page.status_code == 200
    assert mobile_page.headers["cache-control"] == "private, no-store"
    for path in ["users/me", "auth/mobile-session", "home", "map-data", "alerts", "notifications"]:
        assert client.get(f"/api/v1/{path}").status_code == 200
    assert (
        client.patch(
            "/api/v1/users/me", json={"city": "Santos", "state": "SP"}, headers=csrf_headers(client)
        ).status_code
        == 200
    )
    for path in ["dashboard", "admin/users", "reports/review-queue", "alerts/review-queue"]:
        assert client.get(f"/api/v1/{path}").status_code == 403
    for path in ["alerts", "severe-forecasts", "stations/sync-catalog"]:
        assert (
            client.post(f"/api/v1/{path}", json={}, headers=csrf_headers(client)).status_code == 403
        )


@pytest.mark.parametrize("path", ["/mapa.html", "/mapa.html/", "/MAPA.HTML", "/x/%2e%2e/mapa.html"])
def test_website_html_cannot_be_read_by_mobile_session(registered_client, path):
    response = registered_client.get(path, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/meteorologista.html"


@pytest.mark.parametrize("role", ["ADMIN", "METEOROLOGIST"])
def test_professional_can_open_website_but_not_mobile_content(client, db, role):
    user = add_user(db, email="pages@example.com", role_code=role, public_code="PAGES")
    client.post(
        "/api/v1/auth/login-professional", json={"email": user.email, "password": "Senha123!"}
    )
    assert client.get("/mapa.html", follow_redirects=False).status_code == 200
    response = client.get("/mobile/inicio.html", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/mobile/index.html"


def test_anonymous_login_recovery_assets_and_mobile_entry_stay_public(client):
    for path in ["/", "/meteorologista.html", "/conta.html", "/mobile/", "/assets/js/api.js"]:
        assert client.get(path, follow_redirects=False).status_code == 200
    for path in ["/inicio.html", "/mapa.html", "/alertas.html", "/perfil.html", "/admin.html"]:
        assert client.get(path, follow_redirects=False).status_code == 303
    assert client.get("/mobile/inicio.html", follow_redirects=False).status_code == 303
    assert (
        client.get("/cadastro.html", follow_redirects=False).headers["location"]
        == "/mobile/#cadastro"
    )
