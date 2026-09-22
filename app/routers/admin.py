from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.audit import record_audit
from app.dependencies import DbSession, require_roles
from app.models import Role, User
from app.routers.auth import new_public_code, normalized_email
from app.schemas import MessageOut, RoleUpdateRequest, StaffCreateRequest, UserOut
from app.security import hash_password
from app.services import user_out

router = APIRouter(
    prefix="/admin",
    tags=["administracao"],
    dependencies=[Depends(require_roles("ADMIN"))],
)


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: DbSession,
    search: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=50, ge=1, le=100),
):
    query = select(User).where(User.is_active.is_(True)).order_by(User.name).limit(limit)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(User.name.ilike(term), User.email.ilike(term), User.public_code.ilike(term))
        )
    return [user_out(user) for user in db.scalars(query)]


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: StaffCreateRequest,
    db: DbSession,
    admin: Annotated[User, Depends(require_roles("ADMIN"))],
):
    email = normalized_email(str(payload.email))
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado")
    role = db.scalar(select(Role).where(Role.code == "METEOROLOGIST"))
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
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado"
        ) from error
    record_audit(
        db,
        actor=admin,
        action="METEOROLOGIST_CREATED",
        target_type="user",
        target_id=user.id,
        details={"email": user.email, "role": "METEOROLOGIST"},
    )
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.patch("/users/{user_id}/role", response_model=UserOut)
def update_role(
    user_id: int,
    payload: RoleUpdateRequest,
    db: DbSession,
    admin: Annotated[User, Depends(require_roles("ADMIN"))],
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta não encontrada")
    if user.id == admin.id or user.role.code == "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A função desta conta administrativa não pode ser alterada",
        )
    role = db.scalar(select(Role).where(Role.code == payload.role))
    if not role:
        raise HTTPException(status_code=503, detail="As funções de acesso não foram inicializadas")
    previous_role = user.role.code
    user.role_id = role.id
    user.token_version += 1
    record_audit(
        db,
        actor=admin,
        action="USER_ROLE_CHANGED",
        target_type="user",
        target_id=user.id,
        details={"previous_role": previous_role, "new_role": payload.role},
    )
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.delete("/users/{user_id}", response_model=MessageOut)
def deactivate_user(
    user_id: int,
    db: DbSession,
    admin: Annotated[User, Depends(require_roles("ADMIN"))],
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conta não encontrada")
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Você não pode desativar a própria conta",
        )
    if not user.is_active:
        return MessageOut(message="Conta já estava desativada")
    user.is_active = False
    user.token_version += 1
    record_audit(
        db,
        actor=admin,
        action="USER_DEACTIVATED",
        target_type="user",
        target_id=user.id,
        details={"email": user.email, "role": user.role.code},
    )
    db.commit()
    return MessageOut(message="Conta desativada com sucesso")
