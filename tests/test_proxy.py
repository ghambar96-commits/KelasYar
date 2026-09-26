"""Proxy auto-detection tests (Hiddify / v2rayN / Clash local proxies)."""

from __future__ import annotations

import asyncio
import time

import pytest

from app.bot import bot as bot_module
from app.bot.bot import PROXY_CANDIDATES, _proxy_endpoint, _tcp_port_open


async def test_proxy_endpoint_parsing():
    assert _proxy_endpoint("socks5://user:pass@127.0.0.1:1080") == ("127.0.0.1", 1080)
    assert _proxy_endpoint("http://127.0.0.1:12334") == ("127.0.0.1", 12334)
    assert _proxy_endpoint("socks5://127.0.0.1") is None  # no port
    assert _proxy_endpoint("not-a-url") is None


async def test_candidate_list_contains_hiddify():
    ports = [p for p in PROXY_CANDIDATES if "12334" in p]
    assert any(p.startswith("http://") for p in ports)
    assert any(p.startswith("socks5://") for p in ports)


async def test_tcp_port_probe():
    async def closer(reader, writer):
        writer.close()

    server = await asyncio.start_server(closer, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    try:
        assert await _tcp_port_open("127.0.0.1", port) is True
    finally:
        server.close()

    start = time.monotonic()
    assert await _tcp_port_open("127.0.0.1", 1) is False  # nothing listens on port 1
    assert time.monotonic() - start < 2.0, "closed ports must be skipped fast"


async def test_resolve_reports_all_failed_routes(monkeypatch):
    """When every route fails, a descriptive ConnectionError lists the attempts."""
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "123456:ABCdefGHIjklMNOpqrs")
    monkeypatch.setattr(settings, "telegram_proxy_url", "")
    monkeypatch.setattr(settings, "telegram_proxy_auto", True)

    async def failing_probe(proxy):
        raise ConnectionError("simulated: direct blocked")

    monkeypatch.setattr(bot_module, "_probe", failing_probe)

    with pytest.raises(ConnectionError) as err:
        await bot_module.resolve_bot()

    message = str(err.value)
    assert "direct (ConnectionError)" in message
    assert "port closed" in message  # candidates with closed ports skipped fast
    assert "Hiddify" in message  # helpful Persian hint for the operator


async def test_invalid_token_is_fatal_not_retried(monkeypatch):
    """A 401 from Telegram means the TOKEN is wrong – no route can fix it."""
    from aiogram.exceptions import TelegramUnauthorizedError

    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "123456:ABCdefGHIjklMNOpqrs")
    monkeypatch.setattr(settings, "telegram_proxy_url", "")
    monkeypatch.setattr(settings, "telegram_proxy_auto", True)

    async def unauthorized_probe(proxy):
        raise TelegramUnauthorizedError(method="getMe", message="Unauthorized")

    monkeypatch.setattr(bot_module, "_probe", unauthorized_probe)

    with pytest.raises(TelegramUnauthorizedError):
        await bot_module.resolve_bot()


# --------------------------------------------------------------------------
# End-to-end: a real request must traverse a local HTTP proxy (Hiddify-style
# mixed port). Requires outbound access to api.telegram.org; skipped otherwise.
# --------------------------------------------------------------------------
async def _start_connect_proxy(host: str, port: int):
    async def handle(reader, writer):
        try:
            line = await reader.readline()
            if not line:
                writer.close()
                return
            while True:
                header = await reader.readline()
                if header in (b"\r\n", b"\n", b""):
                    break
            method, target, _ = line.decode().split()
            if method != "CONNECT":
                writer.write(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
                await writer.drain()
                writer.close()
                return
            remote_host, _, remote_port = target.partition(":")
            remote_r, remote_w = await asyncio.open_connection(remote_host, int(remote_port))
            writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await writer.drain()

            async def pump(src, dst):
                try:
                    while True:
                        data = await src.read(65536)
                        if not data:
                            break
                        dst.write(data)
                        await dst.drain()
                except Exception:  # noqa: BLE001
                    pass
                finally:
                    try:
                        dst.close()
                    except Exception:  # noqa: BLE001
                        pass

            await asyncio.gather(pump(reader, remote_w), pump(remote_r, writer))
        except Exception:  # noqa: BLE001
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass

    return await asyncio.start_server(handle, host, port)


async def test_route_traverses_local_http_proxy(monkeypatch):
    from aiogram.exceptions import TelegramUnauthorizedError

    from app.bot.bot import resolve_bot
    from app.config import get_settings

    # pre-check outbound connectivity (CI sandboxes may block it)
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection("api.telegram.org", 443), timeout=5
        )
        writer.close()
    except Exception:  # noqa: BLE001
        pytest.skip("no outbound access to api.telegram.org in this environment")

    server = await _start_connect_proxy("127.0.0.1", 0)
    proxy_port = server.sockets[0].getsockname()[1]

    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "123456:INVALID_TOKEN_FOR_TESTS")
    monkeypatch.setattr(settings, "telegram_proxy_url", f"http://127.0.0.1:{proxy_port}")
    monkeypatch.setattr(settings, "telegram_proxy_auto", False)

    try:
        # An invalid token is used on purpose: TelegramUnauthorizedError can only
        # come back if the request REALLY went through our proxy to Telegram.
        with pytest.raises(TelegramUnauthorizedError):
            await asyncio.wait_for(resolve_bot(), timeout=30)
    finally:
        server.close()
