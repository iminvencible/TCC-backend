from functools import lru_cache

from pydantic import field_validator
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
    seed_owner_email: str | None = None
    seed_owner_password: str | None = None
    seed_meteorologist_email: str | None = None
    seed_meteorologist_password: str | None = None
    seed_user_email: str | None = None
    seed_user_password: str | None = None

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
            raise RuntimeError("Set a unique JWT_SECRET with at least 32 characters")
        if not self.cookie_secure:
            raise RuntimeError("COOKIE_SECURE must be enabled in production")
        if self.database_url.startswith("sqlite"):
            raise RuntimeError("Configure a production database instead of SQLite")
        if "*" in self.cors_origins:
            raise RuntimeError("Wildcard CORS origins are not allowed in production")
        if self.seed_demo_data:
            raise RuntimeError("SEED_DEMO_DATA must be disabled in production")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production()
    return settings
