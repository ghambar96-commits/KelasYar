"""Audit log coverage of important operations."""

from __future__ import annotations

from app.utils.time import today_local

from conftest import ADMIN_TG, CONTRIB_TG, STUDENT_TG, auth_headers

HW = {"title": "t", "subject": "ریاضی", "homework_date": None}


async def _logs(client, headers, **params):
    resp = await client.get("/api/admin/audit-logs", params=params, headers=headers)
    assert resp.status_code == 200
    return resp.json()


async def test_homework_crud_audited(client, admin_user, contributor):
    headers = await auth_headers(client, CONTRIB_TG)
    created = await client.post(
        "/api/homework", json={**HW, "homework_date": today_local().isoformat()}, headers=headers
    )
    hw_id = created.json()["id"]
    await client.put(f"/api/homework/{hw_id}", json={"title": "new"}, headers=headers)
    await client.delete(f"/api/homework/{hw_id}", headers=headers)

    admin_headers = await auth_headers(client, ADMIN_TG)
    logs = await _logs(client, admin_headers, action="homework")
    actions = [l["action"] for l in logs["items"]]
    assert "homework.create" in actions
    assert "homework.update" in actions
    assert "homework.delete" in actions

    entry = next(l for l in logs["items"] if l["action"] == "homework.create")
    assert entry["actor_id"] is not None
    assert entry["details"]["subject"] == "ریاضی"


async def test_role_change_and_ban_audited(client, admin_user, student):
    from app.database import AsyncSessionLocal
    from app.models import User
    from sqlalchemy import select

    headers = await auth_headers(client, ADMIN_TG)
    async with AsyncSessionLocal() as session:
        uid = (await session.execute(select(User).where(User.telegram_id == STUDENT_TG))).scalar_one().id

    await client.put(f"/api/admin/users/{uid}/role", json={"role": "CONTRIBUTOR"}, headers=headers)
    await client.post(f"/api/admin/users/{uid}/ban", json={"reason": "test"}, headers=headers)

    logs = await _logs(client, headers)
    actions = [l["action"] for l in logs["items"]]
    assert "user.role_change" in actions
    assert "user.ban" in actions

    role_entry = next(l for l in logs["items"] if l["action"] == "user.role_change")
    assert role_entry["details"]["from"] == "USER"
    assert role_entry["details"]["to"] == "CONTRIBUTOR"


async def test_audit_pagination_and_source(client, admin_user):
    headers = await auth_headers(client, ADMIN_TG)
    page = await _logs(client, headers, page=1, page_size=2)
    assert page["page_size"] == 2
    if page["total"] > 2:
        assert len(page["items"]) == 2
