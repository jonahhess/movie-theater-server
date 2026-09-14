from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_admin_db
from ...exceptions import NotFoundError
from ...models import Ticket
from .schemas import TicketResponse, TicketUpdate

router = APIRouter(prefix="/tickets")
db_dependency = Depends(get_admin_db)


@router.get("", response_model=list[TicketResponse])
async def list_tickets(db: AsyncSession = db_dependency):
    tickets = (await db.scalars(select(Ticket).order_by(Ticket.id.desc()))).all()
    return tickets


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: int, db: AsyncSession = db_dependency):
    ticket = await db.scalar(select(Ticket).where(Ticket.id == ticket_id))
    if ticket is None:
        raise NotFoundError("Ticket", ticket_id)
    return ticket


@router.patch("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(
    ticket_id: int,
    ticket_data: TicketUpdate,
    db: AsyncSession = db_dependency,
):
    ticket = await db.scalar(select(Ticket).where(Ticket.id == ticket_id))
    if ticket is None:
        raise NotFoundError("Ticket", ticket_id)

    for key, value in ticket_data.model_dump(exclude_unset=True).items():
        setattr(ticket, key, value)

    await db.commit()
    await db.refresh(ticket)
    return ticket


@router.delete("/{ticket_id}", status_code=204)
async def delete_ticket(ticket_id: int, db: AsyncSession = db_dependency):
    ticket = await db.scalar(select(Ticket).where(Ticket.id == ticket_id))
    if ticket is None:
        raise NotFoundError("Ticket", ticket_id)

    await db.delete(ticket)
    await db.commit()
    return None
