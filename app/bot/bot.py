"""Bot assembly & polling lifecycle.

Includes automatic proxy support for networks where Telegram is blocked
(e.g. Iran):

  1. direct connection is always tried first (works when Hiddify runs in
     TUN mode, or on unrestricted networks);
  2. if that fails, well-known LOCAL proxy ports are probed
     (Hiddify 12334, v2rayN 10808/10809, Clash 7890, generic 1080/8118)
     and the first working route is used;
  3. a supervisor loop re-detects the route whenever connectivity changes
     (e.g. the user turns Hiddify on/off while the app is running).

An explicit proxy can be forced via TELEGRAM_PROXY_URL in .env.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from urllib.parse import urlsplit

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramConflictError, TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.utils.token import TokenValidationError

from app.config import get_settings
from app.core.logging import get_logger
from app.bot.middlewares import UserSessionMiddleware
from app.bot.handlers import admin, common, manage, ranking, view

logger = get_logger("bot")

RETRY_SECONDS = 15
CONNECT_TIMEOUT = 10.0
PORT_PROBE_TIMEOUT = 1.0

# Well-known local proxy endpoints. Hiddify's "mixed" port serves BOTH
# HTTP-CONNECT and SOCKS5 on the same port, so it is listed twice.
PROXY_CANDIDATES = [
    "http://127.0.0.1:12334",    # Hiddify (mixed)
    "socks5://127.0.0.1:12334",  # Hiddify (mixed)
    "socks5://127.0.0.1:10808",  # v2rayN / HiddifyNG (socks)
    "http://127.0.0.1:10809",    # v2rayN (http)
    "http://127.0.0.1:7890",     # Clash / Mihomo (mixed)
    "socks5://127.0.0.1:7890",
    "socks5://127.0.0.1:1080",   # generic socks
    "http://127.0.0.1:8118",     # privoxy
]

COMMANDS = [
    BotCommand(command="start", description="شروع و نمایش منو"),
    BotCommand(command="menu", description="منوی اصلی"),
    BotCommand(command="help", description="راهنما"),
    BotCommand(command="api", description="کد اتصال به پنل وب / API"),
    BotCommand(command="cancel", description="لغو عملیات جاری"),
    BotCommand(command="add_homework", description="ثبت تکلیف جدید"),
]


def create_bot(proxy: str | None = None) -> Bot:
    settings = get_settings()
    session: AiohttpSession | None = None
    if proxy:
        session = AiohttpSession(proxy=proxy)
    return Bot(
        token=settings.telegram_bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    middleware = UserSessionMiddleware()
    dp.message.outer_middleware(middleware)
    dp.callback_query.outer_middleware(middleware)

    # Router order matters:
    #  common  -> commands (/start /cancel ...) must win over FSM states
    #  admin   -> guarded admin flows
    #  manage  -> contributor FSM flows
    #  ranking -> menu buttons
    #  view    -> menu buttons + fallback handlers (registered last)
    dp.include_routers(common.router, admin.router, manage.router, ranking.router, view.router)
    return dp


# ------------------------------------------------------------- proxy picking
def _proxy_endpoint(proxy_url: str) -> tuple[str, int] | None:
    """Extract (host, port) from a proxy URL; None when malformed."""
    try:
        parts = urlsplit(proxy_url)
        if not parts.hostname or parts.port is None:
            return None
        return parts.hostname, parts.port
    except ValueError:
        return None


async def _tcp_port_open(host: str, port: int, timeout: float = PORT_PROBE_TIMEOUT) -> bool:
    """Fast local port check so closed proxies are skipped in milliseconds."""
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
    except Exception:  # noqa: BLE001
        return False
    with suppress(Exception):
        writer.close()
    with suppress(Exception):
        await writer.wait_closed()
    return True


async def _probe(proxy: str | None) -> Bot:
    """Call get_me() through the given route; raises on any failure."""
    bot = create_bot(proxy)
    try:
        me = await asyncio.wait_for(bot.get_me(), timeout=CONNECT_TIMEOUT)
        how = f"local proxy {proxy}" if proxy else "direct connection"
        logger.info("bot authorized as @%s via %s", me.username, how)
        if proxy:
            logger.info("proxy mode active — Hiddify/VPN detected on this port")
        return bot
    except Exception:
        with suppress(Exception):
            await bot.session.close()
        raise


async def resolve_bot() -> Bot:
    """Return a Bot connected through the first working route to Telegram.

    Order: explicit TELEGRAM_PROXY_URL (if set) -> direct -> auto-detected
    local proxies (when TELEGRAM_PROXY_AUTO is enabled).
    """
    settings = get_settings()
    explicit = settings.telegram_proxy_url.strip()

    order: list[str | None] = []
    if explicit:
        order.append(explicit)
    order.append(None)  # direct is always attempted (Hiddify TUN / open networks)
    if settings.telegram_proxy_auto:
        order.extend(p for p in PROXY_CANDIDATES if p != explicit)

    tried: list[str] = []
    for proxy in order:
        label = proxy or "direct"
        if proxy:
            endpoint = _proxy_endpoint(proxy)
            if endpoint is None:
                logger.warning("invalid TELEGRAM_PROXY_URL: %r — skipping", proxy)
                continue
            if not await _tcp_port_open(*endpoint):
                tried.append(f"{label} (port closed)")
                continue
        try:
            return await _probe(proxy)
        except (TokenValidationError, TelegramUnauthorizedError):
            raise  # the token itself is invalid — no route can fix that
        except Exception as exc:  # noqa: BLE001
            tried.append(f"{label} ({type(exc).__name__})")

    raise ConnectionError(
        "Telegram unreachable — tried: " + ", ".join(tried)
        + ". تلگرام در این شبکه در دسترس نیست؛ Hiddify را روشن کنید تا دوباره تلاش شود."
    )


# ------------------------------------------------------------ polling loop
async def run_bot_forever() -> None:
    """Supervised polling: re-detects the proxy route when the network changes.

    Used both by the API process (asyncio task in the FastAPI lifespan)
    and by `python run.py --bot-only`.
    """
    settings = get_settings()
    if not settings.bot_enabled_effective:
        logger.warning("bot not enabled – nothing to do")
        return

    dp = build_dispatcher()
    attempt = 0
    while True:
        bot: Bot | None = None
        try:
            bot = await resolve_bot()
            attempt = 0
            await bot.set_my_commands(COMMANDS, scope=BotCommandScopeDefault())
            logger.info("bot polling started")
            await dp.start_polling(bot)
            logger.info("bot polling stopped")
            return
        except asyncio.CancelledError:
            logger.info("bot polling cancelled")
            raise
        except (TokenValidationError, TelegramUnauthorizedError):
            logger.error(
                "BOT TOKEN is invalid — check TELEGRAM_BOT_TOKEN in .env "
                "and get a fresh one from @BotFather (/revoke)."
            )
            return
        except TelegramConflictError:
            logger.error(
                "409 Conflict: another polling/webhook instance is already running "
                "with this token. Stop the other instance and restart."
            )
            return
        except Exception as exc:  # noqa: BLE001
            attempt += 1
            logger.warning(
                "cannot reach Telegram (%s: %s) — attempt #%s, retrying in %ss. "
                "اگر تلگرام فیلتر است Hiddify را روشن کنید تا مسیر پروکسی تشخیص داده شود.",
                type(exc).__name__,
                exc,
                attempt,
                RETRY_SECONDS,
            )
            await asyncio.sleep(RETRY_SECONDS)
        finally:
            if bot is not None:
                with suppress(Exception):
                    await bot.session.close()
