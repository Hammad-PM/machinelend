from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Machine, MachineCategory, Role, User
from app.schemas import MachineIn, MachineOut, MachineSearchResult, MachineUpdate, QuoteOut
from app.security import require_role
from app.services import as_utc, bounding_box, has_conflict, haversine_km, quote

router = APIRouter(prefix="/machines", tags=["machines"])


@router.get("/search", response_model=list[MachineSearchResult])
def search(
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    radius_km: float = Query(default=50, gt=0, le=500),
    category: MachineCategory | None = None,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Find active machines near a job site, optionally only those free for a time window."""
    if (start_at is None) != (end_at is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Provide both start_at and end_at, or neither")
    min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, radius_km)
    stmt = select(Machine).where(
        Machine.is_active.is_(True),
        Machine.latitude.between(min_lat, max_lat),
        Machine.longitude.between(min_lng, max_lng),
    )
    if category:
        stmt = stmt.where(Machine.category == category)

    results = []
    for m in db.scalars(stmt):
        distance = haversine_km(lat, lng, m.latitude, m.longitude)
        # Must be within the searcher's radius AND the owner's service area.
        if distance > radius_km or distance > m.service_radius_km:
            continue
        if start_at and has_conflict(db, m.id, as_utc(start_at), as_utc(end_at)):
            continue
        results.append(MachineSearchResult(**MachineOut.model_validate(m).model_dump(),
                                           distance_km=round(distance, 2)))
    results.sort(key=lambda r: r.distance_km)
    return results[:limit]


@router.get("/mine", response_model=list[MachineOut])
def my_machines(user: User = Depends(require_role(Role.owner)), db: Session = Depends(get_db)):
    return db.scalars(select(Machine).where(Machine.owner_id == user.id).order_by(Machine.id)).all()


@router.get("/{machine_id}", response_model=MachineOut)
def get_machine(machine_id: int, db: Session = Depends(get_db)):
    machine = db.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Machine not found")
    return machine


@router.get("/{machine_id}/quote", response_model=QuoteOut)
def get_quote(machine_id: int, start_at: datetime, end_at: datetime, db: Session = Depends(get_db)):
    machine = get_machine(machine_id, db)
    if as_utc(end_at) <= as_utc(start_at):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "end_at must be after start_at")
    return quote(machine, start_at, end_at)


@router.post("", response_model=MachineOut, status_code=status.HTTP_201_CREATED)
def create_machine(body: MachineIn, user: User = Depends(require_role(Role.owner)),
                   db: Session = Depends(get_db)):
    machine = Machine(owner_id=user.id, **body.model_dump())
    db.add(machine)
    db.commit()
    return machine


@router.patch("/{machine_id}", response_model=MachineOut)
def update_machine(machine_id: int, body: MachineUpdate, user: User = Depends(require_role(Role.owner)),
                   db: Session = Depends(get_db)):
    machine = db.get(Machine, machine_id)
    if machine is None or machine.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Machine not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(machine, field, value)
    db.commit()
    return machine
