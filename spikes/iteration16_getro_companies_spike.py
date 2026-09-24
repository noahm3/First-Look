"""
Iteration 16 spike: can Getro's /companies "Load more" be sourced headlessly?

Follow-up to the /companies domain-field finding added to SPEC.md §7.2 in the
previous session. That finding was real (every entry on the first page has a
`domain`) but incomplete: `/companies` only renders 12 companies server-side
(`companies.total` is 767/79/28 on the three networks already checked), and
the UI's own "Load more" button implies the rest is one client-side fetch
away -- this spike tries to find that fetch without a browser.

**It did not find it.** Two things ARE confirmed here, one of them a real
correction to already-shipped code (see the bottom of this file's output):

1. The Next.js SSR data route (`/_next/data/{buildId}/companies.json`)
   ignores every pagination-shaped query param tried (`page`, `offset`,
   `skip`, `cursor`, `after`, `companiesPage`, `p`) -- always returns the
   same first page. "Load more" is not server-side pagination via a query
   string on this route.
2. **The same undercount applies to `/jobs`, which `src/getro.py` already
   ships against.** Climate Draft's `/jobs` page reports
   `initialState.jobs.total = 11474` but `initialState.jobs.found` only ever
   has 20 entries. `src/getro.py`'s `extract_companies` only reads `found` --
   on a large network, it silently sees a small slice of the real company
   list, the same shape of gap as `/companies`. Not a correctness bug (every
   company it does see is real), but a completeness one, and it predates
   this spike -- it was already true the day M6 shipped, just not measured
   until this session pulled on the same thread for `/companies`.

Static analysis of the JS actually loaded for `/companies` (main app bundle,
every page-specific and shared chunk the Next.js build manifest lists for
that route, ~14 files, ~800KB total) found no `fetch`/`.get`/`.post` call
site building a companies-search request, and no hardcoded API base URL
beyond getro.com's own marketing pages. The most likely explanation: the
actual search/pagination feature module is behind a `Load more` button's own
dynamic `import()`, which Next.js code-splits into a chunk that's never
requested until the button is clicked -- invisible to anything that doesn't
actually click it in a real browser. Same method that found Consider's real
endpoint (`spikes/iteration2_consider_spike.py`) is the honest next step
here, not more URL guessing from the terminal.

Run: python -m spikes.iteration16_getro_companies_spike
"""

import json
import re

from src.http import FetchClient

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)

PAGINATION_QUERY_GUESSES = ["page=2", "offset=12", "skip=12", "cursor=12", "after=12", "p=2"]


def get_next_data(client: FetchClient, url: str) -> dict:
    result = client.get(url)
    if not result.ok:
        raise ValueError(f"{url}: fetch failed ({result.error or result.status})")
    match = NEXT_DATA_RE.search(result.text)
    if match is None:
        raise ValueError(f"{url}: no __NEXT_DATA__ found")
    return json.loads(match.group(1))


def check_companies_pagination(client: FetchClient, board_url: str) -> None:
    data = get_next_data(client, board_url)
    build_id = data["buildId"]
    companies = data["props"]["pageProps"]["initialState"]["companies"]
    found, total = companies.get("found", []), companies.get("total")
    with_domain = sum(1 for c in found if c.get("domain"))
    print(f"{board_url}")
    print(f"  first page: {len(found)} of {total} total, {with_domain}/{len(found)} with domain")

    base = f"https://{board_url.split('/')[2]}/_next/data/{build_id}/companies.json"
    first_name = found[0]["name"] if found else None
    for query in PAGINATION_QUERY_GUESSES:
        body = client.get(f"{base}?{query}").json()
        page_found = body["pageProps"]["initialState"]["companies"]["found"]
        page_first = page_found[0]["name"] if page_found else None
        same = page_first == first_name
        print(f"  ?{query} -> first company still {page_first!r}: {'unchanged (ignored)' if same else 'CHANGED'}")


def check_jobs_undercount(client: FetchClient, board_url: str) -> None:
    data = get_next_data(client, board_url)
    jobs = data["props"]["pageProps"]["initialState"]["jobs"]
    found, total = len(jobs.get("found", [])), jobs.get("total")
    print(f"{board_url} (jobs, not companies): found={found} total={total}")
    if total and found < total:
        print(
            f"  UNDERCOUNT: src/getro.py's extract_companies only ever sees these "
            f"{found} jobs' worth of organizations, not all {total}"
        )


if __name__ == "__main__":
    client = FetchClient()
    try:
        print("=== /companies: does any pagination-shaped query param work? ===")
        check_companies_pagination(client, "https://jobs.climatedraft.org/companies")

        print("\n=== /jobs: is the same undercount real, on already-shipped code's path? ===")
        check_jobs_undercount(client, "https://jobs.climatedraft.org/jobs")
        check_jobs_undercount(client, "https://breakthroughenergy.getro.com/jobs")
    finally:
        client.close()
