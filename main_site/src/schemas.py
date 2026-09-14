from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class MovieResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None = None
    duration_minutes: int
    rating: str
    release_date: date | None = None
    genre: str
    country: str
    language: str
    poster_url: str | None = None
    trailer_url: str | None = None
    backdrop_url: str | None = None
    tagline: str | None = None
    director: str | None = None
    cast: str | None = None



class MovieListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[MovieResponse]

class AuditoriumResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_accessible: bool

class ScreeningResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    movie_id: int
    auditorium_id: int
    start_time: datetime
    price: Decimal
    auditorium: AuditoriumResponse
    movie: MovieResponse


class MoviesListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[MovieResponse]


class ScreeningsListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ScreeningResponse]