"""Populate the local database with demo users and machines.

Run from the backend folder:  python seed.py
Logins: owner@demo.com / renter@demo.com, password "password123".
"""
from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models import Machine, MachineCategory, Role, User
from app.security import hash_password

# Demo coordinates; change to your own region.
BASE_LAT, BASE_LNG = 31.5204, 74.3587

MACHINES = [
    ("Massey Ferguson 385", MachineCategory.tractor, 2000, 12000, 0.02, 0.01),
    ("John Deere 5310", MachineCategory.tractor, 2500, 15000, -0.03, 0.02),
    ("CAT 320 Excavator", MachineCategory.excavator, 9000, 60000, 0.05, -0.04),
    ("JCB 3CX Backhoe", MachineCategory.backhoe, 6000, 40000, -0.01, -0.03),
    ("Claas Lexion Harvester", MachineCategory.harvester, 12000, 80000, 0.08, 0.06),
]


def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == "owner@demo.com")):
            print("Already seeded.")
            return
        owner = User(email="owner@demo.com", password_hash=hash_password("password123"),
                     full_name="Demo Owner", role=Role.owner, is_verified=True)
        renter = User(email="renter@demo.com", password_hash=hash_password("password123"),
                      full_name="Demo Renter", role=Role.renter)
        db.add_all([owner, renter])
        db.flush()
        for title, cat, hourly, daily, dlat, dlng in MACHINES:
            db.add(Machine(owner_id=owner.id, title=title, category=cat, hourly_rate_cents=hourly,
                           daily_rate_cents=daily, latitude=BASE_LAT + dlat, longitude=BASE_LNG + dlng,
                           service_radius_km=40))
        db.commit()
    print(f"Seeded 2 users and {len(MACHINES)} machines.")


if __name__ == "__main__":
    main()
