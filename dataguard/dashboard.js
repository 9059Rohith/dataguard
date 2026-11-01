"use strict";
const $ = (s, root = document) => root.querySelector(s);
const escape = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const paths = {
  overview: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  datasets:
    "M20 6c0 2-16 2-16 0s16-2 16 0v12c0 3-16 3-16 0V6 M4 12c0 3 16 3 16 0",
  contracts: "M8 3H5v18h14V3h-3 M9 2h6v4H9z M8 11h8 M8 15h6",
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
let toastTimer;
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
const heading = (title, desc, actions = "") =>
  `<div class="page-heading"><div><h1>${title}</h1><p>${desc}</p></div><div class="heading-actions">${actions}</div></div>`;
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
function recordTable(c, limit = 500, query = "") {
  const rows = c.records
    .map((r, i) => ({ r, i }))
    .filter(({ r }) =>
      String(r.full_name || "")
        .toLowerCase()
        .includes(query.toLowerCase()),
    )
    .slice(0, limit);
  return `<div class="table-wrap"><table><thead><tr><th>Repository</th><th>Stars</th><th>Open issues</th><th>Source updated</th><th></th></tr></thead><tbody>${rows.map(({ r, i }) => `<tr><td><span class="table-icon">${icon("datasets", 14)}</span><strong>${escape(r.full_name || "Unnamed record")}</strong><span class="sub">${escape(r.language || "No language metadata")} · ID ${escape(r.id)}</span></td><td>${number(r.stargazers_count)}</td><td>${number(r.open_issues_count)}</td><td>${date(r.updated_at).split(" 202")[0]}<span class="sub">${age(r.updated_at)}</span></td><td><button data-action="record" data-id="${c.id}" data-index="${i}" title="Inspect record ${i + 1}" aria-label="Inspect record ${i + 1}">${icon("external", 14)}</button></td></tr>`).join("") || '<tr><td colspan="5">No records match your search.</td></tr>'}</tbody></table></div><div class="data-table-footer"><span>${rows.length} of ${c.row_count} records</span><span>SHA-256 ${c.digest.slice(0, 12)}…</span></div>`;
}
async function api(path, method = "GET", body) {
  const headers = {};
  if (token) headers.Authorization = "Bearer " + token;
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
  if (!r.ok)
    throw Error(
      typeof result.detail === "string"
        ? result.detail
        : "Request validation failed. Check the form values.",
    );
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
  $(".sidebar").classList.remove("open");
  $("#main").focus({ preventScroll: true });
}
function overview() {
  const c = capture();
  if (!c)
    return (
      heading("Your reliability overview.", "Connect a real source to begin.") +
      empty(
        "No captured data.",
        "Import operator data or connect the GitHub source.",
      )
    );
  const passed = c.checks.filter((x) => !x.failed).length,
    score = Math.round((passed / c.checks.length) * 100),
    bad = workspace.captures.filter((c) => c.status === "quarantined").length;
  return (
    heading(
      "Good data. Clear evidence.",
      "A quieter place to understand the health of your data.",
      button(
        `${icon("download", 14)} Export evidence`,
        "download",
        "",
        `data-id="${c.id}"`,
      ) +
        `<a class="button primary" href="/console/batches">${icon("plus", 14)} Import data</a>`,
    ) +
    `<div class="overview-hero"><div class="hero-score"><div class="quality-orbit"><svg viewBox="0 0 180 180"><circle cx="90" cy="90" r="76" fill="none" stroke="#e8eddf" stroke-width="7"/><circle cx="90" cy="90" r="76" fill="none" stroke="#829d62" stroke-width="7" stroke-linecap="round" stroke-dasharray="${score * 4.775} 477.5"/></svg><div class="score-number"><strong>${score}<span style="font-size:20px">%</span></strong><span>checks passed</span></div></div><div class="hero-copy"><div class="status-line">${icon(c.status === "published" ? "check" : "incidents", 12)} ${passed} of ${c.checks.length} checks passed</div><h2>${c.status === "published" ? "Trust starts with<br>the details." : "A closer look<br>is needed."}</h2><p>Quality results from the selected capture. Every check includes its rule, record count, and evaluation time.</p>${link("checks", "Explore quality checks")}</div></div><div class="hero-evidence"><div><span class="mini-label">The source behind the numbers</span><h3>${escape(c.name)}</h3><p>${escape(c.scope)}</p></div><div class="source-footer"><span>${icon("github", 14)} ${c.visibility === "public" ? "GitHub REST API" : "Operator upload"}</span><span>${age(c.captured_at)}</span></div></div></div><div class="metrics-strip">${[
      ["Records in capture", c.row_count, "Actual source records", "datasets"],
      [
        "Checks evaluated",
        c.checks.length,
        "Against the captured contract",
        "checks",
      ],
      [
        "Capture versions",
        workspace.captures.length,
        "Immutable evidence history",
        "versions",
      ],
      ["Quarantined captures", bad, "Held for operator review", "quarantine"],
    ]
      .map(
        ([label, value, hint, ic]) =>
          `<div class="metric"><div class="metric-label">${label}${icon(ic, 14)}</div><strong>${number(value)}</strong><small>${hint}</small></div>`,
      )
      .join(
        "",
      )}</div><div class="split"><div>${section("The data behind your workspace", link("datasets", "View dataset"))}<div class="panel">${recordTable(c, 5)}</div></div><div>${section("Evidence trail", link("lineage", "View lineage"))}<div class="overview-aside"><div class="panel"><div class="activity-row"><span class="activity-icon">${icon("datasets", 13)}</span><div class="activity-copy"><strong>Source records captured</strong><p>${number(c.row_count)} records · ${c.visibility === "public" ? "GitHub public metadata" : "Private operator input"}</p><small>${date(c.captured_at)}</small></div></div><div class="activity-row"><span class="activity-icon">${icon("checks", 13)}</span><div class="activity-copy"><strong>Contract evaluation completed</strong><p>${passed} checks passed · ${c.checks.length - passed} checks failed</p><small>${date(c.evaluated_at)}</small></div></div></div><div class="forest-note"><h3>A little more context.<br>A lot more confidence.</h3><p>Trace a quality result all the way back to the exact source records and contract that produced it.</p>${link("lineage", "Follow the evidence")}</div></div></div></div>`
  );
}
function datasets() {
  const c = capture();
  return (
    heading(
      "Know what flows in.",
      "Explore the real records, metadata, and provenance of each capture.",
      button(
        `${icon("download", 14)} Export JSON`,
        "download",
        "",
        `data-id="${c.id}"`,
      ),
    ) +
    selector() +
    `<div class="panel"><div class="dataset-heading"><div><h2>${escape(c.name)}</h2><p>${escape(c.scope)}</p></div>${status(c)}</div><div class="dataset-info"><div><span>Source</span><strong>${c.visibility === "public" ? "GitHub REST API" : "Private operator upload"}</strong></div><div><span>Captured</span><strong>${date(c.captured_at)}</strong></div><div><span>Content fingerprint</span><strong class="mono">${c.digest.slice(0, 24)}…</strong></div></div><div style="padding:20px 20px 0"><div class="toolbar"><div class="search-input">${icon("search", 14)}<input id="record-search" aria-label="Search repository records" placeholder="Search repositories…"></div><div class="right"><span>${c.row_count} records in this capture</span>${pill(c.visibility, "neutral")}</div></div></div><div id="records-table">${recordTable(c)}</div></div>${section("Source distribution")}<div class="split">${chart(c)}<div class="panel panel-pad"><h3 class="note-title">Read the source, too.</h3><p class="explain">These records describe a small, intentional set of Python infrastructure repositories. They reflect the capture time, and should not be treated as a live count or a complete ecosystem survey.</p>${link("lineage", "Inspect full provenance")}<div class="privacy-stamp">${icon("lock", 13)} Operator uploads remain private.</div></div></div>`
  );
}
function contracts() {
  const r = workspace.contract;
  return (
    heading(
      "Define what good looks like.",
      "One explicit contract. Repeatable checks. A permanent record of what was evaluated.",
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
    `<div class="toolbar"><div class="right"><span>Evaluated ${date(c.evaluated_at)}</span></div><select id="check-filter" aria-label="Filter quality checks"><option value="all">All checks</option><option value="failed">Failed only</option><option value="passed">Passed only</option></select></div><div id="check-list" class="check-list">${checkRows(c)}</div><div class="privacy-stamp">${icon("info", 13)} Historical results are frozen at evaluation time. Re-evaluate to check current freshness.</div>`
  );
}
function checkRows(c, filter = "all") {
  const rows = c.checks.filter((x) => filter === "all" || x.status === filter);
  return (
    rows
      .map(
        (x) =>
          `<article class="check-row"><span class="check-glyph ${x.failed ? "bad" : ""}">${icon(x.failed ? "close" : "check", 17)}</span><div><h3>${escape(x.title)}</h3><p>${escape(x.detail)}</p><small>${x.tested} ${["volume", "freshness"].includes(x.key) ? "capture" : "record"} checks · ${x.failed} failed${x.indices.length ? " · affected zero-based indices: " + x.indices.join(", ") : ""}</small></div>${pill(x.failed ? "Failed" : "Passed", x.failed ? "bad" : "")}</article>`,
      )
      .join("") ||
    `<div class="panel">${empty("No " + filter + " checks.", "Choose All checks to inspect every evaluation.", "checks")}</div>`
  );
}
function batches() {
  return (
    heading(
      "The history stays intact.",
      "Import actual repository metadata or refresh the fixed public GitHub source.",
      button("Sync GitHub " + icon("recovery", 14), "sync", "primary"),
    ) +
    `<div class="split"><div><div class="capture-timeline">${workspace.captures.map((c) => `<article class="capture-event"><h3><span>${escape(c.name)}</span>${status(c)}</h3><p>Captured ${date(c.captured_at)} · evaluated ${date(c.evaluated_at)}</p><div class="capture-meta"><span>${c.row_count} source records</span><span>${c.checks.filter((x) => !x.failed).length}/${c.checks.length} checks passed</span><span>${pill(c.visibility, "neutral")}</span></div><p class="mono">${escape(c.id)}</p><div class="capture-actions">${button("Inspect evidence", "details", "small", `data-id="${c.id}"`)}${button("Re-evaluate", "recheck", "small", `data-id="${c.id}"`)}${button(icon("download", 13), "download", "small", `data-id="${c.id}" aria-label="Download capture ${c.id}"`)}</div></article>`).join("")}</div></div><div><div class="panel panel-pad"><h2 class="upload-title">Bring your own evidence.</h2><p class="explain">Import an actual JSON array of repository metadata. The server evaluates it immediately; uploads stay private.</p><form id="upload-form"><div class="form-field"><label for="upload-name">Capture name</label><input id="upload-name" required maxlength="100" placeholder="Name this source capture"></div><div class="drop-area"><label for="upload-file">Choose a JSON file</label><input id="upload-file" type="file" accept=".json,application/json"><p>Up to 500 records. Required fields: id, full_name, updated_at, stargazers_count, open_issues_count.</p></div><div class="form-field"><label for="upload-json">Or paste your JSON records</label><textarea id="upload-json" placeholder="Paste your actual JSON array here" required></textarea></div><button class="button primary" type="submit">Import & evaluate ${icon("arrow", 14)}</button><p id="upload-error" class="form-error" role="alert"></p></form><div class="privacy-stamp">${icon("lock", 12)} Private upload · operator authentication required</div></div><div class="forest-note"><h3>No silent overwrites.</h3><p>Each import gets a new capture ID. The original records, source time, content hash, and contract stay together.</p>${link("versions", "Compare versions")}</div></div></div>`
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
    const same =
      left &&
      right &&
      JSON.stringify(
        Object.keys(left)
          .sort()
          .map((k) => [k, left[k]]),
      ) ===
        JSON.stringify(
          Object.keys(right)
            .sort()
            .map((k) => [k, right[k]]),
        );
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
          ).filter((k) => JSON.stringify(left[k]) !== JSON.stringify(right[k]))
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
  return (
    heading(
      "Investigate, with evidence.",
      "A real model investigation grounded in source records and visible evidence tools.",
    ) +
    `<div class="agent-layout"><div class="agent-start"><span class="agent-symbol">${icon("agent", 24)}</span><h2>Ask a better question<br>of your data.</h2><p>${provider.public_data_only ? "Gemini inspects only the public GitHub captures. Private uploads and operator notes are excluded from its tools." : "The investigator can list authorized captures and inspect their records, contracts, and checks."} Its actual evidence tool trace stays visible alongside the answer.</p><div class="suggestions">${["Which captures need attention?", "Explain the freshness evidence.", "What should I verify before recovery?"].map((q) => `<button data-action="suggest" data-question="${q}">${q}</button>`).join("")}</div><div class="info-band"><span>${escape(provider.data_notice || "Ask only about the source evidence.")} ${provider.public_data_only ? "This connection uses the free tier; no billing was enabled." : ""}</span></div><form id="agent-form"><label for="agent-question">Your investigation</label><textarea id="agent-question" required minlength="5" maxlength="1500" placeholder="Ask about source freshness, a failed check, or capture provenance…"></textarea><div class="form-actions"><button class="button primary" type="submit">Investigate ${icon("agent", 14)}</button><p>Read-only · 4 turns · 6 tools · 1 quota retry</p></div><p class="form-error" id="agent-error" role="alert"></p></form><div id="agent-result">${lastAgent ? agentResult(lastAgent) : ""}</div></div><div><div class="panel panel-pad"><h3 class="note-title">Every claim needs a source.</h3><p class="explain">A response is accepted only after the model calls at least one evidence tool. The agent cannot change a contract, publish a capture, or execute arbitrary code.</p><ol class="rule-list"><li><span class="rule-num">01</span>List available captures</li><li><span class="rule-num">02</span>Inspect exact evidence</li><li><span class="rule-num">03</span>Explain findings with IDs</li></ol><div class="provider-state">${pill(provider.configured ? "Provider configured" : "Provider not configured", provider.configured ? "" : "warn")}<p>${provider.configured ? `${escape(provider.provider)} · ${escape(provider.model)}` : "This deployment has no AI provider credential. Configure GEMINI_API_KEY or OPENAI_API_KEY to enable investigations."}</p><p>${escape(provider.billing_mode || "")}</p><p>${escape(provider.quota_notice || "")}</p></div></div><div class="forest-note"><h3>Judgment stays<br>with your operator.</h3><p>Use the findings to inform a decision. All data and policy changes remain explicit, authenticated actions.</p>${link("checks", "Read the checks yourself")}</div></div></div>`
  );
}
function agentResult(r) {
  return `<div class="agent-response"><h3>Investigation findings</h3><div class="agent-answer">${escape(r.answer)}</div><p class="form-hint">${escape(r.provider || "AI provider")} · ${escape(r.model)} · ${date(r.created_at)}${r.public_data_only ? " · Public GitHub evidence only" : ""}</p><h3>Evidence tool trace · ${r.trace.length} calls</h3>${r.trace.map((t, i) => `<details class="tool-trace"><summary>${i + 1}. ${escape(t.tool)} ${escape(JSON.stringify(t.arguments))}</summary><pre>${escape(JSON.stringify(t.result, null, 2))}</pre></details>`).join("")}</div>`;
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
    `<div class="settings-layout"><div class="settings-nav"><span>Workspace & access</span><a href="/console/contracts">Data contract</a><a href="/console/connections">Connections</a><a href="/docs">API documentation ↗</a></div><div class="panel settings-section"><h2>Workspace details</h2>${[
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
        (i === 10 ? '<div class="nav-divider"></div>' : "") +
        `<a href="/console/${key}" ${key === page ? 'class="active" aria-current="page"' : ""}>${icon(key, 15)}<span>${label}</span>${key === "quarantine" && workspace.captures.some((c) => c.status === "quarantined") ? `<span class="nav-number">${workspace.captures.filter((c) => c.status === "quarantined").length}</span>` : ""}</a>`,
    )
    .join("");
  $("#profile-label").innerHTML = token
    ? "Connected operator<small>Authenticated access</small>"
    : "Public observer<small>Read-only access</small>";
  $("#access-state").innerHTML =
    `<span class="live-dot"></span> ${token ? "Operator connected" : "Public view"}`;
  $("#connect-button").innerHTML = token
    ? "Disconnect operator"
    : "Connect operator <span>↗</span>";
  $("#refresh").innerHTML = icon("recovery", 16);
  $("#main").innerHTML = renderers[page]();
  $("#footer-time").textContent =
    "Workspace read " + date(workspace.generated_at);
  if (page === "versions") compare();
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
  const c = workspace?.captures.find((c) => c.id === el.dataset.id);
  try {
    if (action === "access") {
      access();
      return;
    }
    if (action === "suggest") {
      $("#agent-question").value = el.dataset.question;
      $("#agent-question").focus();
      return;
    }
    if (action === "record") {
      const row = c.records[Number(el.dataset.index)];
      $("#detail-content").innerHTML =
        `<h2>${escape(row.full_name || "Source record")}</h2><p>Exact record ${Number(el.dataset.index) + 1} from capture <span class="mono">${escape(c.id)}</span>.</p><pre class="record-json">${escape(JSON.stringify(row, null, 2))}</pre><p>Captured ${date(c.captured_at)} · SHA-256 ${c.digest.slice(0, 24)}…</p>`;
      $("#detail-dialog").showModal();
      return;
    }
    if (action === "details") {
      $("#detail-content").innerHTML =
        `<h2>Capture evidence.</h2><p>${escape(c.name)} · ${c.row_count} records</p>${evidence(c)}<h3>Stored contract</h3><pre class="record-json">${escape(JSON.stringify(c.contract, null, 2))}</pre><h3>Quality results</h3>${checkRows(c)}`;
      $("#detail-dialog").showModal();
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
    ].includes(form.id)
  )
    return;
  event.preventDefault();
  const submit = $('button[type="submit"]', form);
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
  if (!needOperator()) return;
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
        lastAgent = await api("/investigate", "POST", {
          question: $("#agent-question").value.trim(),
        });
        $("#agent-result").innerHTML = agentResult(lastAgent);
        toast("Investigation completed with source evidence.");
      }
    });
  } catch (e) {
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
  if (event.target.id === "record-search")
    $("#records-table").innerHTML = recordTable(
      capture(),
      500,
      event.target.value,
    );
});
$("#access-open").addEventListener("click", access);
$("#connect-button").addEventListener("click", access);
$("#refresh").addEventListener("click", async () => {
  await withWork($("#refresh"), refresh);
  toast("Workspace evidence refreshed.");
});
$("#workspace-open").addEventListener("click", () => navigate("connections"));
$("#mobile-menu").addEventListener("click", () =>
  $(".sidebar").classList.toggle("open"),
);
window.addEventListener("popstate", () => {
  page = location.pathname.split("/")[2] || "overview";
  render();
});
refresh();
