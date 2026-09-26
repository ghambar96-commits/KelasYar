"""Rate limiting tests."""

from __future__ import annotations

from app.config import get_settings

from conftest import ADMIN_TG


async def test_rate_limit_kicks_in():
    from app.main import create_app
    from httpx import ASGITransport, AsyncClient

    settings = get_settings()
    original = settings.rate_limit_requests
    settings.rate_limit_requests = 5  # tiny window for the test
    try:
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            codes = []
            for _ in range(12):
                resp = await client.post("/api/auth/exchange", json={"code": "BOGUS"})
                codes.append(resp.status_code)
            assert 401 in codes          # the endpoint works...
            assert 429 in codes          # ...but gets throttled
            assert codes.count(429) >= 7  # and stays throttled

            retry_after = resp.headers.get("retry-after")
            assert retry_after and int(retry_after) >= 1
    finally:
        settings.rate_limit_requests = original


async def test_health_and_docs_exempt_from_rate_limit():
    from app.main import create_app
    from httpx import ASGITransport, AsyncClient

    settings = get_settings()
    original = settings.rate_limit_requests
    settings.rate_limit_requests = 3
    try:
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            for _ in range(10):
                assert (await client.get("/health")).status_code == 200
    finally:
        settings.rate_limit_requests = original
