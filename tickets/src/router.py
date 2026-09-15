import datetime
import logging
import uuid

from aiomysql import IntegrityError
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tickets.src.database import get_admin_db
from tickets.src.helpers import get_or_create_user_uuid
from tickets.src.models import Auditorium, Screening, Seat, Ticket, User, Movie
# from tickets.src.receipts import generate_magic_link
from tickets.src.redis_client import get_redis
from tickets.src.redis_seats import (
    acquire_seats,
    are_screening_seats_warmed,
    change_seat_owner,
    close_screening_sale,
    extend_seat_hold,
    generate_owner_tag,
    get_user_held_seats,
    release_acquired_seats,
    release_all_seats,
    reserve_seat,
    release_seat,
    seat_exists,
    seat_id_from_key,
    stream_sse_events,
    are_screening_seats_warmed,
    warm_screening_seats,
)
from tickets.src.schemas import (
    ContactInfo,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    ScreeningSeatResponse,
    SessionResponse,
    TicketResponse,
)
from tickets.src.token import require_internal_service

logger = logging.getLogger(__name__)

router = APIRouter()
db_dependency = Depends(get_admin_db)
redis_dependency = Depends(get_redis)    
user_uuid_dependency: str = Depends(get_or_create_user_uuid)  

@router.get("/")
async def tickets_welcome():
    return {"message": "Hello from tickets's isolated router endpoint!", "data": []}


@router.get("/session", response_model=SessionResponse)
async def establish_ticket_session(
    user_uuid: str = user_uuid_dependency,
    db: AsyncSession = db_dependency,
):
    owner_tag = generate_owner_tag(user_uuid) if user_uuid else None

    try:
        account_uuid = uuid.UUID(str(user_uuid))
    except (TypeError, ValueError):
        logger.info("ticket session identified guest with invalid account cookie")
        return SessionResponse(authenticated=False, owner_tag=owner_tag)

    try:
        user = await db.execute(
            select(User.id, User.email, User.username).where(User.id == account_uuid)
        )
        user = user.one_or_none()
    except Exception:
        logger.exception("ticket session lookup failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ticket session service is temporarily unavailable.",
        ) from None

    if user is None:
        return SessionResponse(authenticated=False, owner_tag=owner_tag)

    return SessionResponse(
        authenticated=True,
        user_id=str(user.id),
        email=user.email,
        username=user.username,
        owner_tag=owner_tag,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    guest_uuid: str = user_uuid_dependency,
    redis: Redis = redis_dependency,
    db: AsyncSession = db_dependency,
):
    user = await db.scalar(select(User).where(User.email == payload.email))

    if user is None or not bcrypt.checkpw(
        payload.password.encode("utf-8"), user.password_hash.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    migrated_seat_count = await change_seat_owner(
        redis, guest_uuid, str(user.id)
    )

    response.set_cookie(
        key="user_uuid",
        value=str(user.id),
        max_age=3600 * 24 * 30,
        httponly=True,
        samesite="lax",
        secure=False,
    )

    return LoginResponse(
        user_id=str(user.id),
        email=user.email,
        username=user.username,
        migrated_seat_count=migrated_seat_count,
    )


@router.post("/register", response_model=LoginResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    response: Response,
    guest_uuid: str = user_uuid_dependency,
    redis: Redis = redis_dependency,
    db: AsyncSession = db_dependency,
):
    existing_user = await db.scalar(select(User).where(User.email == payload.email))
    if existing_user is not None:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    user = User(
        username=payload.username,
        email=payload.email,
        phone=payload.phone,
        password_hash=bcrypt.hashpw(payload.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
    )
    db.add(user)
    await db.flush()
    migrated_seat_count = await change_seat_owner(redis, guest_uuid, str(user.id))
    await db.commit()

    response.set_cookie(
        key="user_uuid",
        value=str(user.id),
        max_age=3600 * 24 * 30,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return LoginResponse(
        user_id=str(user.id),
        email=user.email,
        username=user.username,
        migrated_seat_count=migrated_seat_count,
    )

@router.post("/logout")
async def logout(
    response: Response):
    response.delete_cookie("user_uuid")
    return {"message": "Logged out successfully"}

@router.post("/release_seats", response_model=bool)
async def release_seats_endpoint(
    redis: Redis = redis_dependency,
    user_uuid: str = user_uuid_dependency
    ):
        await release_all_seats(redis, "*", user_uuid)
        return True

@router.get("/screenings/{screening_id}/availability/stream", 
            response_class=StreamingResponse)
async def stream_seat_availability(
    request: Request,
    screening_id: int, 
    last_event_id: str = "$", 
    redis: Redis = redis_dependency
) -> StreamingResponse:
    header_last_id = request.headers.get("last-event-id")
    effective_last_id = header_last_id or last_event_id or "$"
    return StreamingResponse(
        stream_sse_events(redis, str(screening_id), effective_last_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/screenings/{screening_id}/seats", response_model=list[str])
async def view_selected_seats(screening_id: int, user_uuid: str = user_uuid_dependency, 
                              redis: Redis = redis_dependency):
    my_held_seats = await get_user_held_seats(redis, str(screening_id), user_uuid)

    return my_held_seats


@router.get(
    "/screenings/{screening_id}/seat-map",
    response_model=list[ScreeningSeatResponse],
)
async def view_screening_seat_map(
    screening_id: int,
    db: AsyncSession = db_dependency,
    redis: Redis = redis_dependency,
):
    screening = await db.get(Screening, screening_id)
    if screening is None:
        raise HTTPException(status_code=404, detail="Screening not found")
    
    if await are_screening_seats_warmed(redis, str(screening_id)) == False:
        db_seating = await db.execute(
            select(Seat.id)
            .where(Seat.auditorium_id == screening.auditorium_id)
        )
        seat_ids = [row.id for row in db_seating]
        await warm_screening_seats(redis, str(screening_id), seat_ids)
        
    locked_seat_ids = {
    seat_id_from_key(key)
    async for key in redis.scan_iter(
        match=f"screening:{screening_id}::*"
    )
    }

    locked_seat_id_strings = set(locked_seat_ids)

    seat_rows = (
        await db.execute(
            select(
                Seat.id,
                Seat.id.label("seat_id"),
                Seat.row,
                Seat.number,
                Seat.is_available,
                Seat.is_accessible,
                Seat.x_pos,
                Seat.y_pos,
                Seat.angle,
            )
            .where(Seat.auditorium_id == screening.auditorium_id)
        )
    ).all()

    return [
        ScreeningSeatResponse(
            **row._mapping,
            status=(
                "locked" if str(row.seat_id) in locked_seat_id_strings
                else "available"
            ),
        )
        for row in seat_rows
    ]


@router.post("/screenings/{screening_id}/seats/{seat_id}/hold", response_model=bool)
async def hold_seat(
    screening_id: int,
    seat_id: str,
    db: AsyncSession = db_dependency,
    redis: Redis = redis_dependency,
    user_uuid: str = user_uuid_dependency,):

    logger.info(
        "hold seat requested: screening_id=%s seat_id=%s has_user_uuid=%s",
        screening_id,
        seat_id,
        bool(user_uuid),
    )

    if not await seat_exists(redis, str(screening_id), seat_id):
        logger.warning(
            "hold seat rejected: seat not in inventory: screening_id=%s seat_id=%s",
            screening_id,
            seat_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Seat does not exist for this screening",
        )

    purchased = await db.scalar(
        select(Ticket.seat_id).where(
            Ticket.screening_id == screening_id,
            Ticket.seat_id == int(seat_id),
        )
    )
    if purchased is not None:
        logger.info(
            "hold seat rejected: already purchased: screening_id=%s seat_id=%s",
            screening_id,
            seat_id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seat has already been purchased.",
        )

    try:
        success = await reserve_seat(redis, str(screening_id), seat_id, user_uuid)
    except RedisError:
        logger.exception(
            "hold seat Redis failure: screening_id=%s seat_id=%s",
            screening_id,
            seat_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Seat reservation service is temporarily unavailable.",
        ) from None
    logger.info(
        "hold seat result: screening_id=%s seat_id=%s held=%s",
        screening_id,
        seat_id,
        success,
    )
    return success


@router.delete("/screenings/{screening_id}/seats/{seat_id}/hold", response_model=bool)
async def release_held_seat(
    screening_id: int,
    seat_id: str,
    redis: Redis = redis_dependency,
    user_uuid: str = user_uuid_dependency,
):
    success = await release_seat(redis, str(screening_id), seat_id, user_uuid)
    return success


@router.post("/screenings/{screening_id}/seats/checkout", response_model=bool)
async def checkout_seats(screening_id: int, redis: Redis = redis_dependency, 
                         user_uuid: str = user_uuid_dependency):
    success = await extend_seat_hold(redis, str(screening_id), user_uuid)

    return success

@router.get("/screenings/{screening_id}/checkout/", response_model=list[str])
async def get_checkout(
    screening_id: int,
    user_uuid: str = user_uuid_dependency,
    redis: Redis = redis_dependency,
    db: AsyncSession = db_dependency,):
    held_seats = await get_user_held_seats(redis, str(screening_id), user_uuid)
    tickets = await db.execute(
        select(Seat).where(Seat.id.in_(held_seats))
        )
    
    return tickets.scalars().all()


@router.post("/screenings/{screening_id}/checkout/payment", 
             response_model=bool)
async def make_payment(
    screening_id: int,
    contact_info: ContactInfo,
    user_uuid: str = user_uuid_dependency,
    redis: Redis = redis_dependency,
    db: AsyncSession = db_dependency,
):
    held_seat_keys = await get_user_held_seats(redis, str(screening_id), user_uuid)
    if not held_seat_keys:
        return False

    checkout_id = str(uuid.uuid7())

    # For demonstration, we'll assume payment is always successful.
    extended_reservation = await extend_seat_hold(redis, str(screening_id), user_uuid, 3600)

    if not extended_reservation:
        return False
    
    try:
        seat_ids = [int(seat_id_from_key(seat_key)) for seat_key in held_seat_keys]
        
        async with db.begin():
            purchased_seat_ids = set(
                await db.scalars(
                    select(Ticket.seat_id).where(
                        Ticket.screening_id == screening_id,
                        Ticket.seat_id.in_(seat_ids),
                        Ticket.status != "cancelled",
                    )
                )
            )
        
            if purchased_seat_ids:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="One or more selected seats have already been purchased.",
                )

            tickets_to_add = [
                Ticket(
                    screening_id=screening_id,
                    seat_id=seat_id,
                    email=contact_info.email,
                    phone=contact_info.phone,
                    receipt_number=str(uuid.uuid7()),
                    status="confirmed",
                    checkout_id=checkout_id,
                    purchaser_uuid=uuid.UUID(user_uuid),
                )
                for seat_id in seat_ids
            ]
            db.add_all(tickets_to_add)

        success = await acquire_seats(redis, str(screening_id), user_uuid, checkout_id)
        if not success:
            return False

        # Generate magic links for all tickets
        # magic_links = {ticket.id: generate_magic_link(ticket.receipt_number) for ticket in tickets_to_add}

        # TODO: send email with the magic links to the user's email

        return True

    except IntegrityError:
        # Most likely a concurrent checkout won the race between
        # our SELECT and INSERT. The unique constraint is the final
        # protection against double-selling a seat.
        await db.rollback()

        await release_acquired_seats(
            redis,
            str(screening_id),
            checkout_id,
        )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "One or more selected seats have already "
                "been purchased."
            ),
        )

    except HTTPException:
        await db.rollback()

        await release_acquired_seats(
            redis,
            str(screening_id),
            checkout_id,
        )

        raise

    except Exception as exc:
        await db.rollback()

        logger.exception(
            "Payment ticket creation failed: screening_id=%s",
            screening_id,
        )

        await release_acquired_seats(
            redis,
            str(screening_id),
            checkout_id,
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Payment was accepted, but ticket creation failed. "
                "Seats were released."
            ),
        ) from exc


@router.delete("/screenings/{screening_id}/checkout/", response_model=bool)
async def cancel_checkout(
    screening_id: int,
    user_uuid: str = user_uuid_dependency,
    redis: Redis = redis_dependency):

    # Cancel the checkout and release held seats
    success = await release_all_seats(redis, str(screening_id), user_uuid)
    return success

@router.get("/purchases", response_model=list[TicketResponse])
async def get_tickets(
    user_uuid: str = user_uuid_dependency,
    db: AsyncSession = db_dependency,
):
    # Fetch all users tickets from the database based on held seats
    purchaser_uuid = uuid.UUID(user_uuid)
    tickets = await db.execute(
        select(Ticket)
        .options(selectinload(Ticket.screening), selectinload(Ticket.seat))
        .where(Ticket.purchaser_uuid == purchaser_uuid)
    )
    return tickets.scalars().all()


@router.get("/purchases/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: int,
    user_uuid: str = user_uuid_dependency,
    db: AsyncSession = db_dependency,
):
    purchaser_uuid = uuid.UUID(user_uuid)
    result = await db.execute(
        select(Ticket).where(
            Ticket.id == ticket_id,
            Ticket.purchaser_uuid == purchaser_uuid,
        )
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )
    return ticket


protected_router = APIRouter(dependencies=[Depends(require_internal_service)])

@protected_router.post(
    "/internal/screenings/{screening_id}/sale/open",
)
async def open_screening_sale(
    screening_id: int,
    db: AsyncSession = db_dependency,
    redis: Redis = redis_dependency,
):
    screening = await db.get(Screening, screening_id)
    if not screening:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screening not found",
        )
    if (
        screening.sale_start_time is not None and 
        screening.sale_start_time <= datetime.utcnow()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Screening is already on sale",
        )

    conflicting_screening = await db.scalar(
        select(Screening.id)
        .where(
            Screening.auditorium_id == screening.auditorium_id,
            Screening.id != screening_id,
            Screening.start_time < screening.end_time,
            Screening.end_time > screening.start_time,
        )
        .limit(1)
    )

    if conflicting_screening is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The auditorium is already booked during this time",
        )

    movie_duration = await db.scalar(
        select(Movie.duration_minutes).where(Movie.id == screening.movie_id)
    )

    screening_duration = (screening.end_time - screening.start_time).total_seconds() / 60

    if movie_duration < screening_duration:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Screening duration is shorter than the movie duration",
        )

    auditorium = await db.get(Auditorium, screening.auditorium_id)
    if auditorium is None or auditorium.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Auditorium is not available",
        )

    auditorium_seats = await db.execute(
        select(Auditorium).where(
            Auditorium.id == screening.auditorium_id).options(
            selectinload(Auditorium.seats))
    )
    auditorium = auditorium_seats.scalar_one()
    seat_ids = [seat.id for seat in auditorium.seats]

    await warm_screening_seats(redis, str(screening_id), seat_ids)
    return {
        "status": "ok",
        "screening_id": screening_id,
        "seat_count": len(seat_ids),
    }


@protected_router.post("/internal/screenings/{screening_id}/sale/close")
async def close_screening_sale_endpoint(
    screening_id: int,
    redis: Redis = redis_dependency,
    db: AsyncSession = db_dependency
):

    screening = await db.get(Screening, screening_id)
    if not screening:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screening not found",
        )
    
    if (screening.sale_start_time is None or screening.sale_end_time is None or 
        not (screening.sale_start_time <= datetime.utcnow() <= screening.sale_end_time)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Screening is not currently on sale",
        )
    
    deleted_count = await close_screening_sale(redis, str(screening_id))
    return {
        "status": "ok",
        "screening_id": screening_id,
        "deleted_count": deleted_count,
    }

@protected_router.post("/internal/{ticket_id}/redeem")
async def invalidate_ticket(ticket_id: str, db: AsyncSession = db_dependency):
    ticket = await db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    if ticket.status == "redeemed" or ticket.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticket is no longer valid for redemption",
        )
    
    ticket.status = "redeemed"
    await db.commit()
    return {"status": "ok"}

@protected_router.post("/payments/webhook", response_model=dict, 
    responses={200: {"description": "Payment webhook received successfully"}})
async def payment_webhook():
    return {"status": "success"}

@protected_router.post("/internal/cleanup", response_model=dict)
async def cleanup_internal(
    db: AsyncSession = db_dependency, redis: Redis = redis_dependency):

    # find all screenings that are past or cancelled
    result = await db.execute(
        select(Screening.id).where(
            (Screening.is_cancelled == True) | (Screening.end_time < datetime.utcnow())
        )
    )

    # next clear all the seats in redis for these screenings
    screening_ids = set(row[0] for row in result.fetchall())
    for screening_id in screening_ids:
        await close_screening_sale(redis, str(screening_id))

    return {"status": "ok"}