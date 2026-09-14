from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from admin.src.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    # UUIDv7 is the single, direct primary key
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid7
    )
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


# View filters based on status=now_showing
class MovieView(Base):
    __tablename__ = "movies_public_view"
    __table_args__ = {"info": {"is_view": True}} 

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    rating: Mapped[str] = mapped_column(
        Enum("G", "PG", "PG-13", "R", name="movie_rating_enum"),
        nullable=False,
        server_default="PG-13",
    )
    release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    tagline: Mapped[str | None] = mapped_column(
            String(500),
            nullable=True,
    )
    
    genre: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    country: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    language: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="English",
    )

    imdb_rating: Mapped[Decimal | None] = mapped_column(
        Numeric(3, 1),
        nullable=True,
    )

    rotten_tomatoes_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    director: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cast: Mapped[str | None] = mapped_column(String(255), nullable=True)

    trailer_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    poster_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    backdrop_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    

# view based on is_active
class AuditoriumView(Base):
    __tablename__ = "auditoriums_public_view"
    __table_args__ = {"info": {"is_view": True}} 

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_accessible: Mapped[bool] = mapped_column(Boolean, nullable=False)


# only show viewings based on start_time and status=on_sale
class ScreeningView(Base):
    __tablename__ = "screenings_public_view"
    __table_args__ = {"info": {"is_view": True}} 

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    movie_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("movies_public_view.id", ondelete="RESTRICT"),
        nullable=False,
    )
    auditorium_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("auditoriums_public_view.id", ondelete="RESTRICT"),
        nullable=False,
    )
    start_time: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=12.50,
        nullable=False,
    )

    # Relationships
    movie: Mapped[MovieView] = relationship(
        "MovieView",
        primaryjoin=lambda: foreign(ScreeningView.movie_id) == MovieView.id,
        viewonly=True,
    )
    auditorium: Mapped[AuditoriumView] = relationship(
        "AuditoriumView",
        primaryjoin=lambda: foreign(ScreeningView.auditorium_id) == AuditoriumView.id,
        viewonly=True,
    )
