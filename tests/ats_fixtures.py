"""Shared FetchClient-faking helper for tests/test_ats_*.py.

Copies tests/test_http.py's transport-fake pattern rather than importing from
a test module, so the 8 adapter test files share one helper instead of
duplicating this boilerplate 8 times.
"""

from pathlib import Path

import httpx

from src.http import FetchClient

PUBLIC_IP = "93.184.216.34"
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "ats"


def read_fixture(provider: str, name: str) -> bytes:
    return (FIXTURES_DIR / provider / name).read_bytes()


def fake_client(handler, *, resolves_to: str = PUBLIC_IP, **kwargs) -> FetchClient:
    """Build a FetchClient wired to a fake transport. `handler(request) ->
    httpx.Response` — build that response with `respond()` below, so
    individual test files never need to import httpx themselves (banned
    outside src/http.py and this file, see pyproject.toml's TID251 rule)."""

    def resolver(_host: str) -> list[str]:
        return [resolves_to]

    kwargs.setdefault("rate_per_second", 1000.0)
    return FetchClient(
        resolver=resolver,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def refuse_connection(request) -> httpx.Response:
    """A `fake_client` handler whose every request fails at the socket -- the
    transient "HTTP 0" case, for tests that must not import httpx."""
    raise httpx.ConnectError("connection reset", request=request)


def respond(
    status: int,
    *,
    content: bytes | None = None,
    json: object = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Build the response a `fake_client` handler returns, without the
    caller needing its own `import httpx`. `headers` carries e.g. a redirect's
    `Location`."""
    if json is not None:
        return httpx.Response(status, json=json, headers=headers)
    return httpx.Response(status, content=content or b"", headers=headers)
