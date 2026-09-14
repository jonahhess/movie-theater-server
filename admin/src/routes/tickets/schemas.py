from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TicketStatus(StrEnum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    REDEEMED = "redeemed"


class TicketUpdate(BaseModel):
    email: str | None = None
    phone: str | None = None
    status: TicketStatus | None = None


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    screening_id: int
    seat_id: int
    email: str
    phone: str | None = None
    receipt_number: str
    checkout_id: str | None = None
    purchaser_uuid: UUID | None = None
    status: TicketStatus
    created_at: datetime
