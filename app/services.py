from app.models import User
from app.schemas import UserOut


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        public_code=user.public_code,
        name=user.name,
        email=user.email,
        role=user.role.code,
        role_name=user.role.display_name,
        city=user.city,
        state=user.state,
        latitude=user.latitude,
        longitude=user.longitude,
        weather_notifications=user.weather_notifications,
        alert_sound=user.alert_sound,
        dark_theme=user.dark_theme,
        created_at=user.created_at,
    )
