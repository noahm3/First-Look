"""Verify careers-page links from the user's personal, hand-compiled company list
(kept outside the repo -- Downloads, never committed) and fingerprint the ATS
behind each live one. Output here carries only public data: company name,
careers URL, and detected ATS (CLAUDE.md: company names/ATS tokens/postings are
public and fine to commit). Never touches the source CSV's Contact/Connection
or account-credential columns.
"""

import csv
import re
import sys
import time

import httpx

SOURCE = r"C:\Users\o439n\Downloads\Companies Website Table - Companies_Table.csv"
OUT = "spikes/iteration13_personal_list_results.csv"

FINGERPRINTS = [
    (re.compile(r"boards\.greenhouse\.io|greenhouse\.io/embed"), "greenhouse"),
    (re.compile(r"jobs\.lever\.co"), "lever"),
    (re.compile(r"jobs\.ashbyhq\.com|ashbyhq\.com"), "ashby"),
    (re.compile(r"ats\.rippling\.com|api\.rippling\.com"), "rippling"),
    (re.compile(r"\.workable\.com"), "workable"),
    (re.compile(r"\.bamboohr\.com"), "bamboohr"),
    (re.compile(r"\.taleo\.net"), "taleo"),
    (re.compile(r"\.icims\.com"), "icims"),
    (re.compile(r"\.applytojob\.com"), "applytojob"),
    (re.compile(r"hire\.withgoogle\.com"), "google_hire_defunct"),
    (re.compile(r"angel\.co|wellfound\.com"), "angellist_wellfound"),
    (re.compile(r"\.dayforcehcm\.com|dayforcehcm\.com"), "dayforce"),
    (re.compile(r"\.myworkdayjobs\.com|workday"), "workday"),
    (re.compile(r"\.tbe\.taleo\.net"), "taleo"),
    (re.compile(r"tellent\.com"), "tellent"),
]


def fingerprint_url(url: str) -> str | None:
    for pattern, name in FINGERPRINTS:
        if pattern.search(url):
            return name
    return None


def fingerprint_body(body: str) -> str | None:
    checks = [
        ("greenhouse.io", "greenhouse"),
        ("lever.co", "lever"),
        ("ashbyhq.com", "ashby"),
        ("api.rippling.com", "rippling"),
        ("myworkdayjobs.com", "workday"),
        ("icims.com", "icims"),
        ("workable.com", "workable"),
        ("bamboohr.com", "bamboohr"),
    ]
    low = body.lower()
    for needle, name in checks:
        if needle in low:
            return name
    return None


def check_one(client: httpx.Client, name: str, url: str) -> dict:
    try:
        resp = client.get(url, follow_redirects=True, timeout=12)
        final_url = str(resp.url)
        ats = fingerprint_url(final_url) or fingerprint_url(url)
        if ats is None and resp.status_code < 400:
            ats = fingerprint_body(resp.text)
        return {
            "name": name,
            "original_url": url,
            "final_url": final_url,
            "status": resp.status_code,
            "redirected": final_url != url,
            "ats_guess": ats or "",
        }
    except httpx.HTTPError as exc:
        return {
            "name": name,
            "original_url": url,
            "final_url": "",
            "status": f"ERROR:{type(exc).__name__}",
            "redirected": False,
            "ats_guess": "",
        }


def main() -> int:
    with open(SOURCE, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    candidates = []
    for r in rows:
        careers = (r.get("Careers Page") or "").strip()
        what = (r.get("What they do") or "").strip()
        name = (r.get("Name") or "").strip()
        if not name or careers in ("", "-") or not careers.startswith("http"):
            continue
        if "vc firm" in what.lower() or "portfolio" in what.lower():
            continue
        candidates.append((name, careers))

    print(f"{len(candidates)} candidates to check", file=sys.stderr)

    results = []
    with httpx.Client(headers={"User-Agent": "Mozilla/5.0 (compatible; watchlist-verify/1.0)"}) as client:
        for i, (name, url) in enumerate(candidates):
            result = check_one(client, name, url)
            results.append(result)
            print(f"[{i + 1}/{len(candidates)}] {name}: {result['status']} -> {result['ats_guess'] or 'unknown'}", file=sys.stderr)
            time.sleep(0.3)

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "original_url", "final_url", "status", "redirected", "ats_guess"])
        writer.writeheader()
        writer.writerows(results)

    print(f"wrote {OUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
