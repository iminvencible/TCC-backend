from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.dependencies import DbSession, require_roles
from app.models import Role, User
from app.routers.auth import new_public_code, normalized_email
from app.schemas import RoleUpdateRequest, StaffCreateRequest, UserOut
from app.security import hash_password
from app.services import user_out

router = APIRouter(
    prefix="/admin",
    tags=["administration"],
    dependencies=[Depends(require_roles("OWNER"))],
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
def create_user(payload: StaffCreateRequest, db: DbSession):
    email = normalized_email(str(payload.email))
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    role = db.scalar(select(Role).where(Role.code == payload.role))
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
    return user_out(user)


@router.patch("/users/{user_id}/role", response_model=UserOut)
def update_role(user_id: int, payload: RoleUpdateRequest, db: DbSession):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role.code == "OWNER":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Owner role cannot be changed"
        )
    role = db.scalar(select(Role).where(Role.code == payload.role))
    if not role:
        raise HTTPException(status_code=503, detail="Database roles are not initialized")
    user.role_id = role.id
    user.token_version += 1
    db.commit()
    db.refresh(user)
    return user_out(user)
