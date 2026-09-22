from fastapi import APIRouter

from app.dependencies import CurrentUser, DbSession
from app.schemas import ProfileUpdate, UserOut
from app.services import user_out

router = APIRouter(prefix="/users", tags=["usuários"])


@router.get("/me", response_model=UserOut)
def get_profile(user: CurrentUser):
    return user_out(user)


@router.patch("/me", response_model=UserOut)
def update_profile(payload: ProfileUpdate, user: CurrentUser, db: DbSession):
    location_changed = bool({"city", "state"} & payload.model_fields_set)
    coordinates_supplied = bool({"latitude", "longitude"} & payload.model_fields_set)
    for field in payload.model_fields_set:
        setattr(user, field, getattr(payload, field))
    if location_changed and not coordinates_supplied:
        user.latitude = None
        user.longitude = None
    db.commit()
    db.refresh(user)
    return user_out(user)
