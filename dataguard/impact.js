"use strict";
globalThis.DataGuardImpact = (() => {
  const esc = (value) =>
    String(value ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const defaults = () => ({
    required_metadata: ["id", "full_name"],
    accepted_languages: [],
    reject_archived: false,
    max_push_age_hours: null,
    min_stars: 0,
    max_open_issues: null,
  });
  const labels = {
    metadata: "Required metadata",
    language: "Accepted language",
    archived: "Archive status",
    freshness: "Source push freshness",
    min_stars: "Minimum stars",
    max_open_issues: "Maximum open issues",
  };
  let state = {
    baseline: defaults(),
    candidate: defaults(),
    capture: "",
    clock: "",
    report: null,
    dirty: false,
    running: false,
  };
  let sources = [];
  let revision = 0;
  const field = (side, name, title, note, max, value) =>
    `<label for="impact-${side}-${name}">${title}<input id="impact-${side}-${name}" name="${side}-${name}" type="number" min="0" max="${max}" step="1" value="${value ?? ""}" ${name === "min_stars" ? "required" : ""}><small>${note}</small></label>`;
  function policySheet(side, title, subtitle) {
    const policy = state[side];
    return `<fieldset class="impact-sheet ${side}"><legend><span>${side === "baseline" ? "01" : "02"}</span> ${title}</legend><p>${subtitle}</p><div class="impact-fields"><div class="impact-metadata"><span>Required source metadata</span><div>${["id", "full_name", "description", "language", "license", "default_branch"].map((name) => `<label><input type="checkbox" name="${side}-metadata" value="${name}" ${policy.required_metadata.includes(name) ? "checked" : ""}>${name.replaceAll("_", " ")}</label>`).join("")}</div></div><label for="impact-${side}-languages">Accepted languages<input id="impact-${side}-languages" name="${side}-languages" maxlength="480" value="${esc(policy.accepted_languages.join(", "))}" placeholder="Any language"><small>Comma separated; exact source names, e.g. Python, C.</small></label>${field(side, "max_push_age_hours", "Maximum push age · hours", "Empty accepts any age. Compared to the UTC analysis clock.", 87600, policy.max_push_age_hours)}${field(side, "min_stars", "Minimum stars", "A selection criterion; popularity does not prove software quality.", 1000000000, policy.min_stars)}${field(side, "max_open_issues", "Maximum open issues", "Empty accepts any count. GitHub includes pull requests here.", 1000000000, policy.max_open_issues)}<label class="impact-toggle"><input type="checkbox" name="${side}-reject_archived" ${policy.reject_archived ? "checked" : ""}>Require an active repository<small>The source archived flag must be exactly false.</small></label></div></fieldset>`;
  }
  function readForm() {
    const form = document.querySelector("#impact-form");
    if (!form) return;
    const data = new FormData(form);
    for (const side of ["baseline", "candidate"]) {
      const numeric = (name) =>
        data.get(`${side}-${name}`) === ""
          ? null
          : Number(data.get(`${side}-${name}`));
      state[side] = {
        required_metadata: data.getAll(`${side}-metadata`),
        accepted_languages: String(data.get(`${side}-languages`))
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        reject_archived: data.has(`${side}-reject_archived`),
        max_push_age_hours: numeric("max_push_age_hours"),
        min_stars: numeric("min_stars"),
        max_open_issues: numeric("max_open_issues"),
      };
    }
    state.capture = data.get("capture_id");
    state.clock = data.get("analysis_at");
  }
  function sourceNote() {
    const source = sources.find((c) => c.id === state.capture);
    if (!source) return "";
    return `<span>CAPTURED ${esc(new Date(source.captured_at).toISOString().replace("T", " ").slice(0, 19))} UTC · ${source.row_count} RECORDS</span><code>${esc(source.digest)}</code><button type="button" class="impact-source-link" data-action="go-capture" data-page="datasets" data-id="${esc(source.id)}">Browse source evidence →</button>`;
  }
  function render(workspace, selected) {
    sources = workspace.captures.filter(
      (c) =>
        c.visibility === "public" &&
        c.source === "https://api.github.com/repos/{owner}/{repo}",
    );
    if (!sources.length)
      return "<h1>Contract impact</h1><p>No public GitHub evidence is available.</p>";
    if (!sources.some((c) => c.id === state.capture))
      state.capture =
        sources.find((c) => c.id === selected)?.id || sources[0].id;
    if (!state.clock)
      state.clock = new Date(workspace.generated_at).toISOString().slice(0, 19);
    return `<div class="page-heading"><div><div class="impact-kicker">THE CONTRACT WORKBENCH</div><h1>Change the rule.<br><em>See the consequence.</em></h1><p>Test your next acceptance criteria against the exact same source evidence.</p></div><span class="impact-stamp">PUBLIC EVIDENCE<br><strong>Pure comparison</strong><br>Six bounded rules · zero writes</span></div><div class="impact-intro"><span>One capture. Two contracts.</span><p>Your policies define acceptance for this sample. These results are not security ratings or software quality scores.</p></div><form id="impact-form"><div class="impact-source"><label for="impact-capture">Immutable source capture<select id="impact-capture" name="capture_id">${sources.map((c) => `<option value="${esc(c.id)}" ${c.id === state.capture ? "selected" : ""}>${esc(c.id)} · ${c.row_count} repositories</option>`).join("")}</select></label><label for="impact-clock">Analysis clock · UTC<input id="impact-clock" type="datetime-local" step="1" name="analysis_at" value="${esc(state.clock)}" required><small>Must be at or after capture time. Never a live source refresh.</small></label><div id="impact-source-note">${sourceNote()}</div></div><div class="impact-policies">${policySheet("baseline", "Baseline", "Your reference acceptance criteria.")}${policySheet("candidate", "Candidate", "The proposal you want to understand.")}</div><div class="impact-runbar"><button type="button" class="button" id="impact-copy">Copy baseline → candidate</button><p>Experiments run in memory.<br>No model calls, saved policies, or quota use.</p><button class="button primary" id="impact-run" type="submit">Compare contracts <span aria-hidden="true">↗</span></button></div><p id="impact-error" class="impact-error" role="alert"></p></form><div id="impact-results" aria-live="polite">${results()}</div>`;
  }
  function results() {
    if (state.dirty)
      return '<div class="impact-placeholder"><span>INPUTS CHANGED</span><h2>Ready for another perspective.</h2><p>Compare again to produce evidence for the current inputs. Previous exports are disabled.</p></div>';
    const report = state.report;
    if (!report)
      return '<div class="impact-placeholder"><span>YOUR NEXT DECISION, WITH EVIDENCE</span><h2>What would your contract change?</h2><p>Start with identical conservative policies. Adjust a candidate rule and compare to reveal the affected repositories.</p></div>';
    const t = report.transitions;
    return `<section class="impact-report"><div class="section-title"><h2>The consequence, record by record.</h2><div class="impact-downloads"><button class="button small" data-impact-export="report">Download report</button><button class="button small" data-impact-export="facet">OpenLineage facet</button></div></div><div class="impact-transitions">${[
      [t.accepted_to_rejected, "Newly rejected", "break"],
      [t.rejected_to_accepted, "Newly accepted", "gain"],
      [t.accepted_to_accepted, "Still accepted", ""],
      [t.rejected_to_rejected, "Still rejected", ""],
    ]
      .map(
        ([count, label, style]) =>
          `<div class="${style}"><strong>${count}</strong><span>${label}</span></div>`,
      )
      .join(
        "",
      )}</div><p class="impact-clock-note">Evaluated at ${esc(report.analysis_at)} · capture age ${report.capture.age_hours.toFixed(3)} hours · baseline accepts ${report.baseline.accepted}/${report.capture.rows} · candidate accepts ${report.candidate.accepted}/${report.capture.rows}</p><div class="impact-rule-summary">${Object.entries(
      report.candidate.rules,
    )
      .map(
        ([key, r]) =>
          `<div><span>${esc(labels[key])}</span><strong class="${r.failed ? "impact-failed" : ""}">${r.enabled ? `${r.failed} / ${r.tested} fail` : "Disabled"}</strong>${r.failed ? `<small>${r.witnesses.map(esc).join(", ")}</small>` : ""}</div>`,
      )
      .join("")}</div><div class="impact-records">${report.records
      .map(
        (record) =>
          `<details class="impact-record" ${record.transition === "accepted_to_rejected" ? "open" : ""}><summary><span><strong>${esc(record.identity)}</strong><small>Source repository ID ${esc(record.repository_id)}</small></span><span class="impact-verdict ${record.transition === "accepted_to_rejected" ? "impact-failed" : ""}">${record.baseline.accepted ? "Accepted" : "Rejected"} <span aria-hidden="true">→</span> ${record.candidate.accepted ? "Accepted" : "Rejected"}</span></summary><div class="impact-check-table"><table><caption>Exact observed values and requirements for ${esc(record.identity)}</caption><thead><tr><th>Rule</th><th>Source observation</th><th>Baseline</th><th>Candidate</th></tr></thead><tbody>${record.candidate.checks
            .map((c, i) => {
              const b = record.baseline.checks[i];
              const observation =
                JSON.stringify(c.actual) === JSON.stringify(b.actual)
                  ? `<code>${esc(JSON.stringify(c.actual))}</code>`
                  : `<small>Baseline observation</small><code>${esc(JSON.stringify(b.actual))}</code><small>Candidate observation</small><code>${esc(JSON.stringify(c.actual))}</code>`;
              return `<tr><th scope="row">${esc(labels[c.rule])}<small>${esc(c.explanation)}</small></th><td>${observation}</td><td>${b.enabled ? (b.success ? "Pass" : "Fail") : "Disabled"}<code>${esc(JSON.stringify(b.expected))}</code></td><td class="${!c.success ? "impact-failed" : ""}">${c.enabled ? (c.success ? "Pass" : "Fail") : "Disabled"}<code>${esc(JSON.stringify(c.expected))}</code></td></tr>`;
            })
            .join("")}</tbody></table></div></details>`,
      )
      .join(
        "",
      )}</div><details class="impact-provenance"><summary>Reproduce this comparison · source and policy fingerprints</summary><dl class="evidence-list"><div><dt>Immutable capture</dt><dd>${esc(report.capture.id)}</dd></div><div><dt>Source SHA-256</dt><dd><code>${esc(report.capture.sha256)}</code></dd></div><div><dt>Baseline policy SHA-256</dt><dd><code>${report.baseline.sha256}</code></dd></div><div><dt>Candidate policy SHA-256</dt><dd><code>${report.candidate.sha256}</code></dd></div><div><dt>Report SHA-256</dt><dd><code>${report.sha256}</code></dd></div></dl><p>Report hash covers canonical JSON excluding its own sha256 field. The OpenLineage download is a dataset assertion facet, not a complete lineage event.</p><a class="text-link" href="https://openlineage.io/docs/1.53.0/spec/facets/dataset-facets/data_quality_assertions/" target="_blank" rel="noopener noreferrer">OpenLineage assertion specification ↗</a></details></section>`;
  }
  function invalidate() {
    revision += 1;
    readForm();
    state.dirty = true;
    const result = document.querySelector("#impact-results");
    if (result) result.innerHTML = results();
    const note = document.querySelector("#impact-source-note");
    if (note) note.innerHTML = sourceNote();
  }
  document.addEventListener("input", (event) => {
    if (event.target.closest("#impact-form")) invalidate();
  });
  document.addEventListener("change", (event) => {
    if (event.target.closest("#impact-form")) invalidate();
  });
  document.addEventListener("click", (event) => {
    if (event.target.closest("#impact-copy")) {
      readForm();
      state.candidate = structuredClone(state.baseline);
      const sheet = document.querySelector(".impact-sheet.candidate");
      sheet.outerHTML = policySheet(
        "candidate",
        "Candidate",
        "Copied from baseline. Adjust a rule to explore its effect.",
      );
      invalidate();
    }
    const exportButton = event.target.closest("[data-impact-export]");
    if (exportButton && state.report && !state.dirty && !state.running) {
      const facet = exportButton.dataset.impactExport === "facet";
      const data = facet ? state.report.openlineage_facet : state.report;
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
      );
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `dataguard-${facet ? "assertions" : "impact"}-${state.report.sha256.slice(0, 12)}.json`;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
  });
  document.addEventListener("submit", async (event) => {
    if (event.target.id !== "impact-form") return;
    event.preventDefault();
    if (state.running) return;
    readForm();
    state.running = true;
    const submittedRevision = revision;
    const form = event.target;
    const button = form.querySelector("#impact-run");
    const error = form.querySelector("#impact-error");
    const payload = {
      capture_id: state.capture,
      analysis_at: state.clock + "Z",
      baseline: structuredClone(state.baseline),
      candidate: structuredClone(state.candidate),
    };
    button.disabled = true;
    button.textContent = "Comparing evidence…";
    error.textContent = "";
    // Freeze the input snapshot until the response arrives, so evidence always matches its form.
    for (const input of form.querySelectorAll("input, select, button"))
      input.disabled = true;
    try {
      const response = await fetch("/api/quality/contract-impact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(15000),
      });
      const data = await response.json();
      if (!response.ok)
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Check the contract fields and UTC analysis clock.",
        );
      state.report = data;
      state.dirty = revision !== submittedRevision;
      if (document.querySelector("#impact-results"))
        document.querySelector("#impact-results").innerHTML = results();
    } catch (e) {
      error.textContent = e.message;
    } finally {
      state.running = false;
      for (const input of form.querySelectorAll("input, select, button"))
        input.disabled = false;
      button.textContent = "Compare contracts ↗";
    }
  });
  return { render };
})();
