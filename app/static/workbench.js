const state = {
  payload: null,
  strings: [],
  selectedSampleId: null,
  selectedJobId: null,
  promotePreview: null,
};

const nodes = {
  sampleSelect: document.querySelector("#sample-select"),
  flash: document.querySelector("#flash-message"),
  projectSummary: document.querySelector("#project-summary"),
  stringSearch: document.querySelector("#string-search"),
  includeDeleted: document.querySelector("#include-deleted"),
  stringList: document.querySelector("#string-list"),
  trashKeys: document.querySelector("#trash-keys"),
  trashResult: document.querySelector("#trash-result"),
  importResult: document.querySelector("#import-result"),
  importBatchSelect: document.querySelector("#import-batch-select"),
  devVersion: document.querySelector("#dev-version"),
  candidateRelease: document.querySelector("#candidate-release"),
  devVersionsList: document.querySelector("#dev-versions-list"),
  relSummary: document.querySelector("#rel-summary"),
  activeKey: document.querySelector("#active-key"),
  activeLang: document.querySelector("#active-lang"),
  activeTarget: document.querySelector("#active-target"),
  passiveKey: document.querySelector("#passive-key"),
  passiveFileName: document.querySelector("#passive-file-name"),
  passiveSource: document.querySelector("#passive-source"),
  passiveTranslations: document.querySelector("#passive-translations"),
  passiveRemarks: document.querySelector("#passive-remarks"),
  promoteVersion: document.querySelector("#promote-version"),
  promotePreview: document.querySelector("#promote-preview"),
  verificationResult: document.querySelector("#verification-result"),
  jobsList: document.querySelector("#jobs-list"),
  jobDetail: document.querySelector("#job-detail"),
};

document.querySelector("#reset-demo").addEventListener("click", resetDemo);
document.querySelector("#strings-refresh").addEventListener("click", () => refreshState("刷新 strings..."));
document.querySelector("#import-sample-button").addEventListener("click", runImportSample);
document.querySelector("#dev-import-button").addEventListener("click", runDevImport);
document.querySelector("#active-hotfix-button").addEventListener("click", runActiveHotfix);
document.querySelector("#passive-hotfix-button").addEventListener("click", runPassiveHotfix);
document.querySelector("#promote-preview-button").addEventListener("click", runPromotePreview);
document.querySelector("#promote-execute-button").addEventListener("click", runPromoteExecute);
document.querySelector("#trash-delete-button").addEventListener("click", () => runTrash("/api/trash/delete", nodes.trashResult));
document.querySelector("#trash-restore-button").addEventListener("click", () => runTrash("/api/trash/restore", nodes.trashResult));
document.querySelector("#fill-button").addEventListener("click", runFill);
document.querySelector("#qa-button").addEventListener("click", runQa);
nodes.sampleSelect.addEventListener("change", () => {
  state.selectedSampleId = nodes.sampleSelect.value;
  applySampleDefaults();
});
nodes.stringSearch.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    refreshState("搜索 strings...");
  }
});

boot();

async function boot() {
  await refreshState("加载 workbench 状态...");
}

function currentSample() {
  if (!state.payload) {
    return null;
  }
  return state.payload.samples.find((sample) => sample.sample_id === state.selectedSampleId) || state.payload.samples[0] || null;
}

async function refreshState(message = "状态已刷新") {
  setFlash(message);
  state.payload = await fetchJson("/api/state");
  if (!state.selectedSampleId && state.payload.samples.length > 0) {
    state.selectedSampleId = state.payload.samples[0].sample_id;
  }
  renderState();
  await loadStrings();
  if (state.selectedJobId) {
    await renderJobDetail(state.selectedJobId);
  }
}

async function loadStrings() {
  const search = nodes.stringSearch.value.trim();
  const includeDeleted = nodes.includeDeleted.checked;
  const params = new URLSearchParams();
  if (search) {
    params.set("search", search);
  }
  if (includeDeleted) {
    params.set("include_deleted", "true");
  }
  state.strings = await fetchJson(`/api/strings?${params.toString()}`);
  renderStrings();
}

async function resetDemo() {
  state.payload = await fetchJson("/api/demo/reset", { method: "POST" });
  state.promotePreview = null;
  state.selectedJobId = null;
  if (state.payload.samples.length > 0) {
    state.selectedSampleId = state.payload.samples[0].sample_id;
  }
  renderState();
  await loadStrings();
  setFlash("演示环境已重置");
}

async function runImportSample() {
  const sample = currentSample();
  if (!sample) {
    return;
  }
  const result = await runJobAction("/api/imports/directory", { input_dir: sample.paths.import_dir });
  nodes.importResult.innerHTML = renderSummaryBlock("Import Batch", result.job.summary, result.report.rows);
}

async function runDevImport() {
  const importBatchId = Number(nodes.importBatchSelect.value);
  if (!importBatchId) {
    setFlash("先导入一个 batch。", true);
    return;
  }
  const version = nodes.devVersion.value.trim();
  if (!version) {
    setFlash("dev version 不能为空。", true);
    return;
  }
  await runJobAction("/api/dev-versions/import", {
    import_batch_id: importBatchId,
    version,
    mark_as_candidate: nodes.candidateRelease.checked,
  });
}

async function runActiveHotfix() {
  await runJobAction("/api/rel/hotfix/active", {
    business_key: nodes.activeKey.value.trim(),
    lang: nodes.activeLang.value.trim(),
    target_text: nodes.activeTarget.value.trim(),
  });
}

async function runPassiveHotfix() {
  const translations = parseJsonField(nodes.passiveTranslations.value, "translations_by_lang");
  if (translations === null) {
    return;
  }
  const remarks = parseJsonField(nodes.passiveRemarks.value, "remarks_by_key");
  if (remarks === null) {
    return;
  }
  await runJobAction("/api/rel/hotfix/passive", {
    business_key: nodes.passiveKey.value.trim(),
    file_name: nodes.passiveFileName.value.trim() || null,
    source: nodes.passiveSource.value.trim(),
    translations_by_lang: translations,
    remarks_by_key: remarks,
  });
}

async function runPromotePreview() {
  const version = nodes.promoteVersion.value.trim();
  if (!version) {
    setFlash("promote version 不能为空。", true);
    return;
  }
  state.promotePreview = await fetchJson("/api/promote/preview", {
    method: "POST",
    body: JSON.stringify({ version }),
  });
  renderPromotePreview();
  setFlash("promote preview 已生成");
}

async function runPromoteExecute() {
  const version = nodes.promoteVersion.value.trim();
  if (!version) {
    setFlash("promote version 不能为空。", true);
    return;
  }
  await runJobAction("/api/promote/execute", { version });
}

async function runTrash(url, targetNode) {
  const businessKeys = nodes.trashKeys.value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
  if (businessKeys.length === 0) {
    setFlash("需要至少一个 business_key。", true);
    return;
  }
  const result = await runJobAction(url, { business_keys: businessKeys });
  targetNode.innerHTML = renderSummaryBlock(result.job.job_type, result.job.summary, result.report.rows);
}

async function runFill() {
  const sample = currentSample();
  if (!sample) {
    return;
  }
  const result = await runJobAction("/api/fill", {
    source_dir: sample.paths.fill_dir,
    lang: sample.lang,
  });
  nodes.verificationResult.innerHTML = renderSummaryBlock("Fill Result", result.job.summary, result.report.rows);
}

async function runQa() {
  const sample = currentSample();
  if (!sample) {
    return;
  }
  const result = await runJobAction("/api/qa", {
    source_dir: sample.paths.fill_dir,
    lang: sample.lang,
  });
  nodes.verificationResult.innerHTML = renderSummaryBlock("QA Result", result.job.summary, result.report.rows);
}

async function runJobAction(url, payload) {
  const result = await fetchJson(url, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  state.selectedJobId = result.job.job_id;
  await refreshState(`Job ${result.job.job_id} 完成`);
  await renderJobDetail(result.job.job_id);
  return result;
}

function renderState() {
  renderSamples();
  renderProjectSummary();
  renderImports();
  renderDevVersions();
  renderRelSummary();
  renderJobs();
  renderPromotePreview();
}

function renderSamples() {
  const samples = state.payload.samples || [];
  nodes.sampleSelect.innerHTML = samples
    .map((sample) => `<option value="${escapeHtml(sample.sample_id)}">${escapeHtml(sample.label)}</option>`)
    .join("");
  if (samples.length > 0) {
    nodes.sampleSelect.value = state.selectedSampleId;
    applySampleDefaults();
  }
}

function applySampleDefaults() {
  const sample = currentSample();
  if (!sample) {
    return;
  }
  nodes.devVersion.value = sample.dev_version;
  nodes.activeKey.value = sample.active_hotfix.business_key || "";
  nodes.activeLang.value = sample.active_hotfix.lang || sample.lang || "";
  nodes.activeTarget.value = sample.active_hotfix.target_text || "";
  nodes.passiveKey.value = sample.passive_hotfix.business_key || "";
  nodes.passiveFileName.value = sample.passive_hotfix.file_name || "";
  nodes.passiveSource.value = sample.passive_hotfix.source || "";
  nodes.passiveTranslations.value = JSON.stringify(sample.passive_hotfix.translations_by_lang || {}, null, 2);
  nodes.passiveRemarks.value = JSON.stringify(sample.passive_hotfix.remarks_by_key || {}, null, 2);
  nodes.promoteVersion.value = sample.dev_version || "";
  nodes.trashKeys.value = (sample.trash_keys || []).join("\n");
}

function renderProjectSummary() {
  const payload = state.payload;
  const candidate = payload.candidate_dev_version ? payload.candidate_dev_version.version : "-";
  nodes.projectSummary.innerHTML = `
    <article class="kpi-card">
      <span class="label">Project</span>
      <strong>${escapeHtml(payload.project.name)}</strong>
      <span class="meta">id ${payload.project.project_id}</span>
    </article>
    <article class="kpi-card">
      <span class="label">Schema</span>
      <strong>${escapeHtml(payload.schema.translation_columns.join(", "))}</strong>
      <span class="meta">remarks ${escapeHtml(payload.schema.remark_columns.join(", "))}</span>
    </article>
    <article class="kpi-card">
      <span class="label">Rel</span>
      <strong>${payload.rel_summary.count}</strong>
      <span class="meta">current rel members</span>
    </article>
    <article class="kpi-card">
      <span class="label">Candidate</span>
      <strong>${escapeHtml(candidate)}</strong>
      <span class="meta">trash ${payload.trash_count}</span>
    </article>
  `;
}

function renderStrings() {
  if (!state.strings || state.strings.length === 0) {
    nodes.stringList.innerHTML = `<p class="muted">没有 strings。</p>`;
    return;
  }
  nodes.stringList.innerHTML = state.strings
    .map((item) => {
      const chips = (item.memberships || []).map((membership) => {
        const label = membership.membership_type === "rel"
          ? "rel"
          : `dev:${membership.membership_value}`;
        return `<span class="chip">${escapeHtml(label)}</span>`;
      }).join("");
      const deleted = item.deleted_at
        ? `<span class="chip danger">trash until ${escapeHtml(item.trash_until || "")}</span>`
        : "";
      return `
        <article class="string-row">
          <div class="string-head">
            <strong>${escapeHtml(item.business_key)}</strong>
            <span class="mono">${escapeHtml(item.file_name || "-")}</span>
          </div>
          <p>${escapeHtml(item.source)}</p>
          <div class="chip-row">${chips}${deleted}</div>
          <div class="string-meta">
            <span>fr: ${escapeHtml(item.translations.fr ?? "")}</span>
            <span>en: ${escapeHtml(item.translations.en ?? "")}</span>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderImports() {
  const imports = state.payload.imports || [];
  if (imports.length === 0) {
    nodes.importBatchSelect.innerHTML = `<option value="">No imports</option>`;
    return;
  }
  const previousValue = nodes.importBatchSelect.value;
  nodes.importBatchSelect.innerHTML = imports
    .map((item) => `<option value="${item.import_batch_id}">#${item.import_batch_id} | rows ${item.rows_scanned} | issues ${item.issues}</option>`)
    .join("");
  nodes.importBatchSelect.value = previousValue || String(imports[0].import_batch_id);
}

function renderDevVersions() {
  const versions = state.payload.dev_versions || [];
  if (versions.length === 0) {
    nodes.devVersionsList.innerHTML = `<p class="muted">当前没有活跃 dev versions。</p>`;
    return;
  }
  nodes.devVersionsList.innerHTML = `
    <ul>
      ${versions.map((item) => `
        <li>
          <strong>${escapeHtml(item.version)}</strong>
          <div class="job-meta">line ${escapeHtml(item.version_line)} | members ${item.member_count}</div>
          <div class="job-meta">candidate ${item.is_candidate_release ? "yes" : "no"}</div>
        </li>
      `).join("")}
    </ul>
  `;
}

function renderRelSummary() {
  const rel = state.payload.rel_summary || { count: 0, business_keys: [] };
  nodes.relSummary.innerHTML = renderSummaryBlock("Current Rel", {
    count: rel.count,
    sample_keys: rel.business_keys.join(", "),
  });
}

function renderPromotePreview() {
  if (!state.promotePreview) {
    nodes.promotePreview.innerHTML = `<p class="muted">尚未生成 promote preview。</p>`;
    return;
  }
  nodes.promotePreview.innerHTML = renderSummaryBlock("Promote Preview", {
    version: state.promotePreview.version,
    target_key_count: state.promotePreview.target_key_count,
    added_to_rel_count: state.promotePreview.added_to_rel_count,
    already_in_rel_count: state.promotePreview.already_in_rel_count,
    removed_from_rel_count: state.promotePreview.removed_from_rel_count,
    cleanup_dev_membership_count: state.promotePreview.cleanup_dev_membership_count,
  }, state.promotePreview.report_rows);
}

function renderJobs() {
  const jobs = state.payload.jobs || [];
  if (jobs.length === 0) {
    nodes.jobsList.innerHTML = `<p class="muted">No jobs yet.</p>`;
    nodes.jobDetail.innerHTML = `<p class="muted">选择一个 job 查看 summary、report rows 和 artifact。</p>`;
    return;
  }
  nodes.jobsList.innerHTML = `
    <ul>
      ${jobs.map((job) => `
        <li class="job-row">
          <button type="button" data-job-id="${job.job_id}">
            <strong>#${job.job_id} | ${escapeHtml(job.job_type)}</strong>
            <div class="job-meta">status ${escapeHtml(job.status)} | ${escapeHtml(job.created_at)}</div>
          </button>
        </li>
      `).join("")}
    </ul>
  `;
  nodes.jobsList.querySelectorAll("button[data-job-id]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.selectedJobId = Number(button.dataset.jobId);
      await renderJobDetail(state.selectedJobId);
    });
  });
}

async function renderJobDetail(jobId) {
  const detail = await fetchJson(`/api/jobs/${jobId}`);
  const artifactLink = detail.job.artifact_path
    ? `<a href="/api/jobs/${detail.job.job_id}/artifact/${encodeURIComponent(detail.job.artifact_path.split("/").pop())}">Download artifact</a>`
    : "No artifact";
  nodes.jobDetail.innerHTML = `
    <div class="detail-head">
      <strong>#${detail.job.job_id} | ${escapeHtml(detail.job.job_type)}</strong>
      <span class="mono">${escapeHtml(detail.job.status)}</span>
    </div>
    ${renderDefinitionList(detail.job.summary || {})}
    <div class="chip-row"><span class="chip">${artifactLink}</span></div>
    ${renderRows(detail.report.rows || [])}
  `;
}

function renderSummaryBlock(title, summary, rows = []) {
  return `
    <div class="detail-head">
      <strong>${escapeHtml(title)}</strong>
    </div>
    ${renderDefinitionList(summary || {})}
    ${rows.length > 0 ? renderRows(rows) : `<p class="muted">No rows.</p>`}
  `;
}

function renderRows(rows) {
  if (!rows || rows.length === 0) {
    return `<p class="muted">No rows.</p>`;
  }
  return `
    <pre class="code">${escapeHtml(JSON.stringify(rows, null, 2))}</pre>
  `;
}

function renderDefinitionList(payload) {
  return `
    <dl>
      ${Object.entries(payload || {})
        .map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(formatValue(value))}</dd>`)
        .join("")}
    </dl>
  `;
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function parseJsonField(raw, label) {
  try {
    return raw.trim() ? JSON.parse(raw) : {};
  } catch (error) {
    setFlash(`${label} 必须是合法 JSON。`, true);
    return null;
  }
}

function setFlash(message, isError = false) {
  nodes.flash.textContent = message;
  nodes.flash.classList.toggle("error", isError);
}

async function fetchJson(url, options = {}) {
  const init = {
    headers: { "Content-Type": "application/json" },
    ...options,
  };
  const response = await fetch(url, init);
  let payload = null;
  const text = await response.text();
  if (text) {
    payload = JSON.parse(text);
  }
  if (!response.ok) {
    const message = payload && payload.detail ? payload.detail : response.statusText;
    setFlash(message, true);
    throw new Error(message);
  }
  return payload;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
