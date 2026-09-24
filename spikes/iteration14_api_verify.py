"""Re-verify watchlist candidates against each ATS's real public jobs API --
not a string match in page HTML (iteration13's mistake: a page can carry a
dead/leftover embed script for a token that 404s on the real API).

For each candidate, extracts the provider token from the page (or a known
URL) and confirms the real API returns a non-empty job list.
"""

import re
import sys

import httpx

GREENHOUSE_TOKEN = re.compile(r"greenhouse\.io/(?:embed/job_board/js\?for=|)([a-zA-Z0-9_-]+)")
LEVER_TOKEN = re.compile(r"(?:jobs\.lever\.co|api\.lever\.co/v0/postings)/([a-zA-Z0-9_-]+)")
ASHBY_TOKEN = re.compile(r"ashbyhq\.com/(?:api/non-user-graphql|posting-api/job-board/|)([a-zA-Z0-9_-]+)")
RIPPLING_TOKEN = re.compile(r"data-job-board-id=(?:&quot;|\")([a-zA-Z0-9_-]+)")

CANDIDATES = [
    # (name, page_to_scan_for_token, provider, known_token_or_None)
    ("Owl Labs", "https://owllabs.com/careers", "greenhouse", None),
    ("CircleCI", "https://circleci.com/careers/", "greenhouse", None),
    ("Mark Forged", "https://job-boards.greenhouse.io/markforged", "greenhouse", "markforged"),
    ("Brandwatch", "https://www.brandwatch.com/company/careers/", "greenhouse", None),
    ("Machine Metrics", "https://www.machinemetrics.com/careers", "greenhouse", "machinemetrics"),
    ("Appcues", "https://www.appcues.com/careers", "lever", None),
    ("LogRocket", "https://logrocket.com/careers", "lever", None),
    ("Commonwealth Fusion Systems", "https://jobs.lever.co/cfsenergy", "lever", "cfsenergy"),
    ("Help Scout", "https://www.helpscout.com/company/careers/", "ashby", None),
    ("Wistia", "https://wistia.com/jobs", "ashby", None),
    ("Crusoe Energy", "https://www.crusoe.ai/about/careers", "ashby", None),
]


def extract_token(body: str, provider: str) -> str | None:
    pattern = {
        "greenhouse": GREENHOUSE_TOKEN,
        "lever": LEVER_TOKEN,
        "ashby": ASHBY_TOKEN,
        "rippling": RIPPLING_TOKEN,
    }[provider]
    m = pattern.search(body)
    return m.group(1) if m else None


def api_url(provider: str, token: str) -> str:
    return {
        "greenhouse": f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
        "lever": f"https://api.lever.co/v0/postings/{token}?mode=json",
        "ashby": f"https://api.ashbyhq.com/posting-api/job-board/{token}",
        "rippling": f"https://api.rippling.com/platform/api/ats/v2/board/{token}/jobs",
    }[provider]


def job_count(provider: str, payload) -> int:
    if provider == "greenhouse":
        return len(payload.get("jobs", []))
    if provider == "lever":
        return len(payload) if isinstance(payload, list) else 0
    if provider == "ashby":
        return len(payload.get("jobs", []))
    if provider == "rippling":
        return len(payload.get("items", []))
    return 0


def main() -> int:
    with httpx.Client(headers={"User-Agent": "Mozilla/5.0 (compatible; watchlist-verify/1.0)"}) as client:
        for name, page_url, provider, known_token in CANDIDATES:
            token = known_token
            if token is None:
                try:
                    resp = client.get(page_url, follow_redirects=True, timeout=12)
                    token = extract_token(resp.text, provider)
                except httpx.HTTPError as exc:
                    print(f"{name:30s} PAGE FETCH FAILED: {exc}")
                    continue
            if token is None:
                print(f"{name:30s} no {provider} token found on page")
                continue

            url = api_url(provider, token)
            try:
                api_resp = client.get(url, timeout=12)
            except httpx.HTTPError as exc:
                print(f"{name:30s} token={token!r:20s} API FETCH FAILED: {exc}")
                continue

            if api_resp.status_code != 200:
                print(f"{name:30s} token={token!r:20s} API {api_resp.status_code} -- DEAD")
                continue

            try:
                payload = api_resp.json()
            except ValueError:
                print(f"{name:30s} token={token!r:20s} API 200 but not JSON -- suspicious")
                continue

            count = job_count(provider, payload)
            verdict = "OK" if count > 0 else "API LIVE BUT ZERO JOBS"
            print(f"{name:30s} token={token!r:20s} API 200, {count} jobs -- {verdict}")


if __name__ == "__main__":
    sys.exit(main() or 0)
