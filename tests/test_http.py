"""Tests for src/http.py — the single network chokepoint.

Written before the implementation, guards first, because SECURITY.md names the fetch
guards one of three things that must land before the code they govern: once four
crawlers and three adapters depend on current redirect behaviour, tightening it means
re-testing all seven.

These tests fake the network at httpx's transport layer and inject the DNS resolver,
so nothing here opens a socket (see tests/conftest.py).
"""

import logging

import httpx
import pytest

from src.http import (
    DEFAULT_USER_AGENT,
    FetchClient,
    FetchErrorKind,
    TokenBucket,
)

PUBLIC_IP = "93.184.216.34"


class Recorder:
    """A fake transport that records what was requested and replays canned replies."""

    def __init__(self, handler):
        self.requests: list[httpx.Request] = []
        self._handler = handler

    def transport(self) -> httpx.MockTransport:
        def wrapped(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            return self._handler(request)

        return httpx.MockTransport(wrapped)

    @property
    def count(self) -> int:
        return len(self.requests)

    @property
    def urls(self) -> list[str]:
        return [str(r.url) for r in self.requests]


def client(
    handler=None,
    *,
    resolves_to=PUBLIC_IP,
    sleeps=None,
    **kwargs,
):
    """Build a FetchClient wired to fakes. Returns (client, recorder)."""
    if handler is None:

        def handler(_request):
            return httpx.Response(200, text="ok")

    recorder = Recorder(handler)

    def resolver(host: str) -> list[str]:
        if isinstance(resolves_to, dict):
            if host not in resolves_to:
                raise OSError(f"name or service not known: {host}")
            value = resolves_to[host]
        else:
            value = resolves_to
        return [value] if isinstance(value, str) else list(value)

    recorded_sleeps: list[float] = [] if sleeps is None else sleeps

    kwargs.setdefault("rate_per_second", 1000.0)
    return (
        FetchClient(
            resolver=resolver,
            transport=recorder.transport(),
            sleep=recorded_sleeps.append,
            **kwargs,
        ),
        recorder,
    )


# ---------------------------------------------------------------------------
# Scheme guard — SECURITY.md §S6, C-S.14
# ---------------------------------------------------------------------------


class TestSchemeGuard:
    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "ftp://example.com/x",
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "gopher://example.com",
            "//example.com/no-scheme",
        ],
    )
    def test_non_http_schemes_are_rejected_without_connecting(self, url):
        fetcher, recorder = client()
        result = fetcher.get(url)

        assert not result.ok
        assert result.error.kind is FetchErrorKind.BLOCKED_SCHEME
        assert recorder.count == 0, "a blocked URL must never reach the transport"

    @pytest.mark.parametrize("scheme", ["http", "https"])
    def test_http_and_https_are_allowed(self, scheme):
        fetcher, recorder = client()
        result = fetcher.get(f"{scheme}://example.com/careers")

        assert result.ok
        assert recorder.count == 1


# ---------------------------------------------------------------------------
# Address guard — private, loopback, link-local. C-S.14
# ---------------------------------------------------------------------------


class TestAddressGuard:
    @pytest.mark.parametrize(
        "address",
        [
            "127.0.0.1",
            "127.1.2.3",
            "10.0.0.1",
            "10.255.255.254",
            "192.168.1.1",
            "172.16.0.1",
            "172.31.255.254",
            "0.0.0.0",
            "169.254.1.1",
            # The cloud metadata endpoint SECURITY.md §S6 calls out by name.
            "169.254.169.254",
            "::1",
            "fe80::1",
            "fc00::1",
        ],
    )
    def test_private_loopback_and_link_local_are_rejected(self, address):
        fetcher, recorder = client(resolves_to=address)
        result = fetcher.get("https://internal.example.com/")

        assert not result.ok
        assert result.error.kind is FetchErrorKind.BLOCKED_ADDRESS
        assert recorder.count == 0

    def test_a_public_address_is_allowed(self):
        fetcher, recorder = client(resolves_to="93.184.216.34")
        assert fetcher.get("https://example.com/").ok
        assert recorder.count == 1

    def test_one_bad_address_among_several_rejects_the_whole_host(self):
        # A hostile DNS answer mixing a public and a private record must not be
        # salvaged by picking the public one -- httpx resolves independently and
        # may well pick the other.
        fetcher, recorder = client(resolves_to=[PUBLIC_IP, "169.254.169.254"])
        result = fetcher.get("https://mixed.example.com/")

        assert result.error.kind is FetchErrorKind.BLOCKED_ADDRESS
        assert recorder.count == 0

    def test_dns_failure_is_its_own_error_kind(self):
        fetcher, _ = client(resolves_to={})
        result = fetcher.get("https://nonexistent.example/")

        assert result.error.kind is FetchErrorKind.DNS_FAILURE

    def test_a_literal_private_ip_in_the_url_is_rejected(self):
        fetcher, recorder = client(resolves_to={})
        result = fetcher.get("http://169.254.169.254/latest/meta-data/")

        assert result.error.kind is FetchErrorKind.BLOCKED_ADDRESS
        assert recorder.count == 0


class TestRejectionLogging:
    """SPEC.md §8.4: a silently dropped fetch is indistinguishable from a company
    having no careers page, and would land in the failure distribution as `unknown`,
    corrupting the one measurement the coverage decision rests on."""

    def test_blocked_address_logs_both_the_url_and_the_resolved_address(self, caplog):
        fetcher, _ = client(resolves_to="169.254.169.254")
        with caplog.at_level(logging.WARNING, logger="src.http"):
            fetcher.get("https://sneaky.example.com/careers")

        logged = "\n".join(record.getMessage() for record in caplog.records)
        assert "https://sneaky.example.com/careers" in logged
        assert "169.254.169.254" in logged

    def test_blocked_scheme_logs_the_requested_url(self, caplog):
        fetcher, _ = client()
        with caplog.at_level(logging.WARNING, logger="src.http"):
            fetcher.get("file:///etc/passwd")

        logged = "\n".join(record.getMessage() for record in caplog.records)
        assert "file:///etc/passwd" in logged


# ---------------------------------------------------------------------------
# Redirects — depth cap, and every hop re-guarded
# ---------------------------------------------------------------------------


class TestRedirectGuard:
    def test_follows_redirects_up_to_the_cap(self):
        def handler(request):
            hop = int(str(request.url).rsplit("/", 1)[-1])
            if hop >= 3:
                return httpx.Response(200, text="arrived")
            return httpx.Response(302, headers={"Location": f"https://example.com/{hop + 1}"})

        fetcher, recorder = client(handler, max_redirects=5)
        result = fetcher.get("https://example.com/0")

        assert result.ok
        assert result.text == "arrived"
        assert result.final_url == "https://example.com/3"
        assert recorder.count == 4

    def test_exceeding_the_cap_is_an_error_not_an_infinite_loop(self):
        def handler(request):
            hop = int(str(request.url).rsplit("/", 1)[-1])
            return httpx.Response(302, headers={"Location": f"https://example.com/{hop + 1}"})

        fetcher, recorder = client(handler, max_redirects=5)
        result = fetcher.get("https://example.com/0")

        assert result.error.kind is FetchErrorKind.TOO_MANY_REDIRECTS
        # The initial request plus exactly max_redirects hops, then it stops.
        assert recorder.count == 6

    def test_a_redirect_into_a_private_address_is_blocked(self):
        # The reason redirects are followed by hand rather than by httpx: an
        # apply-redirect chain (SPEC.md §8.1 stage 2) is third-party controlled,
        # and httpx's own follow_redirects would connect before we could look.
        def handler(request):
            if "metadata" in str(request.url):
                pytest.fail("connected to the redirect target before guarding it")
            return httpx.Response(302, headers={"Location": "http://metadata.example.com/latest"})

        fetcher, _ = client(
            handler,
            resolves_to={"example.com": PUBLIC_IP, "metadata.example.com": "169.254.169.254"},
        )
        result = fetcher.get("https://example.com/apply")

        assert result.error.kind is FetchErrorKind.BLOCKED_ADDRESS

    def test_a_redirect_into_a_non_http_scheme_is_blocked(self):
        def handler(_request):
            return httpx.Response(302, headers={"Location": "file:///etc/passwd"})

        fetcher, _ = client(handler)
        result = fetcher.get("https://example.com/apply")

        assert result.error.kind is FetchErrorKind.BLOCKED_SCHEME

    def test_relative_redirect_locations_resolve_against_the_current_url(self):
        def handler(request):
            if str(request.url) == "https://example.com/careers/list":
                return httpx.Response(200, text="landed")
            return httpx.Response(301, headers={"Location": "/careers/list"})

        fetcher, _ = client(handler)
        result = fetcher.get("https://example.com/jobs")

        assert result.ok
        assert result.final_url == "https://example.com/careers/list"


# ---------------------------------------------------------------------------
# Response size cap
# ---------------------------------------------------------------------------


class TestResponseSizeCap:
    def test_a_body_over_the_cap_is_rejected(self):
        def handler(_request):
            return httpx.Response(200, content=b"x" * 5000)

        fetcher, _ = client(handler, max_response_bytes=1000)
        result = fetcher.get("https://example.com/huge")

        assert result.error.kind is FetchErrorKind.RESPONSE_TOO_LARGE

    def test_a_body_at_the_cap_is_accepted(self):
        def handler(_request):
            return httpx.Response(200, content=b"x" * 1000)

        fetcher, _ = client(handler, max_response_bytes=1000)
        assert fetcher.get("https://example.com/exact").ok

    def test_an_oversized_content_length_is_refused_before_reading_the_body(self):
        def handler(_request):
            return httpx.Response(200, content=b"x" * 10, headers={"Content-Length": "999999999"})

        fetcher, _ = client(handler, max_response_bytes=1000)
        result = fetcher.get("https://example.com/lying")

        assert result.error.kind is FetchErrorKind.RESPONSE_TOO_LARGE


# ---------------------------------------------------------------------------
# Retry policy — BUILD.md §3: backoff on timeout/5xx/connection error, never on 4xx
# ---------------------------------------------------------------------------


class TestRetryPolicy:
    def test_retries_a_5xx_and_succeeds(self):
        attempts = {"n": 0}

        def handler(_request):
            attempts["n"] += 1
            if attempts["n"] < 3:
                return httpx.Response(503)
            return httpx.Response(200, text="recovered")

        fetcher, recorder = client(handler, max_attempts=3)
        result = fetcher.get("https://example.com/flaky")

        assert result.ok
        assert result.text == "recovered"
        assert recorder.count == 3

    def test_never_retries_a_404_because_a_404_is_an_answer(self):
        def handler(_request):
            return httpx.Response(404)

        fetcher, recorder = client(handler, max_attempts=3)
        result = fetcher.get("https://example.com/gone")

        assert not result.ok
        assert result.status == 404
        assert result.error.kind is FetchErrorKind.HTTP_ERROR
        assert recorder.count == 1, "4xx must not be retried"

    @pytest.mark.parametrize("status", [400, 401, 403, 404, 410, 429])
    def test_no_4xx_is_retried(self, status):
        fetcher, recorder = client(lambda _r: httpx.Response(status), max_attempts=3)
        fetcher.get("https://example.com/x")
        assert recorder.count == 1

    def test_retries_a_timeout(self):
        attempts = {"n": 0}

        def handler(request):
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise httpx.ReadTimeout("slow", request=request)
            return httpx.Response(200, text="eventually")

        fetcher, recorder = client(handler, max_attempts=3)
        assert fetcher.get("https://example.com/slow").ok
        assert recorder.count == 2

    def test_retries_a_connection_error(self):
        attempts = {"n": 0}

        def handler(request):
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise httpx.ConnectError("reset", request=request)
            return httpx.Response(200)

        fetcher, recorder = client(handler, max_attempts=3)
        assert fetcher.get("https://example.com/reset").ok
        assert recorder.count == 2

    def test_gives_up_after_max_attempts_and_reports_the_kind(self):
        def handler(request):
            raise httpx.ReadTimeout("always slow", request=request)

        fetcher, recorder = client(handler, max_attempts=3)
        result = fetcher.get("https://example.com/dead")

        assert result.error.kind is FetchErrorKind.TIMEOUT
        assert recorder.count == 3

    def test_backoff_grows_exponentially(self):
        sleeps: list[float] = []

        def handler(_request):
            return httpx.Response(500)

        # burst high enough that the token bucket never contributes a wait, so the
        # only sleeps recorded here are the retry backoffs.
        fetcher, _ = client(handler, sleeps=sleeps, max_attempts=4, backoff_base=0.5, burst=100)
        fetcher.get("https://example.com/500")

        # One sleep between each pair of attempts, doubling each time.
        assert sleeps == [0.5, 1.0, 2.0]

    def test_no_backoff_is_slept_when_the_first_attempt_succeeds(self):
        sleeps: list[float] = []
        fetcher, _ = client(sleeps=sleeps, burst=100)
        assert fetcher.get("https://example.com/").ok
        assert sleeps == []


# ---------------------------------------------------------------------------
# The result object — BUILD.md §3: returns a result, never raises, so callers
# need no try/except to satisfy principle §3.7
# ---------------------------------------------------------------------------


class TestResultObject:
    @pytest.mark.parametrize(
        "url",
        ["file:///etc/passwd", "https://example.com/huge", "https://nowhere.example/"],
    )
    def test_no_failure_mode_raises(self, url):
        def handler(_request):
            return httpx.Response(200, content=b"x" * 99999)

        fetcher, _ = client(handler, resolves_to={"example.com": PUBLIC_IP}, max_response_bytes=10)
        result = fetcher.get(url)  # must not raise
        assert result.error is not None

    def test_ok_is_false_for_a_3xx_that_was_not_followed(self):
        def handler(_request):
            return httpx.Response(304)

        fetcher, _ = client(handler)
        result = fetcher.get("https://example.com/cached")
        assert not result.ok

    def test_json_parses_a_body(self):
        def handler(_request):
            return httpx.Response(200, json={"jobs": [{"id": 1}]})

        fetcher, _ = client(handler)
        assert fetcher.get("https://example.com/api").json() == {"jobs": [{"id": 1}]}

    def test_json_on_a_malformed_body_returns_none_rather_than_raising(self):
        def handler(_request):
            return httpx.Response(200, text="<html>not json</html>")

        fetcher, _ = client(handler)
        assert fetcher.get("https://example.com/api").json() is None

    def test_result_records_the_requested_url_even_when_blocked(self):
        fetcher, _ = client()
        result = fetcher.get("file:///etc/passwd")
        assert result.requested_url == "file:///etc/passwd"


class TestUserAgent:
    def test_sends_a_realistic_user_agent(self):
        fetcher, recorder = client()
        fetcher.get("https://example.com/")

        sent = recorder.requests[0].headers["user-agent"]
        assert sent == DEFAULT_USER_AGENT
        assert "python-httpx" not in sent.lower()

    def test_caller_headers_are_merged_without_dropping_the_user_agent(self):
        fetcher, recorder = client()
        fetcher.get("https://example.com/", headers={"Accept": "application/json"})

        headers = recorder.requests[0].headers
        assert headers["accept"] == "application/json"
        assert headers["user-agent"] == DEFAULT_USER_AGENT


# ---------------------------------------------------------------------------
# Per-host rate limiting — BUILD.md §3, SPEC.md §9: 2-5 req/sec per provider
# ---------------------------------------------------------------------------


class TestTokenBucket:
    def test_the_first_request_is_not_delayed(self):
        bucket = TokenBucket(rate_per_second=2.0, capacity=1, monotonic=lambda: 0.0)
        assert bucket.time_until_token() == 0.0

    def test_a_second_immediate_request_waits_for_the_interval(self):
        now = {"t": 0.0}
        bucket = TokenBucket(rate_per_second=2.0, capacity=1, monotonic=lambda: now["t"])
        bucket.consume()
        assert bucket.time_until_token() == pytest.approx(0.5, abs=1e-6)

    def test_waiting_long_enough_refills_the_bucket(self):
        now = {"t": 0.0}
        bucket = TokenBucket(rate_per_second=2.0, capacity=1, monotonic=lambda: now["t"])
        bucket.consume()
        now["t"] = 1.0
        assert bucket.time_until_token() == 0.0


class TestPerHostPacing:
    def test_two_requests_to_one_host_are_paced(self):
        sleeps: list[float] = []
        fetcher, _ = client(sleeps=sleeps, rate_per_second=2.0)

        fetcher.get("https://example.com/a")
        fetcher.get("https://example.com/b")

        assert any(s > 0 for s in sleeps), "the second request to a host should be paced"

    def test_different_hosts_do_not_pace_each_other(self):
        sleeps: list[float] = []
        fetcher, _ = client(
            sleeps=sleeps,
            rate_per_second=2.0,
            resolves_to={"a.example.com": PUBLIC_IP, "b.example.com": PUBLIC_IP},
        )

        fetcher.get("https://a.example.com/")
        fetcher.get("https://b.example.com/")

        assert not any(s > 0 for s in sleeps)


# ---------------------------------------------------------------------------
# Optional dev disk cache
# ---------------------------------------------------------------------------


class TestDiskCache:
    def test_a_second_fetch_is_served_from_cache(self, tmp_path):
        def handler(_request):
            return httpx.Response(200, text="from network")

        fetcher, recorder = client(handler, cache_dir=tmp_path)

        first = fetcher.get("https://example.com/jobs")
        second = fetcher.get("https://example.com/jobs")

        assert first.text == second.text == "from network"
        assert not first.from_cache
        assert second.from_cache
        assert recorder.count == 1

    def test_cache_is_off_by_default(self, tmp_path):
        fetcher, recorder = client()
        fetcher.get("https://example.com/jobs")
        fetcher.get("https://example.com/jobs")
        assert recorder.count == 2

    def test_cache_filenames_are_hashes_not_remote_controlled_paths(self, tmp_path):
        # SECURITY.md §S6: never write a fetched filename to disk from a
        # remote-controlled value.
        fetcher, _ = client(cache_dir=tmp_path)
        fetcher.get("https://example.com/../../etc/passwd?q=%2F%2E%2E")

        written = list(tmp_path.rglob("*"))
        assert written, "expected something to be cached"
        for path in written:
            assert path.parent == tmp_path
            assert ".." not in path.name
            assert "/" not in path.name and "\\" not in path.name

    def test_errors_are_not_cached(self, tmp_path):
        def handler(_request):
            return httpx.Response(500)

        fetcher, recorder = client(handler, cache_dir=tmp_path, max_attempts=1)
        fetcher.get("https://example.com/broken")
        fetcher.get("https://example.com/broken")

        assert recorder.count == 2, "a failed fetch must not poison the cache"
