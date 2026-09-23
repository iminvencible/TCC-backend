from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.config import Settings
from app.inmet_sync import sync_inmet_warnings
from app.integrations.inmet import InmetClient, InmetError, parse_warning_feed
from app.models import WeatherAlert

from .test_backend_workflow import inmet_xml

SOURCE = "https://apiprevmet3.inmet.gov.br/avisos/rss"


def cap_alert(*, status: str = "Actual", scope: str = "Public") -> str:
    now = datetime.now(UTC)
    return f"""<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
      <identifier>INMET-CAP-1</identifier><status>{status}</status><scope>{scope}</scope>
      <info><event>Tempestade</event><headline>Tempestade na costa</headline>
        <description>Rajadas fortes.</description><severity>Severe</severity>
        <effective>{now.isoformat()}</effective>
        <expires>{(now + timedelta(hours=1)).isoformat()}</expires>
        <area><areaDesc>Litoral</areaDesc>
          <polygon>-24,-47 -24,-46 -25,-46 -24,-47</polygon>
        </area></info>
    </alert>"""


@pytest.mark.parametrize(
    ("status", "scope"),
    [
        ("Test", "Public"),
        ("Exercise", "Public"),
        ("Draft", "Public"),
        ("System", "Public"),
        ("Actual", "Private"),
        ("Actual", "Restricted"),
        (" ", "Public"),
        ("Actual", " "),
    ],
)
def test_non_public_or_non_actual_cap_is_never_published(status, scope):
    alert = cap_alert(status=status, scope=scope)
    assert parse_warning_feed(alert.encode(), source_url=SOURCE) == []
    rss = f"<rss><channel><item>{alert}</item></channel></rss>"
    assert parse_warning_feed(rss.encode(), source_url=SOURCE) == []


def test_standalone_cap_requires_distribution_metadata():
    alert = cap_alert()
    assert parse_warning_feed(alert.encode(), source_url=SOURCE)[0].title == "Tempestade na costa"
    for omitted in ("<status>Actual</status>", "<scope>Public</scope>"):
        assert parse_warning_feed(alert.replace(omitted, "").encode(), source_url=SOURCE) == []


def test_nested_cap_is_one_warning_and_conflicting_status_is_rejected():
    alert = cap_alert()
    rss = f"<rss><channel><item><guid>rss-item</guid>{alert}</item></channel></rss>"
    parsed = parse_warning_feed(rss.encode(), source_url=SOURCE)
    assert len(parsed) == 1
    assert parsed[0].title == "Tempestade na costa"
    conflicting = rss.replace(
        "<status>Actual</status>", "<status>Actual</status><status>Test</status>"
    )
    assert parse_warning_feed(conflicting.encode(), source_url=SOURCE) == []
    missing_scope = rss.replace("<scope>Public</scope>", "")
    assert parse_warning_feed(missing_scope.encode(), source_url=SOURCE) == []


def test_empty_rss_is_valid_but_unrecognized_document_fails():
    assert parse_warning_feed(b"<rss><channel/></rss>", source_url=SOURCE) == []
    assert parse_warning_feed(b"<feed/>", source_url=SOURCE) == []
    with pytest.raises(InmetError):
        parse_warning_feed(b"<other/>", source_url=SOURCE)


def test_non_public_cancel_cannot_change_existing_official_warning(db):
    settings = Settings(inmet_enabled=True)

    def feed(content: bytes) -> InmetClient:
        return InmetClient(
            settings, transport=httpx.MockTransport(lambda _: httpx.Response(200, content=content))
        )

    assert sync_inmet_warnings(db, actor=None, client=feed(inmet_xml())) == (1, 0)
    cancellation = b"""<rss><channel><item>
      <guid>CAP-RESTRICTED-CANCEL</guid><status>Actual</status><scope>Restricted</scope>
      <msgType>Cancel</msgType>
      <references>inmet.gov.br,INMET-AVISO-123,2026-09-21T10:00:00Z</references>
    </item></channel></rss>"""
    assert sync_inmet_warnings(db, actor=None, client=feed(cancellation)) == (0, 0)
    official = db.scalar(select(WeatherAlert).where(WeatherAlert.origin == "INMET"))
    assert official.validation_status == "ACTIVE"
