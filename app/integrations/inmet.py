from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from app.config import Settings, get_settings


class InmetError(RuntimeError):
    pass


@dataclass(frozen=True)
class NormalizedWarning:
    source_key: str
    title: str
    message: str
    event_type: str
    severity: str
    area_name: str
    polygon: dict | None
    recommendations: list[str]
    issued_at: datetime
    valid_until: datetime
    source_url: str
    message_type: str
    referenced_source_keys: tuple[str, ...]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _first_text(node, *names: str) -> str | None:
    for name in names:
        wanted = name.lower()
        for child in node.iter():
            if _local_name(child.tag) == wanted and child.text and child.text.strip():
                return child.text.strip()
    return None


def _field_values(node, name: str) -> list[str]:
    """Include nested CAP metadata; reject ambiguous/conflicting distribution tags."""
    return [
        (child.text or "").strip().casefold()
        for child in node.iter()
        if _local_name(child.tag) == name
    ]


def _feed_entries(root) -> list:
    """An RSS item wrapping a CAP alert is one warning, not two."""
    entries = []
    pending = [(root, False)]
    while pending:
        node, inside_entry = pending.pop()
        candidate = _local_name(node.tag) in {"item", "entry", "alert"}
        if candidate and not inside_entry:
            entries.append(node)
        pending.extend((child, inside_entry or candidate) for child in reversed(list(node)))
    return entries


def _parse_datetime(value: str | None, default: datetime) -> datetime:
    if not value:
        return default
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError) as error:
            raise InmetError("Data inválida recebida do INMET") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_polygon(value: str | None) -> dict | None:
    if not value:
        return None
    points: list[list[float]] = []
    try:
        for pair in value.split():
            latitude_text, longitude_text = pair.split(",", 1)
            latitude, longitude = float(latitude_text), float(longitude_text)
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                raise ValueError
            points.append([longitude, latitude])
    except ValueError as error:
        raise InmetError("Polígono inválido recebido do INMET") from error
    if len(points) < 3:
        return None
    if points[0] != points[-1]:
        points.append(points[0])
    return {"type": "Polygon", "coordinates": [points]}


def _severity(value: str | None) -> str | None:
    return {
        "minor": "LOW",
        "moderate": "MODERATE",
        "severe": "HIGH",
        "extreme": "CRITICAL",
    }.get((value or "").strip().lower())


def _source_key(identifier: str) -> str:
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:32].upper()
    return f"INMET-{digest}"


def _reference_keys(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    keys: list[str] = []
    for reference in value.split():
        parts = reference.split(",")
        if len(parts) >= 2 and parts[1].strip():
            keys.append(_source_key(parts[1].strip()))
    return tuple(dict.fromkeys(keys))


def parse_warning_feed(
    xml: bytes, *, source_url: str, now: datetime | None = None
) -> list[NormalizedWarning]:
    reference_time = now or datetime.now(UTC)
    try:
        root = ElementTree.fromstring(xml)
    except (ElementTree.ParseError, DefusedXmlException) as error:
        raise InmetError("O INMET retornou XML inválido") from error
    entries = _feed_entries(root)
    warnings: list[NormalizedWarning] = []
    excluded = 0
    for entry in entries:
        # CAP marks test/exercise/draft messages and limited-audience messages.
        # Legacy RSS items without these CAP fields remain supported, but when
        # either field is present, every value must explicitly permit publishing.
        statuses = _field_values(entry, "status")
        scopes = _field_values(entry, "scope")
        cap_alerts = [node for node in entry.iter() if _local_name(node.tag) == "alert"]
        if (
            any(
                not _field_values(alert, "status") or not _field_values(alert, "scope")
                for alert in cap_alerts
            )
            or any(value != "actual" for value in statuses)
            or any(value != "public" for value in scopes)
        ):
            excluded += 1
            continue
        identifier = _first_text(entry, "identifier", "guid", "id")
        if not identifier:
            continue
        message_type = (_first_text(entry, "msgtype") or "Alert").strip().upper()
        if message_type not in {"ALERT", "UPDATE", "CANCEL"}:
            continue
        referenced_source_keys = _reference_keys(_first_text(entry, "references"))
        if message_type == "CANCEL":
            if not referenced_source_keys:
                continue
            warnings.append(
                NormalizedWarning(
                    source_key=_source_key(identifier),
                    title="Cancelamento de aviso do INMET",
                    message="O INMET cancelou um aviso emitido anteriormente.",
                    event_type=(_first_text(entry, "event") or "AVISO_INMET")[:40],
                    severity=_severity(_first_text(entry, "severity")) or "MODERATE",
                    area_name=(_first_text(entry, "areadesc") or "Área informada pelo INMET")[:160],
                    polygon=None,
                    recommendations=["Consulte o cancelamento no aviso oficial do INMET"],
                    issued_at=reference_time,
                    valid_until=reference_time + timedelta(seconds=1),
                    source_url=source_url,
                    message_type=message_type,
                    referenced_source_keys=referenced_source_keys,
                )
            )
            continue
        title = _first_text(entry, "headline", "title", "event")
        message = _first_text(entry, "description", "summary", "event")
        if not title or not message:
            continue
        issued_text = _first_text(entry, "effective", "onset", "sent", "pubdate", "updated")
        expires_text = _first_text(entry, "expires")
        severity = _severity(_first_text(entry, "severity"))
        if not issued_text or not expires_text or not severity:
            continue
        issued_at = _parse_datetime(issued_text, reference_time)
        valid_until = _parse_datetime(expires_text, issued_at + timedelta(hours=24))
        if valid_until <= issued_at:
            continue
        instruction = _first_text(entry, "instruction")
        link = _first_text(entry, "link") or source_url
        parsed_link = urlparse(link)
        if (
            parsed_link.scheme != "https"
            or not parsed_link.hostname
            or not (
                parsed_link.hostname == "inmet.gov.br"
                or parsed_link.hostname.endswith(".inmet.gov.br")
            )
        ):
            link = source_url
        warnings.append(
            NormalizedWarning(
                source_key=_source_key(identifier),
                title=title[:140],
                message=message[:5000],
                event_type=(_first_text(entry, "event") or "AVISO_INMET")[:40],
                severity=severity,
                area_name=(_first_text(entry, "areadesc") or "Área informada pelo INMET")[:160],
                polygon=_parse_polygon(_first_text(entry, "polygon")),
                recommendations=(
                    [instruction[:300]]
                    if instruction
                    else ["Consulte as orientações no aviso oficial do INMET"]
                ),
                issued_at=issued_at,
                valid_until=valid_until,
                source_url=link,
                message_type=message_type,
                referenced_source_keys=referenced_source_keys,
            )
        )
    if not entries:
        if _local_name(root.tag) in {"rss", "feed", "channel"}:
            return []
        raise InmetError("O feed do INMET nao contem itens reconheciveis")
    if not warnings:
        if excluded == len(entries):
            return []
        raise InmetError("O feed do INMET não contém avisos completos e reconhecíveis")
    return warnings


class InmetClient:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.transport = transport

    def fetch_warnings(self) -> list[NormalizedWarning]:
        if not self.settings.inmet_enabled:
            raise InmetError("A integração com o INMET está desabilitada")
        parsed = urlparse(self.settings.inmet_warning_rss_url)
        if parsed.scheme != "https" or not (
            parsed.hostname == "inmet.gov.br" or parsed.hostname.endswith(".inmet.gov.br")
        ):
            raise InmetError("A URL configurada para o INMET não é permitida")
        try:
            with httpx.Client(
                timeout=self.settings.inmet_timeout_seconds,
                follow_redirects=False,
                transport=self.transport,
                headers={"User-Agent": self.settings.inmet_user_agent},
            ) as client:
                with client.stream("GET", self.settings.inmet_warning_rss_url) as response:
                    response.raise_for_status()
                    chunks: list[bytes] = []
                    total = 0
                    for chunk in response.iter_bytes():
                        total += len(chunk)
                        if total > self.settings.inmet_max_response_bytes:
                            raise InmetError("A resposta do INMET excedeu o limite permitido")
                        chunks.append(chunk)
                    content = b"".join(chunks)
        except httpx.HTTPError as error:
            raise InmetError("Não foi possível consultar o INMET") from error
        return parse_warning_feed(
            content,
            source_url=self.settings.inmet_warning_rss_url,
        )
