"use strict";

/*
 * Dashboard rendering.
 *
 * Every value on a card comes from a third party — job titles, company names,
 * comp strings, location strings — and this page shares an origin with the
 * LinkedIn connection counts that M11 will put in localStorage. So an XSS here
 * is an exfiltration path for hundreds of other people's employment data, not a
 * defacement. SECURITY.md §S1 is the full argument.
 *
 * Two rules, both enforced by tests rather than by memory:
 *
 *   1. No innerHTML, outerHTML, insertAdjacentHTML, or document.write. Ever.
 *      Text goes in with textContent, structure with createElement. tests/
 *      test_dashboard.py greps this file and fails the build otherwise (C-S.3).
 *
 *   2. A URL is only rendered as an href after its scheme is checked. A
 *      `javascript:` URL in a posting executes on click (C-S.2), and the export
 *      ships those verbatim on purpose so the rejection happens here, in the one
 *      place that knows it is building a link.
 *
 * No inline event handlers anywhere — the CSP in index.html forbids them, and
 * that is deliberate.
 */

const DATA_URL = "jobs-recent.json";
const SUPPORTED_SCHEMA_VERSION = 1;
const STALE_AFTER_HOURS = 48;

/* ------------------------------------------------------------------ *
 * Safe construction helpers. Everything user-visible goes through these.
 * ------------------------------------------------------------------ */

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) {
    node.className = className;
  }
  if (text !== undefined && text !== null) {
    // textContent, never innerHTML. A title of `<img src=x onerror=...>`
    // renders as those literal characters (C-S.1).
    node.textContent = String(text);
  }
  return node;
}

function isRenderableHref(url) {
  if (typeof url !== "string" || url === "") {
    return false;
  }
  let parsed;
  try {
    parsed = new URL(url, window.location.href);
  } catch (_err) {
    return false;
  }
  return parsed.protocol === "http:" || parsed.protocol === "https:";
}

function link(url, text) {
  if (!isRenderableHref(url)) {
    // Dropped, not rendered as a dead or dangerous link. The text still shows,
    // so the posting does not silently vanish from the page.
    return el("span", "title title-unlinked", text);
  }
  const anchor = el("a", "title", text);
  anchor.href = url;
  anchor.rel = "noopener noreferrer";
  anchor.target = "_blank";
  return anchor;
}

/* ------------------------------------------------------------------ *
 * Formatting
 * ------------------------------------------------------------------ */

function foundAgo(iso, now) {
  // "Found Nh ago" under 24 hours, "Found N days ago" above (SPEC.md §12.5).
  // Labelled "Found" because first_seen_at is when we saw it, not when it was
  // posted — §6 is explicit that the ATS date is unreliable.
  if (!iso) {
    return "";
  }
  const seen = Date.parse(iso);
  if (Number.isNaN(seen)) {
    return "";
  }
  const hours = Math.floor((now - seen) / 3600000);
  if (hours < 1) {
    return "Found just now";
  }
  if (hours < 24) {
    return "Found " + hours + "h ago";
  }
  const days = Math.floor(hours / 24);
  return "Found " + days + (days === 1 ? " day ago" : " days ago");
}

function compLine(comp) {
  // Never blank: a missing figure must be distinguishable from a broken one
  // (SPEC.md §12.5, C-9.11).
  if (!comp || !comp.summary) {
    return el("div", "comp comp-none", "comp not disclosed");
  }
  const line = el("div", "comp", comp.summary);
  if (comp.tier_count > 1) {
    line.appendChild(el("span", "badge", "multiple ranges"));
  }
  return line;
}

/* ------------------------------------------------------------------ *
 * Cards
 * ------------------------------------------------------------------ */

function card(posting, now) {
  const item = el("li", "card");

  const top = el("div", "card-top");
  const tags = Array.isArray(posting.industry_tags) ? posting.industry_tags.slice(0, 2) : [];
  const heading = posting.company + (tags.length ? " · " + tags.join(", ") : "");
  top.appendChild(el("span", "company", heading));
  top.appendChild(el("span", "age", foundAgo(posting.first_seen_at, now)));
  item.appendChild(top);

  item.appendChild(link(posting.url, posting.title));

  const meta = [posting.department, posting.location_raw].filter(Boolean).join(" · ");
  item.appendChild(el("div", "meta", meta));

  item.appendChild(compLine(posting.comp));

  if (posting.is_repost) {
    item.appendChild(el("span", "badge", "repost"));
  }

  return item;
}

/* ------------------------------------------------------------------ *
 * Page state
 * ------------------------------------------------------------------ */

function show(id, visible) {
  const node = document.getElementById(id);
  if (node) {
    node.hidden = !visible;
  }
}

function renderStatus(payload, now) {
  const status = document.getElementById("status");
  status.textContent = "";

  const last = payload.last_successful_run ? Date.parse(payload.last_successful_run) : NaN;
  const stale =
    payload.stale === true ||
    Number.isNaN(last) ||
    now - last > STALE_AFTER_HOURS * 3600000;

  const dot = el("span", stale ? "dot dot-stale" : "dot dot-ok");
  status.appendChild(dot);
  status.appendChild(
    el(
      "span",
      null,
      payload.last_successful_run
        ? "Last successful run " + foundAgo(payload.last_successful_run, now).replace("Found ", "")
        : "No successful run recorded"
    )
  );

  if (stale) {
    const banner = document.getElementById("stale-banner");
    banner.textContent = payload.last_successful_run
      ? "Data may be stale — last successful run was over " + STALE_AFTER_HOURS + "h ago."
      : "No successful run has been recorded yet.";
    banner.hidden = false;
  }
  return stale;
}

function render(payload, now) {
  const list = document.getElementById("cards");
  list.textContent = "";

  const stale = renderStatus(payload, now);
  const postings = Array.isArray(payload.postings) ? payload.postings : [];

  // The three empty states stay distinct (SPEC.md §12.7).
  if (postings.length === 0) {
    show(stale ? "empty-last-run-failed" : "empty-no-data", true);
    return;
  }

  for (const posting of postings) {
    list.appendChild(card(posting, now));
  }
}

function fail(message) {
  const node = document.getElementById("load-error");
  node.textContent = message;
  node.hidden = false;
}

function init() {
  const toggle = document.getElementById("menu-toggle");
  const menu = document.getElementById("menu");
  // addEventListener, not an onclick attribute — the CSP forbids inline handlers.
  toggle.addEventListener("click", function () {
    const open = menu.hidden;
    menu.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
  });

  fetch(DATA_URL, { cache: "no-cache" })
    .then(function (response) {
      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }
      return response.json();
    })
    .then(function (payload) {
      if (payload.schema_version !== SUPPORTED_SCHEMA_VERSION) {
        // Saying so beats rendering half a page off a shape we do not know.
        fail(
          "This page expects export schema v" +
            SUPPORTED_SCHEMA_VERSION +
            " but received v" +
            payload.schema_version +
            ". Reload, or the site needs redeploying."
        );
        return;
      }
      render(payload, Date.now());
    })
    .catch(function () {
      // No error detail on screen: it would come from a fetch of a file that may
      // itself be the problem, and a stack trace helps nobody here.
      fail("Could not load the job data. See Health.");
    });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
