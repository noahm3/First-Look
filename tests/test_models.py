"""Tests for src/models.py's closed value sets.

New providers land here first: a typo in an enum value silently breaks every
adapter and the mapping cascade's `unsupported_ats:{name}` distribution alike,
so the value strings are pinned by name, not just existence.
"""

from src.models import AtsProvider


def test_all_eight_m2_providers_are_registered():
    values = {p.value for p in AtsProvider}
    assert values == {
        "greenhouse",
        "lever",
        "ashby",
        "smartrecruiters",
        "rippling",
        "bamboohr",
        "workable",
        "personio",
        "breezy_hr",
    }
