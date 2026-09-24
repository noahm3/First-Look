"""Is a discovered domain a company's own site at all?

Iteration 16 found inputs that no mapping cascade could ever map, because they
aren't a company's site: subdomains of someone else's product
(`app.usercentrics.eu`, `api.intellimize.co`, `insightpartners.altareturn.com`)
and media or aggregator sites (`therobotreport.com`). Counting them against
coverage makes the §8.6 number dishonest, so they fail up front as
`not_a_company_domain` -- no requests made -- and the summary reports coverage
over valid inputs as well.

This is the check discovery sources should call before ingesting a domain.
Today only the mapping cascade calls it: the watchlist is hand-entered and
Getro supplies no domains. The VC-portfolio and later discovery ingesters
(M5/M7/M8) are where it belongs upstream.
"""

import pathlib
from functools import cache
from typing import Any

import yaml

NON_COMPANY_DOMAINS_PATH = pathlib.Path("config/non_company_domains.yml")
# Second-level labels under which the registrable domain is three labels deep
# (`acme.co.uk`, `acme.com.au`).
SECOND_LEVEL_SUFFIXES = frozenset({"co", "com", "org", "net", "ac", "gov", "edu"})


def registrable_domain(domain: str) -> str:
    labels = [part for part in domain.lower().strip(".").split(".") if part]
    if labels and labels[0] == "www":
        labels = labels[1:]
    depth = 3 if len(labels) >= 3 and labels[-2] in SECOND_LEVEL_SUFFIXES else 2
    return ".".join(labels[-depth:])


@cache
def load_non_company_domains(path: pathlib.Path = NON_COMPANY_DOMAINS_PATH) -> frozenset[str]:
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return frozenset(str(d).strip().lower() for d in raw if str(d).strip())


def classify_input_domain(domain: str) -> str | None:
    """None if `domain` looks like a company's own site, else why not."""
    host = domain.lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    registrable = registrable_domain(host)
    if host != registrable:
        return "subdomain"
    if registrable in load_non_company_domains():
        return "listed_non_company"
    return None
