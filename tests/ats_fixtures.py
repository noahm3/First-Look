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
    httpx.Response`."""

    def resolver(_host: str) -> list[str]:
        return [resolves_to]

    kwargs.setdefault("rate_per_second", 1000.0)
    return FetchClient(
        resolver=resolver,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )
