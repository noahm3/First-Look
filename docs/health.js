"use strict";

/*
 * Health page. Scaffold — M9 adds run history and mapping coverage (SPEC.md §12.9).
 *
 * Same rules as app.js: textContent only, no innerHTML, no inline handlers. The
 * page must never display an email address, a personal name, or the contents of
 * a notification profile (C-9.15).
 */

const DATA_URL = "jobs-recent.json";

function render(payload) {
  const status = document.getElementById("status");
  status.textContent = "";

  const last = payload.last_successful_run ? Date.parse(payload.last_successful_run) : NaN;
  const ok = !Number.isNaN(last) && payload.stale !== true;

  const dot = document.createElement("span");
  dot.className = ok ? "dot dot-ok" : "dot dot-stale";
  status.appendChild(dot);

  const text = document.createElement("span");
  text.textContent = payload.last_successful_run
    ? "Last successful run: " +
      payload.last_successful_run +
      " (run " +
      payload.run_id +
      ", " +
      payload.counts.postings +
      " live postings across " +
      payload.counts.companies +
      " companies)"
    : "No successful run recorded yet.";
  status.appendChild(text);
}

function init() {
  fetch(DATA_URL, { cache: "no-cache" })
    .then(function (response) {
      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }
      return response.json();
    })
    .then(render)
    .catch(function () {
      const status = document.getElementById("status");
      status.textContent = "Could not load run data.";
    });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
