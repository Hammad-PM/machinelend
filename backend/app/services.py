"""Domain logic kept separate from HTTP routing so it's easy to unit test."""
import math
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ACTIVE_BOOKING_STATUSES, Booking, BookingStatus, Machine

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def bounding_box(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    """Cheap lat/lon box used to pre-filter rows in SQL before the exact distance check."""
    dlat = math.degrees(radius_km / EARTH_RADIUS_KM)
    cos_lat = max(math.cos(math.radians(lat)), 1e-6)
    dlon = math.degrees(radius_km / (EARTH_RADIUS_KM * cos_lat))
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon


def as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def quote(machine: Machine, start_at: datetime, end_at: datetime) -> dict:
    """Full days charged at the daily rate; leftover hours at the hourly rate, capped at one day."""
    hours = (as_utc(end_at) - as_utc(start_at)).total_seconds() / 3600
    full_days, leftover_hours = divmod(hours, 24)
    leftover_cost = min(math.ceil(leftover_hours) * machine.hourly_rate_cents, machine.daily_rate_cents)
    subtotal = int(full_days) * machine.daily_rate_cents + leftover_cost
    fee = round(subtotal * settings.platform_fee_rate)
    return {
        "hours": round(hours, 2),
        "subtotal_cents": subtotal,
        "platform_fee_cents": fee,
        "total_cents": subtotal + fee,
        "currency": settings.currency,
    }


def has_conflict(db: Session, machine_id: int, start_at: datetime, end_at: datetime,
                 exclude_booking_id: int | None = None) -> bool:
    stmt = select(Booking.id).where(
        Booking.machine_id == machine_id,
        Booking.status.in_(ACTIVE_BOOKING_STATUSES),
        Booking.start_at < end_at,
        Booking.end_at > start_at,
    )
    if exclude_booking_id is not None:
        stmt = stmt.where(Booking.id != exclude_booking_id)
    return db.scalar(stmt.limit(1)) is not None


# Who may move a booking from one status to another.
OWNER_TRANSITIONS = {
    BookingStatus.requested: {BookingStatus.accepted, BookingStatus.rejected},
    BookingStatus.accepted: {BookingStatus.in_progress, BookingStatus.cancelled},
    BookingStatus.in_progress: {BookingStatus.completed},
}
RENTER_TRANSITIONS = {
    BookingStatus.requested: {BookingStatus.cancelled},
    BookingStatus.accepted: {BookingStatus.cancelled},
}
