const state = {
  payload: null,
  selectedSampleId: null,
  selectedJobId: null,
  promotePreview: null,
};

const nodes = {
  sampleSelect: document.querySelector("#sample-select"),
  flash: document.querySelector("#flash-message"),
  sampleSummary: document.querySelector("#sample-summary"),
  importsList: document.querySelector("#imports-list"),
  importResult: document.querySelector("#import-result"),
  jobsList: document.querySelector("#jobs-list"),
  jobDetail: document.querySelector("#job-detail"),
  promotePreview: document.querySelector("#promote-preview"),
  verificationResult: document.querySelector("#verification-result"),
  activeKey: document.querySelector("#active-key"),
  activeLang: document.querySelector("#active-lang"),
  activeTarget: document.querySelector("#active-target"),
  passiveKey: document.querySelector("#passive-key"),
  passiveVersion: document.querySelector("#passive-version"),
  passiveSrc: document.querySelector("#passive-src"),
  passiveTargets: document.querySelector("#passive-targets"),
  promoteReleaseVersion: document.querySelector("#promote-release-version"),
  deleteKeys: document.querySelector("#delete-keys"),
  deleteBranch: document.querySelector("#delete-branch"),
};

const branchTargets = {
  dev: document.querySelector("#branch-dev-content"),
  release: document.querySelector("#branch-release-content"),
  master: document.querySelector("#branch-master-content"),
};

document.querySelector("#reset-demo").addEventListener("click", resetDemo);
document.querySelector("#import-button").addEventListener("click", () => runImport());
document.querySelector("#update-dev-button").addEventListener("click", () => runJobAction("/api/workbench/update-dev", samplePayload()));
document.querySelector("#active-hotfix-button").addEventListener("click", runActiveHotfix);
document.querySelector("#passive-hotfix-button").addEventListener("click", runPassiveHotfix);
document.querySelector("#promote-preview-button").addEventListener("click", runPromotePreview);
document.querySelector("#promote-execute-button").addEventListener("click", () => runJobAction("/api/workbench/promote/execute", {
  release_version: nodes.promoteReleaseVersion.value.trim(),
}));
document.querySelector("#archive-button").addEventListener("click", () => runJobAction("/api/workbench/archive"));
document.querySelector("#delete-button").addEventListener("click", runDelete);
document.querySelector("#fill-button").addEventListener("click", () => runJobAction("/api/workbench/fill", samplePayload(), {
  message: "Fill finished. Download the artifact from the selected job.",
  target: nodes.verificationResult,
}));
document.querySelector("#qa-button").addEventListener("click", () => runJobAction("/api/workbench/qa", samplePayload(), {
  message: "QA report generated.",
  target: nodes.verificationResult,
}));
nodes.sampleSelect.addEventListener("change", () => {
  state.selectedSampleId = nodes.sampleSelect.value;
  applySampleDefaults();
});

boot();

async function boot() {
  await refreshState("Loading workbench state...");
}

function currentSample() {
  if (!state.payload) {
    return null;
  }
  return state.payload.samples.find((sample) => sample.sample_id === state.selectedSampleId) || state.payload.samples[0] || null;
}

function samplePayload() {
  return { sample_id: state.selectedSampleId };
}

async function refreshState(message = "State refreshed.") {
  setFlash(message);
  const payload = await fetchJson("/api/workbench/state");
  state.payload = payload;
  if (!state.selectedSampleId && payload.samples.length > 0) {
    state.selectedSampleId = payload.samples[0].sample_id;
  }
  renderState();
}

async function resetDemo() {
  await fetchJson("/api/demo/reset", { method: "POST" });
  state.promotePreview = null;
  state.selectedJobId = null;
  await refreshState("Demo environment reset.");
}

async function runImport() {
  const result = await fetchJson("/api/workbench/import", {
    method: "POST",
    body: JSON.stringify(samplePayload()),
  });
  nodes.importResult.innerHTML = renderSummaryBlock("Import result", {
    import_batch_id: result.import_batch_id,
    files_scanned: result.files_scanned,
    rows_scanned: result.rows_scanned,
    issues: result.issues,
  }, result.issues_list);
  await refreshState(`Imported batch ${result.import_batch_id}.`);
}

async function runActiveHotfix() {
  await runJobAction("/api/workbench/hotfix/active", {
    key: nodes.activeKey.value.trim(),
    lang: nodes.activeLang.value.trim(),
    target_text: nodes.activeTarget.value.trim(),
  });
}

async function runPassiveHotfix() {
  let targets = {};
  try {
    targets = JSON.parse(nodes.passiveTargets.value.trim());
  } catch (error) {
    setFlash("Passive hotfix targets must be valid JSON.", true);
    return;
  }
  await runJobAction("/api/workbench/hotfix/passive", {
    key: nodes.passiveKey.value.trim(),
    src: nodes.passiveSrc.value.trim(),
    version_tag: nodes.passiveVersion.value.trim(),
    targets_by_lang: targets,
  });
}

async function runPromotePreview() {
  const preview = await fetchJson("/api/workbench/promote/preview", {
    method: "POST",
    body: JSON.stringify({
      release_version: nodes.promoteReleaseVersion.value.trim(),
    }),
  });
  state.promotePreview = preview;
  renderPromotePreview();
  setFlash("Promote preview updated.");
}

async function runDelete() {
  const keys = nodes.deleteKeys.value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
  await runJobAction("/api/workbench/delete", {
    branch: nodes.deleteBranch.value,
    keys,
  });
}

async function runJobAction(url, payload = null, options = {}) {
  const result = await fetchJson(url, {
    method: "POST",
    body: payload ? JSON.stringify(payload) : undefined,
  });
  state.selectedJobId = result.job.job_id;
  if (options.target) {
    options.target.innerHTML = renderSummaryBlock(options.message || result.job.job_type, result.job.summary, result.report.rows);
  }
  await refreshState(`Job ${result.job.job_id} finished.`);
  await renderJobDetail(result.job.job_id);
}

function renderState() {
  renderSamples();
  renderBranches();
  renderImports();
  renderJobs();
  renderPromotePreview();
}

function renderSamples() {
  const samples = state.payload.samples || [];
  nodes.sampleSelect.innerHTML = samples
    .map((sample) => `<option value="${escapeHtml(sample.sample_id)}">${escapeHtml(sample.label)}</option>`)
    .join("");
  nodes.sampleSelect.value = state.selectedSampleId;
  const sample = currentSample();
  if (!sample) {
    nodes.sampleSummary.innerHTML = `<p class="muted">No samples available.</p>`;
    return;
  }
  nodes.sampleSummary.innerHTML = `
    <strong>${escapeHtml(sample.label)}</strong>
    <p>${escapeHtml(sample.description)}</p>
    <div class="summary-chips">
      <span>lang: ${escapeHtml(sample.lang)}</span>
      <span>update dev: ${escapeHtml(sample.update_dev_version)}</span>
      <span>promote: ${escapeHtml(sample.promote_release_version)}</span>
    </div>
  `;
  applySampleDefaults();
}

function applySampleDefaults() {
  const sample = currentSample();
  if (!sample) {
    return;
  }
  nodes.activeKey.value = sample.active_hotfix.key;
  nodes.activeLang.value = sample.active_hotfix.lang;
  nodes.activeTarget.value = sample.active_hotfix.target_text;
  nodes.passiveKey.value = sample.passive_hotfix.key;
  nodes.passiveVersion.value = sample.passive_hotfix.version_tag;
  nodes.passiveSrc.value = sample.passive_hotfix.src;
  nodes.passiveTargets.value = JSON.stringify(sample.passive_hotfix.targets_by_lang, null, 2);
  nodes.promoteReleaseVersion.value = sample.promote_release_version;
  nodes.deleteKeys.value = sample.delete_keys.join("\n");
}

function renderBranches() {
  Object.entries(branchTargets).forEach(([branch, target]) => {
    const entry = state.payload.branches[branch];
    target.innerHTML = renderDefinitionList({
      snapshot_id: entry.snapshot_id,
      action_type: entry.action_type,
      created_at: entry.created_at,
      parent_snapshot_id: entry.parent_snapshot_id,
      key_count: entry.key_count,
      meta: JSON.stringify(entry.meta || {}),
    });
  });
}

function renderImports() {
  const imports = state.payload.imports || [];
  if (imports.length === 0) {
    nodes.importsList.innerHTML = `<p class="muted">No imports yet.</p>`;
    return;
  }
  nodes.importsList.innerHTML = `
    <ul>
      ${imports.map((item) => `
        <li>
          <strong>Batch #${item.import_batch_id}</strong>
          <div class="job-meta">rows ${item.rows_scanned} | files ${item.files_scanned} | issues ${item.issues}</div>
          <div class="job-meta">${escapeHtml(JSON.stringify(item.meta || {}))}</div>
        </li>
      `).join("")}
    </ul>
  `;
}

function renderJobs() {
  const jobs = state.payload.jobs || [];
  if (jobs.length === 0) {
    nodes.jobsList.innerHTML = `<p class="muted">No jobs yet.</p>`;
    nodes.jobDetail.innerHTML = `<p class="muted">Select a job to inspect summary, report rows, and artifacts.</p>`;
    return;
  }
  nodes.jobsList.innerHTML = `
    <ul>
      ${jobs.map((job) => `
        <li class="job-row">
          <button type="button" data-job-id="${job.job_id}">
            <strong>#${job.job_id} | ${escapeHtml(job.job_type)}</strong>
            <div class="job-meta">status ${escapeHtml(job.status)} | snapshot ${job.snapshot_id ?? "-"}</div>
            <div class="job-meta">${escapeHtml(JSON.stringify(job.summary || {}))}</div>
          </button>
        </li>
      `).join("")}
    </ul>
  `;
  nodes.jobsList.querySelectorAll("button[data-job-id]").forEach((button) => {
    button.addEventListener("click", () => renderJobDetail(Number(button.dataset.jobId)));
  });
  if (state.selectedJobId) {
    renderJobDetail(state.selectedJobId);
  }
}

async function renderJobDetail(jobId) {
  state.selectedJobId = jobId;
  const detail = await fetchJson(`/api/jobs/${jobId}`);
  const artifact = detail.job.artifact_path
    ? `<p><a href="/api/jobs/${jobId}/artifact/${encodeURIComponent(detail.job.artifact_path.split(/[\\/]/).pop())}">Download artifact</a></p>`
    : "";
  nodes.jobDetail.innerHTML = `
    <div class="summary-chips">
      <span>job #${detail.job.job_id}</span>
      <span>${escapeHtml(detail.job.job_type)}</span>
      <span>${escapeHtml(detail.job.status)}</span>
      <span>snapshot ${detail.job.snapshot_id ?? "-"}</span>
    </div>
    <pre>${escapeHtml(JSON.stringify(detail.job.summary || {}, null, 2))}</pre>
    ${artifact}
    ${renderTable(detail.report.rows)}
  `;
}

function renderPromotePreview() {
  if (!state.promotePreview) {
    nodes.promotePreview.innerHTML = `<p class="muted">Generate a promote preview before executing the release promote.</p>`;
    return;
  }
  const preview = state.promotePreview;
  nodes.promotePreview.innerHTML = renderSummaryBlock("Promote Preview", {
    target_key_count: preview.target_key_count,
    added_count: preview.added_count,
    conflict_src_changed_count: preview.conflict_src_changed_count,
    carried_over_count: preview.carried_over_count,
    deprecated_count: preview.deprecated_count,
  }, preview.report_rows);
}

function renderSummaryBlock(title, summary, rows) {
  return `
    <strong class="result-title">${escapeHtml(title)}</strong>
    <div class="summary-chips">
      ${Object.entries(summary || {}).map(([key, value]) => `<span>${escapeHtml(key)}: ${escapeHtml(formatValue(value))}</span>`).join("")}
    </div>
    ${renderTable(rows)}
  `;
}

function renderTable(rows) {
  if (!rows || rows.length === 0) {
    return `<p class="muted">No detail rows.</p>`;
  }
  const columns = Object.keys(rows[0]);
  return `
    <table>
      <thead>
        <tr>${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("")}</tr>
      </thead>
      <tbody>
        ${rows.map((row) => `
          <tr>${columns.map((column) => `<td>${escapeHtml(String(row[column] ?? ""))}</td>`).join("")}</tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function renderDefinitionList(data) {
  return Object.entries(data).map(([key, value]) => `
    <dt>${escapeHtml(key)}</dt>
    <dd>${escapeHtml(String(value ?? "-"))}</dd>
  `).join("");
}

async function fetchJson(url, options = {}) {
  const request = {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  };
  try {
    const response = await fetch(url, request);
    const text = await response.text();
    const payload = text ? JSON.parse(text) : {};
    if (!response.ok) {
      throw new Error(payload.detail || `${response.status} ${response.statusText}`);
    }
    return payload;
  } catch (error) {
    setFlash(error.message || "Request failed.", true);
    throw error;
  }
}

function setFlash(message, isError = false) {
  nodes.flash.textContent = message;
  nodes.flash.style.background = isError ? "rgba(162, 58, 47, 0.12)" : "rgba(15, 118, 110, 0.08)";
  nodes.flash.style.color = isError ? "#7d2c24" : "#0c5b55";
}

function formatValue(value) {
  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
