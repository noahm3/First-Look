"""
Iteration 1 spike: hit one real company's board on each of the three main ATS
providers, parse out the fields SPEC.md says we'd want to store (see SPEC.md
section 6, the `postings` table, and section 9, the adapter notes), and print
the result. No storage, no framework, no error handling beyond "don't crash" -
this is throwaway exploration, not src/ code.

Run: python spikes/iteration1_ats_spike.py
"""

import json
import urllib.request

USER_AGENT = "first-look-spike/0.1 (+https://github.com/)"


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_greenhouse(token: str, limit: int = 2) -> list[dict]:
    # List endpoint: no first_published, no payInputRanges - those need a
    # per-job detail call. SPEC.md §9 flags this explicitly.
    listing = fetch_json(
        f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    )
    parsed = []
    for job in listing["jobs"][:limit]:
        detail = fetch_json(
            f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{job['id']}"
        )
        parsed.append(
            {
                "source": "greenhouse",
                "ats_job_id": str(job["id"]),
                "title_raw": job["title"],
                "department_raw": ", ".join(
                    d["name"] for d in job.get("departments", [])
                )
                or None,
                "location_raw": (job.get("location") or {}).get("name"),
                "url": job.get("absolute_url"),
                "posted_at": detail.get("first_published"),  # detail-only field
                "updated_at": job.get("updated_at"),  # mutates on any edit - not
                # reliable as "posted" date, see SPEC.md §6
                "comp_raw": detail.get("pay_input_ranges") or None,
            }
        )
    return parsed


def parse_lever(site: str, limit: int = 2) -> list[dict]:
    postings = fetch_json(f"https://api.lever.co/v0/postings/{site}?mode=json")
    parsed = []
    for job in postings[:limit]:
        cats = job.get("categories", {})
        parsed.append(
            {
                "source": "lever",
                "ats_job_id": job["id"],
                "title_raw": job.get("text"),
                "department_raw": cats.get("team") or cats.get("department"),
                "location_raw": cats.get("location"),
                "url": job.get("hostedUrl"),
                "posted_at": job.get("createdAt"),  # undocumented epoch ms,
                # reliable in practice per SPEC.md §9
                "comp_raw": job.get("salaryRange"),
            }
        )
    return parsed


def parse_ashby(board: str, limit: int = 2) -> list[dict]:
    data = fetch_json(
        f"https://api.ashbyhq.com/posting-api/job-board/{board}?includeCompensation=true"
    )
    parsed = []
    for job in data["jobs"][:limit]:
        comp = job.get("compensation") or {}
        parsed.append(
            {
                "source": "ashby",
                "ats_job_id": job["id"],
                "title_raw": job.get("title"),
                "department_raw": job.get("department") or job.get("team"),
                "location_raw": job.get("location"),
                "workplace_type_raw": job.get("workplaceType"),  # Ashby-only
                # structured field, see SPEC.md §9
                "url": job.get("jobUrl"),
                "posted_at": job.get("publishedAt"),
                "comp_raw": comp.get("compensationTierSummary"),
            }
        )
    return parsed


def show(label: str, rows: list[dict]) -> None:
    print(f"\n=== {label} ===")
    for row in rows:
        print(json.dumps(row, indent=2))


if __name__ == "__main__":
    show("Greenhouse - robinhood", parse_greenhouse("robinhood"))
    show("Lever - ro", parse_lever("ro"))
    show("Ashby - ramp", parse_ashby("ramp"))
