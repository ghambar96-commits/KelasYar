# مستندات REST API — کلاس‌یار

آدرس پایه: `http://localhost:8000` — همهٔ مسیرها با پیشوند `/api`.

- **Swagger زنده:** `/docs`  • **ReDoc:** `/redoc`  • **OpenAPI JSON:** `/openapi.json`
- پشتیبانی از دو نوع احراز هویت: `Authorization: Bearer <JWT>` و `X-API-Key: <key>`

---

## احراز هویت

### دریافت JWT (تبدیل کد ربات)

در ربات تلگرام دستور `/api` را بزنید تا کد یک‌بارمصرف (۱۰ دقیقه اعتبار) بگیرید:

```bash
curl -X POST http://localhost:8000/api/auth/exchange \
  -H "Content-Type: application/json" \
  -d '{"code": "K7QMX2AB"}'
```

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 604800,
  "user": {
    "id": 1,
    "telegram_id": 100000001,
    "username": "class_manager",
    "display_name": "مدیر کلاس",
    "role": "SUPER_ADMIN",
    "points": 12,
    "streak_count": 3,
    "is_banned": false
  }
}
```

خطاها: `401` کد نامعتبر/استفاده‌شده/منقضی — `429` محدودیت نرخ.

> در ادامه `TOKEN` یعنی هدر `Authorization: Bearer <access_token>`.

---

## تکالیف (خواندن — همهٔ نقش‌ها)

### GET /api/homework/today
```bash
curl http://localhost:8000/api/homework/today -H "$TOKEN"
```
```json
{
  "items": [
    {
      "id": 3,
      "title": "تمرین‌های صفحه ۴۸",
      "description": null,
      "subject": "ریاضی",
      "homework_date": "2025-09-23",
      "due_date": "2025-09-25",
      "author_id": 2,
      "author_name": "سارا",
      "attachments": [
        {"id": 1, "file_name": "soal.jpg", "file_size": 84213,
         "mime_type": "image/jpeg", "telegram_available": true,
         "url": "/api/attachments/1/file"}
      ],
      "created_at": "2025-09-22T18:03:11",
      "updated_at": "2025-09-22T18:03:11"
    }
  ],
  "total": 3, "page": 1, "page_size": 50, "pages": 1
}
```
💡 مشاهدهٔ این مسیر (مثل دکمهٔ ربات) امتیاز روزانه می‌دهد.

### GET /api/homework/upcoming و /api/homework/past
```bash
curl "http://localhost:8000/api/homework/past?page=1&page_size=10" -H "$TOKEN"
```

### GET /api/homework — فیلتر و جستجو
پارامترها: `date` ، `date_from` ، `date_to` ، `subject` ، `q` (جستجو در عنوان/توضیحات/درس) ، `order=asc|desc` ، `page` ، `page_size` (≤۵۰)

```bash
curl "http://localhost:8000/api/homework?subject=ریاضی&q=صفحه" -H "$TOKEN"
```

### GET /api/homework/{id}
```bash
curl http://localhost:8000/api/homework/3 -H "$TOKEN"
```
خطا: `404 {"error": "not_found", "detail": "تکلیف مورد نظر یافت نشد."}`

### GET /api/subjects
```json
[{"subject": "ریاضی", "count": 12}, {"subject": "فارسی", "count": 7}]
```

---

## تکالیف (نوشتن — CONTRIBUTOR و بالاتر)

### POST /api/homework
```bash
curl -X POST http://localhost:8000/api/homework \
  -H "$TOKEN" -H "Content-Type: application/json" \
  -d '{
        "title": "درس ۷، معنی لغات",
        "description": "لغات صفحه ۴۰ را در دفتر بنویسید",
        "subject": "فارسی",
        "homework_date": "2025-09-24",
        "due_date": "2025-09-26"
      }'
```
`201 Created` + آبجکت تکلیف. (امتیاز `create_homework` تعلق می‌گیرد)

خطاهای اعتبارسنجی (`422`):
```json
{"detail": [
  {"type": "value_error", "loc": ["body"],
   "msg": "Value error, due_date نمی‌تواند قبل از homework_date باشد"}
]}
```

### POST /api/homework/{id}/attachments (multipart)
```bash
curl -X POST http://localhost:8000/api/homework/3/attachments \
  -H "$TOKEN" -F "files=@soal.jpg" -F "files=@jazeera.pdf"
```
`201` + آرایهٔ پیوست‌ها. (تا ۱۰ فایل؛ محدودیت حجم: `MAX_UPLOAD_MB`)

### PUT /api/homework/{id} (ویرایش جزئی)
```bash
curl -X PUT http://localhost:8000/api/homework/3 \
  -H "$TOKEN" -H "Content-Type: application/json" \
  -d '{"title": "عنوان جدید", "due_date": "2025-09-27"}'
```
برای خالی‌کردن توضیحات: `"description": ""`

### DELETE /api/homework/{id} → `204 No Content` (حذف نرم)

### DELETE /api/attachments/{id} → `204`

---

## پیوست‌ها

### GET /api/attachments/{id}/file (دانلود — همهٔ نقش‌ها)
```bash
curl -OJ http://localhost:8000/api/attachments/1/file -H "$TOKEN"
```

---

## کاربر و امتیاز

### GET /api/users/me
### GET /api/users/me/points
```json
{
  "points": 23,
  "streak_count": 4,
  "rank": 2,
  "total_users": 31,
  "activities": 9,
  "history": [
    {"id": 41, "amount": 5, "reason": "create_homework", "description": null,
     "created_at": "2025-09-23T10:12:00"}
  ]
}
```

### GET /api/ranking?limit=10
```json
[
  {"rank": 1, "user_id": 7, "display_name": "نگار", "username": "negar_std",
   "points": 58, "activities": 21},
  {"rank": 2, "user_id": 4, "display_name": "علی", "username": "ali_std",
   "points": 43, "activities": 17}
]
```

### GET /api/ranking/me
```json
{"rank": 2, "total_users": 31, "points": 43, "streak_count": 5, "activities": 17}
```

---

## قوانین امتیازدهی

### GET /api/points/rules (همه)
```json
{
  "enabled": true,
  "actions": {
    "first_daily_activity": 2,
    "streak_bonus": 1,
    "streak_bonus_max": 10,
    "view_homework_today": 1,
    "create_homework": 5,
    "edit_homework": 2,
    "add_attachment": 1
  }
}
```

### PUT /api/points/rules (SUPER_ADMIN)
```bash
curl -X PUT http://localhost:8000/api/points/rules \
  -H "$TOKEN_ADMIN" -H "Content-Type: application/json" \
  -d '{"enabled": true, "actions": {"create_homework": 10, "new_rule": 3}}'
```
کلیدهای جدید هم پذیرفته می‌شوند (کلید: `a-z0-9_`، مقدار: ۰..۱۰۰۰).

---

## مسیرهای مدیریتی (فقط SUPER_ADMIN)

### GET /api/admin/users?q=&role=&banned=&page=&page_size=
### GET /api/admin/users/{id}
### PUT /api/admin/users/{id}/role
```bash
curl -X PUT http://localhost:8000/api/admin/users/9/role \
  -H "$TOKEN_ADMIN" -H "Content-Type: application/json" \
  -d '{"role": "CONTRIBUTOR"}'
```
> `role` فقط `USER` یا `CONTRIBUTOR` می‌پذیرد؛ `SUPER_ADMIN` از طریق env تعیین می‌شود.

### POST /api/admin/users/{id}/ban و /unban
```bash
curl -X POST http://localhost:8000/api/admin/users/9/ban \
  -H "$TOKEN_ADMIN" -H "Content-Type: application/json" \
  -d '{"reason": "ارسال اسپم"}'
```

### POST /api/admin/users/{id}/points/adjust
```bash
curl -X POST http://localhost:8000/api/admin/users/9/points/adjust \
  -H "$TOKEN_ADMIN" -H "Content-Type: application/json" \
  -d '{"amount": 5, "note": "مسابقه ریاضی"}'
```

### GET /api/admin/stats
```json
{
  "users": {"total": 31, "banned": 1,
            "by_role": {"USER": 27, "CONTRIBUTOR": 3, "SUPER_ADMIN": 1}},
  "homework": {"total": 84, "today": 3, "upcoming": 5},
  "top_subjects": [{"subject": "ریاضی", "count": 21}]
}
```

### GET /api/admin/audit-logs?action=&entity_type=&actor_id=&page=&page_size=
```json
{"items": [
  {"id": 120, "actor_id": 1, "actor_name": "مدیر کلاس",
   "action": "user.role_change", "entity_type": "user", "entity_id": "9",
   "details": {"from": "USER", "to": "CONTRIBUTOR"},
   "source": "telegram", "created_at": "2025-09-23T09:41:02"}
], "total": 120, "page": 1, "page_size": 20, "pages": 6}
```

### GET /api/admin/settings و PUT /api/admin/settings/{key}
```bash
curl -X PUT http://localhost:8000/api/admin/settings/class_name \
  -H "$TOKEN_ADMIN" -H "Content-Type: application/json" \
  -d '{"value": "کلاس نهم ۲"}'
```

### کلیدهای API (برای کلاینت‌های سروری)
```bash
# ساخت (مقدار خام فقط یک بار نمایش داده می‌شود)
curl -X POST http://localhost:8000/api/admin/api-keys \
  -H "$TOKEN_ADMIN" -H "Content-Type: application/json" -d '{"name": "panel"}'
# → {"id": 1, "name": "panel", "key": "cb_9f3a...", "key_prefix": "cb_9f3a", ...}

# استفاده
curl http://localhost:8000/api/users/me -H "X-API-Key: cb_9f3a..."

# فهرست / ابطال
curl http://localhost:8000/api/admin/api-keys -H "$TOKEN_ADMIN"
curl -X DELETE http://localhost:8000/api/admin/api-keys/1 -H "$TOKEN_ADMIN"
```

---

## سایر

| مسیر | توضیح |
|---|---|
| `GET /health` ، `GET /api/health` | healthcheck |
| `GET /docs` ، `GET /redoc` | مستندات تعاملی |
| `GET /admin` | پنل مدیریت وب |

## کدهای خطا

| کد | معنی |
|---|---|
| `400` | درخواست نامعتبر (منطق کسب‌وکار) |
| `401` | احراز هویت نشده / توکن یا کد نامعتبر |
| `403` | نقش کافی نیست / کاربر بن است |
| `404` | یافت نشد |
| `409` | تعارض |
| `422` | اعتبارسنجی ورودی ناموفق |
| `429` | محدودیت نرخ (هدر `Retry-After` دارد) |

قالب یکسان خطا: `{"error": "<code>", "detail": "<پیام فارسی>"}`
