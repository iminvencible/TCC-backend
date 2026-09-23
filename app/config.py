from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PrevClima"
    app_env: str = "development"
    database_url: str = "sqlite:///./prevclima.db"
    jwt_secret: str = "development-secret-change-before-production"
    jwt_ttl_minutes: int = 60
    cookie_secure: bool = False
    cors_origins: list[str] = ["http://localhost:8000"]
    seed_demo_data: bool = False
    seed_admin_email: str | None = None
    seed_admin_password: str | None = None
    seed_meteorologist_email: str | None = None
    seed_meteorologist_password: str | None = None
    seed_user_email: str | None = None
    seed_user_password: str | None = None
    inmet_enabled: bool = False
    inmet_warning_rss_url: str = "https://apiprevmet3.inmet.gov.br/avisos/rss"
    inmet_timeout_seconds: float = 8.0
    inmet_max_response_bytes: int = 2_000_000
    inmet_sync_interval_minutes: int = Field(default=60, ge=10, le=1440)
    inmet_user_agent: str = "PrevClima/0.1 (integracao academica)"
    open_meteo_enabled: bool = False
    open_meteo_api_url: str = "https://api.open-meteo.com/v1/forecast"
    open_meteo_geocoding_url: str = "https://geocoding-api.open-meteo.com/v1/search"
    open_meteo_timeout_seconds: float = Field(default=8.0, gt=0, le=60)
    open_meteo_max_response_bytes: int = Field(default=1_000_000, ge=1024, le=5_000_000)
    open_meteo_cache_minutes: int = Field(default=15, ge=1, le=1440)
    open_meteo_stale_hours: int = Field(default=24, ge=1, le=168)
    open_meteo_user_agent: str = "PrevClima/0.1 (integracao academica)"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    def validate_production(self) -> None:
        if self.app_env.lower() != "production":
            return
        if (
            self.jwt_secret == "development-secret-change-before-production"
            or len(self.jwt_secret) < 32
        ):
            raise RuntimeError("Defina JWT_SECRET unico com pelo menos 32 caracteres")
        if not self.cookie_secure:
            raise RuntimeError("COOKIE_SECURE deve estar habilitado em producao")
        if self.database_url.startswith("sqlite"):
            raise RuntimeError("Configure um banco de producao em vez do SQLite")
        if "*" in self.cors_origins:
            raise RuntimeError("Origem CORS curinga nao e permitida em producao")
        if self.seed_demo_data:
            raise RuntimeError("SEED_DEMO_DATA deve estar desabilitado em producao")
        if self.inmet_enabled and not self.inmet_warning_rss_url.startswith("https://"):
            raise RuntimeError("A URL do INMET deve usar HTTPS em producao")
        if self.open_meteo_enabled and not (
            self.open_meteo_api_url.startswith("https://")
            and self.open_meteo_geocoding_url.startswith("https://")
        ):
            raise RuntimeError("As URLs do Open-Meteo devem usar HTTPS em producao")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production()
    return settings
