"""Test fixtures – in-memory SQLite + fresh app per test.

Env vars are set BEFORE any `app.*` import so settings pick them up.
"""

from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-0123456789")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "")
os.environ.setdefault("BOT_ENABLED", "false")
os.environ.setdefault("SUPER_ADMIN_TELEGRAM_IDS", "100000001")
os.environ.setdefault("AUTO_CREATE_TABLES", "false")
os.environ.setdefault("RATE_LIMIT_REQUESTS", "1000")

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database import AsyncSessionLocal, engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base, Role, User  # noqa: E402
from app.services import auth_service, settings_service  # noqa: E402

ADMIN_TG = 100000001
CONTRIB_TG = 200000002
STUDENT_TG = 300000003
STUDENT2_TG = 300000004


@pytest.fixture
async def app():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        await settings_service.ensure_defaults(session)
    application = create_app()
    yield application


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


async def create_db_user(
    telegram_id: int,
    role: Role = Role.USER,
    *,
    username: str | None = None,
    first_name: str | None = None,
) -> User:
    async with AsyncSessionLocal() as session:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name or f"user{telegram_id}",
            role=role,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def get_token(client: AsyncClient, telegram_id: int) -> str:
    """Create a user (if needed) and return a valid JWT via the pairing flow."""
    async with AsyncSessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.telegram_id == telegram_id))
        ).scalar_one()
        code = await auth_service.issue_auth_code(session, user)
    resp = await client.post("/api/auth/exchange", json={"code": code})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


async def auth_headers(client: AsyncClient, telegram_id: int) -> dict:
    return {"Authorization": f"Bearer {await get_token(client, telegram_id)}"}


@pytest.fixture
async def admin_user():
    return await create_db_user(ADMIN_TG, Role.SUPER_ADMIN, username="admin", first_name="Admin")


@pytest.fixture
async def contributor():
    return await create_db_user(CONTRIB_TG, Role.CONTRIBUTOR, username="-contrib", first_name="Ostad")


@pytest.fixture
async def student():
    return await create_db_user(STUDENT_TG, Role.USER, username="student1", first_name="Ali")
