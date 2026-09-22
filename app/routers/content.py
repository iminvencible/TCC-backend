from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select, update

from app.dependencies import CurrentUser, DbSession, require_roles
from app.models import EducationalContent, User, WeatherReport
from app.schemas import (
    EducationalContentOut,
    WeatherReportCreateRequest,
    WeatherReportOut,
    WeatherReportReviewRequest,
)

router = APIRouter(tags=["conteudo e relatos"])


@router.get("/education", response_model=list[EducationalContentOut])
def list_educational_content(
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10_000),
):
    return list(
        db.scalars(
            select(EducationalContent)
            .where(EducationalContent.published_at <= datetime.now(UTC))
            .order_by(desc(EducationalContent.published_at))
            .offset(offset)
            .limit(limit)
        )
    )


@router.post("/reports", response_model=WeatherReportOut, status_code=status.HTTP_201_CREATED)
def create_weather_report(
    payload: WeatherReportCreateRequest,
    user: CurrentUser,
    db: DbSession,
):
    report = WeatherReport(
        reporter_id=user.id,
        description=payload.description,
        occurred_at=payload.occurred_at,
        latitude=payload.latitude,
        longitude=payload.longitude,
        image_url=payload.image_url,
        status="PENDING",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("/reports/me", response_model=list[WeatherReportOut])
def list_my_weather_reports(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10_000),
):
    return list(
        db.scalars(
            select(WeatherReport)
            .where(WeatherReport.reporter_id == user.id)
            .order_by(desc(WeatherReport.created_at))
            .offset(offset)
            .limit(limit)
        )
    )


@router.get("/reports/review-queue", response_model=list[WeatherReportOut])
def report_review_queue(
    db: DbSession,
    _: Annotated[User, Depends(require_roles("METEOROLOGIST"))],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10_000),
):
    return list(
        db.scalars(
            select(WeatherReport)
            .where(WeatherReport.status == "PENDING")
            .order_by(WeatherReport.created_at)
            .offset(offset)
            .limit(limit)
        )
    )


@router.patch("/reports/{report_id}/review", response_model=WeatherReportOut)
def review_weather_report(
    report_id: int,
    payload: WeatherReportReviewRequest,
    db: DbSession,
    user: Annotated[User, Depends(require_roles("METEOROLOGIST"))],
):
    result = db.execute(
        update(WeatherReport)
        .where(WeatherReport.id == report_id, WeatherReport.status == "PENDING")
        .values(
            status=payload.status,
            review_notes=payload.review_notes,
            reviewer_id=user.id,
            reviewed_at=datetime.now(UTC),
        )
    )
    if result.rowcount != 1:
        db.rollback()
        if not db.get(WeatherReport, report_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Relato não encontrado"
            )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Relato já revisado")
    db.commit()
    return db.get(WeatherReport, report_id)
