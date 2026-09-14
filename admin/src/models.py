from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Computed,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    select,
    text,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

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


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid7,
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("TRUE"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class MovieGenre(str, PyEnum):
    Action = "Action"
    Adventure = "Adventure"
    Animation = "Animation"
    Comedy = "Comedy"
    Crime = "Crime"
    Documentary = "Documentary"
    Drama = "Drama"
    Fantasy = "Fantasy"
    Horror = "Horror"
    Mystery = "Mystery"
    Romance = "Romance"
    Sci_Fi = "Sci-Fi"
    Thriller = "Thriller"
    War = "War"
    Western = "Western"
    Other = "Other"


class MovieCountry(str, PyEnum):
    Usa = "USA"
    Uk = "UK"
    Canada = "Canada"
    Australia = "Australia"
    France = "France"
    Germany = "Germany"
    Italy = "Italy"
    Spain = "Spain"
    Japan = "Japan"
    South_Korea = "South Korea"
    India = "India"
    China = "China"
    Israel = "Israel"
    Other = "Other"


class MovieLanguage(str, PyEnum):
    English = "English"
    Hebrew = "Hebrew"
    Arabic = "Arabic"
    French = "French"
    Spanish = "Spanish"
    German = "German"
    Italian = "Italian"
    Portuguese  = "Portuguese"
    Russian = "Russian"
    Japanese = "Japanese"
    Korean = "Korean"
    Chinese = "Chinese"
    Hindi = "Hindi"
    Other = "Other"


class Movie(Base):
    __tablename__ = "movies"

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
    status: Mapped[str] = mapped_column(
        Enum("draft", "now_showing","archived", name="movie_status_enum"),
        server_default="draft",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    tagline: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    genre: Mapped[MovieGenre] = mapped_column(
        Enum(MovieGenre, name="movie_genre_enum"),
        nullable=False,
    )

    country: Mapped[MovieCountry] = mapped_column(
    Enum(
        MovieCountry,
        values_callable=lambda enum_cls: [member.value for member in enum_cls],
    ),
    nullable=False,
)

    language: Mapped[MovieLanguage] = mapped_column(
        Enum(MovieLanguage, name="movie_language_enum"),
        nullable=False,
        server_default=MovieLanguage.English.value,
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


class Auditorium(Base):
    __tablename__ = "auditoriums"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("active", "frozen","inactive", name="auditorium_status_enum"),
        nullable=False,
        server_default=text("'active'"),
    )

    # Relationships
    seats: Mapped[list[Seat]] = relationship(
        "Seat",
        back_populates="auditorium",
        cascade="all, delete-orphan",
    )

    # Dynamic properties
    @hybrid_property
    def total_capacity(self):
        return len(self.seats)

    @total_capacity.inplace.expression
    @classmethod
    def _total_capacity_expression(cls):
        return (
            select(func.count(Seat.id))
            .where(Seat.auditorium_id == cls.id)
            .label("total_capacity")
        )

    # 3. Dynamic property for accessibility (True if >= 1 seat is accessible)
    @hybrid_property
    def is_accessible(self):
        return any(seat.is_accessible and seat.is_available for seat in self.seats)

    @is_accessible.inplace.expression
    @classmethod
    def _is_accessible_expression(cls):
        return select(func.count(Seat.id) > 0).where(
            Seat.auditorium_id == cls.id,
            Seat.is_accessible,
            Seat.is_available,
        ).scalar_subquery()
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class Seat(Base):
    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint(
            "auditorium_id",
            "row",
            "number",
            name="uq_seat_auditorium_row_number",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    auditorium_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("auditoriums.id", ondelete="CASCADE"),
        nullable=False,
    )
    row: Mapped[str] = mapped_column(String(5), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, 
                                               server_default=text("TRUE"))
    is_accessible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("TRUE"),
    )

    x_pos: Mapped[int] = mapped_column(Integer, nullable=False)
    y_pos: Mapped[int] = mapped_column(Integer, nullable=False)
    angle: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    auditorium: Mapped[Auditorium] = relationship(
        "Auditorium", back_populates="seats")


class Screening(Base):
    __tablename__ = "screenings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    movie_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("movies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    auditorium_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("auditoriums.id", ondelete="RESTRICT"),
        nullable=False,
    )
    start_time: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=12.50,
        nullable=False,
    )
    sale_start_time: Mapped[datetime | None] = mapped_column(DateTime, index=True, nullable=True)
    sale_end_time: Mapped[datetime | None] = mapped_column(DateTime, index=True, nullable=True)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))

    # Relationships
    movie: Mapped[Movie] = relationship("Movie")
    auditorium: Mapped[Auditorium] = relationship("Auditorium")


class Ticket(Base):
    __tablename__ = "tickets"

    __table_args__ = (
    UniqueConstraint(
        "screening_id",
        "active_seat_id",
        name="unique_active_ticket_seat_per_screening",
    ),
)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    receipt_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    checkout_id: Mapped[str] = mapped_column(String(50), nullable=True)
    purchaser_uuid: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        index=True,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        Enum("confirmed", "cancelled","redeemed", name="ticket_status_enum"),
        server_default="confirmed",
        nullable=False,
    )

    screening_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("screenings.id", ondelete="RESTRICT"),
        nullable=False,
    )

    seat_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("seats.id", ondelete="RESTRICT"),
        nullable=False,
    )

    active_seat_id: Mapped[int | None] = mapped_column(
    Integer,
    Computed(
        "CASE WHEN status = 'cancelled' THEN NULL ELSE seat_id END",
        persisted=True,
    ),
)
    screening: Mapped[Screening] = relationship("Screening")
    seat: Mapped[Seat] = relationship("Seat")

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )