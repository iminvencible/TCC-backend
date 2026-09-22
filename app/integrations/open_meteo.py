from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import isfinite
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import Settings, get_settings


class OpenMeteoError(RuntimeError):
    pass


@dataclass(frozen=True)
class Coordinates:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class NormalizedForecast:
    condition: str
    temperature_c: float
    minimum_c: float
    maximum_c: float
    humidity: int
    wind_kmh: float
    rain_probability: int
    severity: str
    description: str
    issued_at: datetime
    valid_until: datetime


STATE_NAMES = {
    "AC": "acre",
    "AL": "alagoas",
    "AP": "amapa",
    "AM": "amazonas",
    "BA": "bahia",
    "CE": "ceara",
    "DF": "distrito federal",
    "ES": "espirito santo",
    "GO": "goias",
    "MA": "maranhao",
    "MT": "mato grosso",
    "MS": "mato grosso do sul",
    "MG": "minas gerais",
    "PA": "para",
    "PB": "paraiba",
    "PR": "parana",
    "PE": "pernambuco",
    "PI": "piaui",
    "RJ": "rio de janeiro",
    "RN": "rio grande do norte",
    "RS": "rio grande do sul",
    "RO": "rondonia",
    "RR": "roraima",
    "SC": "santa catarina",
    "SP": "sao paulo",
    "SE": "sergipe",
    "TO": "tocantins",
}


WEATHER_CODES = {
    0: "Céu limpo",
    1: "Predominantemente limpo",
    2: "Parcialmente nublado",
    3: "Nublado",
    45: "Nevoeiro",
    48: "Nevoeiro com geada",
    51: "Garoa fraca",
    53: "Garoa moderada",
    55: "Garoa intensa",
    56: "Garoa congelante fraca",
    57: "Garoa congelante intensa",
    61: "Chuva fraca",
    63: "Chuva moderada",
    65: "Chuva forte",
    66: "Chuva congelante fraca",
    67: "Chuva congelante forte",
    71: "Neve fraca",
    73: "Neve moderada",
    75: "Neve forte",
    77: "Grãos de neve",
    80: "Pancadas de chuva fracas",
    81: "Pancadas de chuva moderadas",
    82: "Pancadas de chuva violentas",
    85: "Pancadas de neve fracas",
    86: "Pancadas de neve fortes",
    95: "Tempestade",
    96: "Tempestade com granizo",
    99: "Tempestade forte com granizo",
}


def _normalized_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    return "".join(
        character for character in value if not unicodedata.combining(character)
    ).casefold()


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OpenMeteoError(f"O Open-Meteo retornou {field} inválido")
    number = float(value)
    if not isfinite(number):
        raise OpenMeteoError(f"O Open-Meteo retornou {field} inválido")
    return number


def _integer(value: Any, field: str) -> int:
    number = _number(value, field)
    if not number.is_integer():
        raise OpenMeteoError(f"O Open-Meteo retornou {field} inválido")
    return int(number)


def _first(values: Any, field: str) -> Any:
    if not isinstance(values, list) or not values:
        raise OpenMeteoError(f"O Open-Meteo não retornou {field}")
    return values[0]


def _severity(weather_code: int, rain_probability: int, wind_gust_kmh: float) -> str:
    if weather_code in {96, 99} or wind_gust_kmh >= 100:
        return "CRITICAL"
    if weather_code in {65, 67, 82, 95} or wind_gust_kmh >= 70 or rain_probability >= 80:
        return "HIGH"
    if weather_code in {55, 63, 66, 80, 81} or wind_gust_kmh >= 50 or rain_probability >= 60:
        return "MODERATE"
    return "LOW"


def parse_forecast_payload(
    payload: dict[str, Any], *, cache_minutes: int, now: datetime | None = None
) -> NormalizedForecast:
    current = payload.get("current")
    daily = payload.get("daily")
    if not isinstance(current, dict) or not isinstance(daily, dict):
        raise OpenMeteoError("O Open-Meteo retornou uma previsão incompleta")

    timestamp = _integer(current.get("time"), "o horário atual")
    issued_at = datetime.fromtimestamp(timestamp, tz=UTC)
    temperature = _number(current.get("temperature_2m"), "a temperatura")
    humidity = _integer(current.get("relative_humidity_2m"), "a umidade")
    wind = _number(current.get("wind_speed_10m"), "a velocidade do vento")
    weather_code = _integer(current.get("weather_code"), "o código meteorológico")
    minimum = _number(
        _first(daily.get("temperature_2m_min"), "a temperatura mínima"), "a temperatura mínima"
    )
    maximum = _number(
        _first(daily.get("temperature_2m_max"), "a temperatura máxima"), "a temperatura máxima"
    )
    rain_probability = _integer(
        _first(daily.get("precipitation_probability_max"), "a chance de chuva"),
        "a chance de chuva",
    )
    gust = _number(
        _first(daily.get("wind_gusts_10m_max"), "as rajadas de vento"),
        "as rajadas de vento",
    )
    if not 0 <= humidity <= 100 or not 0 <= rain_probability <= 100:
        raise OpenMeteoError("O Open-Meteo retornou percentuais fora do intervalo válido")
    if not all(-100 <= value <= 70 for value in (temperature, minimum, maximum)):
        raise OpenMeteoError("O Open-Meteo retornou temperaturas fora do intervalo válido")
    if minimum > maximum:
        raise OpenMeteoError("O Open-Meteo retornou temperaturas mínima e máxima inválidas")
    if not 0 <= wind <= 500 or not 0 <= gust <= 500:
        raise OpenMeteoError("O Open-Meteo retornou vento fora do intervalo válido")

    condition = WEATHER_CODES.get(weather_code, "Condição meteorológica variável")
    reference_time = now or datetime.now(UTC)
    valid_until = max(reference_time, issued_at) + timedelta(minutes=cache_minutes)
    return NormalizedForecast(
        condition=condition,
        temperature_c=temperature,
        minimum_c=minimum,
        maximum_c=maximum,
        humidity=humidity,
        wind_kmh=wind,
        rain_probability=rain_probability,
        severity=_severity(weather_code, rain_probability, gust),
        description=f"{condition}. Rajadas previstas de até {round(gust)} km/h.",
        issued_at=issued_at,
        valid_until=valid_until,
    )


class OpenMeteoClient:
    FORECAST_HOSTS = {"api.open-meteo.com"}
    GEOCODING_HOSTS = {"geocoding-api.open-meteo.com"}

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.transport = transport

    def _request_json(
        self, url: str, *, allowed_hosts: set[str], params: dict[str, Any]
    ) -> dict[str, Any]:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
            raise OpenMeteoError("A URL configurada para o Open-Meteo não é permitida")
        try:
            with httpx.Client(
                timeout=self.settings.open_meteo_timeout_seconds,
                follow_redirects=False,
                transport=self.transport,
                headers={"User-Agent": self.settings.open_meteo_user_agent},
            ) as client:
                with client.stream("GET", url, params=params) as response:
                    response.raise_for_status()
                    chunks: list[bytes] = []
                    total = 0
                    for chunk in response.iter_bytes():
                        total += len(chunk)
                        if total > self.settings.open_meteo_max_response_bytes:
                            raise OpenMeteoError(
                                "A resposta do Open-Meteo excedeu o limite permitido"
                            )
                        chunks.append(chunk)
            payload = json.loads(b"".join(chunks))
        except (httpx.HTTPError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise OpenMeteoError("Não foi possível consultar o Open-Meteo") from error
        if not isinstance(payload, dict) or payload.get("error") is True:
            raise OpenMeteoError("O Open-Meteo retornou uma resposta inválida")
        return payload

    def geocode(self, city: str, state: str) -> Coordinates:
        payload = self._request_json(
            self.settings.open_meteo_geocoding_url,
            allowed_hosts=self.GEOCODING_HOSTS,
            params={
                "name": city,
                "count": 20,
                "language": "pt",
                "format": "json",
                "countryCode": "BR",
            },
        )
        results = payload.get("results")
        if not isinstance(results, list):
            raise OpenMeteoError("Cidade não encontrada no Open-Meteo")
        brazil = [
            result
            for result in results
            if isinstance(result, dict) and result.get("country_code") == "BR"
        ]
        expected_state = STATE_NAMES.get(state.upper())
        selected = next(
            (
                result
                for result in brazil
                if expected_state
                and _normalized_text(str(result.get("admin1", ""))) == expected_state
            ),
            None,
        )
        if not expected_state and brazil:
            selected = brazil[0]
        if not selected:
            raise OpenMeteoError("Cidade e UF não encontradas no Open-Meteo")
        latitude = _number(selected.get("latitude"), "a latitude da cidade")
        longitude = _number(selected.get("longitude"), "a longitude da cidade")
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise OpenMeteoError("O Open-Meteo retornou coordenadas inválidas")
        return Coordinates(latitude=latitude, longitude=longitude)

    def fetch_forecast(self, latitude: float, longitude: float) -> NormalizedForecast:
        if not self.settings.open_meteo_enabled:
            raise OpenMeteoError("A integração com o Open-Meteo está desabilitada")
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise OpenMeteoError("Coordenadas fora dos limites válidos")
        payload = self._request_json(
            self.settings.open_meteo_api_url,
            allowed_hosts=self.FORECAST_HOSTS,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": ("temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"),
                "daily": (
                    "temperature_2m_max,temperature_2m_min,"
                    "precipitation_probability_max,wind_gusts_10m_max"
                ),
                "temperature_unit": "celsius",
                "wind_speed_unit": "kmh",
                "timezone": "UTC",
                "timeformat": "unixtime",
                "forecast_days": 2,
            },
        )
        return parse_forecast_payload(
            payload,
            cache_minutes=self.settings.open_meteo_cache_minutes,
        )


__all__ = [
    "Coordinates",
    "NormalizedForecast",
    "OpenMeteoClient",
    "OpenMeteoError",
    "parse_forecast_payload",
]
