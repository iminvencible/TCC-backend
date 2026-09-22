from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import DbSession, require_roles
from app.inmet_sync import InmetError, cached_active_inmet_count, sync_inmet_warnings
from app.models import User
from app.schemas import InmetWarningSyncOut

router = APIRouter(prefix="/integrations/inmet", tags=["integracao INMET"])


@router.post("/sync-warnings", response_model=InmetWarningSyncOut)
def sync_warnings(
    db: DbSession,
    user: Annotated[User, Depends(require_roles("METEOROLOGIST"))],
):
    try:
        imported, skipped = sync_inmet_warnings(db, actor=user)
    except InmetError as error:
        db.rollback()
        return InmetWarningSyncOut(
            synced=False,
            using_stored_data=True,
            message=str(error),
            imported=0,
            skipped=0,
            stored_active_alerts=cached_active_inmet_count(db),
        )
    return InmetWarningSyncOut(
        synced=True,
        using_stored_data=False,
        message="Avisos do INMET sincronizados com sucesso",
        imported=imported,
        skipped=skipped,
        stored_active_alerts=cached_active_inmet_count(db),
    )
