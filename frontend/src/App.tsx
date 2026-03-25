import { useEffect, useMemo, useRef, useState } from "react";

import { fetchJson, postFolderForm } from "./product-app/api";
import { ImportMappingModal } from "./product-app/components/ImportMappingModal";
import { ComparePage } from "./product-app/pages/ComparePage";
import { ImportsPage } from "./product-app/pages/ImportsPage";
import { InspectionPage } from "./product-app/pages/InspectionPage";
import { MasterPage } from "./product-app/pages/MasterPage";
import { OverviewPage } from "./product-app/pages/OverviewPage";
import { ProjectCreatePage } from "./product-app/pages/ProjectCreatePage";
import { QueuePage } from "./product-app/pages/QueuePage";
import {
  NAV_ITEMS,
  PAGE_SIZE,
  navigate,
  parseRoute,
} from "./product-app/routes";
import type {
  AppRoute,
  BranchCompareResponse,
  BranchReplacePreview,
  BranchSummaryResponse,
  EntryVariantsResponse,
  FlashState,
  ImportPreview,
  ImportSheetMapping,
  JobDetail,
  MasterResponse,
  MasterRow,
  OrphanVariantSummary,
  OrphanVariantsResponse,
  ProductBootstrapResponse,
  ProjectSummary,
  TranslationQueueResponse,
} from "./product-app/types";
import {
  asMessage,
  buildBranchOptions,
  buildInitialImportMappings,
  clearStoredProjectId,
  getStoredProjectId,
  listMissingImportMappings,
  setStoredProjectId,
  splitColumns,
} from "./product-app/utils";

export function App() {
  const [route, setRoute] = useState<AppRoute>(() =>
    parseRoute(window.location.pathname),
  );
  const [projectsLoaded, setProjectsLoaded] = useState(false);
  const [flash, setFlash] = useState<FlashState>({
    message: "Loading product app...",
    error: false,
  });
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(
    null,
  );
  const [bootstrap, setBootstrap] = useState<ProductBootstrapResponse | null>(
    null,
  );
  const [branchSummary, setBranchSummary] =
    useState<BranchSummaryResponse | null>(null);
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
  const [importPreview, setImportPreview] = useState<ImportPreview | null>(
    null,
  );
  const [importMappings, setImportMappings] = useState<
    Record<string, ImportSheetMapping>
  >({});
  const [showImportModal, setShowImportModal] = useState(false);
  const [promotePreview, setPromotePreview] =
    useState<BranchReplacePreview | null>(null);
  const [devVersionInput, setDevVersionInput] = useState("");
  const [promoteVersion, setPromoteVersion] = useState("");
  const [selectedImportBatch, setSelectedImportBatch] = useState("");
  const [candidateRelease, setCandidateRelease] = useState(true);
  const [inspectionLookupKey, setInspectionLookupKey] = useState("");
  const [inspectionEntry, setInspectionEntry] =
    useState<EntryVariantsResponse | null>(null);
  const [orphanVariants, setOrphanVariants] = useState<OrphanVariantSummary[]>(
    [],
  );
  const [createProjectName, setCreateProjectName] = useState("");
  const [createTranslationColumns, setCreateTranslationColumns] =
    useState("fr, en");
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
    setBranchSummary(null);
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
    if (
      storedProjectId &&
      projects.some((project) => project.project_id === storedProjectId)
    ) {
      if (selectedProjectId !== storedProjectId) {
        setSelectedProjectId(storedProjectId);
      }
      return;
    }
    if (
      !selectedProjectId ||
      !projects.some((project) => project.project_id === selectedProjectId)
    ) {
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
    const importBatchValues = bootstrap.imports.map((item) =>
      String(item.import_batch_id),
    );
    if (importBatchValues.length === 0) {
      setSelectedImportBatch("");
    } else if (!importBatchValues.includes(selectedImportBatch)) {
      setSelectedImportBatch(importBatchValues[0]);
    }
  }, [bootstrap, selectedImportBatch, selectedLang]);

  useEffect(() => {
    if (!branchSummary) {
      return;
    }
    const scopeOptions = buildBranchOptions(branchSummary.branches);
    if (!scopeOptions.some((option) => option.value === baseScope)) {
      setBaseScope(
        scopeOptions.find((option) => option.value === "rel/current")?.value ||
          scopeOptions[0]?.value ||
          "",
      );
    }
    if (
      !scopeOptions.some((option) => option.value === targetScope) ||
      targetScope === baseScope
    ) {
      const nextTarget =
        scopeOptions.find((option) => option.value !== (baseScope || "rel/current"))
          ?.value || "";
      setTargetScope(nextTarget);
    }
    const devOptions = branchSummary.branches
      .filter((branch) => branch.branch_ref.startsWith("dev/"))
      .map((branch) => branch.branch_ref);
    if (!devOptions.includes(queueTargetScope)) {
      setQueueTargetScope(devOptions[0] || "");
    }
  }, [branchSummary, baseScope, targetScope, queueTargetScope]);

  useEffect(() => {
    if (
      !selectedProjectId ||
      !branchSummary ||
      !targetScope ||
      !baseScope ||
      !selectedLang
    ) {
      return;
    }
    if (baseScope === targetScope) {
      setCompare(null);
      return;
    }
    void loadCompare();
  }, [
    selectedProjectId,
    branchSummary,
    selectedLang,
    baseScope,
    targetScope,
    comparePage,
  ]);

  useEffect(() => {
    if (!selectedProjectId || !queueTargetScope || !selectedLang) {
      return;
    }
    void loadQueue();
  }, [selectedProjectId, queueTargetScope, selectedLang, queuePage]);

  useEffect(() => {
    if (
      !selectedProjectId ||
      !targetScope ||
      !baseScope ||
      baseScope === targetScope
    ) {
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
  const scopeOptions = useMemo(
    () => buildBranchOptions(branchSummary?.branches || []),
    [branchSummary],
  );
  const importMappingIssues = useMemo(
    () => listMissingImportMappings(importPreview, importMappings),
    [importPreview, importMappings],
  );
  const devScopeOptions = useMemo(
    () => scopeOptions.filter((option) => option.value.startsWith("dev/")),
    [scopeOptions],
  );
  const compareTotalPages = compare
    ? Math.max(1, Math.ceil(compare.total_rows / Math.max(compare.page_size || 1, 1)))
    : 1;
  const queueTotalPages = queue
    ? Math.max(1, Math.ceil(queue.total_rows / Math.max(queue.page_size || 1, 1)))
    : 1;
  const showProjectShell = projects.length > 0;
  const selectedImportSummary =
    imports.find((item) => String(item.import_batch_id) === selectedImportBatch) ||
    null;
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
      const orphaned = await fetchJson<OrphanVariantsResponse>(
        `/api/projects/${projectId}/orphan-variants`,
      );
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
        `/api/projects/${selectedProjectId}/entries/${encodeURIComponent(
          normalized,
        )}/variants`,
      );
      setInspectionLookupKey(normalized);
      setInspectionEntry(result);
    } catch (error) {
      setInspectionEntry(null);
      setFlash({ message: asMessage(error), error: true });
    }
  }

  function handleProjectSelection(projectId: number) {
    if (projectId === selectedProjectId) {
      return;
    }
    resetProjectScopedUi();
    setSelectedProjectId(projectId);
    setStoredProjectId(projectId);
    navigate("overview", setRoute);
    setFlash({ message: `Switched to project #${projectId}`, error: false });
  }

  async function refreshProjectState(
    projectId: number,
    message = "State refreshed",
  ) {
    try {
      setIsBusy(true);
      const state = await fetchJson<ProductBootstrapResponse>(
        `/api/projects/${projectId}/state`,
      );
      const nextLang = selectedLang || state.schema.translation_columns[0] || "";
      const summary = await fetchJson<BranchSummaryResponse>(
        `/api/projects/${projectId}/branches?${new URLSearchParams({
          lang: nextLang,
        }).toString()}`,
      );
      setBootstrap(state);
      setBranchSummary(summary);
      setFlash({ message, error: false });
    } catch (error) {
      setBootstrap(null);
      setBranchSummary(null);
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
      setFlash({
        message: "Base branch and target branch must be different.",
        error: true,
      });
      setCompare(null);
      return;
    }
    try {
      const params = new URLSearchParams({
        base_branch_ref: baseScope,
        target_branch_ref: targetScope,
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
        `/api/projects/${selectedProjectId}/branches/compare?${params.toString()}`,
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
        target_branch_ref: queueTargetScope,
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
        `/api/projects/${selectedProjectId}/branches/queue?${params.toString()}`,
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
        `/api/projects/${selectedProjectId}/branches/master/entries/${encodeURIComponent(
          masterKey.trim(),
        )}`,
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
        `/api/projects/${selectedProjectId}/branches/master/search?${params.toString()}`,
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
      setImportPreview(preview);
      setImportMappings(buildInitialImportMappings(preview));
      setShowImportModal(true);
      if (importInputRef.current) {
        importInputRef.current.value = "";
      }
    } catch (error) {
      setFlash({ message: asMessage(error), error: true });
    }
  }

  async function confirmImportBatch() {
    if (!selectedProjectId || !importPreview) {
      return;
    }
    if (importMappingIssues.length > 0) {
      setFlash({
        message:
          "Import mapping is incomplete. Choose headers for business_key and source before continuing.",
        error: true,
      });
      return;
    }
    try {
      const result = await fetchJson<JobDetail>(
        `/api/projects/${selectedProjectId}/imports/upload-folder`,
        {
          method: "POST",
          body: JSON.stringify({
            upload_session_id: importPreview.upload_session_id,
            column_mapping_json: JSON.stringify(importMappings),
          }),
        },
      );
      setShowImportModal(false);
      setImportPreview(null);
      setImportMappings({});
      const finalResult = await settleJob(
        result,
        `Import job #${result.job.job_id} started`,
        (detail) => {
          const importBatchId = (detail.job.summary as { import_batch_id?: number })
            .import_batch_id;
          return `Import batch #${importBatchId || detail.job.job_id} created`;
        },
      );
      const importBatchId = (finalResult.job.summary as { import_batch_id?: number })
        .import_batch_id;
      if (importBatchId) {
        setSelectedImportBatch(String(importBatchId));
      }
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
      setFlash({
        message: "Import batch and dev version are required.",
        error: true,
      });
      return;
    }
    try {
      const branchRef = `dev/${devVersionInput.trim()}`;
      const result = await fetchJson<JobDetail>(
        `/api/projects/${selectedProjectId}/branches/mutations`,
        {
          method: "POST",
          body: JSON.stringify({
            branch_ref: branchRef,
            input: {
              kind: "import_batch",
              import_batch_id: Number(selectedImportBatch),
              mark_as_candidate_release: candidateRelease,
            },
          }),
        },
      );
      setTargetScope(branchRef);
      setQueueTargetScope(branchRef);
      await settleJob(
        result,
        `Job #${result.job.job_id} started`,
        (detail) => `Job #${detail.job.job_id} finished`,
      );
    } catch (error) {
      setFlash({ message: asMessage(error), error: true });
    }
  }

  async function runPromotePreview() {
    if (!selectedProjectId) {
      return;
    }
    const version =
      promoteVersion.trim() ||
      queueTargetScope.replace(/^dev\//, "") ||
      targetScope.replace(/^dev\//, "");
    if (!version) {
      setFlash({
        message: "Replace source version is required.",
        error: true,
      });
      return;
    }
    try {
      const result = await fetchJson<BranchReplacePreview>(
        `/api/projects/${selectedProjectId}/branches/replace/preview`,
        {
          method: "POST",
          body: JSON.stringify({
            source_branch_ref: `dev/${version}`,
            target_branch_ref: "rel/current",
          }),
        },
      );
      setPromotePreview(result);
    } catch (error) {
      setFlash({ message: asMessage(error), error: true });
    }
  }

  async function runPromoteExecute() {
    if (!selectedProjectId) {
      return;
    }
    const version =
      promoteVersion.trim() ||
      queueTargetScope.replace(/^dev\//, "") ||
      targetScope.replace(/^dev\//, "");
    if (!version) {
      setFlash({
        message: "Replace source version is required.",
        error: true,
      });
      return;
    }
    try {
      const result = await fetchJson<JobDetail>(
        `/api/projects/${selectedProjectId}/branches/replace/execute`,
        {
          method: "POST",
          body: JSON.stringify({
            source_branch_ref: `dev/${version}`,
            target_branch_ref: "rel/current",
          }),
        },
      );
      await settleJob(
        result,
        `Job #${result.job.job_id} started`,
        (detail) => `Job #${detail.job.job_id} finished`,
      );
    } catch (error) {
      setFlash({ message: asMessage(error), error: true });
    }
  }

  async function runFill(files: File[]) {
    if (!selectedProjectId) {
      return;
    }
    try {
      const result = await postFolderForm<JobDetail>(
        `/api/projects/${selectedProjectId}/fill/upload-folder`,
        files,
        {
          lang: selectedLang,
        },
      );
      await settleJob(
        result,
        `Fill job #${result.job.job_id} started`,
        (detail) => `Fill job #${detail.job.job_id} finished`,
      );
    } catch (error) {
      setFlash({ message: asMessage(error), error: true });
    }
  }

  async function runQa(files: File[]) {
    if (!selectedProjectId) {
      return;
    }
    try {
      const result = await postFolderForm<JobDetail>(
        `/api/projects/${selectedProjectId}/qa/upload-folder`,
        files,
        {
          lang: selectedLang,
        },
      );
      await settleJob(
        result,
        `QA job #${result.job.job_id} started`,
        (detail) => `QA job #${detail.job.job_id} finished`,
      );
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
      const detail = await fetchJson<JobDetail>(
        `/api/projects/${selectedProjectId}/jobs/${jobId}`,
      );
      setJobDetail(detail);
    } catch (error) {
      setFlash({ message: asMessage(error), error: true });
    }
  }

  async function settleJob(
    detail: JobDetail,
    startedMessage: string,
    successMessage: (detail: JobDetail) => string,
  ): Promise<JobDetail> {
    if (!selectedProjectId) {
      return detail;
    }
    setSelectedJobId(detail.job.job_id);
    setJobDetail(detail);
    await refreshProjectState(selectedProjectId, startedMessage);

    let finalDetail = detail;
    while (finalDetail.job.status === "running") {
      await new Promise((resolve) => window.setTimeout(resolve, 500));
      finalDetail = await fetchJson<JobDetail>(
        `/api/projects/${selectedProjectId}/jobs/${finalDetail.job.job_id}`,
      );
      setSelectedJobId(finalDetail.job.job_id);
      setJobDetail(finalDetail);
    }

    const completionMessage =
      finalDetail.job.status === "failed"
        ? finalDetail.job.error_message || `Job #${finalDetail.job.job_id} failed`
        : successMessage(finalDetail);
    await refreshProjectState(selectedProjectId, completionMessage);
    if (finalDetail.job.status === "failed") {
      setFlash({ message: completionMessage, error: true });
    }
    return finalDetail;
  }

  if (noProjects && route !== "project-new") {
    return (
      <div className="empty-shell" data-testid="app-empty-state">
        <section className="empty-card">
          <div className="stack">
            <p className="eyebrow">Momo TMS</p>
            <h1>Operator Console</h1>
            <p>
              No projects are available yet. Create the first project to define
              the workbook schema and start import, compare, queue, fill, QA,
              and replace workflows.
            </p>
            <p className="muted">
              Translation and remark column names are fixed after project
              creation.
            </p>
          </div>
          <div className="flash-wrap">
            <p className={`flash ${flash.error ? "error" : ""}`}>
              {flash.message}
            </p>
          </div>
          <div className="toolbar">
            <button
              className="button accent"
              onClick={() => navigate("project-new", setRoute)}
              data-testid="app-empty-create-project"
            >
              Create Project
            </button>
            <button
              className="button subtle"
              onClick={() => void refreshProjects("Projects refreshed")}
            >
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
          <p className="muted">
            Primary product surface for project-scoped compare, queue, import
            workflows, and job inspection.
          </p>
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
                className={`nav-button ${
                  route === "project-new" ? "active" : ""
                }`}
                onClick={() => navigate("project-new", setRoute)}
                data-testid="nav-project-new"
              >
                New Project
              </button>
            </nav>
            <div className="flash-wrap">
              <p className={`flash ${flash.error ? "error" : ""}`}>
                {flash.message}
              </p>
              <button
                className="button subtle"
                onClick={() =>
                  selectedProjectId && void refreshProjectState(selectedProjectId)
                }
              >
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
                  onChange={(event) =>
                    handleProjectSelection(Number(event.target.value))
                  }
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
                <select
                  value={selectedLang}
                  onChange={(event) => setSelectedLang(event.target.value)}
                  data-testid="app-language"
                >
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
          <ProjectCreatePage
            createProjectName={createProjectName}
            createTranslationColumns={createTranslationColumns}
            createRemarkColumns={createRemarkColumns}
            isBusy={isBusy}
            hasProjects={projects.length > 0}
            onProjectNameChange={setCreateProjectName}
            onTranslationColumnsChange={setCreateTranslationColumns}
            onRemarkColumnsChange={setCreateRemarkColumns}
            onCreateProject={() => void createProject()}
            onBackToOverview={() => navigate("overview", setRoute)}
          />
        ) : null}

        {route === "overview" ? (
          <OverviewPage
            branches={branchSummary?.branches || []}
            onGoToImports={() => navigate("imports", setRoute)}
            onSelectBranch={(branchRef) => {
              if (branchRef !== "rel/current") {
                setTargetScope(branchRef);
                if (branchRef.startsWith("dev/")) {
                  setQueueTargetScope(branchRef);
                }
              }
              navigate("compare", setRoute);
            }}
          />
        ) : null}

        {route === "compare" ? (
          <ComparePage
            baseScope={baseScope}
            targetScope={targetScope}
            selectedLang={selectedLang}
            scopeOptions={scopeOptions}
            devScopeOptions={devScopeOptions}
            compareSearch={compareSearch}
            compareState={compareState}
            compareDiff={compareDiff}
            compare={compare}
            compareTotalPages={compareTotalPages}
            onGoToImports={() => navigate("imports", setRoute)}
            onBaseScopeChange={(value) => {
              setBaseScope(value);
              setComparePage(1);
            }}
            onTargetScopeChange={(value) => {
              setTargetScope(value);
              setComparePage(1);
            }}
            onCompareSearchChange={(value) => {
              setCompareSearch(value);
              setComparePage(1);
            }}
            onCompareStateChange={(value) => {
              setCompareState(value);
              setComparePage(1);
            }}
            onCompareDiffChange={(value) => {
              setCompareDiff(value);
              setComparePage(1);
            }}
            onPrevPage={() => setComparePage((value) => Math.max(1, value - 1))}
            onNextPage={() =>
              setComparePage((value) =>
                Math.min(compareTotalPages, value + 1),
              )
            }
          />
        ) : null}

        {route === "queue" ? (
          <QueuePage
            queueTargetScope={queueTargetScope}
            selectedLang={selectedLang}
            devScopeOptions={devScopeOptions}
            queueSearch={queueSearch}
            queueStatus={queueStatus}
            queue={queue}
            queueTotalPages={queueTotalPages}
            onGoToImports={() => navigate("imports", setRoute)}
            onQueueTargetScopeChange={(value) => {
              setQueueTargetScope(value);
              setQueuePage(1);
            }}
            onQueueSearchChange={(value) => {
              setQueueSearch(value);
              setQueuePage(1);
            }}
            onQueueStatusChange={(value) => {
              setQueueStatus(value);
              setQueuePage(1);
            }}
            onPrevPage={() => setQueuePage((value) => Math.max(1, value - 1))}
            onNextPage={() =>
              setQueuePage((value) => Math.min(queueTotalPages, value + 1))
            }
          />
        ) : null}

        {route === "master" ? (
          <MasterPage
            selectedLang={selectedLang}
            masterKey={masterKey}
            masterSource={masterSource}
            masterRows={masterRows}
            masterMode={masterMode}
            onGoToImports={() => navigate("imports", setRoute)}
            onMasterKeyChange={setMasterKey}
            onMasterSourceChange={setMasterSource}
            onLookupByKey={() => void lookupMasterByKey()}
            onLookupBySource={() => void lookupMasterBySource()}
          />
        ) : null}

        {route === "inspection" ? (
          <InspectionPage
            inspectionLookupKey={inspectionLookupKey}
            inspectionEntry={inspectionEntry}
            orphanVariants={orphanVariants}
            onInspectionLookupKeyChange={setInspectionLookupKey}
            onInspectEntry={(businessKey) => void loadInspectionEntry(businessKey)}
            onRefreshLists={() =>
              selectedProjectId && void loadInspectionLists(selectedProjectId)
            }
          />
        ) : null}

        {route === "imports" ? (
          <ImportsPage
            bootstrap={bootstrap}
            selectedLang={selectedLang}
            imports={imports}
            jobs={jobs}
            selectedImportBatch={selectedImportBatch}
            selectedImportSummary={selectedImportSummary}
            devVersionInput={devVersionInput}
            candidateRelease={candidateRelease}
            promoteVersion={promoteVersion}
            queueTargetScope={queueTargetScope}
            promotePreview={promotePreview}
            selectedJobId={selectedJobId}
            jobDetail={jobDetail}
            importInputRef={importInputRef}
            fillInputRef={fillInputRef}
            qaInputRef={qaInputRef}
            onImportBatchChange={setSelectedImportBatch}
            onDevVersionInputChange={setDevVersionInput}
            onCandidateReleaseChange={setCandidateRelease}
            onPromoteVersionChange={setPromoteVersion}
            onImportFilesSelected={(files) => void handleImportPreview(files)}
            onRunDevImport={() => void runDevImport()}
            onFillFilesSelected={(files) => void runFill(files)}
            onQaFilesSelected={(files) => void runQa(files)}
            onRunPromotePreview={() => void runPromotePreview()}
            onRunPromoteExecute={() => void runPromoteExecute()}
            onInspectJob={(jobId) => void inspectJob(jobId)}
            projectId={selectedProjectId}
          />
        ) : null}
      </main>

      {showImportModal ? (
        <ImportMappingModal
          importPreview={importPreview}
          importMappings={importMappings}
          importMappingIssues={importMappingIssues}
          translationColumns={bootstrap?.schema.translation_columns || []}
          remarkColumns={bootstrap?.schema.remark_columns || []}
          onClose={() => setShowImportModal(false)}
          onConfirmImport={() => void confirmImportBatch()}
          onUpdateImportMapping={updateImportMapping}
        />
      ) : null}
    </div>
  );
}
