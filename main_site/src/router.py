from datetime import date, datetime, time, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BeforeValidator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from main_site.src.database import get_read_db
from main_site.src.models import MovieView, ScreeningView
from main_site.src.schemas import (
    MovieResponse,
    MoviesListResponse,
    ScreeningResponse,
    ScreeningsListResponse,
    )

router = APIRouter(prefix="/api/v1")
db_dependency = Depends(get_read_db)


@router.get("/")
async def home():
    return {
        "message": "Welcome to the movie theater main site API.",
        "routes": {
            "movies": "/movies",
            "movie_details": "/movies/{movie_id}",
            "movie_screenings": "/movies/{movie_id}/screenings",
            "screenings": "/screenings",
            "screening_details": "/screenings/{screening_id}",
        },
    }

@router.get("/movies", response_model=MoviesListResponse)
async def browse_movies(
    rating: Annotated[Literal["G", "PG", "PG-13", "R"] | None, Query()] = None,
    release_year: Annotated[int | Literal["null"] | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=100)] = 0,
    db: AsyncSession = db_dependency,
):

    if release_year == "null":
        release_year = None

    count_stmt = select(func.count()).select_from(MovieView)
    list_stmt = select(MovieView)

    if rating is not None:
        count_stmt = count_stmt.where(MovieView.rating == rating)
        list_stmt = list_stmt.where(MovieView.rating == rating)

    if release_year is not None:
        year_filter = func.extract(
            "year", MovieView.release_date
        ) == release_year

        count_stmt = count_stmt.where(year_filter)
        list_stmt = list_stmt.where(year_filter)

    total = await db.scalar(count_stmt) or 0

    items = (
        await db.scalars(
            list_stmt
            .order_by(MovieView.release_date.desc(), MovieView.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()

    return MoviesListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )


@router.get("/movies/{movie_id}", response_model=MovieResponse, 
            responses={404: {"description": "Movie not found"}})
async def movie_details(movie_id: int, db: AsyncSession = db_dependency):
    movie = await db.scalar(select(MovieView).where(MovieView.id == movie_id))

    if movie is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movie {movie_id} was not found",
        )
    return movie


@router.get("/movies/{movie_id}/screenings", response_model=ScreeningsListResponse,
            responses={404: {"description": "Movie not found"}})
async def movie_screenings(
    movie_id: int,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=100)] = 0,
    db: AsyncSession = db_dependency,
):
    movie_exists = await db.scalar(select(MovieView.id).where(MovieView.id == movie_id))
    if movie_exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movie {movie_id} was not found",
        )

    count_stmt = (
        select(func.count())
        .select_from(ScreeningView)
        .where(ScreeningView.movie_id == movie_id)
    )
    list_stmt = (
        select(ScreeningView)
        .options(selectinload(ScreeningView.auditorium), selectinload(ScreeningView.movie))
        .where(ScreeningView.movie_id == movie_id)
        .order_by(ScreeningView.start_time.asc(), ScreeningView.id.asc())
        .offset(offset)
        .limit(limit)
    )

    total = await db.scalar(count_stmt) or 0
    items = (await db.scalars(list_stmt)).all()

    return ScreeningsListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )


@router.get("/screenings", response_model=ScreeningsListResponse)
async def browse_screenings(
    movie_id: Annotated[int | None, Query()] = None,
    start_date: Annotated[date | None,  Query(), 
                          BeforeValidator(lambda v: None if v == "null" else v),
] = None,
    end_date: Annotated[date | None, Query(), 
                        BeforeValidator(lambda v: None if v == "null" else v),
] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=100)] = 0,
    db: AsyncSession = db_dependency,
):

    count_stmt = select(func.count()).select_from(ScreeningView)
    list_stmt = (
        select(ScreeningView)
        .options(selectinload(ScreeningView.auditorium), selectinload(ScreeningView.movie))
        .order_by(ScreeningView.start_time.asc(), 
                  ScreeningView.id.asc())
        .offset(offset)
        .limit(limit)
    )

    if movie_id is not None:
        count_stmt = count_stmt.where(ScreeningView.movie_id == movie_id)
        list_stmt = list_stmt.where(ScreeningView.movie_id == movie_id)

    if start_date is not None:
        start_dt = datetime.combine(start_date, time.min)
        count_stmt = count_stmt.where(ScreeningView.start_time >= start_dt)
        list_stmt = list_stmt.where(ScreeningView.start_time >= start_dt)

    if end_date is not None:
        # Inclusive end-of-day filter by bounding to the next day.
        end_dt_exclusive = datetime.combine(
            end_date + timedelta(days=1),
            time.min,
        )
        count_stmt = count_stmt.where(
            ScreeningView.start_time < end_dt_exclusive
        )
        list_stmt = list_stmt.where(
            ScreeningView.start_time < end_dt_exclusive
        )

    total = await db.scalar(count_stmt) or 0
    items = (await db.scalars(list_stmt)).all()

    return ScreeningsListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )


@router.get("/screenings/{screening_id}", response_model=ScreeningResponse, 
            responses={404: {"description": "Screening not found"}})
async def screening_details(screening_id: int, db: AsyncSession = db_dependency):
    screening = await db.scalar(
        select(ScreeningView)
        .options(selectinload(ScreeningView.auditorium), selectinload(ScreeningView.movie))
        .where(ScreeningView.id == screening_id)
    )

    if screening is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Screening {screening_id} was not found",
        )
    return screening