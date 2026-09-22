"""Shared test configuration.

CLAUDE.md: "Tests never hit the network. Use fixtures in tests/fixtures/." That is
enforced here rather than trusted, because a test that quietly reaches the network
passes locally and then fails in CI for reasons nobody can reproduce.
"""

import socket

import pytest


class NetworkBlockedInTests(RuntimeError):
    """Raised when a test tries to open a socket."""


@pytest.fixture(autouse=True)
def _no_network(request, monkeypatch):
    """Block socket access for every test not marked ``allow_network``."""
    if "allow_network" in request.keywords:
        return

    def blocked(*_args, **_kwargs):
        raise NetworkBlockedInTests(
            "Tests never hit the network. Record a fixture under tests/fixtures/, or "
            "mark the test @pytest.mark.allow_network if it genuinely needs a socket."
        )

    monkeypatch.setattr(socket, "socket", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
