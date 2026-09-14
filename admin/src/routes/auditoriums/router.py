from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...database import get_admin_db
from ...exceptions import NotFoundError
from ...models import Auditorium, Screening, Seat, Ticket
from .schemas import (
    AuditoriumCreateSchema,
    AuditoriumResponse,
    AuditoriumUpdateSchema,
    AuditoriumWithSeats,
    GenerateSeatsSchema,
    SeatBase,
    SeatResponse,
    SeatUpdate,
)

router = APIRouter(prefix="/auditoriums")

db_dependency = Depends(get_admin_db)


async def ensure_seat_map_editable(
    auditorium_id: int,
    db: AsyncSession,
) -> None:
    sale_is_open = await db.scalar(
        select(Screening.id)
        .where(
            Screening.auditorium_id == auditorium_id,
            Screening.sale_start_time <= func.now(),
            Screening.sale_end_time >= func.now(),
        )
        .limit(1)
    )
    if sale_is_open is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "This seat map cannot be changed while ticket sales are open. "
                "Close the affected sale before editing seats."
            ),
        )

    has_paid_tickets = await db.scalar(
        select(Ticket.id)
        .join(Seat, Ticket.seat_id == Seat.id)
        .join(Screening, Ticket.screening_id == Screening.id)
        .where(
            Seat.auditorium_id == auditorium_id,
            Ticket.status != "cancelled",
            Screening.sale_start_time <= func.now(),
            Screening.sale_end_time >= func.now(),
        )
        .limit(1)
    )
    if has_paid_tickets is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "This seat map cannot be changed because paid tickets exist. "
                "Cancel or refund affected tickets before changing seats."
            ),
        )

@router.get("", response_model=list[AuditoriumResponse])
async def list_auditoriums(db: AsyncSession = db_dependency):
    auditoriums = (
        await db.scalars(
            select(Auditorium).options(selectinload(Auditorium.seats))
        )
    ).all()
    return auditoriums


@router.post("", response_model=AuditoriumResponse)
async def create_auditorium(
    auditorium: AuditoriumCreateSchema, db: AsyncSession = db_dependency):
    auditorium = Auditorium(**auditorium.model_dump(exclude_unset=True))
    db.add(auditorium)
    await db.flush()
    created_auditorium_id = auditorium.id
    await db.commit()
    return await db.scalar(
        select(Auditorium)
        .options(selectinload(Auditorium.seats))
        .where(Auditorium.id == created_auditorium_id)
    )


@router.get("/{auditorium_id}", response_model=AuditoriumResponse)
async def get_auditorium(
    auditorium_id: int, db: AsyncSession = db_dependency):
    auditorium = await db.scalar(
        select(Auditorium)
        .options(selectinload(Auditorium.seats))
        .where(Auditorium.id == auditorium_id))

    if auditorium is None:
        raise NotFoundError("Auditorium", auditorium_id)

    return auditorium


@router.patch("/{auditorium_id}", response_model=AuditoriumResponse)
async def update_auditorium(
    auditorium_id: int, 
    auditorium: AuditoriumUpdateSchema, 
    db: AsyncSession = db_dependency):
    existing_auditorium = await db.scalar(
        select(Auditorium)
        .options(selectinload(Auditorium.seats))
        .where(Auditorium.id == auditorium_id))

    if existing_auditorium is None:
        raise NotFoundError("Auditorium", auditorium_id)

    for key, value in auditorium.model_dump(exclude_unset=True).items():
        setattr(existing_auditorium, key, value)
    await db.commit()
    return await db.scalar(
        select(Auditorium)
        .options(selectinload(Auditorium.seats))
        .where(Auditorium.id == auditorium_id)
    )


@router.delete("/{auditorium_id}", status_code=204)
async def delete_auditorium(auditorium_id: int, db: AsyncSession = db_dependency):
    auditorium = await db.scalar(
        select(Auditorium).where(Auditorium.id == auditorium_id))

    if auditorium is None:
        raise NotFoundError("Auditorium", auditorium_id)

    await db.delete(auditorium)
    await db.commit()
    return None

@router.get("/{auditorium_id}/seats", response_model=AuditoriumWithSeats)
async def get_seats(auditorium_id: int, db: AsyncSession = db_dependency):
    auditorium = await db.scalar(
        select(Auditorium)
        .options(selectinload(Auditorium.seats))
        .where(Auditorium.id == auditorium_id))

    if auditorium is None:
        raise NotFoundError("Auditorium", auditorium_id)

    return auditorium

@router.post(
    "/{auditorium_id}/seats",
    response_model=SeatResponse)
async def create_seat(
    auditorium_id: int,
    seat_data: SeatBase,
    db: AsyncSession = db_dependency,
):
    await ensure_seat_map_editable(auditorium_id, db)
    auditorium = await db.scalar(
        select(Auditorium).where(Auditorium.id == auditorium_id))

    if auditorium is None:
        raise NotFoundError("Auditorium", auditorium_id)

    new_seat = Seat(auditorium_id=auditorium_id, **seat_data.model_dump())
    db.add(new_seat)
    await db.commit()
    await db.refresh(new_seat)
    return new_seat

@router.put("/{auditorium_id}/seats", response_model=AuditoriumWithSeats)
async def replace_seats(
    auditorium_id: int, seats: list[SeatBase], db: AsyncSession = db_dependency):
    await ensure_seat_map_editable(auditorium_id, db)
    auditorium = await db.scalar(
        select(Auditorium).where(Auditorium.id == auditorium_id))

    if auditorium is None:
        raise NotFoundError("Auditorium", auditorium_id)

    auditorium.seats = [Seat(auditorium_id=auditorium_id, 
                             **seat.model_dump()) for seat in seats]
    await db.commit()
    return await db.scalar(
        select(Auditorium)
        .options(selectinload(Auditorium.seats))
        .where(Auditorium.id == auditorium_id)
    )

@router.get("/{auditorium_id}/seats/{seat_id}", response_model=SeatResponse)
async def get_seat(
    auditorium_id: int, seat_id: int, db: AsyncSession = db_dependency):
        seat = await db.scalar(
        select(Seat)
        .where(Seat.id == seat_id, Seat.auditorium_id == auditorium_id))

        if seat is None:
            raise NotFoundError("Seat", seat_id)

        return seat

@router.patch("/{auditorium_id}/seats/{seat_id}", response_model=SeatResponse)
async def update_seat(
    auditorium_id: int, 
    seat_id: int, seat_data: SeatUpdate, 
    db: AsyncSession = db_dependency):
    await ensure_seat_map_editable(auditorium_id, db)
    seat = await db.scalar(
        select(Seat)
        .where(Seat.id == seat_id, Seat.auditorium_id == auditorium_id))

    if seat is None:
        raise NotFoundError("Seat", seat_id)

    for key, value in seat_data.model_dump(exclude_unset=True).items():
        setattr(seat, key, value)
    await db.commit()
    await db.refresh(seat)
    return seat

@router.delete("/{auditorium_id}/seats/{seat_id}", status_code=204)
async def delete_seat(
    auditorium_id: int, seat_id: int, db: AsyncSession = db_dependency):
    await ensure_seat_map_editable(auditorium_id, db)
    seat = await db.scalar(
        select(Seat)
        .where(Seat.id == seat_id, Seat.auditorium_id == auditorium_id))

    if seat is None:
        raise NotFoundError("Seat", seat_id)

    await db.delete(seat)
    await db.commit()
    return None


@router.post("/{auditorium_id}/seats/generate", response_model=AuditoriumWithSeats)
async def generate_seat_layout(
    auditorium_id: int,
    config: GenerateSeatsSchema,
    db: AsyncSession = db_dependency,
):
    await ensure_seat_map_editable(auditorium_id, db)
    auditorium = await db.scalar(
        select(Auditorium)
        .options(selectinload(Auditorium.seats))
        .where(Auditorium.id == auditorium_id)
    )

    if auditorium is None:
        raise NotFoundError("Auditorium", auditorium_id)

    generated_seats: list[Seat] = []
    for r_idx in range(config.row_count):
        row_letter = chr(65 + r_idx) if r_idx < 26 else f"R{r_idx + 1}"
        y = config.y_offset + r_idx * config.row_spacing
        for s_idx in range(1, config.seats_per_row + 1):
            x = config.x_offset + (s_idx - 1) * config.seat_spacing
            generated_seats.append(
                Seat(
                    auditorium_id=auditorium_id,
                    row=row_letter,
                    number=s_idx,
                    x_pos=x,
                    y_pos=y,
                    angle=0,
                    is_available=True,
                    is_accessible=row_letter in config.accessible_rows,
                )
            )

    auditorium.seats = generated_seats
    await db.commit()
    return await db.scalar(
        select(Auditorium)
        .options(selectinload(Auditorium.seats))
        .where(Auditorium.id == auditorium_id)
    )

