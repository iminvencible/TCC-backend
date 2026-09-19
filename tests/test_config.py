import pytest

from app.config import Settings


def test_production_rejects_development_defaults():
    settings = Settings(
        app_env="production",
        database_url="mysql+pymysql://user:pass@db/prevclima",
        cookie_secure=True,
    )
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        settings.validate_production()


def test_production_accepts_explicit_safe_settings():
    settings = Settings(
        app_env="production",
        database_url="mysql+pymysql://user:pass@db/prevclima",
        jwt_secret="a-unique-production-secret-that-is-long-enough",
        cookie_secure=True,
        cors_origins=["https://prevclima.example"],
    )
    settings.validate_production()
