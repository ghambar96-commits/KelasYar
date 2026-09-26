"""Admin management: users, roles, ban/unban, settings, api-keys."""

from __future__ import annotations

from app.database import AsyncSessionLocal
from app.models import User
from sqlalchemy import select

from conftest import (
    ADMIN_TG,
    CONTRIB_TG,
    STUDENT_TG,
    auth_headers,
)


async def _uid(telegram_id: int) -> int:
    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one()
        return user.id


async def test_list_and_filter_users(client, admin_user, contributor, student):
    headers = await auth_headers(client, ADMIN_TG)
    resp = await client.get("/api/admin/users", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 3

    resp = await client.get("/api/admin/users", params={"role": "CONTRIBUTOR"}, headers=headers)
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["telegram_id"] == CONTRIB_TG

    resp = await client.get("/api/admin/users", params={"q": str(STUDENT_TG)}, headers=headers)
    assert resp.json()["total"] == 1


async def test_promote_and_demote(client, admin_user, student):
    headers = await auth_headers(client, ADMIN_TG)
    uid = await _uid(STUDENT_TG)

    resp = await client.put(f"/api/admin/users/{uid}/role", json={"role": "CONTRIBUTOR"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == "CONTRIBUTOR"

    # the promoted student can now create homework
    headers_s = await auth_headers(client, STUDENT_TG)
    created = await client.post(
        "/api/homework",
        json={"title": "x", "subject": "s", "homework_date": "2030-01-01"},
        headers=headers_s,
    )
    assert created.status_code == 201

    # demote -> loses access immediately (token re-reads role from DB)
    await client.put(f"/api/admin/users/{uid}/role", json={"role": "USER"}, headers=headers)
    denied = await client.post(
        "/api/homework",
        json={"title": "x", "subject": "s", "homework_date": "2030-01-01"},
        headers=headers_s,
    )
    assert denied.status_code == 403


async def test_cannot_modify_self_or_superadmin(client, admin_user):
    headers = await auth_headers(client, ADMIN_TG)
    uid = await _uid(ADMIN_TG)

    resp = await client.put(f"/api/admin/users/{uid}/role", json={"role": "USER"}, headers=headers)
    assert resp.status_code == 400

    resp = await client.post(f"/api/admin/users/{uid}/ban", json={"reason": "nope"}, headers=headers)
    assert resp.status_code == 400


async def test_ban_unban_flow(client, admin_user, student):
    headers = await auth_headers(client, ADMIN_TG)
    uid = await _uid(STUDENT_TG)

    resp = await client.post(f"/api/admin/users/{uid}/ban", json={"reason": "spam"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_banned"] is True

    # banned user blocked everywhere
    headers_s = await auth_headers(client, STUDENT_TG)
    assert (await client.get("/api/users/me", headers=headers_s)).status_code == 403

    resp = await client.post(f"/api/admin/users/{uid}/unban", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_banned"] is False
    assert (await client.get("/api/users/me", headers=headers_s)).status_code == 200


async def test_stats_shape(client, admin_user, contributor, student):
    headers = await auth_headers(client, ADMIN_TG)
    stats = (await client.get("/api/admin/stats", headers=headers)).json()
    assert stats["users"]["total"] == 3
    assert stats["users"]["by_role"]["USER"] == 1
    assert stats["users"]["by_role"]["CONTRIBUTOR"] == 1
    assert stats["users"]["by_role"]["SUPER_ADMIN"] == 1
    assert "homework" in stats and "top_subjects" in stats


async def test_settings_update(client, admin_user):
    headers = await auth_headers(client, ADMIN_TG)
    resp = await client.put(
        "/api/admin/settings/class_name",
        json={"value": "کلاس نهم ۲"},
        headers=headers,
    )
    assert resp.status_code == 200

    listing = (await client.get("/api/admin/settings", headers=headers)).json()
    by_key = {s["key"]: s["value"] for s in listing}
    assert by_key["class_name"] == "کلاس نهم ۲"

    # point_rules must go through its dedicated endpoint
    resp = await client.put(
        "/api/admin/settings/point_rules",
        json={"value": {}},
        headers=headers,
    )
    assert resp.status_code == 400


async def test_api_key_lifecycle(client, admin_user):
    headers = await auth_headers(client, ADMIN_TG)

    created = await client.post("/api/admin/api-keys", json={"name": "panel"}, headers=headers)
    assert created.status_code == 201
    raw_key = created.json()["key"]
    assert raw_key.startswith("cb_")

    # the raw key authenticates as its owner (the super admin)
    resp = await client.get("/api/users/me", headers={"X-API-Key": raw_key})
    assert resp.status_code == 200
    assert resp.json()["telegram_id"] == ADMIN_TG

    # listing never exposes the raw key again
    listing = (await client.get("/api/admin/api-keys", headers=headers)).json()
    assert all("key" not in k or not k["key"] for k in listing)

    # revoke -> stops working
    key_id = created.json()["id"]
    assert (await client.delete(f"/api/admin/api-keys/{key_id}", headers=headers)).status_code == 204
    assert (await client.get("/api/users/me", headers={"X-API-Key": raw_key})).status_code == 401
