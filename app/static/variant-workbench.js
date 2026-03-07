const state = {
  payload: null,
  scopeSummary: null,
  compare: null,
  selectedJobId: null,
  promotePreview: null,
  importPreview: null,
  pendingImportFiles: [],
};

const nodes = {
  flash: document.querySelector("#flash-message"),
  projectSummary: document.querySelector("#project-summary"),
  importFolder: document.querySelector("#import-folder"),
  importResult: document.querySelector("#import-result"),
  importBatchSelect: document.querySelector("#import-batch-select"),
  devVersion: document.querySelector("#dev-version"),
  candidateRelease: document.querySelector("#candidate-release"),
  importMappingModal: document.querySelector("#import-mapping-modal"),
  importMappingSummary: document.querySelector("#import-mapping-summary"),
  importMappingBody: document.querySelector("#import-mapping-body"),
  scopeSummary: document.querySelector("#scope-summary"),
  compareVersion: document.querySelector("#compare-version"),
  compareLang: document.querySelector("#compare-lang"),
  branchCompare: document.querySelector("#branch-compare"),
  translationQueue: document.querySelector("#translation-queue"),
  masterKey: document.querySelector("#master-key"),
  masterSource: document.querySelector("#master-source"),
  masterResult: document.querySelector("#master-result"),
  promoteVersion: document.querySelector("#promote-version"),
  promotePreview: document.querySelector("#promote-preview"),
  verifyLang: document.querySelector("#verify-lang"),
  fillFolder: document.querySelector("#fill-folder"),
  qaFolder: document.querySelector("#qa-folder"),
  verificationResult: document.querySelector("#verification-result"),
  jobsList: document.querySelector("#jobs-list"),
  jobDetail: document.querySelector("#job-detail"),
};

document.querySelector("#refresh-button").addEventListener("click", () => refreshState("Refreshing state..."));
document.querySelector("#reset-demo").addEventListener("click", resetDemo);
document.querySelector("#upload-import-button").addEventListener("click", uploadImportFolder);
document.querySelector("#dev-import-button").addEventListener("click", runDevImport);
document.querySelector("#close-import-mapping").addEventListener("click", closeImportMappingModal);
document.querySelector("#cancel-import-mapping").addEventListener("click", closeImportMappingModal);
document.querySelector("#confirm-import-mapping").addEventListener("click", confirmImportMapping);
document.querySelectorAll("[data-close-import-mapping]").forEach((node) => {
  node.addEventListener("click", closeImportMappingModal);
});
document.querySelector("#compare-button").addEventListener("click", loadCompare);
document.querySelector("#master-key-button").addEventListener("click", lookupMasterKey);
document.querySelector("#master-source-button").addEventListener("click", lookupMasterSource);
document.querySelector("#promote-preview-button").addEventListener("click", runPromotePreview);
document.querySelector("#promote-execute-button").addEventListener("click", runPromoteExecute);
document.querySelector("#fill-button").addEventListener("click", runFillUpload);
document.querySelector("#qa-button").addEventListener("click", runQaUpload);

boot();

async function boot() {
  await refreshState("Loading variant workbench...");
}

async function refreshState(message = "State refreshed") {
  setFlash(message);
  state.payload = await fetchJson("/api/state");
  state.scopeSummary = await fetchJson(`/api/scopes/summary?${new URLSearchParams({ lang: selectedLang() }).toString()}`);
  renderState();
  if (nodes.compareVersion.value) {
    await loadCompare();
  }
  if (state.selectedJobId) {
    await renderJobDetail(state.selectedJobId);
  }
}

function selectedLang() {
  return nodes.compareLang.value || nodes.verifyLang.value || (state.payload?.schema.translation_columns[0] ?? "fr");
}

function renderState() {
  renderProjectSummary();
  renderImportBatches();
  renderScopeSummary();
  renderDevSelectors();
  renderJobs();
}

function renderProjectSummary() {
  const payload = state.payload;
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
      <span class="label">Release</span>
      <strong>${payload.rel_summary.count}</strong>
      <span class="meta">active rel bindings</span>
    </article>
    <article class="kpi-card">
      <span class="label">Candidate</span>
      <strong>${escapeHtml(payload.candidate_dev_version?.version || "-")}</strong>
      <span class="meta">imports ${payload.imports.length}, jobs ${payload.jobs.length}</span>
    </article>
  `;
}

function renderImportBatches() {
  const imports = state.payload.imports || [];
  nodes.importBatchSelect.innerHTML = imports
    .map((item) => `<option value="${item.import_batch_id}">#${item.import_batch_id} · ${escapeHtml(item.meta.input_dir || "uploaded bundle")}</option>`)
    .join("");
}

function renderScopeSummary() {
  const scopes = state.scopeSummary?.scopes || [];
  if (!scopes.length) {
    nodes.scopeSummary.innerHTML = `<p class="muted">No active scopes.</p>`;
    return;
  }
  nodes.scopeSummary.innerHTML = scopes.map((scope) => `
    <article class="row-card">
      <strong>${escapeHtml(scope.scope_type)}/${escapeHtml(scope.scope_value)}</strong>
      <p class="muted">entries ${scope.entry_count}</p>
      <code>${escapeHtml(JSON.stringify(scope.status_counts))}</code>
    </article>
  `).join("");
}

function renderDevSelectors() {
  const versions = (state.payload.dev_versions || []).map((item) => item.version);
  nodes.compareVersion.innerHTML = versions
    .map((version) => `<option value="${escapeHtml(version)}">${escapeHtml(version)}</option>`)
    .join("");
  if (!nodes.compareVersion.value && versions.length) {
    nodes.compareVersion.value = versions[0];
  }
  nodes.compareLang.innerHTML = (state.payload.schema.translation_columns || [])
    .map((lang) => `<option value="${escapeHtml(lang)}">${escapeHtml(lang)}</option>`)
    .join("");
  nodes.verifyLang.innerHTML = nodes.compareLang.innerHTML;
  if (!nodes.compareLang.value && state.payload.schema.translation_columns.length) {
    nodes.compareLang.value = state.payload.schema.translation_columns[0];
  }
  if (!nodes.verifyLang.value && state.payload.schema.translation_columns.length) {
    nodes.verifyLang.value = state.payload.schema.translation_columns[0];
  }
}

async function uploadImportFolder() {
  const files = Array.from(nodes.importFolder.files || []);
  if (!files.length) {
    setFlash("Select an import folder first.", true);
    return;
  }
  state.pendingImportFiles = files;
  state.importPreview = await postFolderForm("/api/imports/upload-folder/preview", files);
  renderImportMappingModal();
  openImportMappingModal();
}

async function runDevImport() {
  const importBatchId = Number(nodes.importBatchSelect.value);
  const version = nodes.devVersion.value.trim();
  if (!importBatchId || !version) {
    setFlash("Import batch and dev version are required.", true);
    return;
  }
  await runJobAction("/api/dev-versions/import", {
    import_batch_id: importBatchId,
    version,
    mark_as_candidate: nodes.candidateRelease.checked,
  });
}

async function loadCompare() {
  const version = nodes.compareVersion.value;
  if (!version) {
    nodes.branchCompare.innerHTML = `<p class="muted">Select a dev scope first.</p>`;
    nodes.translationQueue.innerHTML = `<p class="muted">Select a dev scope first.</p>`;
    return;
  }
  const params = new URLSearchParams({
    base: "rel/current",
    target: `dev/${version}`,
    lang: selectedLang(),
  });
  state.compare = await fetchJson(`/api/scopes/compare?${params.toString()}`);
  renderCompare();
}

function renderCompare() {
  if (!state.compare) {
    return;
  }
  nodes.branchCompare.innerHTML = state.compare.rows.map((row) => `
    <article class="row-card">
      <strong>${escapeHtml(row.business_key)}</strong>
      <p class="muted">${escapeHtml(row.state)} · ${escapeHtml(row.priority_status)}</p>
      <code>${escapeHtml(JSON.stringify(row.diff_categories))}</code>
    </article>
  `).join("");
  nodes.translationQueue.innerHTML = state.compare.priority_rows.map((row) => `
    <article class="row-card">
      <strong>${escapeHtml(row.business_key)}</strong>
      <p class="muted">${escapeHtml(row.priority_status)}</p>
      <code>${escapeHtml(JSON.stringify(row.diff_categories))}</code>
    </article>
  `).join("");
}

async function lookupMasterKey() {
  const businessKey = nodes.masterKey.value.trim();
  if (!businessKey) {
    setFlash("Business key is required.", true);
    return;
  }
  const result = await fetchJson(`/api/master/entries/${encodeURIComponent(businessKey)}`);
  renderMasterResult(result.results || []);
}

async function lookupMasterSource() {
  const source = nodes.masterSource.value;
  if (!source) {
    setFlash("Source is required.", true);
    return;
  }
  const params = new URLSearchParams({ source });
  const result = await fetchJson(`/api/master/search?${params.toString()}`);
  renderMasterResult(result.results || []);
}

function renderMasterResult(rows) {
  if (!rows.length) {
    nodes.masterResult.innerHTML = `<p class="muted">No active matches.</p>`;
    return;
  }
  nodes.masterResult.innerHTML = rows.map((row) => `
    <article class="row-card">
      <strong>${escapeHtml(row.business_key)}</strong>
      <p class="muted">${escapeHtml(row.scope_type)}/${escapeHtml(row.scope_value)}</p>
      <code>${escapeHtml(JSON.stringify({ source: row.source, translations: row.translations }))}</code>
    </article>
  `).join("");
}

async function runPromotePreview() {
  const version = nodes.promoteVersion.value.trim() || nodes.compareVersion.value;
  if (!version) {
    setFlash("Promote version is required.", true);
    return;
  }
  state.promotePreview = await fetchJson("/api/promote/preview", {
    method: "POST",
    body: JSON.stringify({ version }),
  });
  nodes.promotePreview.innerHTML = renderSummaryBlock("Promote Preview", state.promotePreview, state.promotePreview.report_rows);
}

async function runPromoteExecute() {
  const version = nodes.promoteVersion.value.trim() || nodes.compareVersion.value;
  if (!version) {
    setFlash("Promote version is required.", true);
    return;
  }
  await runJobAction("/api/promote/execute", { version });
}

async function runFillUpload() {
  const files = Array.from(nodes.fillFolder.files || []);
  if (!files.length) {
    setFlash("Select a fill folder first.", true);
    return;
  }
  const result = await uploadFolderJob("/api/fill/upload-folder", files, {
    lang: nodes.verifyLang.value,
  });
  nodes.verificationResult.innerHTML = renderSummaryBlock("Fill Result", result.job.summary, result.report.rows);
}

async function runQaUpload() {
  const files = Array.from(nodes.qaFolder.files || []);
  if (!files.length) {
    setFlash("Select a QA folder first.", true);
    return;
  }
  const result = await uploadFolderJob("/api/qa/upload-folder", files, {
    lang: nodes.verifyLang.value,
  });
  nodes.verificationResult.innerHTML = renderSummaryBlock("QA Result", result.job.summary, result.report.rows);
}

async function resetDemo() {
  await fetchJson("/api/demo/reset", { method: "POST" });
  state.selectedJobId = null;
  state.promotePreview = null;
  state.importPreview = null;
  state.pendingImportFiles = [];
  closeImportMappingModal();
  await refreshState("Demo reset");
}

async function runJobAction(url, payload) {
  const result = await fetchJson(url, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  state.selectedJobId = result.job.job_id;
  await refreshState(`Job ${result.job.job_id} finished`);
  await renderJobDetail(result.job.job_id);
  return result;
}

async function uploadFolderJob(url, files, extraFields = {}) {
  const result = await postFolderForm(url, files, extraFields);
  state.selectedJobId = result.job.job_id;
  await refreshState(`Job ${result.job.job_id} finished`);
  await renderJobDetail(result.job.job_id);
  return result;
}

async function confirmImportMapping() {
  if (!state.pendingImportFiles.length || !state.importPreview) {
    setFlash("No import preview is available.", true);
    return;
  }
  const mapping = collectImportMapping();
  const result = await uploadFolderJob("/api/imports/upload-folder", state.pendingImportFiles, {
    column_mapping_json: JSON.stringify(mapping),
  });
  nodes.importResult.innerHTML = renderSummaryBlock("Import Upload", result.job.summary, result.report.rows);
  closeImportMappingModal();
  state.pendingImportFiles = [];
  state.importPreview = null;
  nodes.importFolder.value = "";
}

function renderImportMappingModal() {
  const preview = state.importPreview;
  if (!preview) {
    nodes.importMappingSummary.innerHTML = "";
    nodes.importMappingBody.innerHTML = "";
    return;
  }
  nodes.importMappingSummary.innerHTML = `
    <div class="stack">
      <strong>${preview.file_count} files · ${preview.sheet_count} sheets</strong>
      <code>${escapeHtml(JSON.stringify({ missing_auto_match_sheets: preview.sheet_previews.filter((item) => !item.auto_match_ready).map((item) => item.sheet_key) }, null, 2))}</code>
    </div>
  `;
  nodes.importMappingBody.innerHTML = preview.sheet_previews.map((sheet, index) => renderMappingCard(sheet, index)).join("");
}

function renderMappingCard(sheet, index) {
  const schema = state.payload.schema;
  const mapping = sheet.suggested_mapping || {};
  const requiredFields = [
    renderMappingSelect(sheet, "business_key", "Business Key", mapping.business_key, true),
    renderMappingSelect(sheet, "source", "Source", mapping.source, true),
  ];
  const translationFields = (schema.translation_columns || []).map((lang) =>
    renderMappingSelect(sheet, `translation:${lang}`, `Translation · ${lang}`, mapping.translation_columns?.[lang] || "", true),
  );
  const remarkFields = (schema.remark_columns || []).map((remarkKey) =>
    renderMappingSelect(sheet, `remark:${remarkKey}`, `Remark · ${remarkKey}`, mapping.remark_columns?.[remarkKey] || "", true),
  );
  return `
    <article class="mapping-card" data-sheet-key="${escapeHtml(sheet.sheet_key)}">
      <strong>${index + 1}. ${escapeHtml(sheet.file_path)} · ${escapeHtml(sheet.sheet_name)}</strong>
      <p class="muted mapping-meta">Derived file_name: ${escapeHtml(sheet.derived_file_name || sheet.file_path)}</p>
      <p class="muted mapping-meta">Headers: ${escapeHtml((sheet.available_headers || []).join(", ")) || "none"}</p>
      <div class="mapping-grid">
        ${requiredFields.join("")}
        ${translationFields.join("")}
        ${remarkFields.join("")}
      </div>
    </article>
  `;
}

function renderMappingSelect(sheet, fieldKey, label, selectedValue, required) {
  const emptyLabel = required ? "Select a header" : "Not mapped";
  const availableOptions = [
    `<option value=""${selectedValue ? "" : " selected"}>${escapeHtml(emptyLabel)}</option>`,
    ...(sheet.available_headers || []).map((header) => `
      <option value="${escapeHtml(header)}"${header === selectedValue ? " selected" : ""}>${escapeHtml(header)}</option>
    `),
  ].join("");
  return `
    <label class="field compact">
      <span>${escapeHtml(label)}</span>
      <select
        data-mapping-sheet="${escapeHtml(sheet.sheet_key)}"
        data-mapping-field="${escapeHtml(fieldKey)}"
      >
        ${availableOptions}
      </select>
    </label>
  `;
}

function collectImportMapping() {
  const mappings = {};
  const schema = state.payload.schema;
  for (const sheet of state.importPreview.sheet_previews || []) {
    const sheetKey = sheet.sheet_key;
    const businessKey = readMappingField(sheetKey, "business_key");
    const source = readMappingField(sheetKey, "source");
    if (!businessKey || !source) {
      throwFlash(`Business key and source are required for ${sheetKey}.`);
    }
    const translationColumns = {};
    for (const lang of schema.translation_columns || []) {
      const value = readMappingField(sheetKey, `translation:${lang}`);
      if (!value) {
        throwFlash(`Translation column ${lang} is required for ${sheetKey}.`);
      }
      translationColumns[lang] = value;
    }
    const remarkColumns = {};
    for (const remarkKey of schema.remark_columns || []) {
      const value = readMappingField(sheetKey, `remark:${remarkKey}`);
      if (!value) {
        throwFlash(`Remark column ${remarkKey} is required for ${sheetKey}.`);
      }
      remarkColumns[remarkKey] = value;
    }
    mappings[sheetKey] = {
      business_key: businessKey,
      source,
      translation_columns: translationColumns,
      remark_columns: remarkColumns,
    };
  }
  return mappings;
}

function readMappingField(sheetKey, fieldKey) {
  const selector = `[data-mapping-sheet="${cssEscape(sheetKey)}"][data-mapping-field="${cssEscape(fieldKey)}"]`;
  const node = nodes.importMappingBody.querySelector(selector);
  return node ? node.value : "";
}

function openImportMappingModal() {
  nodes.importMappingModal.classList.remove("hidden");
}

function closeImportMappingModal() {
  nodes.importMappingModal.classList.add("hidden");
}

async function postFolderForm(url, files, extraFields = {}) {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file, file.name);
    form.append("relative_paths", file.webkitRelativePath || file.name);
  }
  Object.entries(extraFields).forEach(([key, value]) => form.append(key, value));
  const response = await fetch(url, { method: "POST", body: form });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "Request failed" }));
    setFlash(payload.detail || "Request failed", true);
    throw new Error(payload.detail || "Request failed");
  }
  return response.json();
}

function renderJobs() {
  const jobs = state.payload.jobs || [];
  if (!jobs.length) {
    nodes.jobsList.innerHTML = `<p class="muted">No jobs yet.</p>`;
    nodes.jobDetail.innerHTML = `<p class="muted">Select a job to inspect its report.</p>`;
    return;
  }
  nodes.jobsList.innerHTML = jobs.map((job) => `
    <article class="job-card" data-job-id="${job.job_id}">
      <strong>#${job.job_id} · ${escapeHtml(job.job_type)}</strong>
      <p class="muted">${escapeHtml(job.status)}</p>
    </article>
  `).join("");
  nodes.jobsList.querySelectorAll("[data-job-id]").forEach((node) => {
    node.addEventListener("click", () => renderJobDetail(Number(node.dataset.jobId)));
  });
}

async function renderJobDetail(jobId) {
  state.selectedJobId = jobId;
  const detail = await fetchJson(`/api/jobs/${jobId}`);
  nodes.jobDetail.innerHTML = renderSummaryBlock(`Job #${jobId}`, detail.job.summary, detail.report.rows);
}

function renderSummaryBlock(title, summary, rows) {
  const previewRows = (rows || []).slice(0, 20);
  return `
    <div class="stack">
      <strong>${escapeHtml(title)}</strong>
      <code>${escapeHtml(JSON.stringify(summary, null, 2))}</code>
      <code>${escapeHtml(JSON.stringify(previewRows, null, 2))}</code>
    </div>
  `;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: options.body && !(options.body instanceof FormData) ? { "Content-Type": "application/json" } : undefined,
    ...options,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "Request failed" }));
    setFlash(payload.detail || "Request failed", true);
    throw new Error(payload.detail || "Request failed");
  }
  return response.json();
}

function setFlash(message, isError = false) {
  nodes.flash.textContent = message;
  nodes.flash.classList.toggle("error", isError);
}

function throwFlash(message) {
  setFlash(message, true);
  throw new Error(message);
}

function cssEscape(value) {
  return String(value ?? "").replaceAll("\\", "\\\\").replaceAll('"', '\\"');
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
