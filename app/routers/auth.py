import secrets

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.dependencies import CurrentUser, DbSession
from app.models import Role, User
from app.schemas import AuthResponse, LoginRequest, MessageOut, RegisterRequest
from app.security import create_access_token, create_csrf_token, hash_password, verify_password
from app.services import user_out

router = APIRouter(prefix="/auth", tags=["authentication"])
DUMMY_PASSWORD_HASH = hash_password("NotARealPassword123!")


def normalized_email(value: str) -> str:
    return value.strip().lower()


def new_public_code(db: DbSession) -> str:
    while True:
        code = f"PVC-{secrets.token_hex(4).upper()}"
        if not db.scalar(select(User.id).where(User.public_code == code)):
            return code


def set_auth_cookies(response: Response, user: User) -> str:
    settings = get_settings()
    csrf = create_csrf_token()
    response.set_cookie(
        "prevclima_access",
        create_access_token(user.id, user.token_version),
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


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: DbSession):
    email = normalized_email(str(payload.email))
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    role = db.scalar(select(Role).where(Role.code == "USER"))
    if not role:
        raise HTTPException(status_code=503, detail="Database roles are not initialized")

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
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        ) from error
    db.refresh(user)
    csrf = set_auth_cookies(response, user)
    return AuthResponse(user=user_out(user), csrf_token=csrf)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, response: Response, db: DbSession):
    user = authenticate(payload, db)
    csrf = set_auth_cookies(response, user)
    return AuthResponse(user=user_out(user), csrf_token=csrf)


def authenticate(payload: LoginRequest, db: DbSession) -> User:
    user = db.scalar(select(User).where(User.email == normalized_email(str(payload.email))))
    encoded = user.password_hash if user else DUMMY_PASSWORD_HASH
    password_is_valid = verify_password(payload.password, encoded)
    if not user or not user.is_active or not password_is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    return user


@router.post("/login-professional", response_model=AuthResponse)
def login_professional(payload: LoginRequest, response: Response, db: DbSession):
    user = authenticate(payload, db)
    if user.role.code not in {"METEOROLOGIST", "OWNER"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Professional access required"
        )
    csrf = set_auth_cookies(response, user)
    return AuthResponse(user=user_out(user), csrf_token=csrf)


@router.post("/logout", response_model=MessageOut)
def logout(response: Response, user: CurrentUser, db: DbSession):
    user.token_version += 1
    db.commit()
    response.delete_cookie("prevclima_access", path="/")
    response.delete_cookie("prevclima_csrf", path="/")
    return MessageOut(message="Signed out")


@router.get("/me", response_model=AuthResponse)
def me(user: CurrentUser):
    return AuthResponse(user=user_out(user), csrf_token="")
