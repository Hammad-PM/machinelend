from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import BookingStatus, MachineCategory, Role


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth / users ---

class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=120)
    phone: str | None = None
    # Admins are created out-of-band, never via self-registration.
    role: Role = Field(default=Role.renter, description="renter or owner")


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(ORM):
    id: int
    email: EmailStr
    full_name: str
    phone: str | None
    role: Role
    is_verified: bool


# --- Machines ---

class MachineIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    category: MachineCategory
    make: str | None = None
    model: str | None = None
    year: int | None = Field(default=None, ge=1900, le=2100)
    description: str | None = None
    hourly_rate_cents: int = Field(gt=0)
    daily_rate_cents: int = Field(gt=0)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    service_radius_km: float = Field(default=50, gt=0, le=1000)


class MachineUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    hourly_rate_cents: int | None = Field(default=None, gt=0)
    daily_rate_cents: int | None = Field(default=None, gt=0)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    service_radius_km: float | None = Field(default=None, gt=0, le=1000)
    is_active: bool | None = None


class MachineOut(ORM):
    id: int
    owner_id: int
    title: str
    category: MachineCategory
    make: str | None
    model: str | None
    year: int | None
    description: str | None
    hourly_rate_cents: int
    daily_rate_cents: int
    latitude: float
    longitude: float
    service_radius_km: float
    is_active: bool


class MachineSearchResult(MachineOut):
    distance_km: float


# --- Bookings ---

class QuoteOut(BaseModel):
    hours: float
    subtotal_cents: int
    platform_fee_cents: int
    total_cents: int
    currency: str


class BookingIn(BaseModel):
    machine_id: int
    start_at: datetime
    end_at: datetime
    site_address: str = Field(min_length=1, max_length=255)
    site_latitude: float = Field(ge=-90, le=90)
    site_longitude: float = Field(ge=-180, le=180)
    job_notes: str | None = None


class BookingStatusUpdate(BaseModel):
    status: BookingStatus


class BookingOut(ORM):
    id: int
    machine_id: int
    renter_id: int
    start_at: datetime
    end_at: datetime
    site_address: str
    site_latitude: float
    site_longitude: float
    job_notes: str | None
    status: BookingStatus
    subtotal_cents: int
    platform_fee_cents: int
    total_cents: int
    currency: str
    machine: MachineOut


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


class ReviewOut(ORM):
    id: int
    booking_id: int
    rating: int
    comment: str | None
