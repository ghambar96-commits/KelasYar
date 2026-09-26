#!/usr/bin/env python3
"""Seed demo data (for local testing / first look).

Usage:
    python scripts/seed_demo.py            # seeds if DB is empty
    python scripts/seed_demo.py --force    # resets demo users' data

Creates: demo users (1 super admin, 2 contributors, 5 students),
homework for yesterday/today/tomorrow, and some point history –
then prints one-time pairing codes you can use to log into /admin.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete, select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import AsyncSessionLocal, engine  # noqa: E402
from app.models import Base, Homework, PointTransaction, Role, User  # noqa: E402
from app.schemas.homework import HomeworkCreate  # noqa: E402
from app.services import auth_service, homework_service, points_service, settings_service  # noqa: E402
from app.utils.time import now_utc, today_local  # noqa: E402

DEMO = [
    # telegram_id, role, first_name, username
    (100000001, Role.SUPER_ADMIN, "مدیر کلاس", "class_manager"),
    (200000002, Role.CONTRIBUTOR, "سارا", "sara_hw"),
    (200000003, Role.CONTRIBUTOR, "امیر", "amir_hw"),
    (300000004, Role.USER, "علی", "ali_std"),
    (300000005, Role.USER, "نگار", "negar_std"),
    (300000006, Role.USER, "رضا", "reza_std"),
    (300000007, Role.USER, "مریم", "maryam_std"),
    (300000008, Role.USER, "حسین", "hosein_std"),
]

HOMEWORKS = [
    # subject, title, day_offset, due_offset
    ("ریاضی", "صفحه ۴۵، سوال‌های ۱ تا ۱۰", -1, 2),
    ("فارسی", "درس ۷، معنی لغات", -1, 1),
    ("ریاضی", "تمرین‌های صفحه ۴۸", 0, 2),
    ("علوم", "مطالعه درس ۵ + خلاصه‌نویسی", 0, 3),
    ("انگلیسی", "Unit 3 vocabulary", 0, 1),
    ("عربی", "ترجمه متن صفحه ۳۰", 1, 4),
    ("هنر", "آماده‌سازی ابزار نقاشی", 1, 1),
    ("مطالعات اجتماعی", "نقشه منطقه را رسم کن", 2, 6),
]


async def main(force: bool) -> None:
    settings = get_settings()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await settings_service.ensure_defaults(session)

        if force:
            await session.execute(delete(Homework))
            await session.execute(delete(PointTransaction))
            await session.execute(delete(User).where(User.telegram_id != 0))

        # users
        users: dict[int, User] = {}
        for tg_id, role, name, username in DEMO:
            user = await session.scalar(select(User).where(User.telegram_id == tg_id))
            if user is None:
                user = User(telegram_id=tg_id, role=role, first_name=name, username=username)
                session.add(user)
                await session.flush()
            users[tg_id] = user

        # homework
        existing = await session.scalar(select(Homework).limit(1))
        if existing is None:
            today = today_local()
            contributors = [users[200000002], users[200000003]]
            for i, (subject, title, day_off, due_off) in enumerate(HOMEWORKS):
                await homework_service.create(
                    session,
                    HomeworkCreate(
                        title=title,
                        subject=subject,
                        homework_date=today + timedelta(days=day_off),
                        due_date=today + timedelta(days=due_off),
                    ),
                    contributors[i % 2],
                    source="system",
                )

        # simulate a few days of activity for students (ranking demo)
        students = [u for u in users.values() if u.role == Role.USER]
        if not await session.scalar(select(PointTransaction).limit(1)):
            day = today_local()
            for back in range(5, 0, -1):  # 5 days of history
                for idx, student in enumerate(students):
                    if (idx + back) % 2 == 0 and back not in (1,):  # some missed days
                        continue
                    student.streak_count = min(student.streak_count + 1, 6) if back < 5 else 1
                    student.last_activity_date = day - timedelta(days=back)
                    await points_service.award(
                        session, student, "first_daily_activity",
                        meta={"streak": student.streak_count},
                        at=now_utc() - timedelta(days=back),
                    )
                    if (idx + back) % 3 == 0:
                        await points_service.award(
                            session, student, "view_homework_today",
                            at=now_utc() - timedelta(days=back),
                        )
            for student in students:
                student.points = sum(
                    tx.amount
                    for tx in (
                        await session.execute(
                            select(PointTransaction).where(PointTransaction.user_id == student.id)
                        )
                    ).scalars()
                )
            await session.commit()

        # pairing codes for immediate login
        codes = {}
        for tg_id in (100000001, 300000004):
            codes[tg_id] = await auth_service.issue_auth_code(session, users[tg_id])

    print("\n✅ demo data ready")
    print(f"   database : {settings.database_url}")
    print("\n🔑 one-time login codes (valid 10 minutes):")
    print(f"   SUPER_ADMIN (مدیر کلاس) : {codes[100000001]}")
    print(f"   STUDENT     (علی)       : {codes[300000004]}")
    print("\n→ start the server:  python run.py")
    print("→ open http://localhost:8000/admin and paste a code above.")
    print("→ API docs: http://localhost:8000/docs\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="wipe homework/points/users first")
    asyncio.run(main(parser.parse_args().force))
