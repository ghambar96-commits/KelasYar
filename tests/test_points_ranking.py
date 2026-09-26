"""Points, streaks, ranking & runtime-editable rules."""

from __future__ import annotations

from app.database import AsyncSessionLocal
from app.models import User
from app.services import points_service
from app.utils.time import today_local
from sqlalchemy import select

from conftest import (
    ADMIN_TG,
    CONTRIB_TG,
    STUDENT_TG,
    auth_headers,
    create_db_user,
)

HW = {"title": "t", "subject": "ریاضی", "homework_date": None}


async def _points_of(telegram_id: int) -> int:
    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one()
        return user.points


async def test_view_today_awards_points_once(client, admin_user, contributor, student):
    headers_c = await auth_headers(client, CONTRIB_TG)
    await client.post(
        "/api/homework",
        json={**HW, "homework_date": today_local().isoformat()},
        headers=headers_c,
    )

    headers_s = await auth_headers(client, STUDENT_TG)
    first = await client.get("/api/homework/today", headers=headers_s)
    assert first.status_code == 200

    # first_daily_activity(2) + streak bonus 0 (first day) + view_homework_today(1) = 3
    assert await _points_of(STUDENT_TG) == 3

    # second view the same day -> no extra points
    await client.get("/api/homework/today", headers=headers_s)
    assert await _points_of(STUDENT_TG) == 3


async def test_create_homework_awards_contributor(client, admin_user, contributor):
    headers = await auth_headers(client, CONTRIB_TG)
    await client.post("/api/homework", json={**HW, "homework_date": today_local().isoformat()}, headers=headers)
    # create_homework rule = 5 points
    assert await _points_of(CONTRIB_TG) == 5


async def test_ranking_and_my_rank(client, admin_user, contributor, student):
    headers_c = await auth_headers(client, CONTRIB_TG)
    headers_a = await auth_headers(client, ADMIN_TG)

    # give students different points via admin adjust
    async with AsyncSessionLocal() as session:
        student_row = (await session.execute(select(User).where(User.telegram_id == STUDENT_TG))).scalar_one()
        admin_row = (await session.execute(select(User).where(User.telegram_id == ADMIN_TG))).scalar_one()
        await points_service.adjust(session, admin_row, student_row, 50, "test top", source="api")
        await points_service.adjust(session, admin_row, admin_row, 10, "test mid", source="api")

    ranking = (await client.get("/api/ranking", headers=headers_a)).json()
    assert ranking[0]["user_id"] == student_row.id
    assert ranking[0]["points"] == 50
    assert ranking[0]["activities"] >= 1
    assert {"rank", "display_name", "points", "activities"} <= set(ranking[0])

    mine = (await client.get("/api/ranking/me", headers=headers_c)).json()
    assert mine["rank"] >= 1
    assert mine["total_users"] >= 3


async def test_admin_adjust_points(client, admin_user, student):
    headers = await auth_headers(client, ADMIN_TG)
    async with AsyncSessionLocal() as session:
        student_row = (await session.execute(select(User).where(User.telegram_id == STUDENT_TG))).scalar_one()
        uid = student_row.id

    resp = await client.post(
        f"/api/admin/users/{uid}/points/adjust",
        json={"amount": 7, "note": "nice job"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["points"] == 7

    resp = await client.post(
        f"/api/admin/users/{uid}/points/adjust",
        json={"amount": -3, "note": "oops"},
        headers=headers,
    )
    assert resp.json()["points"] == 4

    # zero / too big amounts rejected
    assert (await client.post(f"/api/admin/users/{uid}/points/adjust", json={"amount": 0}, headers=headers)).status_code == 422
    assert (await client.post(f"/api/admin/users/{uid}/points/adjust", json={"amount": 999999}, headers=headers)).status_code == 422


async def test_rules_editable_and_take_effect(client, admin_user, student):
    headers_a = await auth_headers(client, ADMIN_TG)
    headers_s = await auth_headers(client, STUDENT_TG)

    # everyone can READ the rules
    rules = (await client.get("/api/points/rules", headers=headers_s)).json()
    assert rules["enabled"] is True
    assert rules["actions"]["view_homework_today"] == 1

    # admin changes values
    resp = await client.put(
        "/api/points/rules",
        json={"enabled": True, "actions": {"view_homework_today": 5, "first_daily_activity": 10}},
        headers=headers_a,
    )
    assert resp.status_code == 200
    assert resp.json()["actions"]["view_homework_today"] == 5

    # now a student's first view of today earns 10 + 5 = 15
    await client.get("/api/homework/today", headers=headers_s)
    assert await _points_of(STUDENT_TG) == 15

    # disabling stops awarding entirely
    await client.put("/api/points/rules", json={"enabled": False}, headers=headers_a)
    await create_db_user(309999999)  # fresh student never awarded
    from conftest import get_token

    token = await get_token(client, 309999999)
    await client.get("/api/homework/today", headers={"Authorization": f"Bearer {token}"})
    assert await _points_of(309999999) == 0


async def test_bad_rule_values_rejected(client, admin_user):
    headers = await auth_headers(client, ADMIN_TG)
    resp = await client.put(
        "/api/points/rules",
        json={"actions": {"BAD KEY!": 3}},
        headers=headers,
    )
    assert resp.status_code == 422
    resp = await client.put("/api/points/rules", json={"actions": {"ok_key": 5000}}, headers=headers)
    assert resp.status_code == 422
