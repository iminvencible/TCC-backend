from typing import Annotated

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.security import decode_access_token

DbSession = Annotated[Session, Depends(get_db)]


def _extract_token(
    request: Request,
    access_cookie: str | None,
    authorization: str | None,
) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return access_cookie or request.cookies.get("prevclima_access")


def optional_current_user(
    request: Request,
    db: DbSession,
    access_cookie: Annotated[str | None, Cookie(alias="prevclima_access")] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> User | None:
    token = _extract_token(request, access_cookie, authorization)
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        if payload.get("type") != "access":
            return None
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        return None

    user = db.get(User, user_id)
    if not user or not user.is_active or user.token_version != payload.get("tv"):
        return None
    return user


def current_user(user: Annotated[User | None, Depends(optional_current_user)]) -> User:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticação necessária"
        )
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def current_mobile_user(
    request: Request,
    db: DbSession,
    access_cookie: Annotated[str | None, Cookie(alias="prevclima_access")] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    token = _extract_token(request, access_cookie, authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação móvel necessária",
        )
    try:
        payload = decode_access_token(token)
        user = db.get(User, int(payload["sub"]))
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão móvel inválida",
        ) from error
    if (
        payload.get("aud") != "prevclima-mobile"
        or not user
        or not user.is_active
        or user.token_version != payload.get("tv")
        or user.role.code != "USER"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Este acesso móvel é exclusivo para contas de usuário",
        )
    return user


MobileUser = Annotated[User, Depends(current_mobile_user)]


def require_roles(*roles: str):
    def dependency(user: CurrentUser) -> User:
        if user.role.code not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Permissão insuficiente"
            )
        return user

    return dependency
