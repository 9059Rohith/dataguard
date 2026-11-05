"use strict";
const $ = (s, root = document) => root.querySelector(s);
const UI = globalThis.DataGuardUI;
const escape = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const paths = {
  overview: "m3 10 9-7 9 7v11h-6v-7H9v7H3Z",
  shield: "m12 2 9 4v7c0 5-9 9-9 9s-9-4-9-9V6l9-4 m-4 10 3 3 5-6",
  copy: "M8 8h12v13H8z M4 16H2V2h13v2",
  eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12 M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6",
  chevron: "m7 10 5 5 5-5",
  menu: "M4 6h16M4 12h16M4 18h16",
  filter: "M3 5h18M6 12h12M10 19h4",
  code: "m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18",
  branch: "M6 3v12a4 4 0 0 0 4 4h8M6 7h8a4 4 0 0 0 4-4M3 3h6M15 19h6",
  datasets:
    "M20 6c0 2-16 2-16 0s16-2 16 0v12c0 3-16 3-16 0V6 M4 12c0 3 16 3 16 0",
  contracts: "M8 3H5v18h14V3h-3 M9 2h6v4H9z M8 11h8 M8 15h6",
  impact: "M4 4h6v16H4z M14 4h6v16h-6z M10 12h4 m-2-2 2 2-2 2",
  checks: "m4 12 5 5L20 6 M3 3h6 M3 3v6 M21 21h-6 M21 21v-6",
  batches: "M4 3h16v5H4z M4 11h16v10H4z M8 15h8 M8 18h5",
  quarantine: "M12 3 3 7v6c0 5 9 9 9 9s9-4 9-9V7L12 3 M12 8v5 M12 16h.01",
  versions: "M4 4h12v12H4z M9 20h11V9 M8 8h4 M8 12h4",
  lineage: "M3 10h6v6H3z M15 2h6v6h-6z M15 17h6v6h-6z M9 13h3V5h3 M12 13v7h3",
  incidents: "M12 3 2 21h20L12 3 M12 9v5 M12 17h.01",
  recovery: "M3 11a9 9 0 1 1 2 7 M3 4v7h7 M12 7v6l4 2",
  agent: "m12 2 3 7 7 3-7 3-3 7-3-7-7-3 7-3 3-7 M20 2v4 M18 4h4",
  connections:
    "M9 8 6 5a4 4 0 0 0-5 5l4 4 M15 16l3 3a4 4 0 0 0 5-5l-4-4 M8 16l8-8",
  settings:
    "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1 1-3",
  search: "M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14 M15 15l6 6",
  arrow: "M4 12h16 M14 6l6 6-6 6",
  download: "M12 3v12 m-5-5 5 5 5-5 M4 15v6h16v-6",
  plus: "M12 4v16 M4 12h16",
  check: "m5 12 4 4L19 6",
  close: "m6 6 12 12 M6 18 18 6",
  github:
    "M9 19c-4 1-4-2-6-2 M15 22v-4a4 4 0 0 0-1-3c4 0 7-2 7-6 0-2-1-3-1-4 0-2 0-3-1-3-2 0-3 1-4 1-2 0-3-1-5 0C9 3 7 2 5 2c-1 0-1 1-1 3-1 1-1 2-1 4 0 4 3 6 7 6-1 1-1 2-1 3v4",
  lock: "M6 10h12v11H6z M8 10V6a4 4 0 0 1 8 0v4 M12 14v3",
  info: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18 M12 11v6 M12 7h.01",
  external: "M14 3h7v7 M21 3 10 14 M10 3H3v18h18v-7",
};
const icon = (name, size = 16) =>
  `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name] || paths.overview}"/></svg>`;
const pages = [
  ["overview", "Overview"],
  ["datasets", "Datasets"],
  ["contracts", "Contracts"],
  ["impact", "Contract impact"],
  ["checks", "Quality checks"],
  ["batches", "Capture history"],
  ["quarantine", "Quarantine"],
  ["versions", "Version comparison"],
  ["lineage", "Data lineage"],
  ["incidents", "Incidents"],
  ["recovery", "Recovery"],
  ["agent", "AI investigator"],
  ["connections", "Connections"],
  ["settings", "Settings"],
];
let workspace,
  provider,
  token = "",
  selectedId = "",
  page = location.pathname.split("/")[2] || "overview",
  lastAgent = null;
let pendingQuestion = "";
const recordView = { query: "", sort: "repository", filter: "all" };
const historyView = { query: "", status: "all" };
let toastTimer;
let publicCooldownUntil = 0;
let publicCooldownTimer;
const number = (n) =>
  typeof n === "number" && Number.isFinite(n) ? n.toLocaleString("en-US") : "—";
const date = (t) => {
  const d = new Date(t);
  return isNaN(d)
    ? "Unavailable"
    : d.toLocaleString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "UTC",
      }) + " UTC";
};
const age = (t) => {
  if (isNaN(new Date(t).getTime())) return "Unavailable";
  const hours = Math.max(0, (Date.now() - new Date(t)) / 3600000);
  return hours < 1
    ? Math.floor(hours * 60) + "m ago"
    : hours < 48
      ? hours.toFixed(1) + "h ago"
      : Math.floor(hours / 24) + "d ago";
};
const capture = () =>
  workspace.captures.find((c) => c.id === selectedId) || workspace.captures[0];
const pill = (label, style = "") =>
  `<span class="pill ${style}"><span class="live-dot"></span>${escape(label)}</span>`;
const status = (c) =>
  pill(
    c.status === "published" ? "Passed contract" : "Quarantined",
    c.status === "published" ? "" : "bad",
  );
const link = (to, label) =>
  `<a class="text-link" href="/console/${to}">${label} ${icon("arrow", 13)}</a>`;
const button = (label, action, style = "", attrs = "") =>
  `<button class="button ${style}" data-action="${action}" ${attrs}>${label}</button>`;
const heading = (title, desc, actions = "", kicker = "") =>
  `<div class="page-heading"><div>${kicker ? `<span class="archive-kicker">${kicker}</span>` : ""}<h1>${title}</h1><p>${desc}</p></div><div class="heading-actions">${actions}</div></div>`;
const section = (title, right = "") =>
  `<div class="section-title"><h2>${title}</h2>${right}</div>`;
const empty = (title, desc, ic = "datasets") =>
  `<div class="empty-state"><span class="empty-icon">${icon(ic, 36)}</span><h2>${title}</h2><p>${desc}</p></div>`;
const options = (value = selectedId) =>
  workspace.captures
    .map(
      (c) =>
        `<option value="${c.id}" ${c.id === value ? "selected" : ""}>${escape(c.name)} · ${c.id.slice(0, 15)} · ${date(c.evaluated_at)}</option>`,
    )
    .join("");
const selector = () =>
  `<label class="inline-select" for="capture-select">Evidence capture<select id="capture-select">${options(capture()?.id)}</select></label>`;
const evidence = (c) =>
  `<dl class="evidence-list"><div><dt>Capture identifier</dt><dd class="mono">${escape(c.id)}</dd></div><div><dt>SHA-256 · record content</dt><dd class="mono">${c.digest}</dd></div><div><dt>Source</dt><dd>${escape(c.source)}</dd></div><div><dt>Captured at</dt><dd>${date(c.captured_at)}</dd></div><div><dt>Contract evaluated at</dt><dd>${date(c.evaluated_at)}</dd></div><div><dt>Visibility</dt><dd>${escape(c.visibility)}${c.visibility === "private" ? " · requires operator authentication" : ""}</dd></div><div><dt>Collection scope</dt><dd>${escape(c.scope)}</dd></div></dl>`;
const chart = (c) => {
  const rows = c.records
    .filter((r) => Number.isFinite(r.open_issues_count))
    .sort((a, b) => b.open_issues_count - a.open_issues_count)
    .slice(0, 8);
  const max = Math.max(1, ...rows.map((r) => r.open_issues_count));
  return `<div class="panel chart-panel"><h3>Open issues by repository <span class="section-count">Source values</span></h3>${rows.map((r) => `<div class="bar-row"><span>${escape(r.full_name)}</span><div class="bar-track"><span style="width:${(r.open_issues_count / max) * 100}%"></span></div><span>${number(r.open_issues_count)}</span></div>`).join("")}<p class="form-hint">GitHub's open_issues_count includes open pull requests. Captured ${date(c.captured_at)}.</p></div>`;
};
function recordTable(c, limit = 500, query = recordView.query) {
  const rows = UI.selectRecords(
    c.records,
    query,
    recordView.sort,
    recordView.filter,
  ).slice(0, limit);
  return `<div class="table-wrap"><table class="source-table"><thead><tr><th>Repository</th><th><button data-action="sort-records" data-sort="stars">Stars ${icon("chevron", 12)}</button></th><th><button data-action="sort-records" data-sort="issues">Open issues ${icon("chevron", 12)}</button></th><th>Updated</th><th><span class="sr-only">Inspect</span></th></tr></thead><tbody>${rows.map(({ record: r, index: i }) => `<tr><td><div class="repo-cell"><span class="repo-emblem">${icon("github", 20)}</span><div><button class="record-name" data-action="record" data-id="${c.id}" data-index="${i}">${escape(r.full_name || "Unnamed record")}</button><span class="sub repo-description">${escape(r.description || r.language || "No description metadata")}</span></div></div></td><td class="numeric">${number(r.stargazers_count)}</td><td class="numeric">${number(r.open_issues_count)}</td><td><time datetime="${escape(r.updated_at)}">${date(r.updated_at).split(",")[0]}</time><span class="sub">${escape(r.language || "Not specified")}</span></td><td><button class="table-action" data-action="record" data-id="${c.id}" data-index="${i}" aria-label="Inspect record ${i + 1}" title="Inspect source record">${icon("arrow", 17)}</button></td></tr>`).join("") || `<tr><td colspan="5"><div class="table-empty">No source records match these filters. ${button("Clear filters", "clear-record-filters", "small")}</div></td></tr>`}</tbody></table></div><div class="data-table-footer"><span>${rows.length} of ${c.row_count} source records</span>${limit < 500 ? link("datasets", "View all records") : `<span class="mono">SHA-256 ${c.digest.slice(0, 12)}…</span>`}</div>`;
}
function recordToolbar(compact = false) {
  return `<div class="record-toolbar"><div class="search-input">${icon("search", 16)}<input id="record-search" aria-label="Search repository records" placeholder="Search repositories…" value="${escape(recordView.query)}"></div><label class="sr-only" for="record-sort">Sort records</label><select id="record-sort" aria-label="Sort records">${[
    ["repository", "Repository A–Z"],
    ["stars", "Most stars"],
    ["issues", "Most open issues"],
    ["updated", "Recently updated"],
  ]
    .map(
      ([value, label]) =>
        `<option value="${value}" ${recordView.sort === value ? "selected" : ""}>${label}</option>`,
    )
    .join("")}</select>${
    compact
      ? ""
      : `<label class="sr-only" for="record-filter">Filter records</label><select id="record-filter" aria-label="Filter records">${[
          ["all", "All records"],
          ["active", "Active repositories"],
          ["licensed", "License metadata present"],
          ["issues", "With open issues"],
        ]
          .map(
            ([value, label]) =>
              `<option value="${value}" ${recordView.filter === value ? "selected" : ""}>${label}</option>`,
          )
          .join("")}</select>`
  }</div>`;
}
function updateRecords() {
  const target = $("#records-table");
  if (target)
    target.innerHTML = recordTable(capture(), page === "overview" ? 4 : 500);
}
function auditChain(c) {
  return `<div class="audit-chain">${[
    [
      "github",
      "Source",
      c.visibility === "public" ? "GitHub REST API" : "Operator upload",
      "datasets",
    ],
    ["contracts", "Immutable capture", "Versioned records", "lineage"],
    [
      "checks",
      "Contract checks",
      `${c.checks.filter((x) => !x.failed).length}/${c.checks.length} passed`,
      "checks",
    ],
    [
      "versions",
      c.status === "published" ? "Published" : "Quarantined",
      "Inspectable results",
      c.status === "published" ? "versions" : "quarantine",
    ],
  ]
    .map(
      ([ic, title, detail, to]) =>
        `<a href="/console/${to}" class="chain-stage"><span class="chain-icon">${icon(ic, 24)}</span><span><strong>${title}</strong><small>${detail}</small></span></a>`,
    )
    .join("")}</div>`;
}
function sourceRail(c) {
  return `<aside class="evidence-rail"><h2>Every result has a source.</h2><dl class="rail-facts"><div><dt>Source</dt><dd>${c.visibility === "public" ? "GitHub REST API" : "Operator upload"}</dd></div><div><dt>Captured</dt><dd>${date(c.captured_at)}</dd></div><div><dt>SHA-256</dt><dd><code>${c.digest.slice(0, 14)}…</code>${button(icon("copy", 15), "copy-digest", "icon-button", `data-id="${c.id}" aria-label="Copy source digest"`)}</dd></div></dl>${button(`Inspect capture ${icon("arrow", 15)}`, "details", "text-button", `data-id="${c.id}"`)}<div class="rail-history"><h3>Evidence trail</h3>${[
    ["Source captured", c.captured_at],
    ["Contract evaluated", c.evaluated_at],
  ]
    .map(
      ([title, time]) =>
        `<div class="rail-event"><span></span><div><strong>${title}</strong><time>${date(time)}</time></div></div>`,
    )
    .join(
      "",
    )}</div><p class="source-note">Captured state, not live GitHub counters.</p></aside>`;
}
async function api(path, method = "GET", body) {
  const headers = {};
  if (token && path !== "/public-investigate")
    headers.Authorization = "Bearer " + token;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const r = await fetch("/api/quality" + path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let result;
  try {
    result = await r.json();
  } catch {
    throw Error("The service returned an unreadable response. Try refreshing.");
  }
  if (!r.ok) {
    const error = new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Request validation failed. Check the form values.",
    );
    error.status = r.status;
    error.retryAfter = r.headers.get("Retry-After");
    throw error;
  }
  return result;
}
function toast(message, error = false) {
  clearTimeout(toastTimer);
  const t = $("#toast");
  t.textContent = message;
  t.className = "toast" + (error ? " error" : "");
  t.hidden = false;
  toastTimer = setTimeout(() => (t.hidden = true), 6500);
}
function needOperator() {
  if (token) return true;
  $("#access-dialog").showModal();
  return false;
}
async function refresh() {
  try {
    [workspace, provider] = await Promise.all([
      api("/workspace"),
      api("/provider"),
    ]);
    if (!selectedId) selectedId = workspace.captures[0]?.id || "";
    render();
  } catch (e) {
    $("#main").innerHTML =
      heading("Evidence is unavailable.", escape(e.message)) +
      `<div class="panel">${empty("The workspace could not be read.", "Use Refresh workspace to try again. Your data has not been replaced with sample records.", "connections")}</div>`;
    toast(e.message, true);
  }
}
function navigate(next) {
  page = next;
  history.pushState({}, "", "/console/" + page);
  render();
  window.scrollTo(0, 0);
  setMenu(false);
  $("#main").focus({ preventScroll: true });
}
function overview() {
  const c = capture();
  if (!c)
    return (
      heading("Make quality visible.", "Connect a source to begin.") +
      empty(
        "No captured data.",
        "An operator can connect the source or import actual records.",
      )
    );
  const passed = c.checks.filter((x) => !x.failed).length,
    bad = workspace.captures.filter((c) => c.status === "quarantined").length;
  return (
    heading(
      '<span class="archive-underline">Make quality visible.</span>',
      "Inspect real repository evidence, compare contracts, and trace each quality decision.",
      `<a class="button primary" href="/console/checks">Explore quality checks ${icon("arrow", 16)}</a><a class="button" href="/console/datasets">Browse datasets</a>`,
      "Public data engineering",
    ) +
    `<section class="audit-ledger" aria-label="Recorded quality evaluation"><div class="ledger-figures"><div class="ledger-lead"><strong>${passed}<span>/${c.checks.length}</span></strong><span>Checks passed</span></div>${[
      [c.row_count, "Records"],
      [workspace.captures.length, "Captures"],
      [bad, "Quarantined"],
    ]
      .map(
        ([value, label]) =>
          `<div class="ledger-stat"><strong>${number(value)}</strong><span>${label}</span></div>`,
      )
      .join(
        "",
      )}</div>${auditChain(c)}</section><div class="archive-utility">${button(`${icon("download", 15)} Export evidence`, "download", "text-button", `data-id="${c.id}"`)}${link("agent", "Investigate data")}</div><div class="register-layout"><section class="source-register"><div class="register-heading"><h2>Source register</h2>${recordToolbar(true)}</div><div id="records-table">${recordTable(c, 4)}</div></section>${sourceRail(c)}</div>`
  );
}
function datasets() {
  const c = capture();
  return (
    heading(
      "Source register.",
      "Read the exact records. Inspect the evidence behind every value.",
      button(
        `${icon("download", 16)} Export JSON`,
        "download",
        "",
        `data-id="${c.id}"`,
      ),
    ) +
    selector() +
    `<section class="source-register"><div class="dataset-heading"><div><h2>${escape(c.name)}</h2><p>${escape(c.scope)}</p></div>${status(c)}</div><div class="dataset-info"><div><span>Source</span><strong>${c.visibility === "public" ? "GitHub REST API" : "Private operator upload"}</strong></div><div><span>Captured</span><strong>${date(c.captured_at)}</strong></div><div><span>Content fingerprint</span><strong class="mono">${c.digest.slice(0, 24)}…</strong></div></div><div class="register-heading">${recordToolbar()}</div><div id="records-table">${recordTable(c)}</div></section>${section("A view of the source", link("checks", "Review quality checks"))}<div class="split">${chart(c)}<aside class="editorial-note"><span class="note-line"></span><h3>Context belongs<br>with the data.</h3><p>These eight repositories are a deliberate infrastructure sample. Their counters describe the capture time, not a complete ecosystem or a live GitHub feed.</p>${button(`Inspect provenance ${icon("arrow", 15)}`, "details", "text-button", `data-id="${c.id}"`)}<div class="privacy-stamp">${icon("lock", 14)} Private operator uploads remain private.</div></aside></div>`
  );
}
function contracts() {
  const r = workspace.contract;
  return (
    heading(
      "Define what good looks like.",
      "One explicit contract. Repeatable checks. A permanent record of what was evaluated.",
      link("impact", "Explore contract impact") +
        link("checks", "See quality results"),
    ) +
    `<div class="contract-layout"><div class="panel"><div class="contract-intro"><h2>Repository metadata contract</h2><p>Updates apply to new evaluations. Existing capture results retain their original contract.</p></div><form id="contract-form" class="form-body"><div class="form-two"><div class="form-field"><label for="min-rows">Minimum records</label><input type="number" id="min-rows" name="min_rows" value="${r.min_rows}" min="1" max="500" required><p>Quarantine captures below this volume.</p></div><div class="form-field"><label for="max-age">Maximum capture age <small>hours</small></label><input type="number" id="max-age" name="max_age_hours" value="${r.max_age_hours}" min="1" max="8760" required><p>Freshness uses the original source capture time.</p></div></div><div class="checkbox-row"><input type="checkbox" id="require-license" name="require_license" ${r.require_license ? "checked" : ""}><div><label for="require-license">Require license metadata</label><p>Flag records without a source license object. Presence is metadata evidence, not a legal determination.</p></div></div><div class="checkbox-row"><input type="checkbox" id="reject-archived" name="reject_archived" ${r.reject_archived ? "checked" : ""}><div><label for="reject-archived">Allow active repositories only</label><p>Require archived to be explicitly false for every record.</p></div></div><div class="form-actions"><button class="button primary" type="submit">Save contract ${icon("check", 14)}</button><p>${token ? "Connected operator" : "Operator access required to save"}</p></div><p class="form-error" id="contract-error" role="alert"></p></form></div><div><div class="code-panel"><h3>Current contract · JSON</h3><pre>${escape(JSON.stringify(r, null, 2))}</pre><div class="code-note">Contract settings persist in ${escape(workspace.storage)}. Saving a new contract never rewrites previous evidence.</div></div>${section("Always-on checks")}<ol class="rule-list">${[
      ["Required fields", "schema"],
      ["Unique repository IDs", "uniqueness"],
      ["Nonnegative integer counters", "counters"],
      ["Timezone-aware timestamps", "timestamps"],
    ]
      .map(
        ([title, key], i) =>
          `<li><span class="rule-num">0${i + 1}</span>${title}<code>${key}</code></li>`,
      )
      .join("")}</ol></div></div>`
  );
}
function checks() {
  const c = capture();
  return (
    heading(
      "A clear answer to every check.",
      "Inspect the rule, the result, and the affected input rows.",
      button(
        "Re-evaluate capture " + icon("recovery", 14),
        "recheck",
        "primary",
        `data-id="${c.id}"`,
      ),
    ) +
    selector() +
    `<div class="check-summary"><div><strong>${c.checks.filter((check) => !check.failed).length}<span>/${c.checks.length}</span></strong><p>Recorded checks passed</p></div><div class="check-matrix">${c.checks.map((check) => `<a href="#check-${check.key}" class="${check.failed ? "failed" : ""}">${icon(check.failed ? "close" : "check", 15)}<span>${escape(check.title)}</span></a>`).join("")}</div></div>${qualityBenchmark()}<div class="toolbar"><div class="right"><span>Evaluated ${date(c.evaluated_at)}</span></div><select id="check-filter" aria-label="Filter quality checks"><option value="all">All checks</option><option value="failed">Failed only</option><option value="passed">Passed only</option></select></div><div id="check-list" class="check-list">${checkRows(c)}</div><div class="privacy-stamp">${icon("info", 13)} Historical results are frozen at evaluation time. Re-evaluate to check current freshness.</div>`
  );
}
function qualityBenchmark() {
  return `<section class="panel panel-pad quality-benchmark" id="quality-benchmark" aria-labelledby="quality-benchmark-title">
    <span class="mini-label">Reproducible source benchmark</span>
    <h2 id="quality-benchmark-title">The contract at 500 repositories.</h2>
    <p>Replay DataGuard’s checks over 500 distinct public Apache repositories from the GitHub REST API. Change the contract and see which actual rows fail.</p>
    <form id="quality-benchmark-form" class="benchmark-controls">
      <label>Replay policy<select name="policy"><option value="baseline">Baseline · minimum 500 records</option><option value="strict">Strict · license and active status</option></select></label>
      <button class="button primary" type="submit">Replay source checks ${icon("arrow", 16)}</button>
    </form>
    <div class="benchmark-links"><a class="text-link" href="/api/quality/benchmark/artifacts/source">Download pinned source</a><a class="text-link" href="/api/quality/benchmark/artifacts/report">Download benchmark measurements</a></div>
    <div id="quality-benchmark-result" aria-live="polite"></div>
  </section>`;
}
function renderQualityBenchmark(replay, report) {
  const checkItems = replay.checks
    .map(
      (check) =>
        `<li>${pill(check.failed ? "Failed" : "Passed", check.failed ? "bad" : "")} <div><strong>${escape(check.title)}</strong><p>${number(check.failed)} of ${number(check.tested)} failed${check.examples.length ? ` · ${check.examples.map(escape).join(", ")}` : ""}</p></div></li>`,
    )
    .join("");
  const operations = [
    ["upload_and_publish", "Upload and publish"],
    ["recheck_and_quarantine", "Recheck and quarantine"],
    ["blocked_recovery", "Blocked recovery"],
    ["accepted_recovery", "Accepted recovery"],
  ];
  const rows = report.runs
    .flatMap((run) =>
      operations.map(([key, label]) => {
        const values = run.operations[key];
        return `<tr><td>${escape(run.database)} ${escape(run.database_version)}</td><td>${label}</td><td>${number(run.samples_per_operation)}</td><td>${values.median_ms.toFixed(2)} ms</td><td>${values.p95_ms.toFixed(2)} ms</td></tr>`;
      }),
    )
    .join("");
  const policy = replay.policy === "strict" ? "Strict" : "Baseline";
  return `<div class="benchmark-replay"><h3>${policy} replay · ${escape(replay.outcome)}</h3><p>${number(replay.rows)} repositories · source observed ${date(replay.captured_at)}. The replay uses that observation time for freshness and makes no workspace writes.</p><ul>${checkItems}</ul><p class="benchmark-digest mono">SHA-256 ${escape(replay.sha256)}</p></div><div class="benchmark-replay"><h3>Measured in disposable databases</h3><p>Sequential in-process API requests against local SQL. Percentiles cover request through response. The timing excludes external HTTP and source retrieval.</p><div class="table-wrap"><table><thead><tr><th>Database</th><th>Operation</th><th>Samples</th><th>Median</th><th>p95</th></tr></thead><tbody>${rows}</tbody></table></div></div>`;
}
function checkRows(c, filter = "all", prefix = "") {
  const rows = c.checks.filter((x) => filter === "all" || x.status === filter);
  return (
    rows
      .map(
        (x) =>
          `<article class="check-row" id="${prefix}check-${x.key}"><span class="check-glyph ${x.failed ? "bad" : ""}">${icon(x.failed ? "close" : "check", 17)}</span><div><h3>${escape(x.title)}</h3><p>${escape(x.detail)}</p><small>${x.tested} ${["volume", "freshness"].includes(x.key) ? "capture" : "record"} checks · ${x.failed} failed${x.indices.length ? " · affected zero-based indices: " + x.indices.join(", ") : ""}</small></div>${pill(x.failed ? "Failed" : "Passed", x.failed ? "bad" : "")}</article>`,
      )
      .join("") ||
    `<div class="panel">${empty("No " + filter + " checks.", "Choose All checks to inspect every evaluation.", "checks")}</div>`
  );
}
function captureEvents() {
  const visible = workspace.captures.filter(
    (c) =>
      (historyView.status === "all" || c.status === historyView.status) &&
      [c.name, c.id, c.digest].some((value) =>
        String(value).toLowerCase().includes(historyView.query.toLowerCase()),
      ),
  );
  return (
    visible
      .map(
        (c) =>
          `<article class="capture-event"><h3><span>${escape(c.name)}</span>${status(c)}</h3><p>Captured ${date(c.captured_at)} · evaluated ${date(c.evaluated_at)}</p><div class="capture-meta"><span>${c.row_count} source records</span><span>${c.checks.filter((x) => !x.failed).length}/${c.checks.length} checks passed</span><span>${pill(c.visibility, "neutral")}</span></div><p class="mono">${escape(c.id)}</p><div class="capture-actions">${button("Inspect evidence", "details", "small", `data-id="${c.id}"`)}${button("Re-evaluate", "recheck", "small", `data-id="${c.id}"`)}${button(icon("download", 13), "download", "small", `data-id="${c.id}" aria-label="Download capture ${c.id}"`)}</div></article>`,
      )
      .join("") ||
    `<div class="panel">${empty("No matching capture versions.", "Adjust the search or status filter to see the stored history.", "batches")}</div>`
  );
}
function batches() {
  return (
    heading(
      "The history stays intact.",
      "Import actual repository metadata or refresh the fixed public GitHub source.",
      button("Sync GitHub " + icon("recovery", 14), "sync", "primary"),
    ) +
    `<div class="toolbar"><div class="search-input">${icon("search", 16)}<input id="history-search" aria-label="Search capture history" placeholder="Search captures or fingerprints…" value="${escape(historyView.query)}"></div><select id="history-filter" aria-label="Filter capture status"><option value="all">All capture states</option><option value="published" ${historyView.status === "published" ? "selected" : ""}>Passed contract</option><option value="quarantined" ${historyView.status === "quarantined" ? "selected" : ""}>Quarantined</option></select></div><div class="split"><div><div class="capture-timeline" id="history-timeline">${captureEvents()}</div></div><div><div class="panel panel-pad"><h2 class="upload-title">Bring your own evidence.</h2><p class="explain">Import an actual JSON array of repository metadata. The server evaluates it immediately; uploads stay private.</p><form id="upload-form"><div class="form-field"><label for="upload-name">Capture name</label><input id="upload-name" required maxlength="100" placeholder="Name this source capture"></div><div class="drop-area"><label for="upload-file">Choose a JSON file</label><input id="upload-file" type="file" accept=".json,application/json"><p>Up to 500 records. Required fields: id, full_name, updated_at, stargazers_count, open_issues_count.</p></div><div class="form-field"><label for="upload-json">Or paste your JSON records</label><textarea id="upload-json" placeholder="Paste your actual JSON array here" required></textarea></div><button class="button primary" type="submit">Import & evaluate ${icon("arrow", 14)}</button><p id="upload-error" class="form-error" role="alert"></p></form><div class="privacy-stamp">${icon("lock", 12)} Private upload · operator authentication required</div></div><div class="forest-note"><h3>No silent overwrites.</h3><p>Each import gets a new capture ID. The original records, source time, content hash, and contract stay together.</p>${link("versions", "Compare versions")}</div></div></div>`
  );
}
function quarantine() {
  const bad = workspace.captures.filter((c) => c.status === "quarantined");
  return (
    heading(
      "Keep exceptions in view.",
      "Failed captures remain available for inspection without replacing valid evidence.",
      link("contracts", "Review the contract"),
    ) +
    `<div class="incident-summary"><strong>${bad.length}</strong><div><h2>${bad.length ? "Captures need attention" : "No quarantined captures"}</h2><p>${bad.length ? "Inspect the failing check before changing the input or contract." : "Every captured version currently visible to you passed its stored contract."}</p></div>${icon("quarantine", 28)}</div>` +
    (bad.length
      ? `<div class="check-list">${bad
          .map(
            (c) =>
              `<article class="panel panel-pad"><div class="section-title" style="margin:0 0 14px"><h2>${escape(c.name)}</h2>${status(c)}</div><p class="explain">${date(c.evaluated_at)} · ${c.row_count} records · ${escape(c.id)}</p>${c.checks
                .filter((x) => x.failed)
                .map(
                  (x) =>
                    `<div class="info-band warning">${icon("incidents", 14)}<span><strong>${escape(x.title)}</strong><br>${escape(x.detail)}<br>${x.failed} failed checks${x.indices.length ? " · indices " + x.indices.join(", ") : ""}</span></div>`,
                )
                .join(
                  "",
                )}<div class="heading-actions">${button("Inspect input", "details", "small", `data-id="${c.id}"`)}${button("Re-evaluate", "recheck", "small", `data-id="${c.id}"`)}<a class="button small" href="/console/agent">Investigate with AI ${icon("agent", 14)}</a></div></article>`,
          )
          .join("")}</div>`
      : `<div class="panel">${empty("A clear quarantine.", "A failed schema, duplicate ID, invalid counter, timestamp, volume, or freshness check will create an entry here.", "quarantine")}</div>`) +
    `<div class="info-band" style="margin-top:24px">${icon("lock", 15)}<span>Private uploads are visible only to a connected operator. No captured records are fabricated to populate this view.</span></div>`
  );
}
function versions() {
  const cs = workspace.captures;
  return (
    heading(
      "See exactly what changed.",
      "Compare record identities and content across immutable captures.",
      link("batches", "View capture history"),
    ) +
    `<div class="comparison"><div class="version-box"><span class="mini-label">From capture</span><select id="compare-from" aria-label="From capture">${options(cs[1]?.id || cs[0]?.id)}</select><p>Baseline record content</p></div>${icon("arrow", 24)}<div class="version-box"><span class="mini-label">To capture</span><select id="compare-to" aria-label="To capture">${options(cs[0]?.id)}</select><p>Comparison record content</p></div></div>${cs.length === 1 ? `<div class="info-band">${icon("info", 15)}<span>Only one capture is available. This compares the capture with itself; sync GitHub or import another real version to see changes.</span></div>` : ""}<div id="comparison-result"></div>`
  );
}
function compare() {
  const a = workspace.captures.find((c) => c.id === $("#compare-from").value),
    b = workspace.captures.find((c) => c.id === $("#compare-to").value);
  const before = new Map(a.records.map((r) => [String(r.id), r])),
    after = new Map(b.records.map((r) => [String(r.id), r]));
  let counts = { Added: 0, Removed: 0, Changed: 0, Unchanged: 0 };
  const rows = [];
  for (const id of new Set([...before.keys(), ...after.keys()])) {
    const left = before.get(id),
      right = after.get(id);
    const same = left && right && UI.canonical(left) === UI.canonical(right);
    const type = !left
      ? "Added"
      : !right
        ? "Removed"
        : same
          ? "Unchanged"
          : "Changed";
    counts[type]++;
    const changed =
      left && right
        ? Array.from(
            new Set([...Object.keys(left), ...Object.keys(right)]),
          ).filter((k) => UI.canonical(left[k]) !== UI.canonical(right[k]))
        : [];
    rows.push(
      `<tr><td><strong>${escape((right || left).full_name || id)}</strong><span class="sub">ID ${escape(id)}</span></td><td>${pill(type, type === "Removed" ? "bad" : type === "Unchanged" ? "neutral" : "")}</td><td>${escape(changed.join(", ") || "—")}</td></tr>`,
    );
  }
  $("#comparison-result").innerHTML =
    `<div class="diff-summary">${Object.entries(counts)
      .map(
        ([label, count]) =>
          `<div><strong>${count}</strong><span>${label} records</span></div>`,
      )
      .join(
        "",
      )}</div><div class="panel"><div class="table-wrap"><table><thead><tr><th>Record identity</th><th>Difference</th><th>Changed fields</th></tr></thead><tbody>${rows.join("")}</tbody></table></div></div><div class="privacy-stamp">${icon("info", 13)} Compared locally from exact API records. Matching identities use the repository id field.</div>`;
}
function lineage() {
  const c = capture();
  return (
    heading(
      "Follow the evidence.",
      "A source, its bytes, the rules applied, and the resulting decision.",
      button(
        "Download provenance " + icon("download", 14),
        "download",
        "",
        `data-id="${c.id}"`,
      ),
    ) +
    selector() +
    `<div class="lineage-flow">${[
      [
        "github",
        "Source capture",
        c.visibility === "public"
          ? "GitHub public repository API"
          : "Private operator input",
      ],
      [
        "datasets",
        "Immutable content",
        c.row_count + " records · SHA-256 fingerprint",
      ],
      [
        "contracts",
        "Contract evaluation",
        c.checks.length + " reproducible quality checks",
      ],
      [
        "checks",
        c.status === "published" ? "Passed contract" : "Quarantine",
        date(c.evaluated_at),
      ],
    ]
      .map(
        ([ic, title, desc], i) =>
          `<div class="lineage-node ${i === 3 ? "active" : ""}"><span>${icon(ic, 22)}</span><h3>${title}</h3><p>${desc}</p></div>`,
      )
      .join(
        "",
      )}</div><div class="panel">${evidence(c)}</div>${c.parent_id ? `<div class="info-band" style="margin-top:20px">${icon("lineage", 14)}<span>This capture re-evaluates immutable source content from parent <span class="mono">${escape(c.parent_id)}</span>. Capture time and record digest are preserved.</span></div>` : ""}${section("The contract behind this result")}<div class="code-panel"><pre>${escape(JSON.stringify(c.contract, null, 2))}</pre></div>`
  );
}
function incidents() {
  const bad = workspace.captures.filter((c) => c.status === "quarantined"),
    notes = workspace.actions.filter((a) => a.kind === "note");
  return (
    heading(
      "Give issues a paper trail.",
      "Review contract failures and record the actual investigation notes.",
      link("quarantine", "Open quarantine"),
    ) +
    `<div class="incident-summary"><strong>${bad.length}</strong><div><h2>Captures with contract failures</h2><p>${bad.length ? "Each failed capture is evidence for investigation." : "No failures in your visible captures. Notes remain available for source review."}</p></div></div><div class="split"><div>${section("Investigation journal")}<div class="panel">${notes.length ? notes.map((n) => `<div class="activity-row"><span class="activity-icon">${icon("incidents", 13)}</span><div class="activity-copy"><strong>${escape(n.note)}</strong><p class="mono">${escape(n.capture_id)}</p><small>${date(n.created_at)}</small></div></div>`).join("") : empty("No investigation notes yet.", token ? "Add a real finding to keep the investigation traceable." : "Connect your operator to read and add private investigation notes.", "incidents")}</div>${section("Failures by check")}<div class="panel">${bad.length ? `<div class="table-wrap"><table><thead><tr><th>Capture</th><th>Failed check</th><th>Count</th></tr></thead><tbody>${bad.flatMap((c) => c.checks.filter((x) => x.failed).map((x) => `<tr><td>${escape(c.name)}</td><td>${escape(x.title)}</td><td>${x.failed}</td></tr>`)).join("")}</tbody></table></div>` : empty("Nothing to triage.", "Contract exceptions appear automatically when actual data fails a check.", "checks")}</div></div><div><div class="panel panel-pad"><h2 class="note-title">Add an investigation note.</h2><p class="explain">Notes are stored with an exact capture reference and are visible only to authenticated operators.</p><form id="note-form"><div class="form-field"><label for="note-capture">Capture reference</label><select id="note-capture" required style="width:100%">${options(capture()?.id)}</select></div><div class="form-field"><label for="incident-note">Finding or follow-up</label><textarea id="incident-note" required minlength="1" maxlength="2000" placeholder="Describe what you observed in the source evidence…"></textarea></div><button type="submit" class="button primary">Save private note ${icon("plus", 14)}</button><p class="form-error" id="note-error" role="alert"></p></form></div></div></div>`
  );
}
function recovery() {
  const valid = workspace.captures.filter((c) => c.status === "published"),
    restored = workspace.restored;
  return (
    heading(
      "Recover with confidence.",
      "Select a valid capture as the recovery reference after checking the current contract.",
      link("versions", "Compare first"),
    ) +
    `<div class="recovery-steps">${[
      [
        "01",
        "Inspect the source",
        "Read the records and confirm the capture provenance.",
      ],
      [
        "02",
        "Validate current rules",
        "The server runs every current contract rule again.",
      ],
      [
        "03",
        "Set the recovery reference",
        "Only a currently passing capture can be selected.",
      ],
    ]
      .map(
        ([num, title, p]) =>
          `<div><span>${num}</span><h3>${title}</h3><p>${p}</p></div>`,
      )
      .join(
        "",
      )}</div><div class="split"><div class="panel"><div class="contract-intro"><h2>Eligible capture references</h2><p>Previously passing captures. Current freshness and rule changes may still block selection.</p></div>${valid.length ? `<div class="table-wrap"><table><thead><tr><th>Capture</th><th>Captured</th><th>Action</th></tr></thead><tbody>${valid.map((c) => `<tr><td><strong>${escape(c.name)}</strong><span class="sub mono">${c.id.slice(0, 22)}</span></td><td>${age(c.captured_at)}</td><td>${button("Validate & select", "restore", "small", `data-id="${c.id}"`)}</td></tr>`).join("")}</tbody></table></div>` : empty("No eligible captures.", "Correct the source or contract, then create a passing evaluation.", "recovery")}</div><div><div class="code-panel"><h3>Active recovery reference</h3>${restored ? `<pre>${escape(JSON.stringify(restored, null, 2))}</pre>` : `<p class="explain" style="color:#b3c7a1">No reference selected. Choose a passing capture after reviewing its evidence.</p>`}<div class="code-note">This selects a repository quality reference. It does not replay financial transactions or claim to restore a separate production system.</div></div>${section("Recovery audit")}<div class="panel">${
      workspace.actions
        .filter((a) => a.kind === "restore")
        .map(
          (a) =>
            `<div class="activity-row"><span class="activity-icon">${icon("recovery", 13)}</span><div class="activity-copy"><strong>Recovery reference selected</strong><p>${escape(a.capture_id)}</p><small>${date(a.created_at)}</small></div></div>`,
        )
        .join("") ||
      empty(
        "No recovery actions.",
        token
          ? "Successful selections are recorded here."
          : "Connect operator access to inspect the recovery audit.",
        "recovery",
      )
    }</div></div></div>`
  );
}
function agent() {
  const c = workspace.captures.find((item) => item.visibility === "public"),
    has = Boolean(lastAgent);
  return (
    heading(
      "Ask the evidence.",
      "Real questions. Public GitHub records. A visible trail of reasoning.",
    ) +
    `<nav class="investigation-steps" aria-label="Investigation stages"><a href="#question-panel" class="${has ? "complete" : "active"}"><span>01</span>Question</a><a href="#findings-panel" ${has ? 'class="complete"' : 'aria-disabled="true"'}><span>02</span>Findings</a><a href="#evidence-panel" ${has ? 'class="active"' : 'aria-disabled="true"'}><span>03</span>Evidence</a></nav><div class="agent-layout"><section class="question-sheet" id="question-panel"><div class="question-title">${icon("agent", 32)}<h2>What would you like to investigate?</h2></div><form id="agent-form"><label class="sr-only" for="agent-question">Your investigation</label><textarea id="agent-question" required minlength="5" maxlength="600" placeholder="Ask about repository quality, freshness, or the captured source records…">${escape(pendingQuestion)}</textarea><div class="suggestions">${[
      [
        "recovery",
        "Check source freshness",
        "Check the latest public capture freshness. Cite its capture and evaluation times, distinguish historical checks from current freshness.",
      ],
      [
        "agent",
        "Find the most-starred repository",
        "Inspect the latest public source records. Which repository has the most stars? Give its exact captured count and cite the capture ID.",
      ],
      [
        "contracts",
        "Explain the quality checks",
        "Explain the actual quality checks and their recorded outcomes for the latest public capture. Cite the evidence.",
      ],
      [
        "quarantine",
        "Review recovery evidence",
        "What source evidence and quality checks should an operator verify before selecting a recovery reference? Use the actual public capture.",
      ],
    ]
      .map(
        ([ic, label, q]) =>
          `<button type="button" data-action="suggest" data-question="${escape(q)}">${icon(ic, 20)}<span>${label}</span></button>`,
      )
      .join(
        "",
      )}</div><div class="form-actions"><button class="button primary" type="submit">Investigate public data ${icon("arrow", 20)}</button><span class="no-account">No account or token required</span></div><div class="public-limits"><span>3 per visitor / 10 min</span><span>2 shared / min</span><span>30 shared / day</span></div><p class="form-hint">Public GitHub evidence only. Private uploads and notes are excluded.</p><p id="public-quota-state" class="form-hint" role="status"></p><p class="form-error" id="agent-error" role="alert"></p><p class="data-notice">${icon("info", 16)}<span>Google may use unpaid API questions and public evidence to improve its models. Enter public information only. Reserved attempts count even if the provider is unavailable.</span></p></form><div id="agent-result">${has ? agentResult(lastAgent) : ""}</div></section><aside class="agent-rail"><section class="evidence-rail"><h2>Your source material</h2>${c ? `<dl class="rail-facts"><div><dt>Source</dt><dd>GitHub REST API</dd></div><div><dt>Repository records</dt><dd>${c.row_count} repository records</dd></div><div><dt>Quality checks</dt><dd>${c.checks.length} quality checks</dd></div><div><dt>Captured</dt><dd>${date(c.captured_at)}</dd></div><div><dt>Source fingerprint</dt><dd><code>${c.digest.slice(0, 14)}…</code></dd></div></dl>${button(`Inspect source records ${icon("arrow", 15)}`, "go-capture", "text-button", `data-page="datasets" data-id="${c.id}"`)}` : empty("No public source.", "The source has not been captured.")}</section><section class="grounding-panel"><h2>Grounded, step by step.</h2><ol>${[
      [
        "Read the captures",
        "Analyze the captured repository records and quality checks.",
      ],
      [
        "Inspect exact evidence",
        "Trace each finding to source values you can verify.",
      ],
      [
        "Return a cited answer",
        "Read the findings alongside the actual executed tools.",
      ],
    ]
      .map(
        ([title, copy], index) =>
          `<li><span>${index + 1}</span><div><h3>${title}</h3><p>${copy}</p></div></li>`,
      )
      .join(
        "",
      )}</ol></section><div class="provider-strip">${icon("agent", 18)}<span>${escape(provider.provider)} · Public data only</span>${icon("info", 16)}</div></aside></div>`
  );
}
function agentResult(r) {
  const ids = [
    ...new Set(
      r.trace
        .flatMap((t) =>
          Array.isArray(t.result) ? t.result.map((c) => c.id) : [t.result?.id],
        )
        .filter(Boolean),
    ),
  ];
  return `<section class="agent-response" id="findings-panel" tabindex="-1"><div class="finding-heading"><div><span class="mini-label">MODEL FINDINGS</span><h2>A conclusion you can inspect.</h2></div>${icon("checks", 26)}</div><div class="answer-prose" id="answer-content"></div><p class="answer-provenance">${escape(r.provider || "AI provider")} · ${escape(r.model)} · ${date(r.created_at)} · Public GitHub evidence</p>${ids.length ? `<div class="source-citations">${ids.map((id, i) => button(`Source ${String(i + 1).padStart(2, "0")} ${icon("external", 13)}`, "details", "citation-button", `data-id="${escape(id)}"`)).join("")}</div>` : ""}<div id="evidence-panel" class="agent-evidence"><div class="section-title"><h3>Executed evidence tools</h3><span>${r.trace.length} calls · read only</span></div>${r.trace.map((t, i) => `<details class="tool-trace"><summary><span class="tool-number">${String(i + 1).padStart(2, "0")}</span><strong>${escape(t.tool)}</strong><span class="tool-args">${escape(t.arguments?.capture_id || "Public capture register")}</span>${icon("chevron", 15)}</summary><div class="tool-result"><p>Actual tool result${r.evidence_notice ? " · bounded source summary" : ""}</p><pre>${escape(JSON.stringify(t.result, null, 2))}</pre></div></details>`).join("")}</div></section>`;
}
function hydrateFindings() {
  const target = $("#answer-content");
  if (target && lastAgent) {
    const ids = workspace.captures
      .filter((c) => c.visibility === "public")
      .map((c) => c.id);
    UI.renderMarkdown(target, lastAgent.answer, ids);
  }
}
function connections() {
  const c = workspace.captures.find((c) => c.visibility === "public");
  return (
    heading(
      "Connect the things that matter.",
      "Source collection, durable storage, and evidence-led investigation in one workspace.",
    ) +
    `<div class="connection-grid"><article class="connection-card"><div class="connection-card-head"><span class="connection-symbol">${icon("github", 26)}</span>${pill("Source captured")}</div><h2>GitHub</h2><p>Public repository metadata for eight fixed dependencies in the Python data infrastructure ecosystem.</p><dl><div><dt>Access</dt><dd>Public REST API · no credentials</dd></div><div><dt>Last captured</dt><dd>${c ? date(c.captured_at) : "No capture"}</dd></div><div><dt>Collection</dt><dd>8 allowlisted repositories</dd></div></dl>${button("Sync a new capture " + icon("recovery", 14), "sync", "primary")} <a class="button" href="https://docs.github.com/en/rest/repos/repos#get-a-repository" target="_blank" rel="noopener">Source docs ${icon("external", 13)}</a></article><article class="connection-card"><div class="connection-card-head"><span class="connection-symbol">${icon("datasets", 26)}</span>${pill("Connected")}</div><h2>${escape(workspace.storage)}</h2><p>Actual persisted captures, contract settings, private investigation notes, and recovery references.</p><dl><div><dt>Storage engine</dt><dd>${escape(workspace.storage)}</dd></div><div><dt>Capture versions</dt><dd>${workspace.captures.length} visible</dd></div><div><dt>Write access</dt><dd>Authenticated operators</dd></div></dl><a class="button" href="/console/batches">Explore capture history ${icon("arrow", 13)}</a></article><article class="connection-card"><div class="connection-card-head"><span class="connection-symbol">${icon("agent", 26)}</span>${pill(provider.configured ? "Configured" : "Not configured", provider.configured ? "" : "warn")}</div><h2>${escape(provider.provider)}</h2><p>${escape(provider.permissions || "Read-only evidence investigations.")}</p><dl><div><dt>Configured model</dt><dd>${escape(provider.model)}</dd></div><div><dt>Evidence budget</dt><dd>4 turns · 6 tool calls</dd></div><div><dt>Data scope</dt><dd>${provider.public_data_only ? "Public GitHub only" : "Authenticated captures"}</dd></div></dl><a class="button" href="/console/agent">Open investigator ${icon("arrow", 13)}</a></article><article class="connection-card"><div class="connection-card-head"><span class="connection-symbol">${icon("lock", 26)}</span>${pill(token ? "Operator connected" : "Public observer", "neutral")}</div><h2>Operator access</h2><p>Use the existing DataGuard bearer credential to import private records and perform audited changes.</p><dl><div><dt>Token storage</dt><dd>Tab memory only</dd></div><div><dt>Upload visibility</dt><dd>Always private</dd></div><div><dt>Mutation protection</dt><dd>Bearer authorization before body parsing</dd></div></dl>${button(token ? "Disconnect operator" : "Connect operator", "access")}</article></div>`
  );
}
function settings() {
  return (
    heading(
      "A workspace you can account for.",
      "Clear access, explicit source scope, and no hidden background activity.",
    ) +
    `<div class="settings-layout"><div class="settings-nav"><span>Workspace & access</span><a href="/console/contracts">Data contract</a><a href="/console/connections">Connections</a><a href="/docs">API documentation ${icon("external", 13)}</a></div><div class="panel settings-section"><h2>Workspace details</h2>${[
      [
        "Name",
        "Python ecosystem",
        "Public repository quality evidence, plus private operator imports.",
      ],
      [
        "Source scope",
        "8 fixed repositories",
        "Not a representative sample of every repository on GitHub.",
      ],
      [
        "Data freshness",
        "Capture-based",
        "Displayed metrics reflect the shown capture time. Sync requires an explicit operator action.",
      ],
      [
        "Persistence",
        workspace.storage,
        "Records and evaluations persist in the configured database.",
      ],
      [
        "Operator session",
        token ? "Connected" : "Public observer",
        "The credential stays in memory in this tab. Reloading clears it.",
      ],
      [
        "AI provider",
        provider.configured ? "Configured" : "Not configured",
        provider.public_data_only
          ? "Gemini free tier; billing disabled at setup. Questions and public evidence may be used by Google to improve models. Private uploads and notes are excluded."
          : "The investigator requires a provider credential and successful evidence tools.",
      ],
      [
        "Synthetic settlement demo",
        "Separate authenticated API",
        "This workspace never treats the legacy test settlement fixtures as public real-world transactions.",
      ],
    ]
      .map(
        ([label, value, desc]) =>
          `<div class="settings-row"><div><strong>${label}</strong><p>${desc}</p></div><span>${escape(value)}</span></div>`,
      )
      .join(
        "",
      )}<div class="form-actions">${button(token ? "Disconnect operator" : "Connect operator", "access", "primary")}<a class="button" href="/docs" target="_blank" rel="noopener">API reference ${icon("external", 13)}</a></div><p class="readonly-label">${escape(workspace.source_policy)}</p></div></div>`
  );
}
const renderers = {
  impact: () => DataGuardImpact.render(workspace, selectedId),
  overview,
  datasets,
  contracts,
  checks,
  batches,
  quarantine,
  versions,
  lineage,
  incidents,
  recovery,
  agent,
  connections,
  settings,
};
function setMenu(open, restoreFocus = false) {
  $(".sidebar").classList.toggle("open", open);
  $("#mobile-menu").setAttribute("aria-expanded", String(open));
  $("#nav-backdrop").hidden = !open;
  $(".workspace").inert = open;
  document.body.classList.toggle("nav-open", open);
  if (open) $("#navigation a")?.focus();
  else if (restoreFocus) $("#mobile-menu").focus();
}
function showRecord(c, index) {
  const row = c.records[index];
  if (!row) {
    toast("This record is unavailable.", true);
    return;
  }
  const source = UI.safeHref(row.html_url);
  const known = c.visibility === "public";
  $("#detail-content").innerHTML =
    `<div class="drawer-kicker">${icon("github", 20)} Exact source record <span>${index + 1} / ${c.row_count}</span></div><h2 id="detail-title">${escape(row.full_name || "Source record")}</h2><p class="drawer-description">${escape(row.description || "No description was provided by the source.")}</p><div class="record-stat-grid">${[
      ["Stars", row.stargazers_count],
      ["Open issues", row.open_issues_count],
      ["Forks", row.forks_count],
    ]
      .map(
        ([label, value]) =>
          `<div><span>${label}</span><strong>${number(value)}</strong></div>`,
      )
      .join(
        "",
      )}</div><dl class="evidence-list"><div><dt>Repository ID</dt><dd class="mono">${escape(row.id)}</dd></div><div><dt>Source language</dt><dd>${escape(row.language || "Not specified")}</dd></div><div><dt>License metadata</dt><dd>${escape(row.license?.spdx_id || row.license?.name || "Not present")}</dd></div><div><dt>Default branch</dt><dd>${escape(row.default_branch || "Not specified")}</dd></div><div><dt>Source updated</dt><dd>${date(row.updated_at)}</dd></div><div><dt>Captured</dt><dd>${date(c.captured_at)}</dd></div><div><dt>Source capture</dt><dd class="mono">${escape(c.id)}</dd></div></dl><div class="drawer-actions">${source ? `<a class="button" href="${escape(source)}" target="_blank" rel="noopener noreferrer">Open source ${icon("external", 15)}</a>` : ""}${button(`Review checks ${icon("arrow", 15)}`, "go-capture", "", `data-page="checks" data-id="${c.id}"`)}${known ? button(`Investigate this record ${icon("agent", 15)}`, "prepare-investigation", "primary", `data-question="${escape(`Inspect ${row.full_name} in public capture ${c.id}. Explain its recorded source values and quality evidence, citing the capture.`)}"`) : ""}</div><details class="raw-source"><summary>${icon("code", 17)} Raw source JSON ${icon("chevron", 15)}</summary><pre class="record-json">${escape(JSON.stringify(row, null, 2))}</pre></details><p class="source-note">These are captured source values, not live GitHub counters. The capture's quality contract validates specific fields; source metadata presence is not a quality guarantee.</p>`;
  $("#detail-dialog").showModal();
}
function showCapture(c) {
  $("#detail-content").innerHTML =
    `<div class="drawer-kicker">${icon("lineage", 20)} Immutable capture evidence</div><h2 id="detail-title">The source behind<br>the result.</h2><p class="drawer-description">${escape(c.name)} · ${c.row_count} actual records</p>${evidence(c)}<div class="drawer-actions">${button(`Browse records ${icon("arrow", 15)}`, "go-capture", "primary", `data-page="datasets" data-id="${c.id}"`)}${button("Review checks", "go-capture", "", `data-page="checks" data-id="${c.id}"`)}</div><h3>Stored contract</h3><pre class="record-json">${escape(JSON.stringify(c.contract, null, 2))}</pre><h3>Recorded quality results</h3>${checkRows(c, "all", "drawer-")}`;
  $("#detail-dialog").showModal();
}
function render() {
  if (!workspace) return;
  const known = pages.find((p) => p[0] === page);
  if (!known) {
    page = "overview";
  }
  $("#breadcrumb").textContent = (known || pages[0])[1];
  document.title = `${(known || pages[0])[1]} — DataGuard`;
  $("#navigation").innerHTML = pages
    .map(
      ([key, label], i) =>
        (key === "incidents"
          ? '<div class="nav-divider"></div><div class="nav-caption">TOOLS</div>'
          : "") +
        `<a href="/console/${key}" ${key === page ? 'class="active" aria-current="page"' : ""}>${icon(key, 15)}<span>${label}</span>${key === "quarantine" && workspace.captures.some((c) => c.status === "quarantined") ? `<span class="nav-number">${workspace.captures.filter((c) => c.status === "quarantined").length}</span>` : ""}</a>`,
    )
    .join("");
  $("#profile-label").innerHTML = token
    ? "Connected operator<small>Authenticated access</small>"
    : "Public observer<small>Read-only access</small>";
  $("#access-state").innerHTML =
    `${icon("eye", 16)} ${token ? "Operator connected" : "Public view"}`;
  $("#connect-button").innerHTML = token
    ? "Disconnect operator"
    : `Connect operator ${icon("connections", 15)}`;
  $("#refresh").innerHTML = icon("recovery", 16);
  document.body.dataset.page = page;
  $("#main").innerHTML = renderers[page]();
  hydrateFindings();
  $("#footer-time").textContent =
    "Workspace read " + date(workspace.generated_at);
  if (page === "versions") compare();
  if (page === "agent") updatePublicCooldown();
  globalThis.DataGuardArchive?.mount($("#main"), page);
}
function updatePublicCooldown() {
  const seconds = Math.max(
    0,
    Math.ceil((publicCooldownUntil - Date.now()) / 1000),
  );
  const submit = document.querySelector('#agent-form button[type="submit"]');
  if (!submit) return;
  if (seconds) {
    submit.disabled = true;
    submit.textContent = `Try again in ${seconds}s`;
    const state = document.querySelector("#public-quota-state");
    if (state)
      state.textContent = `The public investigator is cooling down. Retry in ${seconds} seconds; provider capacity and shared allowances may also be in use by other visitors.`;
  } else if (publicCooldownUntil) {
    submit.disabled = false;
    submit.innerHTML = `Investigate public data ${icon("arrow", 20)}`;
    publicCooldownUntil = 0;
    clearInterval(publicCooldownTimer);
  }
}
function startPublicCooldown(seconds) {
  publicCooldownUntil = Date.now() + Math.max(1, seconds) * 1000;
  clearInterval(publicCooldownTimer);
  updatePublicCooldown();
  publicCooldownTimer = setInterval(updatePublicCooldown, 1000);
}
async function withWork(element, task) {
  if (element?.disabled) return;
  const text = element?.innerHTML;
  if (element) {
    element.disabled = true;
    element.innerHTML = "Working…";
  }
  try {
    return await task();
  } catch (e) {
    toast(e.message, true);
    throw e;
  } finally {
    if (element?.isConnected) {
      element.disabled = false;
      element.innerHTML = text;
    }
  }
}
function access() {
  if (token) {
    token = "";
    lastAgent = null;
    pendingQuestion = "";
    Object.assign(recordView, { query: "", sort: "repository", filter: "all" });
    Object.assign(historyView, { query: "", status: "all" });
    selectedId = "";
    $("#operator-token").value = "";
    refresh();
    toast("Operator disconnected. Credentials cleared from tab memory.");
  } else $("#access-dialog").showModal();
}
document.addEventListener("click", async (event) => {
  const close = event.target.closest("[data-close]");
  if (close) {
    $("#" + close.dataset.close).close();
    return;
  }
  const anchor = event.target.closest('a[href^="/console/"]');
  if (anchor && !event.ctrlKey && !event.metaKey && !event.shiftKey) {
    event.preventDefault();
    navigate(anchor.getAttribute("href").split("/")[2]);
    return;
  }
  const el = event.target.closest("[data-action]");
  if (!el) return;
  const action = el.dataset.action;
  let c = workspace?.captures.find((c) => c.id === el.dataset.id);
  try {
    if (action === "access") {
      access();
      return;
    }
    if (action === "suggest") {
      pendingQuestion = el.dataset.question;
      $("#agent-question").value = pendingQuestion;
      $("#agent-question").focus();
      return;
    }
    if (
      el.dataset.id &&
      !c &&
      ["details", "record", "download"].includes(action)
    )
      c = await api("/captures/" + encodeURIComponent(el.dataset.id));
    if (action === "copy-digest") {
      await navigator.clipboard.writeText(c.digest);
      toast("Source SHA-256 copied.");
      return;
    }
    if (action === "go-capture") {
      selectedId = el.dataset.id;
      $("#detail-dialog").close();
      navigate(el.dataset.page);
      return;
    }
    if (action === "prepare-investigation") {
      pendingQuestion = el.dataset.question;
      $("#detail-dialog").close();
      navigate("agent");
      $("#agent-question").focus();
      return;
    }
    if (action === "sort-records") {
      recordView.sort = el.dataset.sort;
      const sort = $("#record-sort");
      if (sort) sort.value = recordView.sort;
      updateRecords();
      return;
    }
    if (action === "clear-record-filters") {
      recordView.query = "";
      recordView.filter = "all";
      render();
      return;
    }
    if (action === "record") {
      showRecord(c, Number(el.dataset.index));
      return;
    }
    if (action === "details") {
      showCapture(c);
      return;
    }
    if (action === "download") {
      const raw = await api("/captures/" + c.id);
      const blob = new Blob([JSON.stringify(raw, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "dataguard-" + c.id + ".json";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast("Actual capture evidence downloaded.");
      return;
    }
    if (["sync", "recheck", "restore"].includes(action)) {
      if (!needOperator()) return;
      await withWork(el, async () => {
        const result = await api(
          "/" + action,
          "POST",
          action === "sync" ? undefined : { capture_id: c.id },
        );
        if (result.id) selectedId = result.id;
        await refresh();
        if (action === "sync") {
          navigate("batches");
          toast("GitHub source captured and evaluated.");
        } else if (action === "recheck") {
          navigate("checks");
          toast("New evaluation created. Original source evidence preserved.");
        } else toast("Recovery reference validated and selected.");
      });
    }
  } catch (e) {
    toast(e.message, true);
  }
});
document.addEventListener("submit", async (event) => {
  const form = event.target;
  if (
    ![
      "upload-form",
      "contract-form",
      "note-form",
      "agent-form",
      "access-form",
      "quality-benchmark-form",
    ].includes(form.id)
  )
    return;
  event.preventDefault();
  const submit = $('button[type="submit"]', form);
  if (form.id === "quality-benchmark-form") {
    const result = $("#quality-benchmark-result", form.parentElement);
    result.textContent = "Replaying the pinned source checks…";
    try {
      await withWork(submit, async () => {
        const policy = new FormData(form).get("policy");
        const [replay, report] = await Promise.all([
          api("/benchmark?policy=" + encodeURIComponent(policy)),
          api("/benchmark/artifacts/report"),
        ]);
        if (replay.sha256 !== report.source_sha256)
          throw Error("The replay and measurement source fingerprints differ.");
        result.innerHTML = renderQualityBenchmark(replay, report);
      });
    } catch (error) {
      result.textContent = error.message;
    }
    return;
  }
  if (form.id === "access-form") {
    const old = token;
    token = $("#operator-token").value.trim();
    $("#access-error").textContent = "";
    try {
      await withWork(submit, async () => {
        await api("/workspace");
        $("#access-dialog").close();
        $("#operator-token").value = "";
        await refresh();
        toast(
          "Operator connected. Private records and authenticated actions are available.",
        );
      });
    } catch (e) {
      token = old;
      $("#access-error").textContent = e.message;
    }
    return;
  }
  if (form.id !== "agent-form" && !needOperator()) return;
  try {
    await withWork(submit, async () => {
      if (form.id === "upload-form") {
        const raw = JSON.parse($("#upload-json").value);
        const records = Array.isArray(raw) ? raw : raw.records;
        if (!Array.isArray(records) || !records.length)
          throw Error(
            "Provide a non-empty JSON array or an object with a records array.",
          );
        const result = await api("/uploads", "POST", {
          name: $("#upload-name").value.trim(),
          records,
        });
        selectedId = result.id;
        await refresh();
        navigate(result.status === "quarantined" ? "quarantine" : "datasets");
        toast(
          result.status === "quarantined"
            ? "Imported privately. Quality failures are quarantined for review."
            : "Imported privately. The capture passed its quality contract.",
        );
      }
      if (form.id === "contract-form") {
        await api("/contract", "PUT", {
          min_rows: Number($("#min-rows").value),
          max_age_hours: Number($("#max-age").value),
          require_license: $("#require-license").checked,
          reject_archived: $("#reject-archived").checked,
        });
        await refresh();
        toast("Contract saved. Re-evaluate a capture to apply the new rules.");
      }
      if (form.id === "note-form") {
        await api("/notes", "POST", {
          capture_id: $("#note-capture").value,
          note: $("#incident-note").value.trim(),
        });
        await refresh();
        toast("Private investigation note saved.");
      }
      if (form.id === "agent-form") {
        $("#agent-error").textContent = "";
        pendingQuestion = $("#agent-question").value.trim();
        lastAgent = await api("/public-investigate", "POST", {
          question: $("#agent-question").value.trim(),
        });
        $("#agent-result").innerHTML = agentResult(lastAgent);
        hydrateFindings();
        document.querySelectorAll(".investigation-steps a").forEach((link) => {
          link.removeAttribute("aria-disabled");
          link.classList.add("complete");
        });
        $("#findings-panel").focus({ preventScroll: true });
        $("#findings-panel").scrollIntoView({
          behavior: window.matchMedia("(prefers-reduced-motion: reduce)")
            .matches
            ? "instant"
            : "smooth",
          block: "start",
        });
        const allowance = lastAgent.quota?.remaining;
        if (allowance)
          $("#public-quota-state").textContent =
            `Remaining in current windows: ${allowance.per_client} for this visitor, ${allowance.global_minute} shared this minute, ${allowance.global_day} shared today.`;
        toast("Investigation completed with source evidence.");
      }
    });
  } catch (e) {
    const cooldown = UI.retryCooldownSeconds(e.status, e.retryAfter);
    if (form.id === "agent-form" && cooldown)
      startPublicCooldown(cooldown);
    const id = {
      "upload-form": "upload-error",
      "contract-form": "contract-error",
      "note-form": "note-error",
      "agent-form": "agent-error",
    }[form.id];
    if ($("#" + id))
      $("#" + id).textContent =
        e instanceof SyntaxError
          ? "Invalid JSON. Import an actual JSON array of repository records."
          : e.message;
  }
});
document.addEventListener("change", async (event) => {
  const el = event.target;
  if (el.id === "capture-select") {
    selectedId = el.value;
    render();
  }
  if (el.id === "history-filter") {
    historyView.status = el.value;
    $("#history-timeline").innerHTML = captureEvents();
  }
  if (el.id === "record-sort") {
    recordView.sort = el.value;
    updateRecords();
  }
  if (el.id === "record-filter") {
    recordView.filter = el.value;
    updateRecords();
  }
  if (el.id === "check-filter")
    $("#check-list").innerHTML = checkRows(capture(), el.value);
  if (["compare-from", "compare-to"].includes(el.id)) compare();
  if (el.id === "upload-file") {
    const file = el.files[0];
    if (!file) return;
    if (file.size > 8000000) {
      toast("The JSON file exceeds 8 MB.", true);
      el.value = "";
      return;
    }
    try {
      $("#upload-json").value = await file.text();
      if (!$("#upload-name").value)
        $("#upload-name").value = file.name
          .replace(/\.json$/i, "")
          .slice(0, 100);
    } catch {
      toast("The selected file could not be read.", true);
    }
  }
});
document.addEventListener("input", (event) => {
  if (event.target.id === "record-search") {
    recordView.query = event.target.value;
    updateRecords();
  }
  if (event.target.id === "history-search") {
    historyView.query = event.target.value;
    $("#history-timeline").innerHTML = captureEvents();
  }
  if (event.target.id === "agent-question")
    pendingQuestion = event.target.value;
});
document.addEventListener("click", (event) => {
  if (event.target.closest('[aria-disabled="true"]')) event.preventDefault();
});
$("#access-open").addEventListener("click", access);
$("#connect-button").addEventListener("click", access);
$("#refresh").addEventListener("click", async () => {
  await withWork($("#refresh"), refresh);
  toast("Workspace evidence refreshed.");
});
$("#workspace-open").addEventListener("click", () => navigate("connections"));
$("#mobile-menu").addEventListener("click", () =>
  setMenu(!$(".sidebar").classList.contains("open")),
);
$("#nav-backdrop").addEventListener("click", () => setMenu(false, true));
document.addEventListener("keydown", (event) => {
  if (!$(".sidebar").classList.contains("open")) return;
  if (event.key === "Escape") {
    event.preventDefault();
    setMenu(false, true);
  }
  if (event.key === "Tab") {
    const items = [...$(".sidebar").querySelectorAll("a,button")].filter(
      (el) => el.offsetParent !== null,
    );
    const first = items[0],
      last = items.at(-1);
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
});
window.matchMedia("(max-width: 900px)").addEventListener("change", (event) => {
  if (!event.matches) setMenu(false);
});
window.addEventListener("popstate", () => {
  page = location.pathname.split("/")[2] || "overview";
  render();
});
refresh();
