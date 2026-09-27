import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    renter = "renter"
    owner = "owner"
    admin = "admin"


class MachineCategory(str, enum.Enum):
    tractor = "tractor"
    excavator = "excavator"
    backhoe = "backhoe"
    bulldozer = "bulldozer"
    loader = "loader"
    crane = "crane"
    harvester = "harvester"
    dump_truck = "dump_truck"
    other = "other"


class BookingStatus(str, enum.Enum):
    requested = "requested"  # renter asked, waiting for owner
    accepted = "accepted"  # owner confirmed; slot is reserved
    rejected = "rejected"
    cancelled = "cancelled"
    in_progress = "in_progress"  # operator on site
    completed = "completed"


# Statuses that block the machine's calendar.
ACTIVE_BOOKING_STATUSES = (BookingStatus.requested, BookingStatus.accepted, BookingStatus.in_progress)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(32))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.renter)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    machines: Mapped[list["Machine"]] = relationship(back_populates="owner")


class Machine(Base):
    __tablename__ = "machines"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    category: Mapped[MachineCategory] = mapped_column(Enum(MachineCategory), index=True)
    make: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(80))
    year: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    # Prices are stored in minor units (cents) to avoid float rounding.
    hourly_rate_cents: Mapped[int] = mapped_column(Integer)
    daily_rate_cents: Mapped[int] = mapped_column(Integer)
    # Base location; operator travels from here. Replace with PostGIS geography when scaling.
    latitude: Mapped[float] = mapped_column(Float, index=True)
    longitude: Mapped[float] = mapped_column(Float, index=True)
    service_radius_km: Mapped[float] = mapped_column(Float, default=50)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    owner: Mapped[User] = relationship(back_populates="machines")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="machine")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id"), index=True)
    renter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    site_address: Mapped[str] = mapped_column(String(255))
    site_latitude: Mapped[float] = mapped_column(Float)
    site_longitude: Mapped[float] = mapped_column(Float)
    job_notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[BookingStatus] = mapped_column(Enum(BookingStatus), default=BookingStatus.requested, index=True)
    subtotal_cents: Mapped[int] = mapped_column(Integer)
    platform_fee_cents: Mapped[int] = mapped_column(Integer)
    total_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    machine: Mapped[Machine] = relationship(back_populates="bookings")
    renter: Mapped[User] = relationship()
    review: Mapped["Review | None"] = relationship(back_populates="booking")


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), unique=True)
    rating: Mapped[int] = mapped_column(Integer)  # 1..5
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    booking: Mapped[Booking] = relationship(back_populates="review")
