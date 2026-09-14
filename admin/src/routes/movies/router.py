from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_admin_db
from ...exceptions import NotFoundError
from ...models import Movie
from .schemas import MovieCreateSchema, MovieResponseSchema, MovieUpdateSchema

router = APIRouter(prefix="/movies")

db_dependency = Depends(get_admin_db)

@router.get("", response_model=list[MovieResponseSchema])
async def list_movies(db: AsyncSession = db_dependency):
    movies = (await db.scalars(select(Movie))).all()
    return movies


@router.get("/{movie_id}", response_model=MovieResponseSchema)
async def get_movie(movie_id: int, db: AsyncSession = db_dependency):
    movie = await db.scalar(select(Movie).where(Movie.id == movie_id))

    if movie is None:
        raise NotFoundError("Movie", movie_id)

    return movie


@router.post("", response_model=MovieResponseSchema)
async def create_movie(movie: MovieCreateSchema, db: AsyncSession = db_dependency):
    new_movie = Movie(**movie.model_dump(exclude_unset=True))
    db.add(new_movie)
    try:
        await db.commit()
        await db.refresh(new_movie)
    except Exception as err:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Movie already exists",
        ) from err
    return new_movie

@router.patch("/{movie_id}", response_model=MovieResponseSchema)
async def update_movie(
    movie_id: int, movie: MovieUpdateSchema, db: AsyncSession = db_dependency):
    existing_movie = await db.scalar(select(Movie).where(Movie.id == movie_id))

    if existing_movie is None:
        raise NotFoundError("Movie", movie_id)

    for key, value in movie.model_dump(exclude_unset=True).items():
        setattr(existing_movie, key, value)
    await db.commit()
    await db.refresh(existing_movie)
    return existing_movie


@router.delete("/{movie_id}", status_code=204)
async def delete_movie(movie_id: int, db: AsyncSession = db_dependency):
    movie = await db.scalar(select(Movie).where(Movie.id == movie_id))

    if movie is None:
        raise NotFoundError("Movie", movie_id)

    await db.delete(movie)
    await db.commit()
    return None
