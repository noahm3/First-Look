"""Board probes for the mapping cascade: does (provider, token) name a real board?

One GET per probe, straight at the same public endpoint each M2 adapter polls.
It deliberately does not go through `fetch_postings`: `AdapterResult` flattens
every failure into one error string, and the cascade has to tell `not_found`
(evidence against a token) apart from `inconclusive` (no evidence either way).

A 200 is `live` only if the body really is that provider's board shape *and*
the response came from the host we asked -- BambooHR 302s an unknown tenant
to its own 200 marketing homepage (confirmed live in M2).
"""

import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

from src.http import FetchClient, FetchErrorKind, FetchResult
from src.mapping_validate import BoardProbe, ProbeOutcome, is_valid_token
from src.models import AtsProvider

RIPPLING_API_BASE = "https://api.rippling.com/platform/api/ats/v2/board"

# 4xx codes that say "go away", not "no such board": a bot block or throttle
# must not be read as the board being gone.
_INCONCLUSIVE_4XX = frozenset({401, 403, 408, 425, 429})


def probe_url(provider: AtsProvider, token: str) -> str:
    match provider:
        case AtsProvider.GREENHOUSE:
            # The board endpoint, not /jobs: it carries the board's `name` (the
            # `probable` signal) and stays tiny however many jobs there are.
            return f"https://boards-api.greenhouse.io/v1/boards/{token}"
        case AtsProvider.LEVER:
            return f"https://api.lever.co/v0/postings/{token}?mode=json"
        case AtsProvider.ASHBY:
            return f"https://api.ashbyhq.com/posting-api/job-board/{token}"
        case AtsProvider.RIPPLING:
            return f"{RIPPLING_API_BASE}/{token}/jobs"
        case AtsProvider.BAMBOOHR:
            return f"https://{token}.bamboohr.com/careers/list"
        case AtsProvider.WORKABLE:
            return f"https://apply.workable.com/api/v1/widget/accounts/{token}"
        case AtsProvider.PERSONIO:
            return f"https://{token}/xml?language=en"
        case AtsProvider.BREEZY_HR:
            return f"https://{token}.breezy.hr/json"
    raise ValueError(f"no probe for provider {provider!r}")


def probe(client: FetchClient, provider: AtsProvider, token: str) -> BoardProbe:
    """Never raises; every outcome is a `BoardProbe`."""

    def outcome(kind: ProbeOutcome, **kw) -> BoardProbe:
        return BoardProbe(provider, token, kind, **kw)

    if not is_valid_token(provider, token):
        return outcome(ProbeOutcome.NOT_FOUND, detail="invalid token")

    url = probe_url(provider, token)
    result = client.get(url)

    if not result.ok:
        return outcome(_classify_failure(result), detail=str(result.error or result.status))

    final_host = urlsplit(result.final_url or url).hostname
    if final_host != urlsplit(url).hostname:
        return outcome(ProbeOutcome.NOT_A_BOARD, detail=f"redirected to {final_host}")

    try:
        parsed = _parse_board(provider, result)
    except Exception as exc:  # an undocumented endpoint's body is never trusted
        return outcome(ProbeOutcome.NOT_A_BOARD, detail=f"unparseable: {type(exc).__name__}")
    if parsed is None:
        return outcome(ProbeOutcome.NOT_A_BOARD, detail="unexpected shape")
    org_name, count = parsed
    return outcome(ProbeOutcome.LIVE, org_name=org_name, posting_count=count)


def _classify_failure(result: FetchResult) -> ProbeOutcome:
    error = result.error
    if error is not None and error.kind is not FetchErrorKind.HTTP_ERROR:
        # Timeouts, connection and DNS failures, SSRF-guard rejections, size
        # caps: none of them say anything about whether the board exists.
        return ProbeOutcome.INCONCLUSIVE
    status = result.status or 0
    if 400 <= status < 500 and status not in _INCONCLUSIVE_4XX:
        return ProbeOutcome.NOT_FOUND
    return ProbeOutcome.INCONCLUSIVE


def _str_or_none(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip() or None


def _parse_board(
    provider: AtsProvider, result: FetchResult
) -> tuple[str | None, int | None] | None:
    """(org_name, posting_count) if the body is this provider's board, else None."""
    if provider is AtsProvider.PERSONIO:
        root = ET.fromstring(result.body)
        if root.tag != "workzag-jobs":
            return None
        return None, len(root.findall("position"))

    body = result.json()
    match provider:
        case AtsProvider.GREENHOUSE:
            if isinstance(body, dict) and "name" in body:
                return _str_or_none(body.get("name")), None
        case AtsProvider.WORKABLE:
            if isinstance(body, dict) and isinstance(body.get("jobs"), list):
                return _str_or_none(body.get("name")), len(body["jobs"])
        case AtsProvider.ASHBY:
            if isinstance(body, dict) and isinstance(body.get("jobs"), list):
                return None, len(body["jobs"])
        case AtsProvider.RIPPLING:
            if isinstance(body, dict) and isinstance(body.get("items"), list):
                total = body.get("totalItems")
                return None, total if isinstance(total, int) else len(body["items"])
        case AtsProvider.BAMBOOHR:
            if isinstance(body, dict) and isinstance(body.get("result"), list):
                return None, len(body["result"])
        case AtsProvider.LEVER | AtsProvider.BREEZY_HR:
            if isinstance(body, list):
                return None, len(body)
    return None
