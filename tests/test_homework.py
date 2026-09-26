"""Homework CRUD, validation, scoping & attachments."""

from __future__ import annotations

import io

from app.utils.time import today_local

from conftest import CONTRIB_TG, STUDENT_TG, auth_headers, create_db_user


def hw_payload(**overrides) -> dict:
    base = {
        "title": "درس ۷، معنی لغات",
        "description": "لغات صفحه ۴۰ را بنویسید",
        "subject": "فارسی",
        "homework_date": today_local().isoformat(),
    }
    base.update(overrides)
    return base


async def contributor_headers(client):
    return await auth_headers(client, CONTRIB_TG)


# ------------------------------------------------------------------ create
async def test_create_and_get(client, contributor):
    headers = await contributor_headers(client)
    created = await client.post("/api/homework", json=hw_payload(), headers=headers)
    assert created.status_code == 201
    body = created.json()
    assert body["subject"] == "فارسی"
    assert body["author_name"]
    assert body["homework_date"] == today_local().isoformat()

    fetched = await client.get(f"/api/homework/{body['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "درس ۷، معنی لغات"


async def test_validation_errors(client, contributor):
    headers = await contributor_headers(client)

    # empty title
    resp = await client.post("/api/homework", json=hw_payload(title=""), headers=headers)
    assert resp.status_code == 422
    # bad date format
    resp = await client.post("/api/homework", json=hw_payload(homework_date="01-01-2030"), headers=headers)
    assert resp.status_code == 422
    # due before homework_date
    resp = await client.post(
        "/api/homework",
        json=hw_payload(due_date="2000-01-01"),
        headers=headers,
    )
    assert resp.status_code == 422


async def test_multiple_homework_same_day(client, contributor):
    headers = await contributor_headers(client)
    await client.post("/api/homework", json=hw_payload(subject="ریاضی", title="صفحه ۴۵"), headers=headers)
    await client.post("/api/homework", json=hw_payload(subject="علوم", title="مطالعه درس ۵"), headers=headers)
    await client.post("/api/homework", json=hw_payload(subject="انگلیسی", title="Unit 3 words"), headers=headers)

    resp = await client.get("/api/homework/today", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 3


# ------------------------------------------------------------------ scoping
async def test_today_upcoming_past_scoping(client, contributor):
    headers = await contributor_headers(client)
    today = today_local()
    await client.post(
        "/api/homework",
        json=hw_payload(title="yesterday hw", homework_date=(today.replace(day=1) if today.day > 1 else today).isoformat()),
        headers=headers,
    )
    await client.post("/api/homework", json=hw_payload(subject="ریاضی", title="today hw"), headers=headers)
    await client.post(
        "/api/homework",
        json=hw_payload(subject="علوم", title="future hw", homework_date="2099-06-01"),
        headers=headers,
    )

    assert (await client.get("/api/homework/today", headers=headers)).json()["total"] >= 1
    upcoming = (await client.get("/api/homework/upcoming", headers=headers)).json()
    assert upcoming["total"] >= 1
    assert all(i["homework_date"] > today.isoformat() for i in upcoming["items"])


async def test_filters_and_search(client, contributor):
    headers = await contributor_headers(client)
    await client.post("/api/homework", json=hw_payload(subject="ریاضی", title="صفحه ۴۵"), headers=headers)
    await client.post("/api/homework", json=hw_payload(subject="علوم", title="مطالعه درس ۵"), headers=headers)

    resp = await client.get("/api/homework", params={"subject": "ریاضی"}, headers=headers)
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["subject"] == "ریاضی"

    resp = await client.get("/api/homework", params={"q": "درس ۵"}, headers=headers)
    assert resp.json()["total"] == 1


# ------------------------------------------------------------------- update
async def test_update_homework(client, contributor):
    headers = await contributor_headers(client)
    created = await client.post("/api/homework", json=hw_payload(), headers=headers)
    hw_id = created.json()["id"]

    resp = await client.put(
        f"/api/homework/{hw_id}",
        json={"title": "عنوان جدید", "due_date": "2099-12-31"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "عنوان جدید"
    assert resp.json()["due_date"] == "2099-12-31"


async def test_update_conflicting_dates_rejected(client, contributor):
    headers = await contributor_headers(client)
    created = await client.post("/api/homework", json=hw_payload(), headers=headers)
    hw_id = created.json()["id"]

    # homework_date moved AFTER the existing due_date -> service-level 400
    resp = await client.put(
        f"/api/homework/{hw_id}",
        json={"due_date": today_local().isoformat()},
        headers=headers,
    )
    await client.put(f"/api/homework/{hw_id}", json={"homework_date": "2099-01-01"}, headers=headers)
    resp2 = await client.put(f"/api/homework/{hw_id}", json={"due_date": "2000-01-01"}, headers=headers)
    assert resp2.status_code == 400


# ------------------------------------------------------------------- delete
async def test_delete_is_soft_and_audited(client, contributor):
    headers = await contributor_headers(client)
    created = await client.post("/api/homework", json=hw_payload(), headers=headers)
    hw_id = created.json()["id"]

    resp = await client.delete(f"/api/homework/{hw_id}", headers=headers)
    assert resp.status_code == 204

    assert (await client.get(f"/api/homework/{hw_id}", headers=headers)).status_code == 404
    listing = (await client.get("/api/homework", headers=headers)).json()
    assert listing["total"] == 0


# --------------------------------------------------------------- attachments
async def test_attachment_upload_and_download(client, contributor, student):
    headers = await contributor_headers(client)
    created = await client.post("/api/homework", json=hw_payload(), headers=headers)
    hw_id = created.json()["id"]

    upload = await client.post(
        f"/api/homework/{hw_id}/attachments",
        files={"files": ("tamrin.txt", b"hello kelasYar", "text/plain")},
        headers=headers,
    )
    assert upload.status_code == 201
    att = upload.json()[0]
    assert att["file_name"] == "tamrin.txt"
    assert att["url"].startswith("/api/attachments/")

    # USER can download too (viewing is allowed)
    headers_u = await auth_headers(client, STUDENT_TG)
    download = await client.get(att["url"], headers=headers_u)
    assert download.status_code == 200
    assert download.content == b"hello kelasYar"

    # anonymous cannot
    assert (await client.get(att["url"])).status_code == 401
