from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ScreeningCreate(BaseModel):
    movie_id: int
    auditorium_id: int
    start_time: datetime
    end_time: datetime
    price: Decimal
    sale_start_time: datetime | None = None
    sale_end_time: datetime | None = None
    is_cancelled: bool = False


class ScreeningUpdate(BaseModel):
    movie_id: int | None = None
    auditorium_id: int | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    price: Decimal | None = None
    sale_start_time: datetime | None = None
    sale_end_time: datetime | None = None
    is_cancelled: bool | None = None


class ScreeningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    movie_id: int
    auditorium_id: int
    start_time: datetime
    end_time: datetime
    price: Decimal
    sale_start_time: datetime | None
    sale_end_time: datetime | None
    is_cancelled: bool
