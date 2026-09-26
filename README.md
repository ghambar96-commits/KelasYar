# 📚 کلاس‌یار (KelasYar)

ربات تلگرام + REST API حرفه‌ای برای **مدیریت تکالیف یک کلاس مدرسه**.

دانش‌آموزانِ منتخب (همکارها) تکالیف روزانه را ثبت می‌کنند و بقیهٔ کلاس آن را از طریق ربات یا API مشاهده می‌کنند؛ همراه با سیستم امتیازدهی، رتبه‌بندی، لاگ رویدادها و پنل مدیریت.

---

## فهرست

1. [امکانات](#امکانات)
2. [معماری](#معماری)
3. [استک فناوری و دلیل انتخاب](#استک-فناوری)
4. [ساختار پروژه](#ساختار-پروژه)
5. [نصب و راه‌اندازی سریع](#نصب-و-راه‌اندازی-سریع)
6. [ساخت ربات تلگرام و قرار دادن توکن](#۱-ساخت-ربات-تلگرام)
7. [تعیین SUPER_ADMIN](#۲-تعیین-super_admin)
8. [اجرای Development](#۳-اجرای-development)
9. [اضافه کردن Contributor](#۴-اضافه-کردن-contributor)
10. [Deploy در Production](#۵-deploy-در-production)
11. [پنل مدیریت وب](#پنل-مدیریت-وب)
12. [سیستم امتیازدهی](#سیستم-امتیازدهی)
13. [API و احراز هویت](#api)
14. [امنیت](#امنیت)
15. [تست‌ها](#تست‌ها)
16. [رفع اشکال](#رفع-اشکال)

---

## امکانات

| بخش | توضیح |
|---|---|
| 🎭 نقش‌ها | `SUPER_ADMIN` / `CONTRIBUTOR` / `USER` با RBAC کامل |
| 📚 تکالیف | ثبت چند تکلیف در روز، درس، عنوان، توضیحات، تاریخ، مهلت، **پیوست فایل/عکس** |
| 🤖 ربات تلگرام | منوی فارسی برای هر نقش، ثبت تکلیف به‌صورت گفت‌وگویی (FSM)، ویرایش/حذف، مشاهدهٔ امروز/آینده/گذشته |
| 🏆 امتیازدهی | قوانین **قابل تغییر در زمان اجرا** (دیتابیس)، استریک روزانه، دفتر کل تراکنش‌ها |
| 🥇 رتبه‌بندی | رتبه، نام، امتیاز، تعداد فعالیت‌ها |
| 🔌 REST API | ۲۸ مسیر مستند (Swagger خودکار) + RBAC + Rate Limit |
| 🛡 امنیت | شناسایی با Telegram ID (نه username)، JWT + API Key، اعتبارسنجی ورودی، ضد SQL Injection، Audit Log |
| 🖥 پنل مدیریت | وب (در `/admin`) + داخل خود ربات |

---

## معماری

```
┌────────────────┐   ┌──────────────────┐   ┌─────────────────┐
│  Telegram Bot  │   │   REST API       │   │  Web Admin Panel│
│   (aiogram 3)  │   │   (FastAPI)      │   │  (static SPA)   │
└───────┬────────┘   └────────┬─────────┘   └────────┬────────┘
        │      هر دو از یک Backend مشترک استفاده می‌کنند      │
        └──────────────┬───────┴──────────────────────┘
                       ▼
              ┌─────────────────┐
              │  Service Layer  │  ← تمام منطق کسب‌وکار + RBAC دوباره‌رسی
              │ users / homework│
              │ points / audit  │
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │ SQLAlchemy 2    │  (async ORM)
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │ SQLite / Postgres│
              └─────────────────┘
```

- **Telegram Bot و REST API از یک Service Layer مشترک استفاده می‌کنند**؛ هیچ منطقی در دو جا تکرار نشده است.
- افزودن Web Panel یا اپ موبایل در آینده = فقط یک کلاینت جدید روی همان API.
- ربات و API می‌توانند در **یک پروسه** (پیش‌فرض) یا **پروسه‌های جدا** (`run.py --api-only` / `--bot-only`) اجرا شوند.

جزئیات کامل: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## استک فناوری

| ابزار | چرا؟ |
|---|---|
| **Python 3.11+ / FastAPI** | async، سریع، اعتبارسنجی با Pydantic و **مستندات Swagger خودکار** (دقیقاً نیاز «API مستند» پروژه) |
| **aiogram 3** | مدرن‌ترین فریم‌ورک async ربات تلگرام؛ FSM داخلی برای فلوهای گفت‌وگویی، هم‌روید‌لوپ با FastAPI |
| **SQLAlchemy 2 (async) + Alembic** | ORM استاندارد صنعت + مهاجرت‌های نسخه‌دار؛ تعویض SQLite↔PostgreSQL فقط با تغییر یک متغیر محیطی |
| **SQLite (dev) / PostgreSQL (prod)** | SQLite برای شروع بدون دردسر؛ PostgreSQL برای مقیاس واقعی |
| **PyJWT** | توکن‌های استاندارد JWT برای API |
| **jdatetime** | نمایش/دریافت تاریخ شمسی برای دانش‌آموزان ایرانی |

---

## ساختار پروژه

```
kelasyar/
├── run.py                  # نقطهٔ ورود (API + ربات + مهاجرت)
├── run.bat                 # اجرا در ویندوز با دابل‌کلیک
├── run.sh                  # اجرا در لینوکس/مک
├── requirements.txt        # وابستگی‌های اصلی
├── requirements-dev.txt    # + ابزار تست
├── alembic.ini             # تنظیمات مهاجرت
├── migrations/             # مهاجرت‌های دیتابیس
├── .env.example            # نمونهٔ متغیرهای محیطی
├── Dockerfile
├── docker-compose.yml      # app + postgres
├── app/
│   ├── config.py           # تنظیمات از env (هیچ Secret هاردکد نشده)
│   ├── database.py         # engine + session
│   ├── main.py             # ساخت FastAPI + lifespan (اجرای ربات)
│   ├── core/               # امنیت (JWT/کلید)، Rate Limit، استثناها، لاگ
│   ├── models/             # ۹ جدول ORM (اسکیما در پایین)
│   ├── schemas/            # اعتبارسنجی Pydantic
│   ├── services/           # منطق کسب‌وکار (مشترک بین ربات و API)
│   ├── api/                # مسیرهای REST + RBAC
│   ├── bot/                # ربات تلگرام (هندلرها، کیبورد، متن فارسی)
│   ├── static/admin.html   # پنل مدیریت وب
│   └── utils/              # تاریخ شمسی، زمان، فایل
├── scripts/seed_demo.py    # دادهٔ نمونه
├── tests/                  # ۴۰ تست خودکار
└── docs/
    ├── API.md              # مستندات کامل API با نمونه
    └── ARCHITECTURE.md     # طراحی، اسکیما، ماتریس دسترسی
```

### اسکیمای دیتابیس (خلاصه)

| جدول | فیلدهای کلیدی |
|---|---|
| `users` | telegram_id (یکتا)، username، first/last_name، role، points، streak_count، is_banned، timestamps |
| `homeworks` | title، description، subject، homework_date، due_date، created_by، deleted_at (حذف نرم) |
| `attachments` | homework_id، file_name، file_path، mime_type، file_size، **telegram_file_id** |
| `point_transactions` | user_id، amount، reason، meta، awarded_by، created_at (دفتر کل) |
| `settings` | key/value (JSON) — قوانین امتیاز، نام کلاس و… |
| `audit_logs` | actor_user_id، action، entity_type/id، details، source، created_at |
| `auth_codes` | user_id، code، expires_at، used_at (کد یک‌بارمصرف اتصال) |
| `api_keys` | name، key_prefix، key_hash، owner_user_id، last_used_at |

نسخهٔ کامل با روابط: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## نصب و راه‌اندازی سریع

### ویندوز (ساده‌ترین راه)

1. **Python 3.10+** را از [python.org](https://www.python.org/downloads/) نصب کنید (تیک *Add Python to PATH* را بزنید).
2. پوشهٔ پروژه را باز کنید و **روی `run.bat` دابل‌کلیک** کنید.
3. بار اول: فایل `.env` خودکار ساخته می‌شود → سرور را ببندید، `.env` را ویرایش کنید (توکن ربات و آیدی مدیر) و دوباره `run.bat` را اجرا کنید.
4. اگر تلگرام فیلتر است، **Hiddify را روشن** بگذارید — پروکسی خودکار تشخیص داده می‌شود (بخش [۲.۵](#۲۵-اتصال-از-طریق-پروکسی-hiddify-و-مشابه)).

### لینوکس / مک

```bash
cd kelasyar
./run.sh          # یا: python3 -m venv .venv && source .venv/bin/activate &&
                  #     pip install -r requirements.txt && python run.py
```

پس از اجرا:

- 🖥 پنل مدیریت: `http://localhost:8000/admin`
- 📖 مستندات API: `http://localhost:8000/docs`

---

## ۱. ساخت ربات تلگرام

1. در تلگرام به [@BotFather](https://t.me/BotFather) پیام بدهید: `/newbot`
2. یک نام (مثلاً «کلاس‌یار ۹/۲») و یک username منتهی به `bot` (مثلاً `kelas9_2_hw_bot`) انتخاب کنید.
3. BotFather یک **توکن** مثل `7712345678:AAF...` می‌دهد.
4. آن را در فایل `.env` بگذارید:
   ```env
   TELEGRAM_BOT_TOKEN="7712345678:AAF..."
   ```
⚠️ توکن را با کسی به اشتراک نگذارید؛ اگر لو رفت از BotFather با `/revoke` آن را عوض کنید.

## ۲. تعیین SUPER_ADMIN

- آیدی عددی تلگرام خودتان را پیدا کنید (از [@userinfobot](https://t.me/userinfobot) بفرستید `/start`).
- در `.env`:
  ```env
  SUPER_ADMIN_TELEGRAM_IDS="123456789"
  ```
- حالا در ربات `/start` بزنید — نقش شما خودکار **SUPER_ADMIN** می‌شود.

**نکتهٔ امنیتی مهم:** SUPER_ADMIN **فقط** از طریق این متغیر محیطی اعطا می‌شود. از داخل ربات یا API (حتی توسط خود مدیر) نمی‌توان کسی را SUPER_ADMIN کرد؛ بنابراین قابل جعل با username نیست و کاربر عادی هیچ راهی برای ارتقای دسترسی ندارد.

## ۲.۵ اتصال از طریق پروکسی (Hiddify و مشابه)

اگر تلگرام در شبکهٔ شما فیلتر است، **هیچ کار اضافه‌ای لازم نیست** — حالت پروکسی خودکار است:

1. ربات ابتدا **اتصال مستقیم** را امتحان می‌کند (اگر Hiddify در حالت TUN باشد همین مستقیم کار می‌کند).
2. اگر مستقیم ممکن نبود، پورت‌های پروکسی محلیِ رایج را در چند میلی‌ثانیه بررسی می‌کند و اولین مسیر سالم را برمی‌دارد:
   `Hiddify: 12334` (پورت Mixed — هم HTTP هم SOCKS)، `v2rayN: 10808/10809`، `Clash: 7890`، `SOCKS عمومی: 1080`
3. اگر حین کار شبکه عوض شود (Hiddify را روشن/خاموش کنید)، ربات هر **۱۵ ثانیه** مسیر را دوباره تشخیص می‌دهد و خودش وصل می‌شود — نیازی به ری‌استارت نیست.

```env
# پیش‌فرض در .env (حالت خودکار):
TELEGRAM_PROXY_URL=""
TELEGRAM_PROXY_AUTO=true

# یا صریح، اگر پورت سفارشی دارید:
TELEGRAM_PROXY_URL="socks5://127.0.0.1:12334"
```

در لاگ هم می‌بینید از کدام مسیر وصل شده: `bot authorized as @your_bot via local proxy http://127.0.0.1:12334`

## ۳. اجرای Development

```bash
# 1) محیط مجازی و وابستگی‌ها
python -m venv .venv
source .venv/bin/activate          # ویندوز: .venv\Scripts\activate
pip install -r requirements-dev.txt

# 2) تنظیمات
cp .env.example .env               # ویندوز: copy .env.example .env
# JWT_SECRET را با یک مقدار قوی پر کنید (python run.py --setup خودکار می‌سازد)

# 3) مهاجرت دیتابیس
alembic upgrade head

# 4) (اختیاری) دادهٔ نمونه
python scripts/seed_demo.py

# 5) اجرا
python run.py                      # API + ربات
# یا فقط API با ری‌لود سریع برای توسعه:
uvicorn app.main:app --reload
# یا فقط ربات:
python run.py --bot-only
```

## ۴. اضافه کردن Contributor

فقط SUPER_ADMIN می‌تواند (طبق طراحی پروژه):

- **داخل ربات:** 🛠 پنل مدیریت → 👥 کاربران → کاربر را انتخاب کنید → «⬆️ ارتقا به همکار تکالیف». (کاربر باید قبلاً حداقل یک بار ربات را `/start` کرده باشد.)
- **از پنل وب:** بخش «👥 کاربران» → دکمهٔ «ارتقا».
- **از API:** `PUT /api/admin/users/{id}/role` با body `{"role": "CONTRIBUTOR"}`.

برای حذف دسترسی، همان‌جا «سلب دسترسی» یا role `USER` را بگذارید.

## ۵. Deploy در Production

### گزینهٔ A) Docker (پیشنهادی)

```bash
cp .env.example .env      # مقادیر واقعی را پر کنید
docker compose up -d --build
```
`docker-compose.yml` شامل PostgreSQL + اپ است و مهاجرت‌ها خودکار اجرا می‌شوند.

### گزینهٔ B) سرور شخصی (systemd + uvicorn)

```ini
# /etc/systemd/system/kelasyar.service
[Unit]
Description=KelasYar homework bot
After=network.target

[Service]
User=kelasyar
WorkingDirectory=/opt/kelasyar
EnvironmentFile=/opt/kelasyar/.env
ExecStart=/opt/kelasyar/.venv/bin/python run.py --no-migrate
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now kelasyar
```

نکات production:
- دیتابیس را روی **PostgreSQL** بگذارید (`DATABASE_URL=postgresql+asyncpg://...` + `pip install asyncpg psycopg2-binary`).
- `AUTO_CREATE_TABLES=false` بماند و مهاجرت با `alembic upgrade head` انجام شود.
- پشت nginx قرار دهید و HTTPS فعال کنید.
- برای چند نمونه (scale افقی) حافظهٔ Rate Limiter را به Redis منتقل کنید و FSM ربات را `RedisStorage` کنید.

---

## پنل مدیریت وب

آدرس: `http://<server>/admin` — تک‌فایل، بدون نیاز به build.

1. در ربات دستور `/api` را بزنید تا **کد اتصال** بگیرید.
2. همان کد را در صفحهٔ ورود پنل وارد کنید (تبدیل به JWT می‌شود).

امکانات: داشبورد آمار، مدیریت تکالیف، مدیریت کاربران (نقش/بن/امتیاز)، رتبه‌بندی، ویرایش قوانین امتیازدهی، لاگ رویدادها و کلیدهای API.

## سیستم امتیازدهی

قوانین در جدول `settings` (کلید `point_rules`) ذخیره می‌شوند و **هیچ‌کدام هاردکد نیستند**. مقادیر پیش‌فرض (bootstrap):

| کلید | معنی | پیش‌فرض |
|---|---|---|
| `first_daily_activity` | اولین فعالیت هر روز | ۲ |
| `streak_bonus` | پاداش هر روز استریک | ۱ |
| `streak_bonus_max` | سقف روزهای محاسبهٔ استریک | ۱۰ |
| `view_homework_today` | مشاهدهٔ تکالیف امروز (روزی یک‌بار) | ۱ |
| `create_homework` | ثبت تکلیف توسط همکار | ۵ |
| `edit_homework` | ویرایش تکلیف | ۲ |
| `add_attachment` | ارسال پیوست | ۱ |

تغییر در زمان اجرا:
- ربات: 🛠 → ⚙️ قوانین امتیاز → ویرایش مقدار (مثلاً `create_homework 10`) یا فعال/غیرفعال کردن کل سیستم.
- API: `PUT /api/points/rules`

هر امتیاز یک ردیف در `point_transactions` است (دفتر کل)، بنابراین تاریخچه، حساب‌دستی مدیر و بازمحاسبهٔ آینده ممکن است.

## API

مستندات کامل با نمونهٔ Request/Response: [`docs/API.md`](docs/API.md) — و Swagger زنده: `/docs`

### احراز هویت (چطور کلاینت وب/موبایل وصل می‌شود)

```
کاربر در ربات:  /api   →   کد یک‌بارمصرف (۱۰ دقیقه اعتبار)
کلاینت:         POST /api/auth/exchange {"code": "..."}   →   JWT
بعدی:           Authorization: Bearer <JWT>
ماشین/پنل سروری: هدر  X-API-Key: cb_...  (کلید از /api/admin/api-keys)
```

نقش و وضعیت بن **در هر درخواست از دیتابیس خوانده می‌شود**؛ یعنی سلب دسترسی یا بن، بلافاصله روی توکن‌های موجود اثر می‌کند.

### خلاصهٔ مسیرها

| متد | مسیر | دسترسی |
|---|---|---|
| POST | `/api/auth/exchange` | عمومی |
| GET | `/api/homework/today` \| `/upcoming` \| `/past` | همهٔ کاربران |
| GET | `/api/homework` ، `/api/homework/{id}` ، `/api/subjects` | همهٔ کاربران |
| POST/PUT/DELETE | `/api/homework...` | CONTRIBUTOR+ |
| GET | `/api/attachments/{id}/file` | همهٔ کاربران |
| GET | `/api/ranking` ، `/api/ranking/me` ، `/api/users/me...` | همهٔ کاربران |
| GET/PUT | `/api/points/rules` | خواندن: همه / نوشتن: SUPER_ADMIN |
| همهٔ `/api/admin/*` | کاربران، نقش، بن، آمار، لاگ، تنظیمات، کلیدها | SUPER_ADMIN |

## امنیت

- ✅ شناسایی فقط با **Telegram User ID** عددی (username فقط اطلاعات نمایشی است و هر به‌روزرسانی می‌شود).
- ✅ RBAC در **دو لایه**: وابستگی‌های FastAPI + بازبینی داخل Service Layer.
- ✅ اعتبارسنجی تمام ورودی‌ها با Pydantic (طول، نوع، بازهٔ تاریخ‌ها، سایز فایل).
- ✅ ضد SQL Injection: فقط ORM با پارامترهای bind.
- ✅ Rate Limiting پیش‌فرض ۶۰ درخواست/دقیقه برای هر هویت (توکن/کلید/IP) + هدر `Retry-After`.
- ✅ توکن ربات، DATABASE_URL و JWT_SECRET فقط از Environment Variables.
- ✅ Audit Log برای ایجاد/ویرایش/حذف تکلیف، تغییر نقش، بن، تنظیمات، کلیدها.
- ✅ SUPER_ADMIN فقط از طریق env؛ تغییر نقش توسط کاربر عادی غیرممکن است.
- ✅ API Key فقط به‌صورت hash (SHA-256) ذخیره می‌شود و یک‌بار نمایش داده می‌شود.
- ✅ فایل‌های پیوست فقط از داخل `UPLOAD_DIR` و پس از احراز هویت سرو می‌شوند.

## تست‌ها

```bash
pip install -r requirements-dev.txt
pytest -v
```

پوشش: جریان احراز هویت، RBAC (USER/CONTRIBUTOR/SUPER_ADMIN)، CRUD و اعتبارسنجی تکلیف، پیوست‌ها، امتیاز و استریک، رتبه‌بندی، مدیریت کاربران (ارتقا/سلب/بن)، تنظیمات، کلیدهای API، Audit Log و Rate Limit — **۴۰ تست**.

## رفع اشکال

| مشکل | راه‌حل |
|---|---|
| `JWT_SECRET is not set` | `python run.py --setup` یا `.env` را پر کنید |
| ربات پاسخ نمی‌دهد | توکن را در `.env` چک کنید؛ لاگ `authorized as @...` را ببینید |
| «هیچکس مدیر نیست» | `SUPER_ADMIN_TELEGRAM_IDS` را با آیدی عددی درست تنظیم و `/start` بزنید |
| خطای دیتابیس قفل (SQLite) | برای استفادهٔ جدی به PostgreSQL مهاجرت کنید |
| پورت اشغال است | `python run.py --port 8001` |

---

ساخته‌شده با ❤️ برای کلاس‌های درس.
