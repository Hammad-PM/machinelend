from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Booking, BookingStatus, Machine, Review, Role, User
from app.schemas import BookingIn, BookingOut, BookingStatusUpdate, ReviewIn, ReviewOut
from app.security import get_current_user, require_role
from app.services import OWNER_TRANSITIONS, RENTER_TRANSITIONS, as_utc, has_conflict, haversine_km, quote

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(body: BookingIn, user: User = Depends(require_role(Role.renter)),
                   db: Session = Depends(get_db)):
    start_at, end_at = as_utc(body.start_at), as_utc(body.end_at)
    if start_at <= datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Booking must start in the future")
    if end_at - start_at < timedelta(hours=settings.min_booking_hours):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            f"Booking must be at least {settings.min_booking_hours} hour(s)")

    # Lock the machine row (no-op on SQLite) so two renters can't grab the same slot concurrently.
    machine = db.scalar(select(Machine).where(Machine.id == body.machine_id).with_for_update())
    if machine is None or not machine.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Machine not available")
    distance = haversine_km(machine.latitude, machine.longitude, body.site_latitude, body.site_longitude)
    if distance > machine.service_radius_km:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Job site is outside this machine's service area")
    if has_conflict(db, machine.id, start_at, end_at):
        raise HTTPException(status.HTTP_409_CONFLICT, "Machine is already booked for that time")

    price = quote(machine, start_at, end_at)
    booking = Booking(
        machine_id=machine.id, renter_id=user.id, start_at=start_at, end_at=end_at,
        site_address=body.site_address, site_latitude=body.site_latitude,
        site_longitude=body.site_longitude, job_notes=body.job_notes,
        subtotal_cents=price["subtotal_cents"], platform_fee_cents=price["platform_fee_cents"],
        total_cents=price["total_cents"], currency=price["currency"],
    )
    db.add(booking)
    db.commit()
    return booking


@router.get("/mine", response_model=list[BookingOut])
def my_bookings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Renters see bookings they made; owners see bookings on their machines."""
    stmt = select(Booking).order_by(Booking.start_at.desc())
    if user.role == Role.owner:
        stmt = stmt.join(Machine).where(Machine.owner_id == user.id)
    elif user.role == Role.renter:
        stmt = stmt.where(Booking.renter_id == user.id)
    return db.scalars(stmt).all()


def _get_visible_booking(db: Session, booking_id: int, user: User) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None or (user.role != Role.admin
                           and user.id not in (booking.renter_id, booking.machine.owner_id)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    return booking


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_visible_booking(db, booking_id, user)


@router.patch("/{booking_id}/status", response_model=BookingOut)
def update_status(booking_id: int, body: BookingStatusUpdate, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    booking = _get_visible_booking(db, booking_id, user)
    transitions = OWNER_TRANSITIONS if user.id == booking.machine.owner_id else RENTER_TRANSITIONS
    if user.role == Role.admin:
        allowed = {s for targets in (OWNER_TRANSITIONS, RENTER_TRANSITIONS) for s in targets.get(booking.status, ())}
    else:
        allowed = transitions.get(booking.status, set())
    if body.status not in allowed:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Cannot change booking from {booking.status.value} to {body.status.value}")
    booking.status = body.status
    db.commit()
    return booking


@router.post("/{booking_id}/review", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def review_booking(booking_id: int, body: ReviewIn, user: User = Depends(require_role(Role.renter)),
                   db: Session = Depends(get_db)):
    booking = _get_visible_booking(db, booking_id, user)
    if booking.renter_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Booking not found")
    if booking.status != BookingStatus.completed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only completed bookings can be reviewed")
    if booking.review is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Booking already reviewed")
    review = Review(booking_id=booking.id, **body.model_dump())
    db.add(review)
    db.commit()
    return review
