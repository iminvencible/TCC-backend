"""The live INMET RSS links CAP documents; its summary is not an alert contract."""

import httpx
import pytest
from sqlalchemy import select

from app.config import Settings, get_settings
from app.inmet_sync import sync_inmet_warnings
from app.integrations.inmet import InmetClient, InmetError
from app.models import WeatherAlert

from .test_inmet_cap_safety import cap_alert

SOURCE = "https://apiprevmet3.inmet.gov.br/avisos/rss"
DETAIL = SOURCE + "/56193"


def index(link=DETAIL):
    # Structure observed in the official feed on 2026-10-26: no CAP fields inline.
    return f"""<rss><channel><item>
      <title>Aviso de Tempestade. Severidade Grau: Perigo Potencial</title>
      <link>{link}</link><guid>{link}</guid>
      <description><![CDATA[<table><tr><th>Status</th><td>Alert</td></tr>
      <tr><th>Severidade</th><td>Perigo Potencial</td></tr></table>]]></description>
    </item></channel></rss>""".encode()


def provider(detail, *, rss=None):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(
            200, content=(rss or index()) if str(request.url) == SOURCE else detail
        )

    return InmetClient(Settings(inmet_enabled=True), transport=httpx.MockTransport(handler)), calls


def test_rss_follows_cap_to_import_real_geometry_and_timezone(client, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "inmet_enabled", True)
    detail = (
        cap_alert()
        .replace("<description>", "<web>https://avisos.inmet.gov.br/56193</web><description>")
        .encode()
    )
    feed, calls = provider(detail)
    assert sync_inmet_warnings(db, actor=None, client=feed) == (1, 0)
    assert calls == [SOURCE, DETAIL]
    data = client.get("/api/v1/map-data").json()
    official = next(item for item in data["alerts"] if item["origin"] == "INMET")
    assert official["polygon"]["coordinates"][0][0] == [-47, -24]
    assert official["source_url"] == "https://avisos.inmet.gov.br/56193"
    assert official["issued_at"].endswith("Z")
    assert sync_inmet_warnings(db, actor=None, client=feed) == (0, 1)


def test_rss_alert_summary_cannot_override_cap_cancellation(db):
    feed, _ = provider(cap_alert().encode())
    assert sync_inmet_warnings(db, actor=None, client=feed) == (1, 0)
    # This mismatch was observed in the live feed: RSS says Alert; detail says Cancel.
    cancel = (
        cap_alert()
        .replace("INMET-CAP-1", "INMET-CAP-CANCEL")
        .replace(
            "<info>",
            "<msgType>Cancel</msgType><references>inmet.gov.br,INMET-CAP-1,2026-10-26T00:00:00Z</references><info>",
        )
        .encode()
    )
    feed, _ = provider(cancel)
    assert sync_inmet_warnings(db, actor=None, client=feed) == (0, 1)
    official = db.scalar(select(WeatherAlert).where(WeatherAlert.origin == "INMET"))
    assert official.validation_status == "FALSE_ALARM"


@pytest.mark.parametrize("status,scope", [("Test", "Public"), ("Actual", "Private")])
def test_linked_cap_distribution_restrictions_are_preserved(status, scope):
    feed, _ = provider(cap_alert(status=status, scope=scope).encode())
    assert feed.fetch_warnings() == []


@pytest.mark.parametrize(
    "link",
    [
        "https://evil.example/avisos/rss/1",
        "http://apiprevmet3.inmet.gov.br/avisos/rss/1",
        "https://apiprevmet3.inmet.gov.br/other",
        "https://user@apiprevmet3.inmet.gov.br/avisos/rss/1",
        "https://apiprevmet3.inmet.gov.br:8443/avisos/rss/1",
    ],
)
def test_rss_cannot_make_arbitrary_outbound_requests(link):
    feed, calls = provider(cap_alert().encode(), rss=index(link))
    with pytest.raises(InmetError):
        feed.fetch_warnings()
    assert calls == [SOURCE]


def test_detail_failure_never_imports_unverified_rss_summary(db):
    def handler(request):
        if str(request.url) == SOURCE:
            return httpx.Response(200, content=index())
        return httpx.Response(503)

    feed = InmetClient(Settings(inmet_enabled=True), transport=httpx.MockTransport(handler))
    with pytest.raises(InmetError):
        sync_inmet_warnings(db, actor=None, client=feed)
    assert db.scalar(select(WeatherAlert).where(WeatherAlert.origin == "INMET")) is None


def test_non_cap_detail_and_excessive_documents_are_rejected():
    feed, _ = provider(b"<html><body>No alert</body></html>")
    with pytest.raises(InmetError):
        feed.fetch_warnings()
    rss = (
        "<rss><channel>"
        + "".join(f"<item><link>{SOURCE}/{n}</link></item>" for n in range(101))
        + "</channel></rss>"
    ).encode()
    feed, calls = provider(cap_alert().encode(), rss=rss)
    with pytest.raises(InmetError):
        feed.fetch_warnings()
    assert calls == [SOURCE]
