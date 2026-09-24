"""The single network chokepoint. Nothing else in this project imports httpx.

That rule is enforced in CI by ruff's banned-api (see pyproject.toml), not by
review, because the whole value of a chokepoint is that there is exactly one place
where fetch policy lives: guards, retries, pacing, and the user agent.

Two deliberate shapes here, both from BUILD.md §3 and SECURITY.md:

*   **Nothing raises.** Every call returns a :class:`FetchResult`, so callers never
    need try/except to satisfy SPEC.md §3.7 ("no exception escapes a per-company
    loop"). A guard rejection, a DNS failure, and a 404 are all just results.

*   **Redirects are followed by hand.** httpx's own ``follow_redirects`` would
    connect to the next hop before we could look at it, and redirect chains here
    are third-party controlled — SPEC.md §8.1 stage 2 follows Built In's
    apply-redirect links deliberately. So every hop is re-guarded before it is
    fetched.

Every rejection is logged with both the requested URL and the resolved address.
SPEC.md §8.4 is explicit about why: a guard that silently drops a legitimate fetch
is indistinguishable from a company having no careers page, and lands in the
failure distribution as ``unknown`` — corrupting the one measurement the entire
coverage decision rests on (§8.6, §18).

Known limitation, recorded rather than hidden: the address check resolves the host
and then lets httpx resolve it again when connecting, so a DNS answer that changes
between the two could slip past (classic rebinding). Closing that properly means
connecting to a pinned IP, which breaks TLS certificate verification for https.
SECURITY.md §S6 judges real SSRF impact here low — the runner has almost no
internal network to reach — and asks for controls that are "nearly free", which
this is.
"""

import base64
import hashlib
import ipaddress
import json
import logging
import os
import socket
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

log = logging.getLogger(__name__)

# A plain, honest identifier. Not a browser impersonation: every endpoint this
# project touches is public and unauthenticated, and SPEC.md §1 rules out anything
# that needs pretending to be a person.
DEFAULT_USER_AGENT = (
    "first-look/0.1 (+https://github.com/topics/job-search; public ATS boards only)"
)

MAX_REDIRECTS = 5
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
DEFAULT_RATE_PER_SECOND = 3.0
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_BASE = 0.5
DEFAULT_COOLDOWN_SECONDS = 25 * 60.0

# apply.workable.com: 3 req/sec (the old uniform default) triggered a sustained
# ~20min 429 during M3's 300-domain cascade. A live probe (DEVLOG, M4 kickoff)
# found 1-2 req/sec clean with no rate-limit response headers at either rate.
DEFAULT_RATE_OVERRIDES: dict[str, float] = {
    "apply.workable.com": 1.0,
}

ALLOWED_SCHEMES = frozenset({"http", "https"})

Resolver = Callable[[str], list[str]]


class FetchErrorKind(StrEnum):
    """Why a fetch produced no usable body.

    Kept distinct rather than collapsed into one "failed" state because these map
    onto different remedies: SPEC.md §14 splits transient from permanent for
    per-company flagging, and §8.4 needs the reason to classify a mapping failure.
    """

    BLOCKED_SCHEME = "blocked_scheme"
    BLOCKED_ADDRESS = "blocked_address"
    DNS_FAILURE = "dns_failure"
    TOO_MANY_REDIRECTS = "too_many_redirects"
    RESPONSE_TOO_LARGE = "response_too_large"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    HTTP_ERROR = "http_error"
    RATE_LIMITED = "rate_limited"

    @property
    def is_transient(self) -> bool:
        """Whether retrying later could plausibly succeed (SPEC.md §14)."""
        return self in (
            FetchErrorKind.TIMEOUT,
            FetchErrorKind.CONNECTION_ERROR,
            FetchErrorKind.DNS_FAILURE,
            FetchErrorKind.RATE_LIMITED,
        )


@dataclass(frozen=True, slots=True)
class FetchError:
    kind: FetchErrorKind
    detail: str = ""

    def __str__(self) -> str:
        return f"{self.kind.value}: {self.detail}" if self.detail else self.kind.value


@dataclass(frozen=True, slots=True)
class FetchResult:
    requested_url: str
    status: int | None = None
    body: bytes = b""
    final_url: str | None = None
    error: FetchError | None = None
    from_cache: bool = False
    headers: Mapping[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None and self.status is not None and 200 <= self.status < 300

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any | None:
        """Parse the body as JSON, or return None.

        Degrades rather than raising, on the same principle as the rest of this
        module: a provider serving an HTML error page where JSON was documented is
        an outcome to record, not an exception to propagate into a polling loop.
        """
        if not self.body:
            return None
        try:
            return json.loads(self.body)
        except (ValueError, UnicodeDecodeError):
            log.warning("response from %s was not valid JSON", self.final_url or self.requested_url)
            return None


class TokenBucket:
    """Per-host pacing. SPEC.md §9 budgets 2-5 req/sec per provider."""

    __slots__ = ("_capacity", "_last", "_monotonic", "_rate", "_tokens")

    def __init__(
        self,
        rate_per_second: float,
        capacity: int = 1,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if rate_per_second <= 0:
            raise ValueError("rate_per_second must be positive")
        self._rate = rate_per_second
        self._capacity = max(1, capacity)
        self._monotonic = monotonic
        self._tokens = float(self._capacity)
        self._last = monotonic()

    def _refill(self) -> None:
        now = self._monotonic()
        elapsed = max(0.0, now - self._last)
        self._last = now
        self._tokens = min(float(self._capacity), self._tokens + elapsed * self._rate)

    def time_until_token(self) -> float:
        self._refill()
        if self._tokens >= 1.0:
            return 0.0
        return (1.0 - self._tokens) / self._rate

    def consume(self) -> None:
        self._refill()
        self._tokens -= 1.0


def _default_resolver(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return [info[4][0] for info in infos]


def _is_forbidden_address(address: str) -> bool:
    """Whether an address is in a range this project must never fetch from.

    169.254.169.254 — the cloud metadata endpoint SECURITY.md §S6 names — falls in
    here as link-local, along with private, loopback, reserved, multicast, and
    unspecified ranges.
    """
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        # An address we cannot parse is not an address we are willing to connect to.
        return True
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _literal_ip(host: str) -> str | None:
    """Return the host as an IP literal, or None if it is a name."""
    candidate = host[1:-1] if host.startswith("[") and host.endswith("]") else host
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return None
    return candidate


class FetchClient:
    """Every outbound HTTP request in this project goes through here."""

    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        rate_per_second: float = DEFAULT_RATE_PER_SECOND,
        rate_overrides: Mapping[str, float] | None = None,
        cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
        burst: int = 1,
        max_redirects: int = MAX_REDIRECTS,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
        resolver: Resolver | None = None,
        cache_dir: str | os.PathLike[str] | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._user_agent = user_agent
        self._rate = rate_per_second
        self._rate_overrides = (
            dict(DEFAULT_RATE_OVERRIDES) if rate_overrides is None else dict(rate_overrides)
        )
        self._cooldown_seconds = cooldown_seconds
        self._burst = burst
        self._max_redirects = max_redirects
        self._max_response_bytes = max_response_bytes
        self._max_attempts = max(1, max_attempts)
        self._backoff_base = backoff_base
        self._resolve = resolver or _default_resolver
        self._cache_dir = Path(cache_dir) if cache_dir is not None else None
        self._sleep = sleep
        self._monotonic = monotonic
        self._buckets: dict[str, TokenBucket] = {}
        self._cooldowns: dict[str, float] = {}

        if self._cache_dir is not None:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

        self._client = httpx.Client(
            follow_redirects=False,  # every hop is guarded by hand; see module docstring
            timeout=timeout,
            transport=transport,
            headers={"User-Agent": user_agent},
        )

    # -- lifecycle ---------------------------------------------------------

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "FetchClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # -- public API --------------------------------------------------------

    def get(self, url: str, *, headers: Mapping[str, str] | None = None) -> FetchResult:
        return self.request("GET", url, headers=headers)

    def post_json(
        self,
        url: str,
        payload: Any,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> FetchResult:
        """POST a JSON body. Needed by Consider's search endpoint (SPEC.md §7.6)."""
        return self.request("POST", url, headers=headers, json_body=payload)

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json_body: Any | None = None,
    ) -> FetchResult:
        cache_key = self._cache_key(method, url, json_body)
        cached = self._cache_read(cache_key, url)
        if cached is not None:
            return cached

        result = self._request_following_redirects(
            method, url, headers=headers, json_body=json_body
        )
        if result.ok:
            self._cache_write(cache_key, result)
        return result

    # -- redirect loop -----------------------------------------------------

    def _request_following_redirects(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None,
        json_body: Any | None,
    ) -> FetchResult:
        current = url
        hops = 0

        while True:
            guard_error = self._guard(current, requested_url=url)
            if guard_error is not None:
                return FetchResult(requested_url=url, final_url=current, error=guard_error)

            outcome = self._attempt_with_retries(
                method, current, headers=headers, json_body=json_body, requested_url=url
            )
            if isinstance(outcome, FetchError):
                return FetchResult(requested_url=url, final_url=current, error=outcome)

            status, body, response_headers = outcome
            location = response_headers.get("location")

            if 300 <= status < 400 and location:
                if hops >= self._max_redirects:
                    log.warning(
                        "redirect cap of %d exceeded for %s (stopped at %s)",
                        self._max_redirects,
                        url,
                        current,
                    )
                    return FetchResult(
                        requested_url=url,
                        status=status,
                        final_url=current,
                        error=FetchError(
                            FetchErrorKind.TOO_MANY_REDIRECTS,
                            f"more than {self._max_redirects} redirects from {url}",
                        ),
                    )
                hops += 1
                current = urljoin(current, location)
                # A redirect body is never the payload, and methods other than GET
                # become GET on the far side of one, as every browser does.
                method, json_body = "GET", None
                continue

            error = None
            if status == 429:
                host = (urlsplit(current).hostname or "").lower()
                self._cooldowns[host] = self._monotonic() + self._cooldown_seconds
                log.warning(
                    "HTTP 429 from %s: cooling down %s for %.0fs",
                    current,
                    host,
                    self._cooldown_seconds,
                )
                error = FetchError(
                    FetchErrorKind.RATE_LIMITED, f"HTTP 429 from {current}, cooling down {host}"
                )
            elif not 200 <= status < 300:
                error = FetchError(FetchErrorKind.HTTP_ERROR, f"HTTP {status} from {current}")

            return FetchResult(
                requested_url=url,
                status=status,
                body=body,
                final_url=current,
                error=error,
                headers=response_headers,
            )

    # -- guards ------------------------------------------------------------

    def _guard(self, url: str, *, requested_url: str) -> FetchError | None:
        parts = urlsplit(url)
        scheme = parts.scheme.lower()

        if scheme not in ALLOWED_SCHEMES:
            log.warning(
                "blocked fetch of %s (requested as %s): scheme %r is not http or https",
                url,
                requested_url,
                scheme or "<none>",
            )
            return FetchError(
                FetchErrorKind.BLOCKED_SCHEME, f"scheme {scheme or '<none>'!r} in {url}"
            )

        host = parts.hostname
        if not host:
            log.warning("blocked fetch of %s (requested as %s): no host", url, requested_url)
            return FetchError(FetchErrorKind.BLOCKED_SCHEME, f"no host in {url}")

        cooldown_until = self._cooldowns.get(host.lower())
        if cooldown_until is not None:
            remaining = cooldown_until - self._monotonic()
            if remaining > 0:
                log.warning(
                    "skipping fetch of %s (requested as %s): %s is cooling down after a 429 "
                    "for another %.0fs",
                    url,
                    requested_url,
                    host,
                    remaining,
                )
                return FetchError(
                    FetchErrorKind.RATE_LIMITED,
                    f"{host} is cooling down for another {remaining:.0f}s",
                )
            del self._cooldowns[host.lower()]

        literal = _literal_ip(host)
        if literal is not None:
            addresses: Iterable[str] = [literal]
        else:
            try:
                addresses = self._resolve(host)
            except OSError as exc:
                log.warning(
                    "blocked fetch of %s (requested as %s): DNS resolution failed (%s)",
                    url,
                    requested_url,
                    exc,
                )
                return FetchError(FetchErrorKind.DNS_FAILURE, f"could not resolve {host}")

        addresses = list(addresses)
        if not addresses:
            log.warning(
                "blocked fetch of %s (requested as %s): host %s resolved to nothing",
                url,
                requested_url,
                host,
            )
            return FetchError(FetchErrorKind.DNS_FAILURE, f"{host} resolved to no addresses")

        forbidden = [a for a in addresses if _is_forbidden_address(a)]
        if forbidden:
            # Any bad record poisons the host. Picking a good one would be theatre:
            # httpx resolves independently when it connects and may choose the other.
            log.warning(
                "blocked fetch of %s (requested as %s): host %s resolved to %s, "
                "which is private, loopback, link-local, or otherwise not routable",
                url,
                requested_url,
                host,
                ", ".join(forbidden),
            )
            return FetchError(
                FetchErrorKind.BLOCKED_ADDRESS,
                f"{host} resolved to {', '.join(forbidden)}",
            )

        return None

    # -- one URL, with retries --------------------------------------------

    def _attempt_with_retries(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None,
        json_body: Any | None,
        requested_url: str,
    ) -> tuple[int, bytes, dict[str, str]] | FetchError:
        last_error: FetchError | None = None

        for attempt in range(1, self._max_attempts + 1):
            self._pace(url)
            outcome = self._attempt_once(method, url, headers=headers, json_body=json_body)

            if isinstance(outcome, tuple):
                status, _body, _headers = outcome
                if not (500 <= status < 600):
                    return outcome
                last_error = FetchError(FetchErrorKind.HTTP_ERROR, f"HTTP {status} from {url}")
            else:
                last_error = outcome
                # A 4xx is an answer, not a failure to retry (BUILD.md §3). Those
                # never arrive here — they return above — so anything in this branch
                # is transient or a hard size rejection.
                if outcome.kind is FetchErrorKind.RESPONSE_TOO_LARGE:
                    return outcome

            if attempt < self._max_attempts:
                delay = self._backoff_base * (2 ** (attempt - 1))
                log.info(
                    "retrying %s in %.2fs (attempt %d of %d, last: %s)",
                    url,
                    delay,
                    attempt + 1,
                    self._max_attempts,
                    last_error,
                )
                self._sleep(delay)

        log.warning(
            "giving up on %s (requested as %s) after %d attempts: %s",
            url,
            requested_url,
            self._max_attempts,
            last_error,
        )
        return last_error or FetchError(FetchErrorKind.CONNECTION_ERROR, url)

    def _attempt_once(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None,
        json_body: Any | None,
    ) -> tuple[int, bytes, dict[str, str]] | FetchError:
        merged = {"User-Agent": self._user_agent}
        if headers:
            merged.update(headers)

        try:
            request = self._client.build_request(
                method, url, headers=merged, json=json_body if json_body is not None else None
            )
            response = self._client.send(request, stream=True)
        except httpx.TimeoutException as exc:
            return FetchError(FetchErrorKind.TIMEOUT, f"{type(exc).__name__} on {url}")
        except httpx.HTTPError as exc:
            return FetchError(FetchErrorKind.CONNECTION_ERROR, f"{type(exc).__name__} on {url}")

        try:
            declared = response.headers.get("content-length")
            if declared is not None:
                try:
                    if int(declared) > self._max_response_bytes:
                        log.warning(
                            "blocked fetch of %s: declared Content-Length %s exceeds the "
                            "%d byte cap",
                            url,
                            declared,
                            self._max_response_bytes,
                        )
                        return FetchError(
                            FetchErrorKind.RESPONSE_TOO_LARGE,
                            f"Content-Length {declared} exceeds cap for {url}",
                        )
                except ValueError:
                    pass  # an unparseable header proves nothing; the byte cap below holds

            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > self._max_response_bytes:
                    log.warning(
                        "blocked fetch of %s: body exceeded the %d byte cap",
                        url,
                        self._max_response_bytes,
                    )
                    return FetchError(
                        FetchErrorKind.RESPONSE_TOO_LARGE,
                        f"body over {self._max_response_bytes} bytes from {url}",
                    )
                chunks.append(chunk)

            return (
                response.status_code,
                b"".join(chunks),
                {k.lower(): v for k, v in response.headers.items()},
            )
        except httpx.TimeoutException as exc:
            return FetchError(FetchErrorKind.TIMEOUT, f"{type(exc).__name__} reading {url}")
        except httpx.HTTPError as exc:
            return FetchError(
                FetchErrorKind.CONNECTION_ERROR, f"{type(exc).__name__} reading {url}"
            )
        finally:
            response.close()

    # -- pacing ------------------------------------------------------------

    def _pace(self, url: str) -> None:
        host = (urlsplit(url).hostname or "").lower()
        bucket = self._buckets.get(host)
        if bucket is None:
            rate = self._rate_overrides.get(host, self._rate)
            bucket = TokenBucket(rate, self._burst, self._monotonic)
            self._buckets[host] = bucket

        wait = bucket.time_until_token()
        if wait > 0:
            self._sleep(wait)
        bucket.consume()

    # -- optional development cache ----------------------------------------

    def _cache_key(self, method: str, url: str, json_body: Any | None) -> str | None:
        if self._cache_dir is None:
            return None
        material = json.dumps([method.upper(), url, json_body], sort_keys=True, default=str).encode(
            "utf-8"
        )
        # Hashed, never derived from the URL's own path: SECURITY.md §S6 forbids
        # writing a filename built from a remote-controlled value.
        return hashlib.sha256(material).hexdigest()

    def _cache_path(self, key: str) -> Path:
        assert self._cache_dir is not None
        return self._cache_dir / f"{key}.json"

    def _cache_read(self, key: str | None, requested_url: str) -> FetchResult | None:
        if key is None:
            return None
        path = self._cache_path(key)
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return FetchResult(
                requested_url=requested_url,
                status=payload["status"],
                body=base64.b64decode(payload["body"]),
                final_url=payload["final_url"],
                from_cache=True,
                headers=payload.get("headers", {}),
            )
        except (OSError, ValueError, KeyError):
            log.info("ignoring unreadable cache entry %s", path.name)
            return None

    def _cache_write(self, key: str | None, result: FetchResult) -> None:
        if key is None:
            return
        payload = {
            "status": result.status,
            "final_url": result.final_url,
            "body": base64.b64encode(result.body).decode("ascii"),
            "headers": dict(result.headers),
        }
        try:
            self._cache_path(key).write_text(json.dumps(payload), encoding="utf-8")
        except OSError as exc:
            log.info("could not write cache entry: %s", exc)
