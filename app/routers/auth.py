import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.dependencies import CurrentUser, DbSession, MobileUser
from app.email_auth import consume_challenge, issue_challenge, rate_limit
from app.models import Role, User
from app.schemas import (
    AuthResponse,
    CodeRequest,
    EmailRequest,
    LoginRequest,
    MessageOut,
    RegisterRequest,
    RegistrationOut,
    ResetPasswordRequest,
)
from app.security import create_access_token, create_csrf_token, hash_password, verify_password
from app.services import user_out

router = APIRouter(prefix="/auth", tags=["autenticacao"])
DUMMY_PASSWORD_HASH = hash_password("NotARealPassword123!")


def normalized_email(value: str) -> str:
    return value.strip().lower()


def new_public_code(db: DbSession) -> str:
    while True:
        code = f"PVC-{secrets.token_hex(4).upper()}"
        if not db.scalar(select(User.id).where(User.public_code == code)):
            return code


def set_auth_cookies(
    response: Response,
    user: User,
    *,
    audience: str = "prevclima-web",
) -> str:
    settings = get_settings()
    csrf = create_csrf_token()
    response.set_cookie(
        "prevclima_access",
        create_access_token(user.id, user.token_version, audience=audience),
        max_age=settings.jwt_ttl_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        "prevclima_csrf",
        csrf,
        max_age=settings.jwt_ttl_minutes * 60,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return csrf


@router.post("/register", response_model=RegistrationOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: DbSession):
    rate_limit(db, request, "email", normalized_email(str(payload.email)))
    email = normalized_email(str(payload.email))
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado")

    role = db.scalar(select(Role).where(Role.code == "USER"))
    if not role:
        raise HTTPException(status_code=503, detail="As funções de acesso não foram inicializadas")

    user = User(
        public_code=new_public_code(db),
        name=payload.name,
        email=email,
        password_hash=hash_password(payload.password),
        role_id=role.id,
        city=payload.city,
        state=payload.state,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado"
        ) from error
    db.refresh(user)
    issue_challenge(db, user, "verify")
    return RegistrationOut(
        email=user.email, message="Confira seu e-mail e confirme o cadastro com o código recebido."
    )


@router.get("/mobile-session", response_model=AuthResponse)
def mobile_session(user: MobileUser):
    return AuthResponse(user=user_out(user), csrf_token="")


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, response: Response, request: Request, db: DbSession):
    rate_limit(db, request, "login", normalized_email(str(payload.email)))
    user = authenticate(payload, db)
    csrf = set_auth_cookies(response, user)
    return AuthResponse(user=user_out(user), csrf_token=csrf)


@router.post("/login-mobile", response_model=AuthResponse)
def login_mobile(payload: LoginRequest, response: Response, request: Request, db: DbSession):
    rate_limit(db, request, "login", normalized_email(str(payload.email)))
    user = authenticate(payload, db)
    if user.role.code != "USER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este acesso é exclusivo para contas de usuário",
        )
    csrf = set_auth_cookies(response, user, audience="prevclima-mobile")
    return AuthResponse(user=user_out(user), csrf_token=csrf)


def authenticate(payload: LoginRequest, db: DbSession) -> User:
    user = db.scalar(select(User).where(User.email == normalized_email(str(payload.email))))
    encoded = user.password_hash if user else DUMMY_PASSWORD_HASH
    password_is_valid = verify_password(payload.password, encoded)
    if not user or not user.is_active or not password_is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos"
        )
    if user.email_verified_at is None:
        raise HTTPException(
            403, "Confirme seu e-mail para entrar. Solicite um novo código se necessário."
        )
    return user


@router.post("/login-professional", response_model=AuthResponse)
def login_professional(payload: LoginRequest, response: Response, request: Request, db: DbSession):
    rate_limit(db, request, "login", normalized_email(str(payload.email)))
    user = authenticate(payload, db)
    if user.role.code not in {"METEOROLOGIST", "ADMIN"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Acesso profissional necessário"
        )
    csrf = set_auth_cookies(response, user)
    return AuthResponse(user=user_out(user), csrf_token=csrf)


@router.post("/logout", response_model=MessageOut)
def logout(response: Response, user: CurrentUser, db: DbSession):
    user.token_version += 1
    db.commit()
    response.delete_cookie("prevclima_access", path="/")
    response.delete_cookie("prevclima_csrf", path="/")
    return MessageOut(message="Sessão encerrada")


@router.get("/me", response_model=AuthResponse)
def me(user: CurrentUser):
    return AuthResponse(user=user_out(user), csrf_token="")


@router.post("/resend-verification", response_model=MessageOut)
def resend(payload: EmailRequest, request: Request, db: DbSession):
    email = normalized_email(str(payload.email))
    rate_limit(db, request, "email", email)
    user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    if user and user.email_verified_at is None:
        issue_challenge(db, user, "verify")
    return MessageOut(message="Se houver um cadastro pendente, enviaremos um novo código.")


@router.post("/verify-email", response_model=MessageOut)
def verify_email(payload: CodeRequest, request: Request, db: DbSession):
    email = normalized_email(str(payload.email))
    rate_limit(db, request, "code", email)
    user = consume_challenge(db, email, "verify", payload.code)
    user.email_verified_at = datetime.now(UTC)
    db.commit()
    return MessageOut(message="E-mail confirmado. Você já pode entrar.")


@router.post("/forgot-password", response_model=MessageOut)
def forgot_password(payload: EmailRequest, request: Request, db: DbSession):
    email = normalized_email(str(payload.email))
    rate_limit(db, request, "email", email)
    user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    if user and user.email_verified_at is not None:
        issue_challenge(db, user, "reset")
    return MessageOut(
        message="Se houver uma conta confirmada, enviaremos um código de redefinição."
    )


@router.post("/reset-password", response_model=MessageOut)
def reset_password(payload: ResetPasswordRequest, request: Request, db: DbSession):
    email = normalized_email(str(payload.email))
    rate_limit(db, request, "code", email)
    user = consume_challenge(db, email, "reset", payload.code)
    user.password_hash = hash_password(payload.password)
    user.token_version += 1
    db.commit()
    return MessageOut(message="Senha atualizada. Entre novamente com a nova senha.")
