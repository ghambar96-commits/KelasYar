"""Auth flow tests: pairing code -> JWT -> /me, expiry & reuse."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import AuthCode, User
from app.services import auth_service
from app.utils.time import now_utc

from conftest import STUDENT_TG, auth_headers, create_db_user, get_token


async def test_exchange_and_me(client):
    await create_db_user(STUDENT_TG)
    token = await get_token(client, STUDENT_TG)
    resp = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["telegram_id"] == STUDENT_TG
    assert body["role"] == "USER"
    assert "points" in body and "streak_count" in body


async def test_me_without_token(client):
    resp = await client.get("/api/users/me")
    assert resp.status_code == 401


async def test_invalid_code(client):
    resp = await client.post("/api/auth/exchange", json={"code": "WRONGCODE"})
    assert resp.status_code == 401


async def test_code_single_use(client):
    await create_db_user(STUDENT_TG)
    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.telegram_id == STUDENT_TG))).scalar_one()
        code = await auth_service.issue_auth_code(session, user)

    first = await client.post("/api/auth/exchange", json={"code": code})
    assert first.status_code == 200
    second = await client.post("/api/auth/exchange", json={"code": code})
    assert second.status_code == 401


async def test_expired_code(client):
    await create_db_user(STUDENT_TG)
    async with AsyncSessionLocal() as session:
        user = (await session.execute(select(User).where(User.telegram_id == STUDENT_TG))).scalar_one()
        stale = AuthCode(
            user_id=user.id,
            code="STALE001",
            expires_at=now_utc() - timedelta(minutes=1),
        )
        session.add(stale)
        await session.commit()

    resp = await client.post("/api/auth/exchange", json={"code": "STALE001"})
    assert resp.status_code == 401
    assert "منقضی" in resp.json()["detail"]


async def test_banned_user_rejected(client, admin_user):
    from app.services import user_service

    await create_db_user(STUDENT_TG)
    headers = await auth_headers(client, STUDENT_TG)
    assert (await client.get("/api/users/me", headers=headers)).status_code == 200

    async with AsyncSessionLocal() as session:
        target = (await session.execute(select(User).where(User.telegram_id == STUDENT_TG))).scalar_one()
        admin = (await session.execute(select(User).where(User.telegram_id == admin_user.telegram_id))).scalar_one()
        await user_service.ban(session, admin, target, "test ban", source="api")

    resp = await client.get("/api/users/me", headers=headers)
    assert resp.status_code == 403
    assert "مسدود" in resp.json()["detail"]
