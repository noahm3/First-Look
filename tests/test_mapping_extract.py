"""Tests for src/mapping_extract.py -- (provider, token) evidence from raw HTML.

Snippets are the real shapes each provider's embed or link takes, including
the ones earlier spikes got wrong (the Greenhouse `embed/job_board/js?for=`
shape, entity-escaped Rippling embeds, BambooHR's `staticfe` asset host).
"""

import pytest

from src.mapping_extract import extract
from src.models import AtsProvider

P = AtsProvider


def tokens(html):
    return extract(html).tokens


class TestSupportedTokens:
    @pytest.mark.parametrize(
        ("html", "expected"),
        [
            ('<a href="https://boards.greenhouse.io/owllabs">Jobs</a>', (P.GREENHOUSE, "owllabs")),
            (
                '<a href="https://job-boards.greenhouse.io/markforged/jobs/123">x</a>',
                (P.GREENHOUSE, "markforged"),
            ),
            (
                '<script src="https://boards.greenhouse.io/embed/job_board/js?for=vestmark">',
                (P.GREENHOUSE, "vestmark"),
            ),
            (
                '<iframe src="https://boards.greenhouse.io/embed/job_board?for=brandwatch&b=x">',
                (P.GREENHOUSE, "brandwatch"),
            ),
            (
                'fetch("https://boards-api.greenhouse.io/v1/boards/3playmedia/jobs")',
                (P.GREENHOUSE, "3playmedia"),
            ),
            ('<a href="https://jobs.lever.co/logrocket">', (P.LEVER, "logrocket")),
            # Lever, Rippling and Workable tokens are case-sensitive (confirmed
            # live: Lever `JourneyClinical` 200, `journeyclinical` 404).
            ('<a href="https://jobs.lever.co/JourneyClinical/abc">', (P.LEVER, "JourneyClinical")),
            ('<a href="https://ats.rippling.com/Acme-Inc/jobs">', (P.RIPPLING, "Acme-Inc")),
            ('<a href="https://apply.workable.com/AcmeCo/">', (P.WORKABLE, "AcmeCo")),
            # ...the others are not, and are normalised to lowercase.
            ('<a href="https://boards.greenhouse.io/OwlLabs">', (P.GREENHOUSE, "owllabs")),
            ('<a href="https://jobs.ashbyhq.com/Crusoe">', (P.ASHBY, "crusoe")),
            ('<a href="https://Forge-Nano.breezy.hr/">', (P.BREEZY_HR, "forge-nano")),
            ("api.lever.co/v0/postings/palantir?mode=json", (P.LEVER, "palantir")),
            ('<a href="https://jobs.ashbyhq.com/crusoe">', (P.ASHBY, "crusoe")),
            (
                '<script src="https://jobs.ashbyhq.com/helpscout/embed?version=2">',
                (P.ASHBY, "helpscout"),
            ),
            ("api.ashbyhq.com/posting-api/job-board/wistia", (P.ASHBY, "wistia")),
            ('<a href="https://ats.rippling.com/stem/jobs">', (P.RIPPLING, "stem")),
            ('<a href="https://ats.rippling.com/en-GB/algorand/jobs">', (P.RIPPLING, "algorand")),
            ('<a href="https://ats.rippling.com/embed/gotenna">', (P.RIPPLING, "gotenna")),
            (
                "https://api.rippling.com/platform/api/ats/v2/board/shippo/jobs",
                (P.RIPPLING, "shippo"),
            ),
            (
                '<div data-job-board-id="&amp;quot;gradient-comfort&amp;quot;">',
                (P.RIPPLING, "gradient-comfort"),
            ),
            ('<a href="https://svante.bamboohr.com/careers">', (P.BAMBOOHR, "svante")),
            (
                '<script src="https://ph7.bamboohr.com/js/embed.js">',
                (P.BAMBOOHR, "ph7"),
            ),
            ('<a href="https://apply.workable.com/aerones/">', (P.WORKABLE, "aerones")),
            (
                "https://apply.workable.com/api/v1/widget/accounts/seeq",
                (P.WORKABLE, "seeq"),
            ),
            ('<a href="https://terabase.workable.com">', (P.WORKABLE, "terabase")),
            (
                '<a href="https://strohm.jobs.personio.com/">',
                (P.PERSONIO, "strohm.jobs.personio.com"),
            ),
            (
                '<a href="https://liveeo-gmbh.jobs.personio.de/job/1">',
                (P.PERSONIO, "liveeo-gmbh.jobs.personio.de"),
            ),
            ('<a href="https://forge-nano.breezy.hr/">', (P.BREEZY_HR, "forge-nano")),
        ],
    )
    def test_each_provider_shape_yields_its_token(self, html, expected):
        assert tokens(html) == (expected,)

    def test_json_escaped_slashes_in_inline_scripts(self):
        html = r'<script>var u = "https:\/\/jobs.lever.co\/logrocket";</script>'
        assert tokens(html) == ((P.LEVER, "logrocket"),)

    def test_repeated_links_to_one_board_yield_it_once(self):
        html = '<a href="https://jobs.lever.co/ro">a</a><a href="https://jobs.lever.co/ro/x">b</a>'
        assert tokens(html) == ((P.LEVER, "ro"),)

    def test_two_different_boards_are_both_reported(self):
        html = '<a href="https://jobs.lever.co/aaa111">a</a><a href="https://boards.greenhouse.io/bbb222">'
        assert set(tokens(html)) == {(P.LEVER, "aaa111"), (P.GREENHOUSE, "bbb222")}


class TestNonTokens:
    @pytest.mark.parametrize(
        "html",
        [
            # CircleCI: an allowlist/CSP mention of the provider, no board path.
            '<meta http-equiv="Content-Security-Policy" content="frame-src *.greenhouse.io">',
            '{"allowlist": ["greenhouse.io", "lever.co"]}',
            '<a href="https://boards.greenhouse.io/">',
            # Workable's own job-detail links carry a shortcode, not the account.
            '<a href="https://apply.workable.com/j/C5AA4AA02F">',
            # Asset and marketing hosts are not tenants.
            '<script src="https://staticfe.bamboohr.com/assets/x.js">',
            # 3yourmind.com, first 50-domain dry run: a numbered image host.
            '<img src="https://images4.bamboohr.com/123/logo.png">',
            '<img src="https://cdn2.breezy.hr/x.png">',
            '<a href="https://www.bamboohr.com/">',
            '<a href="https://www.workable.com/">',
            '<a href="https://jobs.workable.com/search">',
            '<a href="https://www.personio.com/">',
            '<a href="https://app.breezy.hr/signin">',
            '<a href="https://www.breezy.hr/">',
            "just the words greenhouse, lever and ashby in prose",
        ],
    )
    def test_no_token(self, html):
        assert tokens(html) == ()


class TestUnsupported:
    @pytest.mark.parametrize(
        ("html", "name"),
        [
            ('<a href="https://careers-acme.icims.com/jobs">', "icims"),
            ('<a href="https://acme.wd5.myworkdayjobs.com/External">', "workday"),
            ('<a href="https://acme.teamtailor.com/jobs">', "teamtailor"),
            ('<a href="https://jobs.smartrecruiters.com/Acme">', "smartrecruiters"),
            ('<a href="https://acme.recruitee.com/">', "recruitee"),
            ('<a href="https://acme.applytojob.com/apply">', "jazzhr"),
            ('<a href="https://jobs.jobvite.com/acme">', "jobvite"),
            ('<a href="https://app.trinethire.com/companies/1-acme/jobs/2-x">', "trinet"),
        ],
    )
    def test_unsupported_ats_hosts_are_named(self, html, name):
        assert extract(html).unsupported == (name,)

    def test_unsupported_names_come_only_from_urls_not_prose(self):
        assert extract("<p>We migrated off iCIMS and Workday last year.</p>").unsupported == ()

    def test_a_supported_board_is_not_also_reported_unsupported(self):
        result = extract('<a href="https://jobs.lever.co/logrocket">')
        assert result.unsupported == ()

    def test_wordpress_job_plugin_is_recorded(self):
        html = '<link rel="stylesheet" href="/wp-content/plugins/wp-job-manager/x.css">'
        assert extract(html).unsupported == ("wordpress-job-plugin",)
