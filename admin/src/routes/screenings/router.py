import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_admin_db
from ...exceptions import NotFoundError
from ...models import Auditorium, Movie, Screening, Ticket
from .schemas import ScreeningCreate, ScreeningResponse, ScreeningUpdate

router = APIRouter(prefix="/screenings")
db_dependency = Depends(get_admin_db)
TICKETS_BASE_URL = os.getenv("TICKETS_BASE_URL", "http://127.0.0.1:8000/tickets")
INTERNAL_SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN")


async def ensure_screening_editable(
    screening: Screening,
    db: AsyncSession,
) -> None:
    if screening.sale_start_time is not None and screening.sale_end_time is None and screening.sale_start_time <= datetime.now():
        raise HTTPException(
            status_code=409,
            detail=(
                "This screening cannot be changed while ticket sales are open. "
                "Close the sale before editing it."
            ),
        )

    has_paid_tickets = await db.scalar(
        select(Ticket.id)
        .where(
            Ticket.screening_id == screening.id,
            Ticket.status != "cancelled",
        )
        .limit(1)
    )
    if has_paid_tickets is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "This screening cannot be changed because paid tickets exist. "
                "Cancel or refund affected tickets before making this change."
            ),
        )


async def ensure_screening_references_active(
    screening: Screening,
    db: AsyncSession,
) -> None:
    movie_status = await db.scalar(
        select(Movie.status).where(Movie.id == screening.movie_id)
    )
    if movie_status != "now_showing":
        raise HTTPException(
            status_code=409,
            detail="The screening movie must be now showing before sales can open.",
        )

    auditorium_active = await db.scalar(
        select(Auditorium.status).where(Auditorium.id == screening.auditorium_id)
    )
    if auditorium_active != "active":
        raise HTTPException(
            status_code=409,
            detail="The screening auditorium must be active before sales can open.",
        )

@router.get("", response_model=list[ScreeningResponse])
async def list_screenings(db: AsyncSession = db_dependency):
    screenings = (await db.scalars(select(Screening))).all()
    return screenings

@router.post("", response_model=ScreeningResponse)
async def create_screening(
    screening: ScreeningCreate, db: AsyncSession = db_dependency):
    if screening.sale_start_time is not None and screening.sale_end_time is None and screening.sale_start_time <= datetime.now():
        raise HTTPException(
            status_code=409,
            detail="Cannot create a screening while ticket sales are open.",
        )
    screening = Screening(**screening.model_dump(exclude_unset=True))
    db.add(screening)
    try:
        await db.commit()
        await db.refresh(screening)
    except Exception as err:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Screening already exists",
        ) from err
    return screening

@router.get("/{screening_id}", response_model=ScreeningResponse)
async def get_screening(screening_id: int, db: AsyncSession = db_dependency):
    screening = await db.scalar(
        select(Screening).where(Screening.id == screening_id))

    if screening is None:
        raise NotFoundError("Screening", screening_id)  

    return screening

@router.patch("/{screening_id}", response_model=ScreeningResponse)
async def update_screening(
    screening_id: int, screening: ScreeningUpdate, db: AsyncSession = db_dependency):
    existing_screening = await db.scalar(
        select(Screening).where(Screening.id == screening_id))

    if existing_screening is None:
        raise NotFoundError("Screening", screening_id)

    await ensure_screening_editable(existing_screening, db)

    existing_start_time = existing_screening.sale_start_time
    existing_end_time = existing_screening.sale_end_time

    if screening.sale_start_time is None:
        screening.sale_start_time = existing_start_time
    if screening.sale_end_time is None:
        screening.sale_end_time = existing_end_time

    if (screening.sale_start_time is None) != (screening.sale_end_time is None):
        raise HTTPException(
            status_code=409,
            detail="Both sale_start_time and sale_end_time must be set together or both be None.",
        )

    if screening.sale_end_time is not None and screening.sale_start_time is not None and \
       screening.sale_end_time <= screening.sale_start_time:
        raise HTTPException(
            status_code=409,
            detail="sale end time must be after sale start time.",
        )

    for key, value in screening.model_dump(exclude_unset=True).items():
        setattr(existing_screening, key, value)
    await db.commit()
    await db.refresh(existing_screening)
    return existing_screening



@router.delete("/{screening_id}", status_code=204)
async def delete_screening(screening_id: int, db: AsyncSession = db_dependency):
    existing_screening = await db.scalar(
        select(Screening).where(Screening.id == screening_id))

    if existing_screening is None:
        raise NotFoundError("Screening", screening_id)

    await ensure_screening_editable(existing_screening, db)
    await db.delete(existing_screening)
    await db.commit()
    return None
