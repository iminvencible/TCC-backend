import re
from datetime import UTC, datetime
from decimal import Decimal
from math import isfinite
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,128}$")


def utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def validate_geojson_polygon(value: dict) -> dict:
    if value.get("type") != "Polygon" or set(value) - {"type", "coordinates"}:
        raise ValueError("polygon must be a GeoJSON Polygon geometry")
    rings = value.get("coordinates")
    if not isinstance(rings, list) or not rings:
        raise ValueError("polygon must contain at least one ring")
    point_count = 0
    for ring in rings:
        if not isinstance(ring, list) or len(ring) < 4 or ring[0] != ring[-1]:
            raise ValueError("every polygon ring must be closed and contain at least four points")
        for point in ring:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError("polygon points must be [longitude, latitude] pairs")
            longitude, latitude = point
            if (
                isinstance(longitude, bool)
                or isinstance(latitude, bool)
                or not isinstance(longitude, (int, float))
                or not isinstance(latitude, (int, float))
                or not isfinite(longitude)
                or not isfinite(latitude)
                or not -180 <= longitude <= 180
                or not -90 <= latitude <= 90
            ):
                raise ValueError("polygon coordinates are outside valid geographic bounds")
            point_count += 1
            if point_count > 10_000:
                raise ValueError("polygon cannot contain more than 10000 points")
    return value


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, min_length=2, max_length=2)

    @field_validator("name", "city")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value else value

    @field_validator("state")
    @classmethod
    def normalize_state(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not PASSWORD_PATTERN.match(value):
            raise ValueError("use upper/lowercase letters, a number and a special character")
        return value

    @model_validator(mode="after")
    def location_pair(self):
        if bool(self.city) != bool(self.state):
            raise ValueError("city and state must be supplied together")
        return self


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class StaffCreateRequest(RegisterRequest):
    role: Literal["USER", "METEOROLOGIST"]


class RoleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["USER", "METEOROLOGIST"]


class UserOut(BaseModel):
    id: int
    public_code: str
    name: str
    email: EmailStr
    role: str
    role_name: str
    city: str | None
    state: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    weather_notifications: bool
    alert_sound: bool
    dark_theme: bool
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return utc_iso(value)


class AuthResponse(BaseModel):
    user: UserOut
    csrf_token: str


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, min_length=2, max_length=2)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    weather_notifications: bool | None = None
    alert_sound: bool | None = None
    dark_theme: bool | None = None

    @field_validator("name", "city")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value else value

    @field_validator("state")
    @classmethod
    def normalize_state(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @model_validator(mode="after")
    def validate_pairs(self):
        supplied = self.model_fields_set
        if "name" in supplied and self.name is None:
            raise ValueError("name cannot be null")
        if "city" in supplied or "state" in supplied:
            if not {"city", "state"}.issubset(supplied) or bool(self.city) != bool(self.state):
                raise ValueError("city and state must be supplied together or both cleared")
        if "latitude" in supplied or "longitude" in supplied:
            if not {"latitude", "longitude"}.issubset(supplied) or (
                (self.latitude is None) != (self.longitude is None)
            ):
                raise ValueError("latitude and longitude must be supplied together or both cleared")
        for field in ("weather_notifications", "alert_sound", "dark_theme"):
            if field in supplied and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ForecastOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    city: str
    state: str
    condition: str
    temperature_c: Decimal
    minimum_c: Decimal
    maximum_c: Decimal
    humidity: int
    wind_kmh: Decimal
    rain_probability: int
    severity: str
    description: str | None
    source_name: str
    issued_at: datetime
    valid_until: datetime

    @field_serializer("issued_at", "valid_until")
    def serialize_datetimes(self, value: datetime) -> str:
        return utc_iso(value)


class AlertOut(BaseModel):
    id: int
    title: str
    message: str
    event_type: str
    severity: str
    area_name: str
    recommendations: list[str]
    is_demo: bool
    issued_at: datetime
    valid_until: datetime
    is_read: bool = False

    @field_serializer("issued_at", "valid_until")
    def serialize_datetimes(self, value: datetime) -> str:
        return utc_iso(value)


class AlertCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=140)
    message: str = Field(min_length=10, max_length=5000)
    event_type: Literal["SEVERE_STORM", "TORNADO", "WINDSTORM", "HEAVY_RAIN"]
    severity: Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]
    area_name: str = Field(min_length=2, max_length=160)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    radius_km: Decimal | None = Field(default=None, gt=0, le=1000)
    polygon: dict | None = None
    recommendations: list[str] = Field(min_length=1, max_length=12)
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    valid_until: datetime

    @field_validator("recommendations")
    @classmethod
    def validate_recommendations(cls, values: list[str]) -> list[str]:
        cleaned = [" ".join(value.split()) for value in values if value.strip()]
        if not cleaned or any(len(value) > 300 for value in cleaned):
            raise ValueError("recommendations must contain text up to 300 characters")
        return cleaned

    @model_validator(mode="after")
    def validate_area_and_time(self):
        if self.valid_until <= self.issued_at:
            raise ValueError("valid_until must be after issued_at")
        has_circle = all(
            value is not None for value in (self.latitude, self.longitude, self.radius_km)
        )
        if self.polygon:
            self.polygon = validate_geojson_polygon(self.polygon)
        elif not has_circle:
            raise ValueError("provide a polygon or latitude, longitude and radius_km")
        return self


class HomeOut(BaseModel):
    forecast: ForecastOut | None
    active_alerts: list[AlertOut]
    unread_alert_count: int


class MapAlertOut(BaseModel):
    id: int
    title: str
    event_type: str
    severity: str
    area_name: str
    latitude: Decimal | None
    longitude: Decimal | None
    radius_km: Decimal | None
    polygon: dict | None
    is_demo: bool
    issued_at: datetime
    valid_until: datetime

    @field_serializer("issued_at", "valid_until")
    def serialize_datetimes(self, value: datetime) -> str:
        return utc_iso(value)


class MapForecastOut(BaseModel):
    id: int
    city: str
    state: str
    severity: str
    polygon: dict
    source_name: str
    valid_until: datetime

    @field_serializer("valid_until")
    def serialize_valid_until(self, value: datetime) -> str:
        return utc_iso(value)


class MapDataOut(BaseModel):
    alerts: list[MapAlertOut]
    forecast_areas: list[MapForecastOut]
    generated_at: datetime

    @field_serializer("generated_at")
    def serialize_generated_at(self, value: datetime) -> str:
        return utc_iso(value)


class EducationalContentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str
    media_url: str | None
    reference_url: str
    published_at: datetime

    @field_serializer("published_at")
    def serialize_published_at(self, value: datetime) -> str:
        return utc_iso(value)


class WeatherReportCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=10, max_length=2000)
    occurred_at: datetime
    latitude: Decimal = Field(ge=-90, le=90)
    longitude: Decimal = Field(ge=-180, le=180)
    image_url: str | None = Field(default=None, max_length=500, pattern=r"^https?://")

    @field_validator("description", mode="before")
    @classmethod
    def clean_description(cls, value: object) -> object:
        return " ".join(value.split()) if isinstance(value, str) else value

    @field_validator("occurred_at")
    @classmethod
    def occurrence_not_in_future(cls, value: datetime) -> datetime:
        normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        if normalized > datetime.now(UTC):
            raise ValueError("occurred_at cannot be in the future")
        return normalized


class WeatherReportReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["APPROVED", "REJECTED"]
    review_notes: str | None = Field(default=None, max_length=2000)

    @field_validator("review_notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value else value


class WeatherReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    description: str
    occurred_at: datetime
    latitude: Decimal
    longitude: Decimal
    image_url: str | None
    status: str
    review_notes: str | None
    reviewed_at: datetime | None
    created_at: datetime

    @field_serializer("occurred_at", "reviewed_at", "created_at")
    def serialize_datetimes(self, value: datetime | None) -> str | None:
        return utc_iso(value) if value else None


class MessageOut(BaseModel):
    message: str
