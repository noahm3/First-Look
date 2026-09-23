"""Static checks on the dashboard source.

SECURITY.md lists CSP and the rendering rules among the three things that must
land before the code they govern: a page written with innerHTML and inline
handlers works fine until CSP arrives, then fails quietly with nothing in the
console. These assertions run from M0 so the constraint is present from the first
line rather than retrofitted at M9.

C-S.3 and C-S.4 are verified here against the source, and again in M9 and M12
against what actually shipped.
"""

import pathlib
import re

import pytest

DOCS = pathlib.Path(__file__).resolve().parents[1] / "docs"

HTML_FILES = sorted(DOCS.glob("*.html"))
JS_FILES = sorted(DOCS.glob("*.js"))

BANNED_SINKS = ["innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"]

REQUIRED_CSP_DIRECTIVES = [
    "default-src 'self'",
    "script-src 'self'",
    "img-src 'self' data:",
    "connect-src 'self'",
]

# onclick=, onerror=, onload=, ... as an HTML attribute.
INLINE_HANDLER = re.compile(r"<[^>]*\son[a-z]+\s*=", re.IGNORECASE)
INLINE_SCRIPT = re.compile(r"<script(?![^>]*\ssrc=)[^>]*>", re.IGNORECASE)

HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
JS_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def code_only(path: pathlib.Path) -> str:
    """The file with comments removed.

    Both dashboard files document the rules they follow, which means they quote
    the banned sinks by name. Scanning raw text would flag the documentation and
    miss the point, so comments come out first and the assertions then apply to
    code alone.
    """
    source = path.read_text(encoding="utf-8")
    if path.suffix == ".html":
        return HTML_COMMENT.sub("", source)

    source = JS_BLOCK_COMMENT.sub("", source)
    kept = [line for line in source.splitlines() if not line.strip().startswith(("//", "*"))]
    return "\n".join(kept)


def test_there_is_something_to_check():
    assert HTML_FILES, "no dashboard HTML found"
    assert JS_FILES, "no dashboard JS found"


@pytest.mark.parametrize("path", JS_FILES + HTML_FILES, ids=lambda p: p.name)
class TestNoUnsafeSinks:
    def test_no_banned_html_sink_appears(self, path):
        """C-S.3."""
        source = code_only(path)
        for sink in BANNED_SINKS:
            assert sink not in source, f"{path.name} uses {sink}"

    def test_no_eval_or_function_constructor(self, path):
        source = code_only(path)
        assert "eval(" not in source
        assert "new Function(" not in source


@pytest.mark.parametrize("path", HTML_FILES, ids=lambda p: p.name)
class TestContentSecurityPolicy:
    def test_a_csp_meta_tag_is_present(self, path):
        """C-S.4."""
        source = path.read_text(encoding="utf-8")
        assert "Content-Security-Policy" in source, f"{path.name} has no CSP"

    def test_the_csp_carries_the_directives_security_md_specifies(self, path):
        source = path.read_text(encoding="utf-8")
        for directive in REQUIRED_CSP_DIRECTIVES:
            assert directive in source, f"{path.name} CSP is missing: {directive}"

    def test_there_are_no_inline_event_handlers(self, path):
        """CSP blocks these, and in some browsers it does so with no console error."""
        found = INLINE_HANDLER.findall(code_only(path))
        assert not found, f"{path.name} has inline handlers: {found}"

    def test_every_script_is_external(self, path):
        inline = INLINE_SCRIPT.findall(code_only(path))
        assert not inline, f"{path.name} has an inline <script>: {inline}"


class TestLinkSafety:
    @property
    def app_js(self) -> str:
        return (DOCS / "app.js").read_text(encoding="utf-8")

    def test_a_urls_scheme_is_checked_before_it_becomes_an_href(self):
        """C-S.2 — a javascript: URL in a posting executes on click."""
        source = self.app_js
        assert "isRenderableHref" in source
        assert 'protocol === "http:"' in source
        assert 'protocol === "https:"' in source

    def test_outbound_links_carry_noopener_noreferrer(self):
        assert 'rel = "noopener noreferrer"' in self.app_js

    def test_text_is_set_with_textcontent(self):
        assert "textContent" in self.app_js


class TestPrivacySurface:
    """C-9.15 / SPEC.md §15: nothing personal on either page, at any milestone."""

    @pytest.mark.parametrize("path", HTML_FILES + JS_FILES, ids=lambda p: p.name)
    def test_no_email_shaped_string_in_the_source(self, path):
        source = path.read_text(encoding="utf-8")
        assert not re.search(r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}", source)

    @pytest.mark.parametrize("path", HTML_FILES, ids=lambda p: p.name)
    def test_pages_are_not_indexable(self, path):
        # Low-profile, not hidden (SPEC.md §15) — the dashboard carries no
        # personal data by construction, but there is no reason to court search
        # traffic for it either.
        assert "noindex" in path.read_text(encoding="utf-8")


class TestThreeEmptyStates:
    """SPEC.md §12.7 — conflating these recreates silent failure in the UI."""

    def test_all_three_exist_as_distinct_elements(self):
        source = (DOCS / "index.html").read_text(encoding="utf-8")
        for element_id in ("empty-no-data", "empty-last-run-failed", "empty-no-match"):
            assert f'id="{element_id}"' in source

    def test_the_stale_banner_is_on_the_jobs_page_not_only_on_health(self):
        # §12.1's explicit exception to health living behind the hamburger.
        assert 'id="stale-banner"' in (DOCS / "index.html").read_text(encoding="utf-8")
