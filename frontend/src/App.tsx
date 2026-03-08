import { useEffect, useMemo, useRef, useState } from "react";

type AppRoute = "overview" | "compare" | "queue" | "master" | "imports" | "inspection" | "project-new";

type ProjectSummary = {
  project_id: number;
  name: string;
  is_default: boolean;
  created_at: string;
};

type ProductBootstrapResponse = {
  project: ProjectSummary;
  schema: { translation_columns: string[]; remark_columns: string[] };
  candidate_dev_version: { version: string } | null;
  dev_versions: Array<{ version: string; version_line: string; is_candidate_release: boolean }>;
  imports: ImportBatchSummary[];
  jobs: JobSummary[];
};

type ImportBatchSummary = {
  import_batch_id: number;
  project_id: number;
  created_at: string;
  meta: Record<string, unknown>;
  rows_scanned: number;
  files_scanned: number;
  issues: number;
};

type JobStageSummary = {
  stage: string;
  elapsed_ms: number;
  meta: Record<string, unknown>;
};

type JobSummary = {
  job_id: number;
  project_id: number;
  job_type: string;
  status: string;
  input: Record<string, unknown>;
  summary: Record<string, unknown>;
  report_path: string | null;
  artifact_path: string | null;
  error_message: string | null;
  created_at: string;
  finished_at?: string | null;
};

type JobDetail = {
  job: JobSummary;
  report: { summary: Record<string, unknown>; rows: Array<Record<string, unknown>> };
};

type ScopeSummaryResponse = {
  scopes: Array<{
    scope_type: string;
    scope_value: string;
    entry_count: number;
    status_counts: Record<string, number>;
    version_line?: string | null;
    is_candidate_release?: boolean | null;
  }>;
};

type BranchSide = {
  file_name: string | null;
  source: string;
  translations: Record<string, string>;
  remarks: Record<string, string>;
};

type BranchCompareRow = {
  business_key: string;
  state: string;
  diff_categories: string[];
  priority_status: string;
  base: BranchSide | null;
  target: BranchSide | null;
};

type BranchCompareResponse = {
  base_scope: string;
  target_scope: string;
  status_counts: Record<string, number>;
  rows: BranchCompareRow[];
  total_rows: number;
  page: number;
  page_size: number;
};

type QueueRow = {
  business_key: string;
  priority_status: string;
  state: string;
  diff_categories: string[];
  file_name: string | null;
  source: string;
  target_text: string;
};

type TranslationQueueResponse = {
  target_scope: string;
  lang: string | null;
  status_counts: Record<string, number>;
  rows: QueueRow[];
  total_rows: number;
  page: number;
  page_size: number;
};

type MasterRow = {
  business_key: string;
  scope_type: string;
  scope_value: string;
  file_name: string | null;
  source: string;
  translations: Record<string, string>;
  remarks: Record<string, string>;
};

type MasterResponse = {
  results: MasterRow[];
};

type ImportPreview = {
  schema: { translation_columns: string[]; remark_columns: string[] };
  file_count: number;
  sheet_count: number;
  sheet_previews: ImportSheetPreview[];
};

type ImportSheetPreview = {
  sheet_key: string;
  file_path: string;
  derived_file_name: string;
  sheet_name: string;
  available_headers: string[];
  missing_targets: string[];
  auto_match_ready: boolean;
};

type ImportSheetMapping = {
  business_key: string;
  source: string;
  translation_columns: Record<string, string>;
  remark_columns: Record<string, string>;
};

type PromotePreview = Record<string, unknown> & { report_rows?: Array<Record<string, unknown>> };

type VariantBindingSummary = {
  scope_type: string;
  scope_value: string;
  created_at: string;
  updated_at: string;
};

type EntryVariantInspection = {
  variant_id: number;
  file_name: string | null;
  source: string;
  translations: Record<string, string>;
  remarks: Record<string, string>;
  bindings: VariantBindingSummary[];
  is_orphaned: boolean;
  is_trashed: boolean;
  orphaned_at: string | null;
  trashed_at: string | null;
  trash_until: string | null;
  restored_at: string | null;
  created_at: string;
  updated_at: string;
};

type EntryVariantsResponse = {
  project_id: number;
  entry_id: number;
  business_key: string;
  variants: EntryVariantInspection[];
};

type OrphanVariantSummary = {
  project_id: number;
  entry_id: number;
  business_key: string;
  variant_id: number;
  file_name: string | null;
  source: string;
  translations: Record<string, string>;
  remarks: Record<string, string>;
  orphaned_at: string;
  updated_at: string;
};

type OrphanVariantsResponse = {
  project_id: number;
  results: OrphanVariantSummary[];
};

const PAGE_SIZE = 25;
const PROJECT_STORAGE_KEY = "momo_tms_selected_project_id";
const NAV_ITEMS: Array<{ route: AppRoute; label: string }> = [
  { route: "overview", label: "Branch Overview" },
  { route: "compare", label: "Branch Compare" },
  { route: "queue", label: "Translation Queue" },
  { route: "master", label: "Master Query" },
  { route: "imports", label: "Imports & Jobs" },
  { route: "inspection", label: "Inspection" },
];

export function App() {
  const [route, setRoute] = useState<AppRoute>(() => parseRoute(window.location.pathname));
  const [projectsLoaded, setProjectsLoaded] = useState(false);
  const [flash, setFlash] = useState<{ message: string; error: boolean }>({
    message: "Loading product app...",
    error: false,
  });
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [bootstrap, setBootstrap] = useState<ProductBootstrapResponse | null>(null);
  const [scopeSummary, setScopeSummary] = useState<ScopeSummaryResponse | null>(null);
  const [selectedLang, setSelectedLang] = useState("fr");
  const [baseScope, setBaseScope] = useState("rel/current");
  const [targetScope, setTargetScope] = useState("");
  const [queueTargetScope, setQueueTargetScope] = useState("");
  const [compare, setCompare] = useState<BranchCompareResponse | null>(null);
  const [queue, setQueue] = useState<TranslationQueueResponse | null>(null);
  const [compareSearch, setCompareSearch] = useState("");
  const [compareState, setCompareState] = useState("");
  const [compareDiff, setCompareDiff] = useState("");
  const [queueStatus, setQueueStatus] = useState("");
  const [queueSearch, setQueueSearch] = useState("");
  const [comparePage, setComparePage] = useState(1);
  const [queuePage, setQueuePage] = useState(1);
  const [masterKey, setMasterKey] = useState("");
  const [masterSource, setMasterSource] = useState("");
  const [masterRows, setMasterRows] = useState<MasterRow[]>([]);
  const [masterMode, setMasterMode] = useState<"key" | "source">("key");
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [jobDetail, setJobDetail] = useState<JobDetail | null>(null);
  const [importPreview, setImportPreview] = useState<ImportPreview | null>(null);
  const [importMappings, setImportMappings] = useState<Record<string, ImportSheetMapping>>({});
  const [pendingImportFiles, setPendingImportFiles] = useState<File[]>([]);
  const [showImportModal, setShowImportModal] = useState(false);
  const [promotePreview, setPromotePreview] = useState<PromotePreview | null>(null);
  const [devVersionInput, setDevVersionInput] = useState("");
  const [promoteVersion, setPromoteVersion] = useState("");
  const [selectedImportBatch, setSelectedImportBatch] = useState("");
  const [candidateRelease, setCandidateRelease] = useState(true);
  const [inspectionLookupKey, setInspectionLookupKey] = useState("");
  const [inspectionEntry, setInspectionEntry] = useState<EntryVariantsResponse | null>(null);
  const [orphanVariants, setOrphanVariants] = useState<OrphanVariantSummary[]>([]);
  const [createProjectName, setCreateProjectName] = useState("");
  const [createTranslationColumns, setCreateTranslationColumns] = useState("fr, en");
  const [createRemarkColumns, setCreateRemarkColumns] = useState("context");
  const [isBusy, setIsBusy] = useState(false);

  const importInputRef = useRef<HTMLInputElement | null>(null);
  const fillInputRef = useRef<HTMLInputElement | null>(null);
  const qaInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const onPopState = () => setRoute(parseRoute(window.location.pathname));
    window.addEventListener("popstate", onPopState);
    void refreshProjects("Loading product app...");
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  function clearFolderInputs() {
    if (importInputRef.current) {
      importInputRef.current.value = "";
    }
    if (fillInputRef.current) {
      fillInputRef.current.value = "";
    }
    if (qaInputRef.current) {
      qaInputRef.current.value = "";
    }
  }

  function resetProjectScopedUi() {
    setBootstrap(null);
    setScopeSummary(null);
    setCompare(null);
    setQueue(null);
    setCompareSearch("");
    setCompareState("");
    setCompareDiff("");
    setQueueStatus("");
    setQueueSearch("");
    setComparePage(1);
    setQueuePage(1);
    setMasterKey("");
    setMasterSource("");
    setMasterRows([]);
    setMasterMode("key");
    setSelectedJobId(null);
    setJobDetail(null);
    setImportPreview(null);
    setImportMappings({});
    setPendingImportFiles([]);
    setShowImportModal(false);
    setPromotePreview(null);
    setPromoteVersion("");
    setDevVersionInput("");
    setSelectedImportBatch("");
    setInspectionLookupKey("");
    setInspectionEntry(null);
    setOrphanVariants([]);
    clearFolderInputs();
  }

  useEffect(() => {
    if (!projectsLoaded) {
      return;
    }
    if (projects.length === 0) {
      clearStoredProjectId();
      resetProjectScopedUi();
      setSelectedProjectId(null);
      return;
    }
    const storedProjectId = getStoredProjectId();
    if (storedProjectId && projects.some((project) => project.project_id === storedProjectId)) {
      if (selectedProjectId !== storedProjectId) {
        setSelectedProjectId(storedProjectId);
      }
      return;
    }
    if (!selectedProjectId || !projects.some((project) => project.project_id === selectedProjectId)) {
      const fallback = projects[0].project_id;
      setSelectedProjectId(fallback);
      setStoredProjectId(fallback);
    }
  }, [projects, projectsLoaded, selectedProjectId]);

  useEffect(() => {
    if (!selectedProjectId) {
      resetProjectScopedUi();
      return;
    }
    void refreshProjectState(selectedProjectId, "Project loaded");
  }, [selectedProjectId]);

  useEffect(() => {
    if (!bootstrap) {
      return;
    }
    if (
      bootstrap.schema.translation_columns.length > 0 &&
      !bootstrap.schema.translation_columns.includes(selectedLang)
    ) {
      setSelectedLang(bootstrap.schema.translation_columns[0]);
    }
    const importBatchValues = bootstrap.imports.map((item) => String(item.import_batch_id));
    if (importBatchValues.length === 0) {
      setSelectedImportBatch("");
    } else if (!importBatchValues.includes(selectedImportBatch)) {
      setSelectedImportBatch(importBatchValues[0]);
    }
  }, [bootstrap, selectedImportBatch, selectedLang]);

  useEffect(() => {
    if (!scopeSummary) {
      return;
    }
    const scopeOptions = buildScopeOptions(scopeSummary.scopes);
    if (!scopeOptions.some((option) => option.value === baseScope)) {
      setBaseScope(scopeOptions.find((option) => option.value === "rel/current")?.value || scopeOptions[0]?.value || "");
    }
    if (!scopeOptions.some((option) => option.value === targetScope) || targetScope === baseScope) {
      const nextTarget = scopeOptions.find((option) => option.value !== (baseScope || "rel/current"))?.value || "";
      setTargetScope(nextTarget);
    }
    const devOptions = scopeSummary.scopes
      .filter((scope) => scope.scope_type === "dev")
      .map((scope) => `dev/${scope.scope_value}`);
    if (!devOptions.includes(queueTargetScope)) {
      setQueueTargetScope(devOptions[0] || "");
    }
  }, [scopeSummary, baseScope, targetScope, queueTargetScope]);

  useEffect(() => {
    if (!selectedProjectId || !scopeSummary || !targetScope || !baseScope || !selectedLang) {
      return;
    }
    if (baseScope === targetScope) {
      setCompare(null);
      return;
    }
    void loadCompare();
  }, [selectedProjectId, scopeSummary, selectedLang, baseScope, targetScope, comparePage]);

  useEffect(() => {
    if (!selectedProjectId || !queueTargetScope || !selectedLang) {
      return;
    }
    void loadQueue();
  }, [selectedProjectId, queueTargetScope, selectedLang, queuePage]);

  useEffect(() => {
    if (!selectedProjectId || !targetScope || !baseScope || baseScope === targetScope) {
      return;
    }
    const handle = window.setTimeout(() => {
      void loadCompare();
    }, 150);
    return () => window.clearTimeout(handle);
  }, [compareSearch, compareState, compareDiff]);

  useEffect(() => {
    if (!selectedProjectId || !queueTargetScope) {
      return;
    }
    const handle = window.setTimeout(() => {
      void loadQueue();
    }, 150);
    return () => window.clearTimeout(handle);
  }, [queueSearch, queueStatus]);

  const languageOptions = bootstrap?.schema.translation_columns || [];
  const imports = bootstrap?.imports || [];
  const jobs = bootstrap?.jobs || [];
  const scopeOptions = useMemo(() => buildScopeOptions(scopeSummary?.scopes || []), [scopeSummary]);
  const importMappingIssues = useMemo(
    () => listMissingImportMappings(importPreview, importMappings),
    [importPreview, importMappings],
  );
  const devScopeOptions = useMemo(
    () => scopeOptions.filter((option) => option.value.startsWith("dev/")),
    [scopeOptions],
  );
  const compareTotalPages = compare ? Math.max(1, Math.ceil(compare.total_rows / Math.max(compare.page_size || 1, 1))) : 1;
  const queueTotalPages = queue ? Math.max(1, Math.ceil(queue.total_rows / Math.max(queue.page_size || 1, 1))) : 1;
  const showProjectShell = projects.length > 0;
  const selectedImportSummary = imports.find((item) => String(item.import_batch_id) === selectedImportBatch) || null;
  const noProjects = projectsLoaded && projects.length === 0;

  useEffect(() => {
    if (!selectedJobId) {
      setJobDetail(null);
      return;
    }
    if (isBusy || !bootstrap) {
      return;
    }
    if (!jobs.some((job) => job.job_id === selectedJobId)) {
      setSelectedJobId(null);
      setJobDetail(null);
    }
  }, [bootstrap, isBusy, jobs, selectedJobId]);

  useEffect(() => {
    if (!selectedProjectId || route !== "inspection") {
      return;
    }
    void loadInspectionLists(selectedProjectId);
  }, [selectedProjectId, route]);

  async function refreshProjects(message = "Projects refreshed") {
    try {
      setIsBusy(true);
      const result = await fetchJson<ProjectSummary[]>("/api/projects");
      setProjects(result);
      if (result.length === 0) {
        clearStoredProjectId();
      }
      setFlash({ message, error: false });
    } catch (error) {
      setFlash({ message: asMessage(error), error: true });
    } finally {
      setProjectsLoaded(true);
      setIsBusy(false);
    }
  }

  async function loadInspectionLists(projectId: number) {
    try {
      const orphaned = await fetchJson<OrphanVariantsResponse>(`/api/projects/${projectId}/orphan-variants`);
      setOrphanVariants(orphaned.results);
    } catch (error) {
      setFlash({ message: asMessage(error), error: true });
    }
  }

  async function loadInspectionEntry(businessKey: string) {
    if (!selectedProjectId) {
      return;
    }
    const normalized = businessKey.trim();
    if (!normalized) {
      setFlash({ message: "Business key is required.", error: true });
      return;
    }
    try {
      const result = await fetchJson<EntryVariantsResponse>(
        `/api/projects/${selectedProjectId}/entries/${encodeURIComponent(normalized)}/variants`,
      );
      setInspectionLookupKey(normalized);
      setInspectionEntry(result);
    } catch (error) {
      setInspectionEntry(null);
      setFlash({ message: asMessage(error), error: true });
    }
  }

  async function handleProjectSelection(projectId: number) {
    if (projectId === selectedProjectId) {
      return;
    }
    resetProjectScopedUi();
    setSelectedProjectId(projectId);
    setStoredProjectId(projectId);
    navigate("overview", setRoute);
    setFlash({ message: `Switched to project #${projectId}`, error: false });
  }

  async function refreshProjectState(projectId: number, message = "State refreshed") {
    try {
      setIsBusy(true);
      const state = await fetchJson<ProductBootstrapResponse>(`/api/projects/${projectId}/state`);
      const nextLang = selectedLang || state.schema.translation_columns[0] || "";
      const summary = await fetchJson<ScopeSummaryResponse>(
        `/api/projects/${projectId}/scopes/summary?${new URLSearchParams({ lang: nextLang }).toString()}`,
      );
      setBootstrap(state);
      setScopeSummary(summary);
      setFlash({ message, error: false });
    } catch (error) {
      setBootstrap(null);
      setScopeSummary(null);
      setFlash({ message: asMessage(error), error: true });
    } finally {
      setIsBusy(false);
    }
  }

  async function createProject() {
    const translationColumns = splitColumns(createTranslationColumns);
    const remarkColumns = splitColumns(createRemarkColumns);
    try {
      setIsBusy(true);
      const project = await fetchJson<ProjectSummary>("/api/projects", {
        method: "POST",
        body: JSON.stringify({
          name: createProjectName,
          translation_columns: translationColumns,
          remark_columns: remarkColumns,
        }),
      });
      await refreshProjects(`Project ${project.name} created`);
      setSelectedProjectId(project.project_id);
      setStoredProjectId(project.project_id);
      setCreateProjectName("");
      navigate("imports", setRoute);
    } catch (error) {
      setFlash({ message: asMessage(error), error: true });
    } finally {
      setIsBusy(false);
    }
  }

  async function loadCompare() {
    if (!selectedProjectId || !baseScope || !targetScope) {
      return;
    }
    if (baseScope === targetScope) {
      setFlash({ message: "Base scope and target scope must be different.", error: true });
      setCompare(null);
      return;
    }
    try {
      const params = new URLSearchParams({
        base: baseScope,
        target: targetScope,
        lang: selectedLang,
        page: String(comparePage),
        page_size: String(PAGE_SIZE),
      });
      if (compareSearch.trim()) {
        params.set("search", compareSearch.trim());
      }
      if (compareState) {
        params.append("state", compareState);
      }
      if (compareDiff) {
        params.append("diff_category", compareDiff);
      }
      const result = await fetchJson<BranchCompareResponse>(
        `/api/projects/${selectedProjectId}/scopes/compare?${params.toString()}`,
      );
      setCompare(result);
    } catch (error) {
      setFlash({ message: asMessage(error), error: true });
    }
  }

  async function loadQueue() {
    if (!selectedProjectId || !queueTargetScope) {
      return;
    }
    try {
      const params = new URLSearchParams({
        target: queueTargetScope,
        lang: selectedLang,
        page: String(queuePage),
        page_size: String(PAGE_SIZE),
      });
      if (queueSearch.trim()) {
        params.set("search", queueSearch.trim());
      }
      if (queueStatus) {
        params.append("priority_status", queueStatus);
      }
      const result = await fetchJson<TranslationQueueResponse>(
        `/api/projects/${selectedProjectId}/translation-queue?${params.toString()}`,
      );
      setQueue(result);
    } catch (error) {
      setFlash({ message: asMessage(error), error: true });
    }
  }

  async function lookupMasterByKey() {
    if (!selectedProjectId || !masterKey.trim()) {
      setFlash({ message: "Business key is required.", error: true });
      return;
    }
    try {
      setMasterMode("key");
      const response = await fetchJson<MasterResponse>(
        `/api/projects/${selectedProjectId}/master/entries/${encodeURIComponent(masterKey.trim())}`,
      );
      setMasterRows(response.results || []);
      navigate("master", setRoute);
    } catch (error) {
      setFlash({ message: asMessage(error), error: true });
    }
  }

  async function lookupMasterBySource() {
    if (!selectedProjectId || !masterSource.trim()) {
      setFlash({ message: "Source is required.", error: true });
      return;
    }
    try {
      setMasterMode("source");
      const params = new URLSearchParams({ source: masterSource.trim() });
      const response = await fetchJson<MasterResponse>(
        `/api/projects/${selectedProjectId}/master/search?${params.toString()}`,
      );
      setMasterRows(response.results || []);
      navigate("master", setRoute);
    } catch (error) {
      setFlash({ message: asMessage(error), error: true });
    }
  }

  async function handleImportPreview(files: File[]) {
    if (!selectedProjectId) {
      return;
    }
    try {
      const preview = await postFolderForm<ImportPreview>(
        `/api/projects/${selectedProjectId}/imports/upload-folder/preview`,
        files,
      );
      setPendingImportFiles(files);
      setImportPreview(preview);
      setImportMappings(buildInitialImportMappings(preview));
      setShowImportModal(true);
    } catch (error) {
      setFlash({ message: asMessage(error), error: true });
    }
  }

  async function confirmImportBatch() {
    if (!selectedProjectId || !importPreview || pendingImportFiles.length === 0) {
      return;
    }
    if (importMappingIssues.length > 0) {
      setFlash({ message: "Import mapping is incomplete. Choose headers for every required field before continuing.", error: true });
      return;
    }
    try {
      const result = await postFolderForm<JobDetail>(
        `/api/projects/${selectedProjectId}/imports/upload-folder`,
        pendingImportFiles,
        { column_mapping_json: JSON.stringify(importMappings) },
      );
      setSelectedJobId(result.job.job_id);
      setJobDetail(result);
      setShowImportModal(false);
      setImportPreview(null);
      setImportMappings({});
      setPendingImportFiles([]);
      if (importInputRef.current) {
        importInputRef.current.value = "";
      }
      const importBatchId = (result.job.summary as { import_batch_id?: number }).import_batch_id;
      if (importBatchId) {
        setSelectedImportBatch(String(importBatchId));
      }
      await refreshProjectState(selectedProjectId, `Import batch #${importBatchId || result.job.job_id} created`);
    } catch (error) {
      setFlash({ message: asMessage(error), error: true });
    }
  }

  function updateImportMapping(
    sheetKey: string,
    kind: "business_key" | "source" | "translation" | "remark",
    fieldKey: string,
    value: string,
  ) {
    setImportMappings((current) => {
      const existing = current[sheetKey] || {
        business_key: "",
        source: "",
        translation_columns: {},
        remark_columns: {},
      };
      if (kind === "business_key" || kind === "source") {
        return {
          ...current,
          [sheetKey]: {
            ...existing,
            [kind]: value,
          },
        };
      }
      if (kind === "translation") {
        return {
          ...current,
          [sheetKey]: {
            ...existing,
            translation_columns: {
              ...existing.translation_columns,
              [fieldKey]: value,
            },
          },
        };
      }
      return {
        ...current,
        [sheetKey]: {
          ...existing,
          remark_columns: {
            ...existing.remark_columns,
            [fieldKey]: value,
          },
        },
      };
    });
  }

  async function runDevImport() {
    if (!selectedProjectId || !selectedImportBatch || !devVersionInput.trim()) {
      setFlash({ message: "Import batch and dev version are required.", error: true });
      return;
    }
    try {
      const result = await fetchJson<JobDetail>(`/api/projects/${selectedProjectId}/dev-versions/import`, {
        method: "POST",
        body: JSON.stringify({
          import_batch_id: Number(selectedImportBatch),
          version: devVersionInput.trim(),
          mark_as_candidate: candidateRelease,
        }),
      });
      setTargetScope(`dev/${devVersionInput.trim()}`);
      setQueueTargetScope(`dev/${devVersionInput.trim()}`);
      setSelectedJobId(result.job.job_id);
      setJobDetail(result);
      await refreshProjectState(selectedProjectId, `Job #${result.job.job_id} finished`);
    } catch (error) {
      setFlash({ message: asMessage(error), error: true });
    }
  }

  async function runPromotePreview() {
    if (!selectedProjectId) {
      return;
    }
    const version = promoteVersion.trim() || queueTargetScope.replace(/^dev\//, "") || targetScope.replace(/^dev\//, "");
    if (!version) {
      setFlash({ message: "Promote version is required.", error: true });
      return;
    }
    try {
      const result = await fetchJson<PromotePreview>(`/api/projects/${selectedProjectId}/promote/preview`, {
        method: "POST",
        body: JSON.stringify({ version }),
      });
      setPromotePreview(result);
    } catch (error) {
      setFlash({ message: asMessage(error), error: true });
    }
  }

  async function runPromoteExecute() {
    if (!selectedProjectId) {
      return;
    }
    const version = promoteVersion.trim() || queueTargetScope.replace(/^dev\//, "") || targetScope.replace(/^dev\//, "");
    if (!version) {
      setFlash({ message: "Promote version is required.", error: true });
      return;
    }
    try {
      const result = await fetchJson<JobDetail>(`/api/projects/${selectedProjectId}/promote/execute`, {
        method: "POST",
        body: JSON.stringify({ version }),
      });
      setSelectedJobId(result.job.job_id);
      setJobDetail(result);
      await refreshProjectState(selectedProjectId, `Job #${result.job.job_id} finished`);
    } catch (error) {
      setFlash({ message: asMessage(error), error: true });
    }
  }

  async function runFill(files: File[]) {
    if (!selectedProjectId) {
      return;
    }
    try {
      const result = await postFolderForm<JobDetail>(`/api/projects/${selectedProjectId}/fill/upload-folder`, files, {
        lang: selectedLang,
      });
      setSelectedJobId(result.job.job_id);
      setJobDetail(result);
      await refreshProjectState(selectedProjectId, `Fill job #${result.job.job_id} finished`);
    } catch (error) {
      setFlash({ message: asMessage(error), error: true });
    }
  }

  async function runQa(files: File[]) {
    if (!selectedProjectId) {
      return;
    }
    try {
      const result = await postFolderForm<JobDetail>(`/api/projects/${selectedProjectId}/qa/upload-folder`, files, {
        lang: selectedLang,
      });
      setSelectedJobId(result.job.job_id);
      setJobDetail(result);
      await refreshProjectState(selectedProjectId, `QA job #${result.job.job_id} finished`);
    } catch (error) {
      setFlash({ message: asMessage(error), error: true });
    }
  }

  async function inspectJob(jobId: number) {
    if (!selectedProjectId) {
      return;
    }
    try {
      setSelectedJobId(jobId);
      const detail = await fetchJson<JobDetail>(`/api/projects/${selectedProjectId}/jobs/${jobId}`);
      setJobDetail(detail);
    } catch (error) {
      setFlash({ message: asMessage(error), error: true });
    }
  }

  if (noProjects && route !== "project-new") {
    return (
      <div className="empty-shell" data-testid="app-empty-state">
        <section className="empty-card">
          <div className="stack">
            <p className="eyebrow">Momo TMS</p>
            <h1>Operator Console</h1>
            <p>No projects are available yet. Create the first project to define the workbook schema and start import, compare, queue, fill, QA, and promote workflows.</p>
            <p className="muted">Translation and remark column names are fixed after project creation.</p>
          </div>
          <div className="flash-wrap">
            <p className={`flash ${flash.error ? "error" : ""}`}>{flash.message}</p>
          </div>
          <div className="toolbar">
            <button
              className="button accent"
              onClick={() => navigate("project-new", setRoute)}
              data-testid="app-empty-create-project"
            >
              Create Project
            </button>
            <button className="button subtle" onClick={() => void refreshProjects("Projects refreshed")}>
              Refresh Projects
            </button>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="app-shell" data-testid="product-app">
      <aside className="sidebar">
        <div>
          <p className="eyebrow">Momo TMS</p>
          <h1>Operator Console</h1>
          <p className="muted">Primary product surface for project-scoped compare, queue, import workflows, and job inspection.</p>
        </div>
        {showProjectShell ? (
          <>
            <nav className="nav">
              {NAV_ITEMS.map((item) => (
                <button
                  key={item.route}
                  className={`nav-button ${route === item.route ? "active" : ""}`}
                  onClick={() => navigate(item.route, setRoute)}
                  data-testid={`nav-${item.route}`}
                >
                  {item.label}
                </button>
              ))}
              <button
                className={`nav-button ${route === "project-new" ? "active" : ""}`}
                onClick={() => navigate("project-new", setRoute)}
                data-testid="nav-project-new"
              >
                New Project
              </button>
            </nav>
            <div className="flash-wrap">
              <p className={`flash ${flash.error ? "error" : ""}`}>{flash.message}</p>
              <button className="button subtle" onClick={() => selectedProjectId && void refreshProjectState(selectedProjectId)}>
                Refresh
              </button>
            </div>
          </>
        ) : null}
      </aside>

      <main className="main-content">
        {route !== "project-new" && projects.length > 0 ? (
          <header className="topbar">
            <div>
              <p className="eyebrow">Project</p>
              <h2>{bootstrap?.project.name || "Select a project"}</h2>
            </div>
            <div className="toolbar">
              <label className="field compact">
                <span>Project</span>
                <select
                  value={selectedProjectId || ""}
                  onChange={(event) => void handleProjectSelection(Number(event.target.value))}
                  data-testid="app-project-select"
                >
                  {projects.map((project) => (
                    <option key={project.project_id} value={project.project_id}>
                      {project.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field compact">
                <span>Language</span>
                <select value={selectedLang} onChange={(event) => setSelectedLang(event.target.value)} data-testid="app-language">
                  {languageOptions.map((lang) => (
                    <option key={lang} value={lang}>
                      {lang}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </header>
        ) : null}

        {route === "project-new" ? (
          <section className="panel panel-wide" data-testid="project-create-page">
            <div className="panel-head">
              <div>
                <p className="panel-kicker">Project Setup</p>
                <h3>Create Project</h3>
              </div>
            </div>
            <p className="muted">
              Define the fixed template once. Translation and remark column names are fixed after project creation and are used by import, compare, queue, fill, and master query.
            </p>
            <div className="stack form-stack">
              <label className="field">
                <span>Project Name</span>
                <input value={createProjectName} onChange={(event) => setCreateProjectName(event.target.value)} data-testid="project-name-input" />
              </label>
              <label className="field">
                <span>Translation Columns</span>
                <input
                  value={createTranslationColumns}
                  onChange={(event) => setCreateTranslationColumns(event.target.value)}
                  placeholder="fr, en"
                  data-testid="project-translation-columns"
                />
              </label>
              <label className="field">
                <span>Remark Columns</span>
                <input
                  value={createRemarkColumns}
                  onChange={(event) => setCreateRemarkColumns(event.target.value)}
                  placeholder="context"
                  data-testid="project-remark-columns"
                />
              </label>
              <div className="toolbar">
                <button className="button accent" onClick={() => void createProject()} disabled={isBusy} data-testid="project-create-button">
                  Create Project
                </button>
                {projects.length > 0 ? (
                  <button className="button subtle" onClick={() => navigate("overview", setRoute)}>
                    Back to Overview
                  </button>
                ) : null}
              </div>
            </div>
          </section>
        ) : null}

        {route === "overview" ? (
          <section className="panel" data-testid="overview-page">
            <div className="panel-head">
              <div>
                <p className="panel-kicker">Summary</p>
                <h3>Branch Overview</h3>
              </div>
              <button className="button subtle" onClick={() => navigate("imports", setRoute)}>
                Go to Imports & Jobs
              </button>
            </div>
            {(scopeSummary?.scopes || []).length > 0 ? (
              <div className="overview-grid" data-testid="overview-grid">
                {(scopeSummary?.scopes || []).map((scope) => (
                  <button
                    key={`${scope.scope_type}/${scope.scope_value}`}
                    className="scope-card"
                    onClick={() => {
                      const nextTarget = `${scope.scope_type}/${scope.scope_value}`;
                      if (nextTarget !== "rel/current") {
                        setTargetScope(nextTarget);
                        if (nextTarget.startsWith("dev/")) {
                          setQueueTargetScope(nextTarget);
                        }
                      }
                      navigate("compare", setRoute);
                    }}
                  >
                    <div className="scope-card__top">
                      <strong>{scope.scope_type}/{scope.scope_value}</strong>
                      {scope.is_candidate_release ? <span className="badge accent">candidate</span> : null}
                    </div>
                    <span className="muted">entries {scope.entry_count}</span>
                    <code>{JSON.stringify(scope.status_counts)}</code>
                  </button>
                ))}
              </div>
            ) : (
              <PanelEmptyState
                message="No scopes are available yet. Create an import batch and run dev import to populate branch views."
                actionLabel="Go to Imports & Jobs"
                onAction={() => navigate("imports", setRoute)}
              />
            )}
          </section>
        ) : null}

        {route === "compare" ? (
          <section className="panel" data-testid="compare-page">
            <div className="panel-head">
              <div>
                <p className="panel-kicker">Diff</p>
                <h3>Branch Compare</h3>
              </div>
              <button className="button subtle" onClick={() => navigate("imports", setRoute)}>
                Go to Imports & Jobs
              </button>
            </div>
            <div className="toolbar">
              <label className="field compact">
                <span>Base Scope</span>
                <select
                  value={baseScope}
                  onChange={(event) => {
                    setBaseScope(event.target.value);
                    setComparePage(1);
                  }}
                  data-testid="app-base-scope"
                >
                  {scopeOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field compact">
                <span>Target Scope</span>
                <select
                  value={targetScope}
                  onChange={(event) => {
                    setTargetScope(event.target.value);
                    setComparePage(1);
                  }}
                  disabled={devScopeOptions.length === 0}
                  data-testid="app-target-scope"
                >
                  {scopeOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field compact">
                <span>Search Key</span>
                <input value={compareSearch} onChange={(event) => { setCompareSearch(event.target.value); setComparePage(1); }} />
              </label>
              <label className="field compact">
                <span>State</span>
                <select value={compareState} onChange={(event) => { setCompareState(event.target.value); setComparePage(1); }}>
                  <option value="">All</option>
                  <option value="aligned">aligned</option>
                  <option value="diverged">diverged</option>
                  <option value="base_only">base_only</option>
                  <option value="target_only">target_only</option>
                </select>
              </label>
              <label className="field compact">
                <span>Diff</span>
                <select value={compareDiff} onChange={(event) => { setCompareDiff(event.target.value); setComparePage(1); }}>
                  <option value="">All</option>
                  <option value="source_changed">source_changed</option>
                  <option value="translation_changed">translation_changed</option>
                  <option value="remark_changed">remark_changed</option>
                  <option value="file_name_changed">file_name_changed</option>
                </select>
              </label>
            </div>
            {baseScope === targetScope ? (
              <p className="flash error">Base scope and target scope must be different.</p>
            ) : null}
            {devScopeOptions.length === 0 ? (
              <PanelEmptyState
                message="No dev scopes are available for compare yet. Run dev import from Imports & Jobs first."
                actionLabel="Go to Imports & Jobs"
                onAction={() => navigate("imports", setRoute)}
              />
            ) : (
              <>
                <DataTable
                  headers={["business_key", "file_name", "source", `target:${selectedLang}`, "state", "priority", "diffs"]}
                  rows={(compare?.rows || []).map((row) => [
                    row.business_key,
                    row.target?.file_name || row.base?.file_name || "-",
                    row.target?.source || row.base?.source || "-",
                    row.target?.translations?.[selectedLang] || row.base?.translations?.[selectedLang] || "",
                    presentState(row.state, baseScope, targetScope),
                    row.priority_status,
                    row.diff_categories.join(", ") || "-",
                  ])}
                  emptyText="No compare rows for the current filters."
                  dataTestId="compare-table"
                />
                <Pagination
                  page={compare?.page || 1}
                  totalPages={compareTotalPages}
                  onPrev={() => setComparePage((value) => Math.max(1, value - 1))}
                  onNext={() => setComparePage((value) => Math.min(compareTotalPages, value + 1))}
                />
              </>
            )}
          </section>
        ) : null}

        {route === "queue" ? (
          <section className="panel" data-testid="queue-page">
            <div className="panel-head">
              <div>
                <p className="panel-kicker">Operations</p>
                <h3>Translation Queue</h3>
              </div>
              <button className="button subtle" onClick={() => navigate("imports", setRoute)}>
                Go to Imports & Jobs
              </button>
            </div>
            <div className="toolbar">
              <label className="field compact">
                <span>Target Scope</span>
                <select
                  value={queueTargetScope}
                  onChange={(event) => {
                    setQueueTargetScope(event.target.value);
                    setQueuePage(1);
                  }}
                  disabled={devScopeOptions.length === 0}
                  data-testid="app-queue-target"
                >
                  {devScopeOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field compact">
                <span>Search Key</span>
                <input value={queueSearch} onChange={(event) => { setQueueSearch(event.target.value); setQueuePage(1); }} />
              </label>
              <label className="field compact">
                <span>Status</span>
                <select value={queueStatus} onChange={(event) => { setQueueStatus(event.target.value); setQueuePage(1); }}>
                  <option value="">All</option>
                  <option value="fillable">fillable</option>
                  <option value="needs_translation">needs_translation</option>
                  <option value="needs_review">needs_review</option>
                  <option value="source_mismatch">source_mismatch</option>
                  <option value="already_translated">already_translated</option>
                </select>
              </label>
            </div>
            {devScopeOptions.length === 0 ? (
              <PanelEmptyState
                message="No dev scopes are available for translation queue yet. Run dev import from Imports & Jobs first."
                actionLabel="Go to Imports & Jobs"
                onAction={() => navigate("imports", setRoute)}
              />
            ) : (
              <>
                <DataTable
                  headers={["business_key", "file_name", "source", `target:${selectedLang}`, "state", "priority", "diffs"]}
                  rows={(queue?.rows || []).map((row) => [
                    row.business_key,
                    row.file_name || "-",
                    row.source,
                    row.target_text,
                    presentState(row.state, "rel/current", queueTargetScope),
                    row.priority_status,
                    row.diff_categories.join(", ") || "-",
                  ])}
                  emptyText="No queue rows for the current filters."
                  dataTestId="queue-table"
                />
                <Pagination
                  page={queue?.page || 1}
                  totalPages={queueTotalPages}
                  onPrev={() => setQueuePage((value) => Math.max(1, value - 1))}
                  onNext={() => setQueuePage((value) => Math.min(queueTotalPages, value + 1))}
                />
              </>
            )}
          </section>
        ) : null}

        {route === "master" ? (
          <section className="panel" data-testid="master-page">
            <div className="panel-head">
              <div>
                <p className="panel-kicker">Lookup</p>
                <h3>Master Query</h3>
              </div>
              <button className="button subtle" onClick={() => navigate("imports", setRoute)}>
                Go to Imports & Jobs
              </button>
            </div>
            <div className="toolbar">
              <label className="field compact">
                <span>Business Key</span>
                <input value={masterKey} onChange={(event) => setMasterKey(event.target.value)} data-testid="app-master-key" />
              </label>
              <button className="button" onClick={() => void lookupMasterByKey()} data-testid="master-key-button">
                Lookup Key
              </button>
              <label className="field compact">
                <span>Exact Source</span>
                <input value={masterSource} onChange={(event) => setMasterSource(event.target.value)} data-testid="app-master-source" />
              </label>
              <button className="button" onClick={() => void lookupMasterBySource()} data-testid="master-source-button">
                Lookup Source
              </button>
            </div>
            <p className="muted">Mode: {masterMode === "key" ? "business_key" : "source"}</p>
            <DataTable
              headers={["business_key", "scope", "file_name", "source", `translations:${selectedLang}`]}
              rows={masterRows.map((row) => [
                row.business_key,
                `${row.scope_type}/${row.scope_value}`,
                row.file_name || "-",
                row.source,
                row.translations[selectedLang] || "",
              ])}
              emptyText="No active matches."
              dataTestId="master-table"
            />
          </section>
        ) : null}

        {route === "inspection" ? (
          <section className="imports-layout" data-testid="app-inspection-page">
            <section className="panel">
              <div className="panel-head">
                <div>
                  <p className="panel-kicker">Debug</p>
                  <h3>Inspection</h3>
                </div>
              </div>
              <div className="toolbar">
                <label className="field compact">
                  <span>Business Key</span>
                  <input
                    value={inspectionLookupKey}
                    onChange={(event) => setInspectionLookupKey(event.target.value)}
                    data-testid="app-inspection-key"
                  />
                </label>
                <button className="button" onClick={() => void loadInspectionEntry(inspectionLookupKey)} data-testid="app-inspection-lookup">
                  Inspect Entry
                </button>
                <button className="button subtle" onClick={() => selectedProjectId && void loadInspectionLists(selectedProjectId)}>
                  Refresh Lists
                </button>
              </div>
            </section>

            <section className="inspection-grid">
              <section className="panel">
                <div className="panel-head">
                  <div>
                    <p className="panel-kicker">Lifecycle</p>
                    <h3>Orphan Variants</h3>
                  </div>
                </div>
                <div className="job-list" data-testid="app-orphan-list">
                  {orphanVariants.length > 0 ? (
                    orphanVariants.map((item) => (
                      <button
                        key={`orphan-${item.variant_id}`}
                        className={`job-card ${inspectionEntry?.business_key === item.business_key ? "active" : ""}`}
                        onClick={() => void loadInspectionEntry(item.business_key)}
                      >
                        <strong>{item.business_key}</strong>
                        <span className="muted">{item.file_name || "-"}</span>
                        <span className="muted">{formatTimestamp(item.orphaned_at)}</span>
                      </button>
                    ))
                  ) : (
                    <PanelEmptyState message="No orphan variants in this project." />
                  )}
                </div>
              </section>
            </section>

            <section className="panel" data-testid="app-inspection-detail">
              <div className="panel-head">
                <div>
                  <p className="panel-kicker">Entry</p>
                  <h3>{inspectionEntry?.business_key || "Variant Detail"}</h3>
                </div>
              </div>
              {inspectionEntry ? (
                <div className="stack">
                  {inspectionEntry.variants.map((variant) => (
                    <article key={variant.variant_id} className="mapping-card">
                      <div className="scope-card__top">
                        <strong>variant #{variant.variant_id}</strong>
                        <div className="toolbar">
                          {variant.is_orphaned ? <span className="badge warning">orphan</span> : null}
                          {variant.is_trashed ? <span className="badge danger">trashed</span> : null}
                        </div>
                      </div>
                      <SummaryKeyValueList
                        items={[
                          ["file_name", variant.file_name || "-"],
                          ["source", variant.source],
                          ["orphaned_at", variant.orphaned_at || "-"],
                          ["updated_at", formatTimestamp(variant.updated_at)],
                        ]}
                      />
                      <SummaryKeyValueList title="translations" items={Object.entries(variant.translations)} />
                      <SummaryKeyValueList title="remarks" items={Object.entries(variant.remarks)} />
                      <SummaryKeyValueList
                        title="bindings"
                        items={
                          variant.bindings.length > 0
                            ? variant.bindings.map((binding) => [
                                `${binding.scope_type}/${binding.scope_value}`,
                                formatTimestamp(binding.updated_at),
                              ])
                            : [["state", "No active bindings"]]
                        }
                      />
                    </article>
                  ))}
                </div>
              ) : (
                <PanelEmptyState message="Look up a business key or pick an orphan row to inspect bindings and lifecycle flags." />
              )}
            </section>
          </section>
        ) : null}

        {route === "imports" ? (
          <section className="imports-layout" data-testid="imports-page">
            <section className="panel">
              <div className="panel-head">
                <div>
                  <p className="panel-kicker">Template</p>
                  <h3>Imports & Jobs</h3>
                </div>
              </div>
              <div className="schema-summary">
                <span className="badge accent">
                  translations: {(bootstrap?.schema.translation_columns || []).join(", ") || "-"}
                </span>
                <span className="badge accent">
                  remarks: {(bootstrap?.schema.remark_columns || []).join(", ") || "-"}
                </span>
                <p className="muted">Upload opens a guided mapping modal with auto-suggested headers. `file_name` still comes from the workbook path, not from an Excel column.</p>
              </div>
            </section>

            <section className="panel">
              <div className="panel-head">
                <div>
                  <p className="panel-kicker">Step 1</p>
                  <h3>Upload and Validate</h3>
                </div>
              </div>
              <div className="stack">
                <label className="field">
                  <span>Import Folder</span>
                  <input
                    ref={importInputRef}
                    type="file"
                    {...({ webkitdirectory: "", directory: "" } as Record<string, string>)}
                    multiple
                    onChange={(event) => {
                      const files = Array.from(event.target.files || []);
                      if (files.length > 0) {
                        void handleImportPreview(files);
                      }
                    }}
                    data-testid="app-import-folder"
                  />
                </label>
                <p className="muted">After preview, choose the header for `business_key`, `source`, translation columns, and remark columns for each sheet. Extra columns are ignored.</p>
              </div>
            </section>

            <section className="panel">
              <div className="panel-head">
                <div>
                  <p className="panel-kicker">Step 2</p>
                  <h3>Run Dev Import</h3>
                </div>
              </div>
              <div className="stack">
                {imports.length > 0 ? (
                  <>
                    <label className="field">
                      <span>Import Batch</span>
                      <select value={selectedImportBatch} onChange={(event) => setSelectedImportBatch(event.target.value)} data-testid="app-import-batch">
                        {imports.map((item) => (
                          <option key={item.import_batch_id} value={item.import_batch_id}>
                            #{item.import_batch_id}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="job-list" data-testid="app-import-batches">
                      {imports.map((item) => (
                        <button
                          key={item.import_batch_id}
                          className={`job-card ${selectedImportBatch === String(item.import_batch_id) ? "active" : ""}`}
                          onClick={() => setSelectedImportBatch(String(item.import_batch_id))}
                        >
                          <strong>batch #{item.import_batch_id}</strong>
                          <span className="muted">{formatTimestamp(item.created_at)}</span>
                          <span className="muted">{item.files_scanned} files · {item.rows_scanned} rows · {item.issues} issues</span>
                        </button>
                      ))}
                    </div>
                    {selectedImportSummary ? (
                      <SummaryKeyValueList
                        title="selected batch"
                        items={[
                          ["created_at", formatTimestamp(selectedImportSummary.created_at)],
                          ["files_scanned", String(selectedImportSummary.files_scanned)],
                          ["rows_scanned", String(selectedImportSummary.rows_scanned)],
                          ["issues", String(selectedImportSummary.issues)],
                        ]}
                      />
                    ) : null}
                    <label className="field">
                      <span>Dev Version</span>
                      <input value={devVersionInput} onChange={(event) => setDevVersionInput(event.target.value)} placeholder="2.3.2" data-testid="app-dev-version-input" />
                    </label>
                    <label className="checkbox">
                      <input type="checkbox" checked={candidateRelease} onChange={(event) => setCandidateRelease(event.target.checked)} />
                      <span>Mark as candidate release</span>
                    </label>
                    <button className="button accent" onClick={() => void runDevImport()} data-testid="app-run-dev-import">
                      Run Dev Import
                    </button>
                  </>
                ) : (
                  <PanelEmptyState message="No import batches yet. Upload a folder to create the first import batch." />
                )}
              </div>
            </section>

            <section className="panel">
              <div className="panel-head">
                <div>
                  <p className="panel-kicker">Step 3</p>
                  <h3>Fill, QA, and Promote</h3>
                </div>
              </div>
              <div className="imports-actions-grid">
                <div className="stack">
                  <label className="field">
                    <span>Fill Folder</span>
                    <input
                      ref={fillInputRef}
                      type="file"
                      {...({ webkitdirectory: "", directory: "" } as Record<string, string>)}
                      multiple
                      onChange={(event) => {
                        const files = Array.from(event.target.files || []);
                        if (files.length > 0) {
                          void runFill(files);
                        }
                      }}
                      data-testid="app-fill-folder"
                    />
                  </label>
                  <p className="muted">Fill results appear in the selected job detail panel.</p>
                </div>
                <div className="stack">
                  <label className="field">
                    <span>QA Folder</span>
                    <input
                      ref={qaInputRef}
                      type="file"
                      {...({ webkitdirectory: "", directory: "" } as Record<string, string>)}
                      multiple
                      onChange={(event) => {
                        const files = Array.from(event.target.files || []);
                        if (files.length > 0) {
                          void runQa(files);
                        }
                      }}
                      data-testid="app-qa-folder"
                    />
                  </label>
                  <p className="muted">QA report details appear in the selected job detail panel.</p>
                </div>
                <div className="stack">
                  <label className="field">
                    <span>Promote Version</span>
                    <input value={promoteVersion} onChange={(event) => setPromoteVersion(event.target.value)} placeholder={queueTargetScope.replace(/^dev\//, "") || "2.3.2"} />
                  </label>
                  <div className="toolbar">
                    <button className="button" onClick={() => void runPromotePreview()} data-testid="app-promote-preview">
                      Preview
                    </button>
                    <button className="button accent" onClick={() => void runPromoteExecute()} data-testid="app-promote-execute">
                      Execute
                    </button>
                  </div>
                  {promotePreview ? (
                    <SummaryKeyValueList
                      title="promote preview"
                      items={Object.entries(promotePreview).filter(([key]) => key !== "report_rows").map(([key, value]) => [key, stringifyValue(value)])}
                    />
                  ) : (
                    <p className="muted">Preview summarize promote impact before execution.</p>
                  )}
                </div>
              </div>
            </section>

            <section className="panel">
              <div className="panel-head">
                <div>
                  <p className="panel-kicker">Jobs</p>
                  <h3>Recent Jobs</h3>
                </div>
              </div>
              <div className="imports-jobs-grid">
                <div className="job-list" data-testid="app-jobs-list">
                  {jobs.length > 0 ? (
                    jobs.map((job) => (
                      <button key={job.job_id} className={`job-card ${selectedJobId === job.job_id ? "active" : ""}`} onClick={() => void inspectJob(job.job_id)}>
                        <strong>#{job.job_id} · {job.job_type}</strong>
                        <span className="muted">{job.status}</span>
                        <span className="muted">{formatTimestamp(job.created_at)}</span>
                        <span className="muted">{summarizeJob(job)}</span>
                      </button>
                    ))
                  ) : (
                    <PanelEmptyState message="No jobs yet. Run import, dev import, fill, QA, or promote to populate this list." />
                  )}
                </div>
                <div className="job-detail" data-testid="app-job-detail">
                  <JobDetailPanel jobDetail={jobDetail} projectId={selectedProjectId} />
                </div>
              </div>
            </section>
          </section>
        ) : null}
      </main>

      {showImportModal && importPreview ? (
        <div className="modal-shell" data-testid="app-import-modal">
          <div className="modal-backdrop" onClick={() => setShowImportModal(false)} />
          <div className="modal-card">
            <div className="panel-head">
              <div>
                <p className="panel-kicker">Template Validation</p>
                <h3>Create Import Batch</h3>
              </div>
              <button className="button subtle" onClick={() => setShowImportModal(false)}>
                Close
              </button>
            </div>
            <p className="muted">{importPreview.file_count} files · {importPreview.sheet_count} sheets</p>
            <div className="modal-body">
              {importPreview.sheet_previews.map((sheet) => (
                <article key={sheet.sheet_key} className="mapping-card">
                  <strong>{sheet.file_path} · {sheet.sheet_name}</strong>
                  <p className="muted">Derived file_name: {sheet.derived_file_name}</p>
                  <p className="muted">Headers: {sheet.available_headers.join(", ") || "none"}</p>
                  {importMappingIssues.find((item) => item.sheet_key === sheet.sheet_key) ? (
                    <p className="flash error">
                      Missing mappings: {importMappingIssues.find((item) => item.sheet_key === sheet.sheet_key)?.missing.join(", ")}
                    </p>
                  ) : (
                    <p className="flash">Ready to create import batch.</p>
                  )}
                  <div className="mapping-grid">
                    <label className="field compact">
                      <span>Business Key</span>
                      <select
                        value={importMappings[sheet.sheet_key]?.business_key || ""}
                        onChange={(event) => updateImportMapping(sheet.sheet_key, "business_key", "", event.target.value)}
                      >
                        <option value="">Select header</option>
                        {sheet.available_headers.map((header) => (
                          <option key={`${sheet.sheet_key}-business-${header}`} value={header}>
                            {header}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field compact">
                      <span>Source</span>
                      <select
                        value={importMappings[sheet.sheet_key]?.source || ""}
                        onChange={(event) => updateImportMapping(sheet.sheet_key, "source", "", event.target.value)}
                      >
                        <option value="">Select header</option>
                        {sheet.available_headers.map((header) => (
                          <option key={`${sheet.sheet_key}-source-${header}`} value={header}>
                            {header}
                          </option>
                        ))}
                      </select>
                    </label>
                    {(bootstrap?.schema.translation_columns || []).map((lang) => (
                      <label key={`${sheet.sheet_key}-translation-${lang}`} className="field compact">
                        <span>Translation · {lang}</span>
                        <select
                          value={importMappings[sheet.sheet_key]?.translation_columns?.[lang] || ""}
                          onChange={(event) => updateImportMapping(sheet.sheet_key, "translation", lang, event.target.value)}
                        >
                          <option value="">Select header</option>
                          {sheet.available_headers.map((header) => (
                            <option key={`${sheet.sheet_key}-translation-${lang}-${header}`} value={header}>
                              {header}
                            </option>
                          ))}
                        </select>
                      </label>
                    ))}
                    {(bootstrap?.schema.remark_columns || []).map((remarkKey) => (
                      <label key={`${sheet.sheet_key}-remark-${remarkKey}`} className="field compact">
                        <span>Remark · {remarkKey}</span>
                        <select
                          value={importMappings[sheet.sheet_key]?.remark_columns?.[remarkKey] || ""}
                          onChange={(event) => updateImportMapping(sheet.sheet_key, "remark", remarkKey, event.target.value)}
                        >
                          <option value="">Select header</option>
                          {sheet.available_headers.map((header) => (
                            <option key={`${sheet.sheet_key}-remark-${remarkKey}-${header}`} value={header}>
                              {header}
                            </option>
                          ))}
                        </select>
                      </label>
                    ))}
                  </div>
                </article>
              ))}
            </div>
            <div className="toolbar">
              <button className="button subtle" onClick={() => setShowImportModal(false)}>
                Cancel
              </button>
              <button
                className="button accent"
                onClick={() => void confirmImportBatch()}
                disabled={importMappingIssues.length > 0}
                data-testid="app-confirm-import"
              >
                Create Import Batch
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function DataTable(props: {
  headers: string[];
  rows: string[][];
  emptyText: string;
  dataTestId: string;
}) {
  if (props.rows.length === 0) {
    return <p className="muted" data-testid={props.dataTestId}>{props.emptyText}</p>;
  }
  return (
    <div className="table-wrap" data-testid={props.dataTestId}>
      <table className="data-table">
        <thead>
          <tr>
            {props.headers.map((header) => (
              <th key={header}>{header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row, index) => (
            <tr key={`${index}-${row[0]}`}>
              {row.map((cell, cellIndex) => (
                <td key={`${index}-${cellIndex}`}>{cell || "-"}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Pagination(props: {
  page: number;
  totalPages: number;
  onPrev: () => void;
  onNext: () => void;
}) {
  return (
    <div className="pagination">
      <button className="button subtle" onClick={props.onPrev} disabled={props.page <= 1}>
        Previous
      </button>
      <span className="muted">Page {props.page} / {props.totalPages}</span>
      <button className="button subtle" onClick={props.onNext} disabled={props.page >= props.totalPages}>
        Next
      </button>
    </div>
  );
}

function PanelEmptyState(props: { message: string; actionLabel?: string; onAction?: () => void }) {
  return (
    <div className="empty-card empty-card--inline">
      <p className="muted">{props.message}</p>
      {props.actionLabel && props.onAction ? (
        <button className="button subtle" onClick={props.onAction}>
          {props.actionLabel}
        </button>
      ) : null}
    </div>
  );
}

function SummaryKeyValueList(props: { title?: string; items: Array<[string, string]> }) {
  if (props.items.length === 0) {
    return null;
  }
  return (
    <div className="summary-list">
      {props.title ? <p className="eyebrow">{props.title}</p> : null}
      {props.items.map(([label, value]) => (
        <div key={`${props.title || "summary"}-${label}`} className="summary-row">
          <span className="summary-label">{label}</span>
          <span>{value || "-"}</span>
        </div>
      ))}
    </div>
  );
}

function JobDetailPanel(props: { jobDetail: JobDetail | null; projectId: number | null }) {
  if (!props.jobDetail || !props.projectId) {
    return <p className="muted">Select a job to inspect report output, stages, and downloads.</p>;
  }
  const stages = readJobStages(props.jobDetail.job.summary);
  const reportRows = props.jobDetail.report.rows.slice(0, 12);
  const artifactHref = buildArtifactHref(props.projectId, props.jobDetail.job);
  const reportHref = `/api/projects/${props.projectId}/jobs/${props.jobDetail.job.job_id}/report`;
  return (
    <div className="stack">
      <div className="mapping-card">
        <div className="panel-head">
          <div>
            <p className="panel-kicker">Job Detail</p>
            <h3>#{props.jobDetail.job.job_id} · {props.jobDetail.job.job_type}</h3>
          </div>
          <span className={`badge ${props.jobDetail.job.status === "done" ? "accent" : "warning"}`}>{props.jobDetail.job.status}</span>
        </div>
        <SummaryKeyValueList
          items={[
            ["created_at", formatTimestamp(props.jobDetail.job.created_at)],
            ["finished_at", props.jobDetail.job.finished_at ? formatTimestamp(props.jobDetail.job.finished_at) : "-"],
            ["error", props.jobDetail.job.error_message || "-"],
          ]}
        />
        <div className="toolbar">
          <a className="button subtle" href={reportHref} target="_blank" rel="noreferrer" data-testid="app-job-report-link">
            Open Report
          </a>
          {artifactHref ? (
            <a className="button subtle" href={artifactHref} target="_blank" rel="noreferrer" data-testid="app-job-artifact-link">
              Download Artifact
            </a>
          ) : null}
        </div>
      </div>

      <SummaryKeyValueList title="input" items={objectEntries(props.jobDetail.job.input)} />
      <SummaryKeyValueList title="summary" items={objectEntries(props.jobDetail.job.summary, ["stages"])} />

      {stages.length > 0 ? (
        <div className="mapping-card">
          <p className="eyebrow">stages</p>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>stage</th>
                  <th>elapsed_ms</th>
                  <th>meta</th>
                </tr>
              </thead>
              <tbody>
                {stages.map((stage) => (
                  <tr key={stage.stage}>
                    <td>{stage.stage}</td>
                    <td>{String(stage.elapsed_ms)}</td>
                    <td>{stringifyValue(stage.meta)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      <div className="mapping-card">
        <p className="eyebrow">report rows</p>
        <ReportRowsPreview rows={reportRows} />
      </div>
    </div>
  );
}

function ReportRowsPreview(props: { rows: Array<Record<string, unknown>> }) {
  if (props.rows.length === 0) {
    return <p className="muted">No report rows recorded for this job.</p>;
  }
  const columns = Array.from(
    new Set(props.rows.flatMap((row) => Object.keys(row))),
  ).slice(0, 8);
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row, index) => (
            <tr key={`report-row-${index}`}>
              {columns.map((column) => (
                <td key={`report-row-${index}-${column}`}>{stringifyValue(row[column])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function parseRoute(pathname: string): AppRoute {
  if (pathname.startsWith("/app/projects/new")) {
    return "project-new";
  }
  if (pathname.startsWith("/app/compare")) {
    return "compare";
  }
  if (pathname.startsWith("/app/queue")) {
    return "queue";
  }
  if (pathname.startsWith("/app/master")) {
    return "master";
  }
  if (pathname.startsWith("/app/imports")) {
    return "imports";
  }
  if (pathname.startsWith("/app/inspection")) {
    return "inspection";
  }
  return "overview";
}

function routePath(route: AppRoute): string {
  switch (route) {
    case "overview":
      return "/app/overview";
    case "compare":
      return "/app/compare";
    case "queue":
      return "/app/queue";
    case "master":
      return "/app/master";
    case "imports":
      return "/app/imports";
    case "inspection":
      return "/app/inspection";
    case "project-new":
      return "/app/projects/new";
  }
}

function navigate(route: AppRoute, setter: (route: AppRoute) => void) {
  const nextPath = routePath(route);
  if (window.location.pathname !== nextPath) {
    window.history.pushState({}, "", nextPath);
  }
  setter(route);
}

function buildScopeOptions(
  scopes: Array<{ scope_type: string; scope_value: string; is_candidate_release?: boolean | null }>,
) {
  return scopes.map((scope) => ({
    value: `${scope.scope_type}/${scope.scope_value}`,
    label: `${scope.scope_type}/${scope.scope_value}${scope.is_candidate_release ? " · candidate" : ""}`,
  }));
}

function splitColumns(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildInitialImportMappings(preview: ImportPreview): Record<string, ImportSheetMapping> {
  const mappings: Record<string, ImportSheetMapping> = {};
  for (const sheet of preview.sheet_previews) {
    const suggested = sheet.suggested_mapping || {};
    mappings[sheet.sheet_key] = {
      business_key: String(suggested.business_key || ""),
      source: String(suggested.source || ""),
      translation_columns: Object.fromEntries(
        Object.entries((suggested.translation_columns || {}) as Record<string, unknown>).map(([key, value]) => [
          key,
          String(value || ""),
        ]),
      ),
      remark_columns: Object.fromEntries(
        Object.entries((suggested.remark_columns || {}) as Record<string, unknown>).map(([key, value]) => [
          key,
          String(value || ""),
        ]),
      ),
    };
  }
  return mappings;
}

function listMissingImportMappings(
  preview: ImportPreview | null,
  mappings: Record<string, ImportSheetMapping>,
): Array<{ sheet_key: string; missing: string[] }> {
  if (!preview) {
    return [];
  }
  const issues: Array<{ sheet_key: string; missing: string[] }> = [];
  for (const sheet of preview.sheet_previews) {
    const mapping = mappings[sheet.sheet_key];
    const missing: string[] = [];
    if (!mapping?.business_key) {
      missing.push("business_key");
    }
    if (!mapping?.source) {
      missing.push("source");
    }
    for (const lang of preview.schema.translation_columns || []) {
      if (!mapping?.translation_columns?.[lang]) {
        missing.push(`translation:${lang}`);
      }
    }
    for (const remarkKey of preview.schema.remark_columns || []) {
      if (!mapping?.remark_columns?.[remarkKey]) {
        missing.push(`remark:${remarkKey}`);
      }
    }
    if (missing.length > 0) {
      issues.push({ sheet_key: sheet.sheet_key, missing });
    }
  }
  return issues;
}

function presentState(value: string, baseScope: string, targetScope: string): string {
  const isReleaseCompare = baseScope === "rel/current" && targetScope.startsWith("dev/");
  if (!isReleaseCompare) {
    return value;
  }
  if (value === "base_only") {
    return "rel_only";
  }
  if (value === "target_only") {
    return "dev_only";
  }
  return value;
}

function asMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed";
}

function getStoredProjectId(): number | null {
  const raw = window.localStorage.getItem(PROJECT_STORAGE_KEY);
  if (!raw) {
    return null;
  }
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function setStoredProjectId(projectId: number) {
  window.localStorage.setItem(PROJECT_STORAGE_KEY, String(projectId));
}

function clearStoredProjectId() {
  window.localStorage.removeItem(PROJECT_STORAGE_KEY);
}

function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return value.replace("T", " ").replace("+00:00", "Z");
}

function stringifyValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function objectEntries(value: Record<string, unknown>, exclude: string[] = []): Array<[string, string]> {
  return Object.entries(value)
    .filter(([key]) => !exclude.includes(key))
    .map(([key, item]) => [key, stringifyValue(item)]);
}

function readJobStages(summary: Record<string, unknown>): JobStageSummary[] {
  const stages = summary.stages;
  if (!Array.isArray(stages)) {
    return [];
  }
  return stages
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }
      const stage = item as Record<string, unknown>;
      return {
        stage: String(stage.stage || ""),
        elapsed_ms: Number(stage.elapsed_ms || 0),
        meta: (stage.meta as Record<string, unknown>) || {},
      };
    })
    .filter((item): item is JobStageSummary => Boolean(item && item.stage));
}

function summarizeJob(job: JobSummary): string {
  const summaryEntries = objectEntries(job.summary, ["stages"]).slice(0, 2);
  if (summaryEntries.length === 0) {
    return "No summary metrics";
  }
  return summaryEntries.map(([key, value]) => `${key}: ${value}`).join(" · ");
}

function buildArtifactHref(projectId: number, job: JobSummary): string | null {
  if (!job.artifact_path) {
    return null;
  }
  const artifactName = job.artifact_path.split("/").pop();
  if (!artifactName) {
    return null;
  }
  return `/api/projects/${projectId}/jobs/${job.job_id}/artifact/${encodeURIComponent(artifactName)}`;
}

async function fetchJson<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    headers: options.body && !(options.body instanceof FormData) ? { "Content-Type": "application/json" } : undefined,
    ...options,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(payload.detail || "Request failed");
  }
  return response.json() as Promise<T>;
}

async function postFolderForm<T>(url: string, files: File[], extraFields: Record<string, string> = {}): Promise<T> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file, file.name);
    form.append("relative_paths", (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name);
  }
  Object.entries(extraFields).forEach(([key, value]) => form.append(key, value));
  return fetchJson<T>(url, { method: "POST", body: form });
}
