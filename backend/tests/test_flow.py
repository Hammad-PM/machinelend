from datetime import datetime, timedelta, timezone

from tests.conftest import auth_headers

FARM = {"latitude": 31.5204, "longitude": 74.3587}  # machine base
SITE = {"site_latitude": 31.55, "site_longitude": 74.40, "site_address": "Plot 12, Village Road"}


def future(hours: int) -> str:
    base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) + timedelta(days=2)
    return (base + timedelta(hours=hours)).isoformat()


def create_tractor(client, owner) -> int:
    res = client.post("/machines", headers=owner, json={
        "title": "John Deere 5050D", "category": "tractor",
        "hourly_rate_cents": 2500, "daily_rate_cents": 15000, **FARM, "service_radius_km": 30,
    })
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_register_rejects_admin_and_duplicates(client):
    auth_headers(client, "a@x.com", "renter")
    assert client.post("/auth/register", json={
        "email": "A@x.com", "password": "password123", "full_name": "A"}).status_code == 409
    assert client.post("/auth/register", json={
        "email": "b@x.com", "password": "password123", "full_name": "B", "role": "admin"}).status_code == 403


def test_renter_cannot_list_machine(client):
    renter = auth_headers(client, "r@x.com", "renter")
    res = client.post("/machines", headers=renter, json={
        "title": "X", "category": "tractor", "hourly_rate_cents": 1, "daily_rate_cents": 1, **FARM})
    assert res.status_code == 403


def test_search_filters_by_distance_and_category(client):
    owner = auth_headers(client, "o@x.com", "owner")
    create_tractor(client, owner)
    near = client.get("/machines/search", params={"lat": 31.55, "lng": 74.40, "radius_km": 20}).json()
    assert len(near) == 1 and near[0]["distance_km"] < 10
    assert client.get("/machines/search", params={"lat": 33.7, "lng": 73.0}).json() == []
    assert client.get("/machines/search", params={
        "lat": 31.55, "lng": 74.40, "category": "crane"}).json() == []


def test_quote_uses_daily_rate_for_full_days(client):
    owner = auth_headers(client, "o@x.com", "owner")
    mid = create_tractor(client, owner)
    q = client.get(f"/machines/{mid}/quote", params={"start_at": future(0), "end_at": future(27)}).json()
    # 1 day (15000) + 3 hours (3 * 2500) = 22500, +10% fee
    assert q["subtotal_cents"] == 22500
    assert q["platform_fee_cents"] == 2250
    assert q["total_cents"] == 24750
    # 10 hours hourly (25000) is capped at the daily rate
    q = client.get(f"/machines/{mid}/quote", params={"start_at": future(0), "end_at": future(10)}).json()
    assert q["subtotal_cents"] == 15000


def test_full_booking_lifecycle(client):
    owner = auth_headers(client, "o@x.com", "owner")
    renter = auth_headers(client, "r@x.com", "renter")
    other = auth_headers(client, "r2@x.com", "renter")
    mid = create_tractor(client, owner)

    booking = {"machine_id": mid, "start_at": future(0), "end_at": future(8), **SITE}
    res = client.post("/bookings", headers=renter, json=booking)
    assert res.status_code == 201, res.text
    bid = res.json()["id"]
    assert res.json()["status"] == "requested"

    # Overlapping request is rejected; machine disappears from availability search.
    overlap = {**booking, "start_at": future(4), "end_at": future(12)}
    assert client.post("/bookings", headers=other, json=overlap).status_code == 409
    assert client.get("/machines/search", params={
        "lat": 31.55, "lng": 74.40, "start_at": future(2), "end_at": future(3)}).json() == []

    # Other users can't see it; renter can't accept their own booking.
    assert client.get(f"/bookings/{bid}", headers=other).status_code == 404
    assert client.patch(f"/bookings/{bid}/status", headers=renter, json={"status": "accepted"}).status_code == 409

    for status in ("accepted", "in_progress", "completed"):
        res = client.patch(f"/bookings/{bid}/status", headers=owner, json={"status": status})
        assert res.status_code == 200, res.text

    assert [b["id"] for b in client.get("/bookings/mine", headers=owner).json()] == [bid]
    assert client.post(f"/bookings/{bid}/review", headers=renter, json={"rating": 5}).status_code == 201
    assert client.post(f"/bookings/{bid}/review", headers=renter, json={"rating": 4}).status_code == 409

    # Completed booking no longer blocks the slot.
    assert client.post("/bookings", headers=other, json=overlap).status_code == 201


def test_booking_outside_service_area_rejected(client):
    owner = auth_headers(client, "o@x.com", "owner")
    renter = auth_headers(client, "r@x.com", "renter")
    mid = create_tractor(client, owner)
    res = client.post("/bookings", headers=renter, json={
        "machine_id": mid, "start_at": future(0), "end_at": future(8),
        "site_address": "Far away", "site_latitude": 33.7, "site_longitude": 73.0})
    assert res.status_code == 422
