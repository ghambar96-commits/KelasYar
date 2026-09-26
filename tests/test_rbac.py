"""Role-based access control tests."""

from __future__ import annotations

from conftest import (
    ADMIN_TG,
    CONTRIB_TG,
    STUDENT_TG,
    auth_headers,
    create_db_user,
)

HW = {
    "title": "صفحه ۴۵، سوال‌های ۱ تا ۱۰",
    "subject": "ریاضی",
    "homework_date": "2030-01-01",
}


async def test_unauthenticated_cannot_write(client):
    resp = await client.post("/api/homework", json=HW)
    assert resp.status_code == 401


async def test_user_cannot_create_homework(client, student):
    headers = await auth_headers(client, STUDENT_TG)
    resp = await client.post("/api/homework", json=HW, headers=headers)
    assert resp.status_code == 403


async def test_user_cannot_update_or_delete(client, student, contributor):
    headers_c = await auth_headers(client, CONTRIB_TG)
    created = await client.post("/api/homework", json=HW, headers=headers_c)
    assert created.status_code == 201
    hw_id = created.json()["id"]

    headers_u = await auth_headers(client, STUDENT_TG)
    assert (await client.put(f"/api/homework/{hw_id}", json={"title": "x"}, headers=headers_u)).status_code == 403
    assert (await client.delete(f"/api/homework/{hw_id}", headers=headers_u)).status_code == 403


async def test_contributor_can_create(client, contributor):
    headers = await auth_headers(client, CONTRIB_TG)
    resp = await client.post("/api/homework", json=HW, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["subject"] == "ریاضی"


async def test_user_cannot_reach_admin_endpoints(client, student, contributor):
    headers_u = await auth_headers(client, STUDENT_TG)
    headers_c = await auth_headers(client, CONTRIB_TG)
    for headers in (headers_u, headers_c):
        assert (await client.get("/api/admin/users", headers=headers)).status_code == 403
        assert (await client.get("/api/admin/stats", headers=headers)).status_code == 403
        assert (await client.get("/api/admin/audit-logs", headers=headers)).status_code == 403
        assert (await client.put("/api/points/rules", json={"enabled": False}, headers=headers)).status_code == 403


async def test_super_admin_can_reach_admin_endpoints(client, admin_user):
    headers = await auth_headers(client, ADMIN_TG)
    assert (await client.get("/api/admin/users", headers=headers)).status_code == 200
    assert (await client.get("/api/admin/stats", headers=headers)).status_code == 200


async def test_super_admin_role_not_assignable_via_api(client, admin_user, student):
    """Only the env whitelist can grant SUPER_ADMIN – the API must reject it."""
    from app.database import AsyncSessionLocal
    from app.models import User
    from sqlalchemy import select

    headers = await auth_headers(client, ADMIN_TG)
    async with AsyncSessionLocal() as session:
        target = (await session.execute(select(User).where(User.telegram_id == STUDENT_TG))).scalar_one()
        uid = target.id

    resp = await client.put(f"/api/admin/users/{uid}/role", json={"role": "SUPER_ADMIN"}, headers=headers)
    assert resp.status_code == 422  # schema-level rejection (Literal USER|CONTRIBUTOR)
