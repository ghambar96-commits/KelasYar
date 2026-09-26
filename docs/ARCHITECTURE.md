# معماری و طراحی — کلاس‌یار

## ۱. نمای کلی

```
┌────────────────┐  ┌──────────────────┐  ┌─────────────────┐
│  Telegram Bot  │  │    REST API      │  │  Web Admin Panel│
│  (aiogram 3)   │  │   (FastAPI)      │  │ (static SPA)    │
└───────┬────────┘  └────────┬─────────┘  └────────┬────────┘
        │        ┌───────────┴──────────────────┐   │
        │        │   Presentation Layer         │   │
        │        │  (فقط I/O؛ بدون منطق)        │   │
        └────────┴───────────┬──────────────────┘   │
                             ▼                      │
                   ┌─────────────────────┐          │
                   │    Service Layer    │◄─────────┘
                   │ users / homework /  │
                   │ points / audit /    │
                   │ auth / settings     │
                   │  + RBAC دوباره‌رسی  │
                   └─────────┬───────────┘
                             ▼
                   ┌─────────────────────┐
                   │  SQLAlchemy 2 async │
                   │  (Models / Session) │
                   └─────────┬───────────┘
                             ▼
                   ┌─────────────────────┐
                   │ SQLite / PostgreSQL │
                   └─────────────────────┘
```

**اصل کلیدی:** ربات تلگرام و REST API دو «پوستهٔ» متفاوت روی یک Service Layer مشترک‌اند. هر قاعدهٔ کسب‌وکار (مثلاً «فقط مدیر می‌تواند بن کند» یا «ثبت تکلیف ۵ امتیاز دارد») دقیقاً یک‌بار در سرویس‌ها نوشته شده و در هر دو مسیر اعمال می‌شود. به همین دلیل افزودن Web Panel / اپ موبایل در آینده فقط یک کلاینت جدید است.

## ۲. جریان یک درخواست

### ربات (مثال: ثبت تکلیف)
```
پیام کاربر
  → UserSessionMiddleware (outer)      : بازکردن session + شناسایی با telegram_id
    → اگر بن شده: پیام «مسدود هستید» و توقف
    → فیلتر MinRole(CONTRIBUTOR)       : RBAC لایهٔ ۱
      → هندلر FSM
        → homework_service.create()    : RBAC لایهٔ ۲ + Audit + Points
          → INSERT homework / audit_log / point_transactions
  → Middleware: commit (unit-of-work به‌ازای هر آپدیت)
```

### API (مثال: POST /api/homework)
```
POST /api/homework
  → RateLimitMiddleware (60/min به‌ازای توکن/کلید/IP)
  → get_current_user (JWT یا X-API-Key → بارگذاری تازهٔ نقش/بن از DB)
  → require_contributor (RBAC لایهٔ ۱)
  → Pydantic HomeworkCreate (اعتبارسنجی ورودی)
  → homework_service.create() (RBAC لایهٔ ۲ + Audit + Points)
  → 201 + HomeworkOut
```

## ۳. نقش‌ها و کنترل دسترسی

سلسله‌مراتب: `USER (۱) < CONTRIBUTOR (۲) < SUPER_ADMIN (۳)`

| عملیات | USER | CONTRIBUTOR | SUPER_ADMIN |
|---|:-:|:-:|:-:|
| مشاهدهٔ تکالیف (امروز/آینده/گذشته) و دانلود پیوست | ✅ | ✅ | ✅ |
| رتبه‌بندی و امتیاز خود | ✅ | ✅ | ✅ |
| ثبت / ویرایش / حذف تکلیف و پیوست | ❌ | ✅ | ✅ |
| مدیریت کاربران (نقش، بن) | ❌ | ❌ | ✅ |
| تغییر قوانین امتیازدهی و تنظیمات | ❌ | ❌ | ✅ |
| امتیاز دستی، آمار، Audit Log، کلیدهای API | ❌ | ❌ | ✅ |
| تبدیل کاربر به SUPER_ADMIN | ❌ | ❌ | ❌ (فقط env) |

قواعد سخت‌گیرانه در سرویس‌ها:
- نقش SUPER_ADMIN فقط از `SUPER_ADMIN_TELEGRAM_IDS` (env) و فقط هنگام تماس کاربر با ربات اعطا می‌شود.
- مدیر نمی‌تواند نقش خودش یا مدیرِ دیگر را عوض کند و کسی را SUPER_ADMIN کند.
- مدیر قابل بن نیست.
- توکن‌ها stateless هستند ولی نقش/بن هر بار از DB خوانده می‌شود → سلب دسترسی آنی.

## ۴. اسکیمای دیتابیس

```sql
users
  id              INTEGER PK
  telegram_id     BIGINT UNIQUE INDEX   -- هویت واقعی
  username        VARCHAR(64)           -- صرفاً نمایشی
  first_name      VARCHAR(128)
  last_name       VARCHAR(128)
  role            VARCHAR(20) INDEX     -- USER | CONTRIBUTOR | SUPER_ADMIN
  points          INTEGER DEFAULT 0     -- کش مجموع (دفتر کل: point_transactions)
  streak_count    INTEGER DEFAULT 0
  last_activity_date DATE
  is_banned       BOOLEAN DEFAULT FALSE
  ban_reason      VARCHAR(255)
  created_at / updated_at

homeworks
  id              INTEGER PK
  title           VARCHAR(200)
  description     TEXT
  subject         VARCHAR(100) INDEX
  homework_date   DATE INDEX
  due_date        DATE NULL             -- CHECK(due_date >= homework_date)
  created_by      FK→users.id
  updated_by      FK→users.id NULL
  deleted_at      DATETIME INDEX NULL   -- حذف نرم
  deleted_by      FK→users.id NULL
  created_at / updated_at

attachments
  id              INTEGER PK
  homework_id     FK→homeworks.id (CASCADE) INDEX
  file_name       VARCHAR(255)
  file_path       VARCHAR(512) UNIQUE  -- نسبت به UPLOAD_DIR
  mime_type       VARCHAR(128)
  file_size       INTEGER
  telegram_file_id VARCHAR(255)        -- ارسال مجدد سریع در تلگرام
  created_by      FK→users.id
  created_at

point_transactions                -- دفتر کل پیوست‌نیافتنی
  id, user_id FK INDEX, amount (+/-), reason VARCHAR(50) INDEX,
  description, meta JSON, awarded_by FK NULL, created_at INDEX

settings                          -- پیکربندی قابل‌ویرایش در زمان اجرا
  key VARCHAR(64) PK, value JSON, description, updated_by, updated_at

audit_logs
  id, actor_user_id FK NULL INDEX, action VARCHAR(64) INDEX,
  entity_type INDEX, entity_id, details JSON,
  source ('telegram'|'api'|'system'), created_at INDEX

auth_codes                        -- کد یک‌بارمصرف ربات→JWT
  id, user_id FK INDEX, code UNIQUE, expires_at, used_at, created_at

api_keys                          -- کلید ماشین (hash فقط)
  id, name, key_prefix INDEX, key_hash UNIQUE, owner_user_id FK,
  is_active, last_used_at, created_at / updated_at
```

تصمیم‌های طراحی:
- **حذف نرم تکالیف** برای حفظ ارجاع‌های Audit و امکان بازیابی.
- **امتیاز به‌صورت دفتر کل**: `users.points` فقط کش است؛ همهٔ تغییرات در `point_transactions` ثبت می‌شوند تا بازمحاسبه و حسابرسی ممکن بماند.
- **قوانین امتیاز در `settings` (JSON)**: SUPER_ADMIN مقادیر را عوض می‌کند و می‌تواند **کلید جدید** اضافه کند بدون هیچ تغییری در کد.
- `telegram_file_id` در attachments باعث می‌شود ربات فایل را بدون دانلود/آپلود مجدد فوراً بفرستد؛ فایل محلی هم برای REST API نگه داشته می‌شود.

## ۵. امتیازدهی و استریک

```
record_daily_activity(user):            # یک‌بار در روزِ محلی (TIMEZONE)
    اگر امروز قبلاً ثبت شده → هیچ
    اگر دیروز فعال بوده → streak += 1  وگرنه streak = 1
    award("first_daily_activity")
    award("streak_bonus", مقدار = streak_bonus × min(streak, streak_bonus_max))

award(user, reason):
    قوانین را از settings بخوان؛ اگر غیرفعال یا مقدار 0 → هیچ
    اگر once_per_day و امروز گرفته → هیچ
    INSERT point_transactions + users.points += amount
```

همهٔ اعداد از `settings.point_rules` می‌آیند. `view_homework_today` با پرچم once_per_day اعطا می‌شود (دیدن امروز از ربات یا API).

## ۶. احراز هویت API

```
ربات تلگرام ── /api ──► auth_codes (۱۰ دقیقه، یک‌بارمصرف)
                              │
کلاینت ── POST /api/auth/exchange ──► JWT (HS256, sub=user_id, exp=۷روز)
کلاینت ── Authorization: Bearer ─► get_current_user ──► SELECT user (نقش/بن تازه)

پنل سروری ── X-API-Key ──► sha256 lookup در api_keys ──► کاربرِ مالک کلید
```

- JWT حاوی role است ولی فقط «اطلاعاتی» است؛ مرجع نهایی همیشه DB.
- ابطال کلید یا بن مالک، بلافاصله دسترسی را می‌بندد.

## ۷. اجرا و مقیاس

| حالت | دستور | توضیح |
|---|---|---|
| تک‌پروسه (پیش‌فرض) | `python run.py` | API + ربات روی یک event loop |
| تفکیک | `run.py --api-only` و `run.py --bot-only` | برای scale مستقل |
| Docker | `docker compose up -d` | PostgreSQL + app + مهاجرت خودکار |

مقیاس‌پذیری بیشتر:
- FSM ربات از `MemoryStorage` به `RedisStorage` (aiogram) تغییر کند.
- حافظهٔ Rate Limiter به Redis منتقل شود (الان in-memory برای تک‌نمونه).
- API با چند worker پشت nginx (ربات فقط در یک worker اجرا شود).

## ۸. نکات امنیتی پیاده‌سازی‌شده

1. شناسایی با Telegram ID عددی — username هیچ‌جا برای مجوز استفاده نمی‌شود.
2. RBAC دولایه (dependency + service).
3. اعتبارسنجی کامل ورودی (Pydantic) شامل محدوده‌های تاریخ، طول‌ها و سایز آپلود.
4. فقط ORM با bind parameters — بدون SQL خام.
5. Rate limiting (IP/توکن/کلید) + معافیت preflight.
6. Secretها فقط env؛ `.env` در `.gitignore`.
7. Audit log برای همهٔ عملیات حساس با منبع (telegram/api/system).
8. API Key به‌صورت hash؛ نمایش تک‌بار.
9. سرو فایل با بررسی path traversal (resolve داخل UPLOAD_DIR).
10. کد اتصال یک‌بارمصرف با انقضا؛ ابطال کدهای قبلی.
