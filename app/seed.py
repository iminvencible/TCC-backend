from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.config import get_settings
from app.database import SessionLocal
from app.models import EducationalContent, Forecast, Role, User, WeatherAlert
from app.security import hash_password

ROLES = {
    "USER": "Usuario",
    "METEOROLOGIST": "Meteorologista",
    "OWNER": "Administrador",
}


def ensure_roles(db) -> dict[str, Role]:
    roles = {}
    for code, display_name in ROLES.items():
        role = db.scalar(select(Role).where(Role.code == code))
        if not role:
            role = Role(code=code, display_name=display_name)
            db.add(role)
            db.flush()
        elif role.display_name != display_name:
            role.display_name = display_name
        roles[code] = role
    return roles


def ensure_user(db, roles, *, email: str | None, password: str | None, role: str, name: str):
    if not email or not password:
        return None
    email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user:
        if user.role_id != roles[role].id or not user.is_active:
            raise RuntimeError(f"Seed account {email} exists with an unexpected role or state")
        return user
    user = User(
        public_code=f"DEMO-{role[:4]}-{len(email):04d}",
        name=name,
        email=email,
        password_hash=hash_password(password),
        role_id=roles[role].id,
        city="Mongagua",
        state="SP",
        latitude=Decimal("-24.1008"),
        longitude=Decimal("-46.6200"),
        email_verified_at=datetime.now(UTC),
    )
    db.add(user)
    db.flush()
    return user


def ensure_demo_weather(db, meteorologist: User | None):
    now = datetime.now(UTC)
    bucket_start = datetime.combine(
        now.date() - timedelta(days=now.weekday()), time.min, tzinfo=UTC
    )
    bucket_end = bucket_start + timedelta(days=7)
    author_id = meteorologist.id if meteorologist else None
    forecast = db.scalar(select(Forecast).where(Forecast.source_key == "DEMO-MONGAGUA-CURRENT"))
    if not forecast:
        forecast = Forecast(source_key="DEMO-MONGAGUA-CURRENT")
        db.add(forecast)
    forecast.created_by = author_id
    forecast.city = "Mongagua"
    forecast.state = "SP"
    forecast.condition = "Parcialmente nublado"
    forecast.temperature_c = Decimal("23")
    forecast.minimum_c = Decimal("18")
    forecast.maximum_c = Decimal("26")
    forecast.humidity = 68
    forecast.wind_kmh = Decimal("14")
    forecast.rain_probability = 73
    forecast.severity = "HIGH"
    forecast.description = "Risco de tempestades e rajadas de vento nas proximas horas."
    forecast.polygon = {
        "type": "Polygon",
        "coordinates": [
            [
                [-49.8, -20.0],
                [-43.0, -20.0],
                [-43.0, -26.2],
                [-49.8, -26.2],
                [-49.8, -20.0],
            ]
        ],
    }
    forecast.source_name = "DEMONSTRACAO - dados sem monitoramento em tempo real"
    forecast.issued_at = now - timedelta(minutes=10)
    forecast.valid_until = now + timedelta(days=7)

    examples = [
        {
            "source_key": "DEMO-ALERT-TEMPESTADE",
            "title": "Tempestade severa",
            "event_type": "SEVERE_STORM",
            "severity": "CRITICAL",
            "area_name": "Baixada Santista",
            "message": (
                "Ventos fortes e raios frequentes. Ha risco de alagamento e queda de arvores."
            ),
            "recommendations": [
                "Procure abrigo imediatamente",
                "Evite areas abertas e arvores",
                "Mantenha-se longe de janelas",
                "Emergencias: Bombeiros 193 e Defesa Civil 199",
            ],
        },
        {
            "source_key": "DEMO-ALERT-VENDAVAL",
            "title": "Vendaval",
            "event_type": "WINDSTORM",
            "severity": "HIGH",
            "area_name": "Litoral de Sao Paulo",
            "message": "Rajadas fortes podem ocorrer nas proximas horas.",
            "recommendations": [
                "Evite areas abertas",
                "Afaste-se de arvores e postes",
                "Permaneca em local protegido",
            ],
        },
        {
            "source_key": "DEMO-ALERT-CHUVA",
            "title": "Chuva intensa",
            "event_type": "HEAVY_RAIN",
            "severity": "MODERATE",
            "area_name": "Litoral Sul",
            "message": "Pode haver chuva intensa e pontos de alagamento.",
            "recommendations": [
                "Evite areas sujeitas a alagamentos",
                "Reduza a velocidade no transito",
                "Acompanhe novos alertas",
            ],
        },
    ]
    for position, data in enumerate(examples):
        data["source_key"] = f"{data['source_key']}-{bucket_start.date().isoformat()}"
        alert = db.scalar(select(WeatherAlert).where(WeatherAlert.source_key == data["source_key"]))
        if alert:
            continue
        alert = WeatherAlert(source_key=data["source_key"], is_demo=True)
        db.add(alert)
        for key, value in data.items():
            setattr(alert, key, value)
        alert.created_by = author_id
        alert.latitude = Decimal("-24.1008")
        alert.longitude = Decimal("-46.6200")
        alert.radius_km = Decimal("30")
        alert.issued_at = max(bucket_start, now - timedelta(minutes=15 * (position + 1)))
        alert.valid_until = bucket_end


def ensure_demo_education(db, meteorologist: User | None):
    published_at = datetime.now(UTC)
    items = [
        (
            "DEMO-EDU-TEMPESTADE",
            "Como agir durante uma tempestade severa",
            (
                "Permaneça em local coberto, afaste-se de janelas e não procure abrigo "
                "sob árvores. Desligue equipamentos da tomada quando isso puder ser feito "
                "com segurança e acompanhe os avisos da Defesa Civil."
            ),
            "https://www.gov.br/mdr/pt-br/assuntos/protecao-e-defesa-civil",
        ),
        (
            "DEMO-EDU-ALAGAMENTO",
            "Cuidados em áreas com alagamento",
            (
                "Nunca atravesse uma via alagada a pé ou de veículo. A água pode esconder "
                "buracos, correnteza e redes elétricas. Procure uma rota elevada e ligue 199 "
                "em caso de risco."
            ),
            "https://www.gov.br/mdr/pt-br/assuntos/protecao-e-defesa-civil",
        ),
        (
            "DEMO-EDU-ALERTAS",
            "Entenda os níveis de alerta",
            (
                "Os níveis indicam a gravidade potencial do evento. Consulte a descrição, "
                "a área afetada e as recomendações de cada aviso antes de tomar decisões."
            ),
            "https://portal.inmet.gov.br/",
        ),
    ]
    for source_key, title, body, reference_url in items:
        if db.scalar(
            select(EducationalContent.id).where(EducationalContent.source_key == source_key)
        ):
            continue
        db.add(
            EducationalContent(
                source_key=source_key,
                author_id=meteorologist.id if meteorologist else None,
                title=title,
                body=body,
                reference_url=reference_url,
                published_at=published_at,
            )
        )


def main():
    settings = get_settings()
    with SessionLocal() as db:
        roles = ensure_roles(db)
        if settings.seed_demo_data:
            ensure_user(
                db,
                roles,
                email=settings.seed_owner_email,
                password=settings.seed_owner_password,
                role="OWNER",
                name="Proprietario Demo",
            )
            meteorologist = ensure_user(
                db,
                roles,
                email=settings.seed_meteorologist_email,
                password=settings.seed_meteorologist_password,
                role="METEOROLOGIST",
                name="Meteorologista Demo",
            )
            ensure_user(
                db,
                roles,
                email=settings.seed_user_email,
                password=settings.seed_user_password,
                role="USER",
                name="Usuario Demo",
            )
            ensure_demo_weather(db, meteorologist)
            ensure_demo_education(db, meteorologist)
        db.commit()


if __name__ == "__main__":
    main()
