"""Email delivery and database-backed, single-use account challenges."""

import hashlib
import hmac
import secrets
import smtplib
import ssl
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from fastapi import HTTPException, Request
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuthRateLimit, EmailChallenge, User


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def digest(value: str) -> str:
    return hmac.new(get_settings().jwt_secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def rate_limit(db: Session, request: Request, category: str, identity: str = "") -> None:
    now = datetime.now(UTC)
    # Do not trust arbitrary X-Forwarded-For headers. Proxies must be explicitly trusted.
    source = request.client.host if request.client else "unknown"
    keys = [digest(f"{category}:ip:{source}")]
    if identity:
        keys.append(digest(f"{category}:email:{identity}"))
    db.execute(delete(AuthRateLimit).where(AuthRateLimit.reset_at <= now))
    for key in keys:
        try:
            with db.begin_nested():
                db.add(AuthRateLimit(key=key, count=0, reset_at=now + timedelta(hours=1)))
                db.flush()
        except IntegrityError:
            pass
        limit = 30 if category == "login" else 10
        result = db.execute(
            update(AuthRateLimit)
            .where(AuthRateLimit.key == key, AuthRateLimit.count < limit)
            .values(count=AuthRateLimit.count + 1)
        )
        if result.rowcount != 1:
            db.commit()
            raise HTTPException(429, "Muitas tentativas. Tente novamente em uma hora.")
    db.commit()


def send_code(email: str, purpose: str, code: str) -> None:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_from:
        raise HTTPException(
            503, "Envio de e-mail indisponível. Tente reenviar o código mais tarde."
        )
    if settings.smtp_security not in {"starttls", "ssl"}:
        raise HTTPException(503, "Configuração de e-mail indisponível.")
    label = "Confirme seu cadastro" if purpose == "verify" else "Redefina sua senha"
    duration = "24 horas" if purpose == "verify" else "15 minutos"
    message = EmailMessage()
    message["Subject"] = f"PrevClima — {label}"
    message["From"] = settings.smtp_from
    message["To"] = email
    message.set_content(
        f"{label}\n\nSeu código: {code}\nVálido por {duration}, para um único uso.\n\n"
        f"Acesse {settings.public_base_url.rstrip('/')}/conta.html#{purpose}\n"
        "Se você não solicitou esta mensagem, ignore-a."
    )
    try:
        connection = smtplib.SMTP_SSL if settings.smtp_security == "ssl" else smtplib.SMTP
        with connection(
            settings.smtp_host,
            settings.smtp_port,
            timeout=10,
            **(
                {"context": ssl.create_default_context()} if settings.smtp_security == "ssl" else {}
            ),
        ) as smtp:
            if settings.smtp_security == "starttls":
                smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        raise HTTPException(
            503, "Não foi possível enviar o e-mail. Tente reenviar mais tarde."
        ) from error


def issue_challenge(db: Session, user: User, purpose: str) -> None:
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    challenge = db.scalar(
        select(EmailChallenge)
        .where(EmailChallenge.user_id == user.id, EmailChallenge.purpose == purpose)
        .with_for_update()
    )
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires = datetime.now(UTC) + (
        timedelta(hours=24) if purpose == "verify" else timedelta(minutes=15)
    )
    if challenge is None:
        challenge = EmailChallenge(user_id=user.id, purpose=purpose)
        db.add(challenge)
    challenge.token_hash = digest(f"{user.id}:{purpose}:{code}")
    challenge.expires_at = expires
    challenge.attempts = 0
    challenge.consumed = False
    db.flush()
    try:
        send_code(user.email, purpose, code)
    except HTTPException:
        db.rollback()
        raise
    db.commit()


def consume_challenge(db: Session, email: str, purpose: str, code: str) -> User:
    user = db.scalar(
        select(User).where(User.email == email, User.is_active.is_(True)).with_for_update()
    )
    challenge = (
        db.scalar(
            select(EmailChallenge)
            .where(EmailChallenge.user_id == user.id, EmailChallenge.purpose == purpose)
            .with_for_update()
        )
        if user
        else None
    )
    valid = (
        challenge
        and not challenge.consumed
        and challenge.attempts < 5
        and aware(challenge.expires_at) > datetime.now(UTC)
    )
    if valid:
        expected = digest(f"{user.id}:{purpose}:{code}")
        if hmac.compare_digest(challenge.token_hash, expected):
            claimed = db.execute(
                update(EmailChallenge)
                .execution_options(synchronize_session="fetch")
                .where(
                    EmailChallenge.id == challenge.id,
                    EmailChallenge.consumed.is_(False),
                    EmailChallenge.attempts < 5,
                    EmailChallenge.token_hash == expected,
                    EmailChallenge.expires_at > datetime.now(UTC),
                )
                .values(consumed=True)
            )
            if claimed.rowcount == 1:
                return user
        db.execute(
            update(EmailChallenge)
            .execution_options(synchronize_session="fetch")
            .where(EmailChallenge.id == challenge.id)
            .values(attempts=EmailChallenge.attempts + 1)
        )
        db.commit()
    raise HTTPException(400, "Código inválido, expirado ou já utilizado. Solicite outro código.")
