from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class MovieRating(StrEnum):
    G = "G"
    PG = "PG"
    PG_13 = "PG-13"
    R = "R"


class MovieStatus(StrEnum):
    DRAFT = "draft"
    NOW_SHOWING = "now_showing"
    ARCHIVED = "archived"
    

class MovieBaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    description: str | None = None
    duration_minutes: int
    rating: MovieRating
    release_date: date | None = None
    status: MovieStatus
    genre: str
    country: str
    language: str
    director: str | None = None
    cast: str | None = None
    trailer_url: str | None = None
    poster_url: str | None = None
    backdrop_url: str | None = None


class MovieCreateSchema(MovieBaseSchema):
    pass

class MovieUpdateSchema(MovieBaseSchema):
    title: str | None = None
    description: str | None = None
    duration_minutes: int | None = None
    rating: MovieRating | None = None
    release_date: date | None = None
    status: MovieStatus | None = None
    genre: str | None = None
    country: str | None = None
    language: str | None = None
    director: str | None = None
    cast: str | None = None
    trailer_url: str | None = None
    poster_url: str | None = None
    backdrop_url: str | None = None

class MovieResponseSchema(MovieBaseSchema):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime