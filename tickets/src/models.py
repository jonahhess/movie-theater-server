from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid7)
    username: Mapped[str] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = {"extend_existing": True}

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


class Screening(Base):
    __tablename__ = "screenings"
    __table_args__ = {"extend_existing": True}

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
    
    sale_start_time: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=True)
    sale_end_time: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=True)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))


class Auditorium(Base):
    __tablename__ = "auditoriums"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    status: Mapped[str] = mapped_column(
        Enum("active", "frozen","inactive", name="movie_status_enum"),
        nullable=False,
        server_default=text("'active'"),
    )
    # Relationships
    seats: Mapped[list[Seat]] = relationship(
        "Seat",
        back_populates="auditorium",
        cascade="all, delete-orphan",
    )

class Seat(Base):
    __tablename__ = "seats"
    __table_args__ = {"extend_existing": True}

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
        server_default=text("FALSE"),
    )

    x_pos: Mapped[int] = mapped_column(Integer, nullable=False)
    y_pos: Mapped[int] = mapped_column(Integer, nullable=False)
    angle: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    auditorium: Mapped[Auditorium] = relationship(
        "Auditorium", back_populates="seats")

class Movie(Base):
    __tablename__ = "movies"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    