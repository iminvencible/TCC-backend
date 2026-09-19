from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="ck_user_lat"),
        CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name="ck_user_lon"),
        CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) OR "
            "(latitude IS NOT NULL AND longitude IS NOT NULL)",
            name="ck_user_coordinates_pair",
        ),
        Index("ix_users_name", "name"),
        Index("ix_users_role_id", "role_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    public_code: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False
    )
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(2))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    weather_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    alert_sound: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    dark_theme: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    role: Mapped[Role] = relationship(lazy="joined")


class Forecast(Base):
    __tablename__ = "forecasts"
    __table_args__ = (
        CheckConstraint("valid_until > issued_at", name="ck_forecast_validity"),
        CheckConstraint("humidity BETWEEN 0 AND 100", name="ck_forecast_humidity"),
        CheckConstraint("rain_probability BETWEEN 0 AND 100", name="ck_forecast_rain"),
        Index("ix_forecasts_location_valid", "city", "state", "valid_until"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    condition: Mapped[str] = mapped_column(String(120), nullable=False)
    temperature_c: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    minimum_c: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    maximum_c: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    humidity: Mapped[int] = mapped_column(Integer, nullable=False)
    wind_kmh: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    rain_probability: Mapped[int] = mapped_column(Integer, nullable=False)
    severity: Mapped[str] = mapped_column(String(24), default="LOW", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    polygon: Mapped[dict | None] = mapped_column(JSON)
    source_name: Mapped[str] = mapped_column(
        String(120), default="Dados demonstrativos", nullable=False
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class WeatherAlert(Base):
    __tablename__ = "weather_alerts"
    __table_args__ = (
        CheckConstraint("valid_until > issued_at", name="ck_alert_validity"),
        CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="ck_alert_lat"),
        CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name="ck_alert_lon"),
        CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) OR "
            "(latitude IS NOT NULL AND longitude IS NOT NULL)",
            name="ck_alert_coordinates_pair",
        ),
        CheckConstraint("radius_km IS NULL OR radius_km > 0", name="ck_alert_radius"),
        CheckConstraint(
            "polygon IS NOT NULL OR "
            "(latitude IS NOT NULL AND longitude IS NOT NULL AND radius_km IS NOT NULL)",
            name="ck_alert_has_area",
        ),
        CheckConstraint(
            "severity IN ('LOW', 'MODERATE', 'HIGH', 'CRITICAL')",
            name="ck_alert_severity",
        ),
        Index("ix_alerts_active", "valid_until", "severity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(24), nullable=False)
    area_name: Mapped[str] = mapped_column(String(160), nullable=False)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    radius_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    polygon: Mapped[dict | None] = mapped_column(JSON)
    recommendations: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class AlertRead(Base):
    __tablename__ = "alert_reads"
    __table_args__ = (UniqueConstraint("user_id", "alert_id", name="uq_alert_read_user_alert"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    alert_id: Mapped[int] = mapped_column(
        ForeignKey("weather_alerts.id", ondelete="CASCADE"), nullable=False
    )
    read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class News(Base):
    __tablename__ = "news"
    __table_args__ = (Index("ix_news_published", "published_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WeatherReport(Base):
    __tablename__ = "weather_reports"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_report_lat"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_report_lon"),
        CheckConstraint("status IN ('PENDING', 'APPROVED', 'REJECTED')", name="ck_report_status"),
        Index("ix_reports_review_queue", "status", "created_at"),
        Index("ix_reports_reporter_created", "reporter_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reporter_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(24), default="PENDING", nullable=False)
    review_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class EducationalContent(Base):
    __tablename__ = "educational_contents"
    __table_args__ = (Index("ix_education_published", "published_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_key: Mapped[str | None] = mapped_column(String(80), unique=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    media_url: Mapped[str | None] = mapped_column(String(500))
    reference_url: Mapped[str] = mapped_column(String(500), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
