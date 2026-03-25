import { useEffect, useRef, useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DataGrid } from "react-data-grid";
import { useNavigate } from "react-router-dom";

import { useAppShell } from "@/app/shell/AppShellContext";
import {
  deleteBranchBusinessKeys,
  executeBranchReplace,
  getBranchCompare,
  getBranchQueue,
  lookupMasterByKey,
  lookupMasterBySource,
  previewBranchReplace,
  runBranchMutation,
} from "@/domains/branches/api";
import type { BranchReplacePreview, MasterQueryRow } from "@/domains/branches/types";
import { getImports } from "@/domains/imports/api";
import { restoreVariants } from "@/domains/variants/api";
import { invalidateProjectScope, queryKeys } from "@/shared/api/queryKeys";
import { cx } from "@/shared/lib/cx";
import {
  EmptyState,
  InlineNotice,
  Panel,
  buttonClassName,
  ui,
} from "@/shared/ui/primitives";
import {
  buildDirectColumns,
  CompareTable,
  KeyValuePreview,
  LookupTable,
  QueueTable,
} from "@/pages/branches/BranchOpsSections";
import {
  createDirectPatchRow,
  ensureDevBranch,
  parseLineSeparatedList,
  parseVariantIdList,
  rowsToDirectMutationChanges,
  type DirectPatchRow,
} from "@/pages/branches/model";

import styles from "@/pages/branches/BranchOpsPage.module.css";

const PAGE_SIZE = 25;
const TABS = [
  { key: "compare", label: "Compare" },
  { key: "queue", label: "Queue" },
  { key: "lookup", label: "Lookup" },
  { key: "apply", label: "Apply" },
  { key: "replace", label: "Replace" },
  { key: "trash", label: "Trash / Restore" },
] as const;

export function BranchOpsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const shell = useAppShell();
  const [compareSearch, setCompareSearch] = useState("");
  const [compareState, setCompareState] = useState("");
  const [compareDiff, setCompareDiff] = useState("");
  const [comparePage, setComparePage] = useState(1);
  const [queueSearch, setQueueSearch] = useState("");
  const [queueStatus, setQueueStatus] = useState("");
  const [queuePage, setQueuePage] = useState(1);
  const [lookupKey, setLookupKey] = useState("");
  const [lookupSource, setLookupSource] = useState("");
  const [lookupRequest, setLookupRequest] = useState<{
    mode: "key" | "source";
    value: string;
  } | null>(null);
  const [applyMode, setApplyMode] = useState<"import_batch" | "direct">("import_batch");
  const [selectedImportBatchId, setSelectedImportBatchId] = useState<number | null>(
    null,
  );
  const [directRows, setDirectRows] = useState<DirectPatchRow[]>([]);
  const [replaceSource, setReplaceSource] = useState("");
  const [replacePreview, setReplacePreview] = useState<BranchReplacePreview | null>(null);
  const [deleteKeys, setDeleteKeys] = useState("");
  const [restoreIds, setRestoreIds] = useState("");
  const [applyBranchRef, setApplyBranchRef] = useState("");
  const lastApplyProjectIdRef = useRef<number | null>(null);
  const lastAutoApplyBranchRefRef = useRef("");

  const selectedTab = shell.tab || "compare";
  const projectId = shell.projectId;
  const bootstrap = shell.bootstrap;
  const schema = bootstrap?.schema || null;
  const preferredDevBranch =
    bootstrap?.candidate_dev_branch?.branch_ref ||
    bootstrap?.dev_branches[0]?.branch_ref ||
    null;
  const currentDevBranch = ensureDevBranch(shell.branchRef, preferredDevBranch);

  useEffect(() => {
    if (schema && directRows.length === 0) {
      setDirectRows([createDirectPatchRow(schema)]);
    }
  }, [directRows.length, schema]);

  useEffect(() => {
    if (!projectId || !bootstrap) {
      lastApplyProjectIdRef.current = null;
      lastAutoApplyBranchRefRef.current = "";
      return;
    }
    const defaultApplyBranch = resolveApplyBranchRef(
      shell.branchRef,
      bootstrap,
      shell.branchSummary,
    );
    if (lastApplyProjectIdRef.current !== projectId) {
      setApplyBranchRef(defaultApplyBranch);
      lastApplyProjectIdRef.current = projectId;
      lastAutoApplyBranchRefRef.current = defaultApplyBranch;
      return;
    }
    if (
      applyBranchRef === lastAutoApplyBranchRefRef.current &&
      applyBranchRef !== defaultApplyBranch
    ) {
      setApplyBranchRef(defaultApplyBranch);
      lastAutoApplyBranchRefRef.current = defaultApplyBranch;
    }
  }, [
    applyBranchRef,
    bootstrap,
    projectId,
    shell.branchRef,
    shell.branchSummary,
  ]);

  const compareQuery = useQuery({
    queryKey:
      projectId && shell.lang && currentDevBranch
        ? queryKeys.branchCompare(projectId, {
            base_branch_ref: "rel/current",
            target_branch_ref: currentDevBranch,
            lang: shell.lang,
            search: compareSearch,
            state: compareState,
            diff: compareDiff,
            page: comparePage,
          })
        : ["branch-compare", "idle"],
    queryFn: () =>
      getBranchCompare(projectId!, {
        base_branch_ref: "rel/current",
        target_branch_ref: currentDevBranch!,
        lang: shell.lang,
        search: compareSearch || undefined,
        state: compareState ? [compareState] : undefined,
        diff_category: compareDiff ? [compareDiff] : undefined,
        page: comparePage,
        page_size: PAGE_SIZE,
      }),
    enabled: Boolean(projectId && shell.lang && currentDevBranch),
  });

  const queueQuery = useQuery({
    queryKey:
      projectId && shell.lang && currentDevBranch
        ? queryKeys.branchQueue(projectId, {
            target_branch_ref: currentDevBranch,
            lang: shell.lang,
            search: queueSearch,
            status: queueStatus,
            page: queuePage,
          })
        : ["branch-queue", "idle"],
    queryFn: () =>
      getBranchQueue(projectId!, {
        target_branch_ref: currentDevBranch!,
        lang: shell.lang,
        search: queueSearch || undefined,
        priority_status: queueStatus ? [queueStatus] : undefined,
        page: queuePage,
        page_size: PAGE_SIZE,
      }),
    enabled: Boolean(projectId && shell.lang && currentDevBranch),
  });

  const importsQuery = useQuery({
    queryKey: projectId ? queryKeys.imports(projectId) : ["imports", "idle"],
    queryFn: () => getImports(projectId!),
    enabled: projectId !== null,
  });

  useEffect(() => {
    if (!importsQuery.data || importsQuery.data.length === 0) {
      setSelectedImportBatchId(null);
      return;
    }
    if (
      selectedImportBatchId &&
      importsQuery.data.some((item) => item.import_batch_id === selectedImportBatchId)
    ) {
      return;
    }
    setSelectedImportBatchId(importsQuery.data[0].import_batch_id);
  }, [importsQuery.data, selectedImportBatchId]);

  const lookupQuery = useQuery({
    queryKey:
      projectId && lookupRequest
        ? lookupRequest.mode === "key"
          ? queryKeys.masterByKey(projectId, lookupRequest.value)
          : queryKeys.masterBySource(projectId, lookupRequest.value)
        : ["master-lookup", "idle"],
    queryFn: async () => {
      if (!projectId || !lookupRequest) {
        return { results: [] as MasterQueryRow[] };
      }
      if (lookupRequest.mode === "key") {
        return lookupMasterByKey(projectId, lookupRequest.value);
      }
      return lookupMasterBySource(projectId, lookupRequest.value);
    },
    enabled: Boolean(projectId && lookupRequest),
  });

  const normalizedApplyBranchRef = normalizeBranchRef(applyBranchRef);
  const importBatchTargetError = !normalizedApplyBranchRef
    ? "Enter a target `dev/<version>` branch before applying this import batch."
    : !isDevBranchRef(normalizedApplyBranchRef)
      ? "Import batch apply only supports `dev/<version>` target branches."
      : null;
  const directPatchTargetError = !normalizedApplyBranchRef
    ? "Enter `rel/current` or `dev/<version>` before applying a direct patch."
    : !isMutableBranchRef(normalizedApplyBranchRef)
      ? "Direct patch only supports `rel/current` or `dev/<version>` target branches."
      : null;

  const runJobMutation = useMutation({
    mutationFn: async (task: {
      run: () => Promise<{ job: { job_id: number } }>;
      devVersion?: string | null;
    }) => {
      const detail = await task.run();
      return {
        detail,
        devVersion: task.devVersion || null,
      };
    },
    onSuccess: async ({ detail, devVersion }) => {
      if (!projectId) {
        return;
      }
      await invalidateProjectScope(queryClient, projectId, {
        devVersion:
          devVersion ||
          (shell.branchRef?.startsWith("dev/") ? shell.branchRef.slice(4) : null),
        businessKey: shell.businessKey,
      });
      shell.notify(`Job #${detail.job.job_id} started.`, "success");
      navigate(shell.buildHref("/app/runs", { job: detail.job.job_id }));
    },
    onError: (error) => {
      shell.notify(error instanceof Error ? error.message : "Action failed.", "error");
    },
  });

  if (!shell.hasProjects || !projectId || !bootstrap || !schema) {
    return (
      <Panel kicker="Branch Ops" title="Branch-oriented read and write operations">
        <EmptyState
          title="No project selected"
          body="Branch Ops becomes available once the shell resolves a project and branch context."
        />
      </Panel>
    );
  }

  const directColumns = buildDirectColumns(schema);

  return (
    <div className={styles.layout}>
      <Panel
        kicker="Branch Ops"
        title="Branch-oriented reads and writes"
        description="Compare, queue, lookup, apply, replace, and trash flows are centralized here."
        testId="branches-page"
      >
        <div className={styles.tabs}>
          {TABS.map((tab) => (
            <button
              key={tab.key}
              className={cx(
                styles.tabButton,
                selectedTab === tab.key && styles.tabButtonActive,
              )}
              onClick={() => shell.setTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </Panel>

      {selectedTab === "compare" ? (
        <CompareTab
          currentDevBranch={currentDevBranch}
          compareSearch={compareSearch}
          compareState={compareState}
          compareDiff={compareDiff}
          comparePage={comparePage}
          rows={compareQuery.data?.rows || []}
          totalRows={compareQuery.data?.total_rows || 0}
          lang={shell.lang}
          devBranches={bootstrap.dev_branches.map((branch) => branch.branch_ref)}
          error={compareQuery.error instanceof Error ? compareQuery.error.message : null}
          onBranchChange={(branchRef) => {
            setComparePage(1);
            shell.setBranchRef(branchRef);
          }}
          onSearchChange={(value) => {
            setCompareSearch(value);
            setComparePage(1);
          }}
          onStateChange={(value) => {
            setCompareState(value);
            setComparePage(1);
          }}
          onDiffChange={(value) => {
            setCompareDiff(value);
            setComparePage(1);
          }}
          onPrevPage={() => setComparePage((value) => Math.max(1, value - 1))}
          onNextPage={() => setComparePage((value) => value + 1)}
          onInspect={shell.setBusinessKey}
        />
      ) : null}

      {selectedTab === "queue" ? (
        <QueueTab
          currentDevBranch={currentDevBranch}
          queueSearch={queueSearch}
          queueStatus={queueStatus}
          queuePage={queuePage}
          rows={queueQuery.data?.rows || []}
          totalRows={queueQuery.data?.total_rows || 0}
          lang={shell.lang}
          devBranches={bootstrap.dev_branches.map((branch) => branch.branch_ref)}
          onBranchChange={(branchRef) => {
            setQueuePage(1);
            shell.setBranchRef(branchRef);
          }}
          onSearchChange={(value) => {
            setQueueSearch(value);
            setQueuePage(1);
          }}
          onStatusChange={(value) => {
            setQueueStatus(value);
            setQueuePage(1);
          }}
          onPrevPage={() => setQueuePage((value) => Math.max(1, value - 1))}
          onNextPage={() => setQueuePage((value) => value + 1)}
          onInspect={shell.setBusinessKey}
          onOpenOverview={(businessKey) => {
            shell.setBusinessKey(businessKey);
            navigate(shell.buildHref("/app/overview", { branch: currentDevBranch }));
          }}
        />
      ) : null}

      {selectedTab === "lookup" ? (
        <LookupTab
          lookupKey={lookupKey}
          lookupSource={lookupSource}
          rows={lookupQuery.data?.results || []}
          lang={shell.lang}
          onLookupKeyChange={setLookupKey}
          onLookupSourceChange={setLookupSource}
          onRunKeyLookup={() => setLookupRequest({ mode: "key", value: lookupKey.trim() })}
          onRunSourceLookup={() =>
            setLookupRequest({ mode: "source", value: lookupSource.trim() })
          }
          onInspect={shell.setBusinessKey}
        />
      ) : null}

      {selectedTab === "apply" ? (
        <ApplyTab
          targetBranch={applyBranchRef}
          branchPlaceholder={
            applyMode === "import_batch"
              ? "dev/<version>"
              : "rel/current or dev/<version>"
          }
          applyMode={applyMode}
          importBatches={importsQuery.data || []}
          selectedImportBatchId={selectedImportBatchId}
          directRows={directRows}
          directColumns={directColumns}
          importBatchTargetError={importBatchTargetError}
          directPatchTargetError={directPatchTargetError}
          onBranchChange={setApplyBranchRef}
          onModeChange={setApplyMode}
          onImportBatchChange={setSelectedImportBatchId}
          onDirectRowsChange={setDirectRows}
          onAddRow={() => setDirectRows((rows) => [...rows, createDirectPatchRow(schema)])}
          onRunImportBatch={() => {
            if (importBatchTargetError || !selectedImportBatchId) {
              shell.notify(importBatchTargetError || "Select an import batch first.", "error");
              return;
            }
            runJobMutation.mutate({
              devVersion: normalizedApplyBranchRef.slice(4),
              run: () =>
                runBranchMutation(projectId, normalizedApplyBranchRef, {
                  kind: "import_batch",
                  import_batch_id: selectedImportBatchId,
                  mark_as_candidate_release: true,
                }),
            });
          }}
          onRunDirectPatch={() => {
            if (directPatchTargetError) {
              shell.notify(directPatchTargetError, "error");
              return;
            }
            runJobMutation.mutate({
              devVersion: normalizedApplyBranchRef.startsWith("dev/")
                ? normalizedApplyBranchRef.slice(4)
                : null,
              run: () =>
                runBranchMutation(projectId, normalizedApplyBranchRef, {
                  kind: "direct",
                  changes: rowsToDirectMutationChanges(directRows, schema),
                }),
            });
          }}
        />
      ) : null}

      {selectedTab === "replace" ? (
        <ReplaceTab
          replaceSource={replaceSource || currentDevBranch || ""}
          devBranches={bootstrap.dev_branches.map((branch) => branch.branch_ref)}
          preview={replacePreview}
          onSourceChange={setReplaceSource}
          onPreview={async () => {
            const preview = await previewBranchReplace(
              projectId,
              replaceSource || currentDevBranch!,
              "rel/current",
            );
            setReplacePreview(preview);
          }}
          onExecute={() =>
            runJobMutation.mutate({
              devVersion:
                shell.branchRef?.startsWith("dev/") ? shell.branchRef.slice(4) : null,
              run: () =>
                executeBranchReplace(
                  projectId,
                  replaceSource || currentDevBranch!,
                  "rel/current",
                ),
            })
          }
        />
      ) : null}

      {selectedTab === "trash" ? (
        <TrashTab
          deleteKeys={deleteKeys}
          restoreIds={restoreIds}
          onDeleteKeysChange={setDeleteKeys}
          onRestoreIdsChange={setRestoreIds}
          onDelete={() =>
            runJobMutation.mutate({
              devVersion:
                shell.branchRef?.startsWith("dev/") ? shell.branchRef.slice(4) : null,
              run: () =>
                deleteBranchBusinessKeys(
                  projectId,
                  shell.branchRef || "rel/current",
                  parseLineSeparatedList(deleteKeys),
                ),
            })
          }
          onRestore={() =>
            runJobMutation.mutate({
              devVersion:
                shell.branchRef?.startsWith("dev/") ? shell.branchRef.slice(4) : null,
              run: () => restoreVariants(projectId, parseVariantIdList(restoreIds)),
            })
          }
        />
      ) : null}
    </div>
  );
}

function CompareTab(props: {
  currentDevBranch: string | null;
  compareSearch: string;
  compareState: string;
  compareDiff: string;
  comparePage: number;
  rows: Array<{
    business_key: string;
    state: string;
    priority_status: string;
    diff_categories: string[];
    base: {
      source: string;
      file_name: string | null;
      translations: Record<string, string | null>;
    } | null;
    target: {
      source: string;
      file_name: string | null;
      translations: Record<string, string | null>;
    } | null;
  }>;
  totalRows: number;
  lang: string;
  devBranches: string[];
  error: string | null;
  onBranchChange: (branchRef: string | null) => void;
  onSearchChange: (value: string) => void;
  onStateChange: (value: string) => void;
  onDiffChange: (value: string) => void;
  onPrevPage: () => void;
  onNextPage: () => void;
  onInspect: (businessKey: string) => void;
}) {
  return (
    <Panel kicker="Compare" title={`rel/current -> ${props.currentDevBranch || "dev/*"}`}>
      <div className={styles.filters}>
        <label className={ui.field}>
          <span className={ui.fieldLabel}>Target branch</span>
          <select className={ui.select} value={props.currentDevBranch || ""} onChange={(event) => props.onBranchChange(event.target.value)}>
            {props.devBranches.map((branch) => (
              <option key={branch} value={branch}>
                {branch}
              </option>
            ))}
          </select>
        </label>
        <label className={ui.field}>
          <span className={ui.fieldLabel}>Search</span>
          <input className={ui.input} value={props.compareSearch} onChange={(event) => props.onSearchChange(event.target.value)} />
        </label>
        <label className={ui.field}>
          <span className={ui.fieldLabel}>State</span>
          <select className={ui.select} value={props.compareState} onChange={(event) => props.onStateChange(event.target.value)}>
            <option value="">All</option>
            <option value="aligned">aligned</option>
            <option value="diverged">diverged</option>
            <option value="base_only">base_only</option>
            <option value="target_only">target_only</option>
          </select>
        </label>
        <label className={ui.field}>
          <span className={ui.fieldLabel}>Diff</span>
          <select className={ui.select} value={props.compareDiff} onChange={(event) => props.onDiffChange(event.target.value)}>
            <option value="">All</option>
            <option value="source_changed">source_changed</option>
            <option value="translation_changed">translation_changed</option>
            <option value="remark_changed">remark_changed</option>
            <option value="file_name_changed">file_name_changed</option>
          </select>
        </label>
        <div className={ui.field}>
          <span className={ui.fieldLabel}>Page</span>
          <div className={styles.toolbar}>
            <button className={buttonClassName("secondary")} onClick={props.onPrevPage} disabled={props.comparePage <= 1}>
              Prev
            </button>
            <button className={buttonClassName("secondary")} onClick={props.onNextPage} disabled={props.comparePage >= Math.max(1, Math.ceil(props.totalRows / PAGE_SIZE))}>
              Next
            </button>
          </div>
        </div>
      </div>
      {props.error ? <InlineNotice tone="error" title="Failed to load compare rows">{props.error}</InlineNotice> : null}
      <CompareTable rows={props.rows} lang={props.lang} onInspect={props.onInspect} />
    </Panel>
  );
}

function QueueTab(props: {
  currentDevBranch: string | null;
  queueSearch: string;
  queueStatus: string;
  queuePage: number;
  rows: Array<{
    business_key: string;
    file_name: string | null;
    source: string;
    target_text: string;
    state: string;
    priority_status: string;
    diff_categories: string[];
  }>;
  totalRows: number;
  lang: string;
  devBranches: string[];
  onBranchChange: (branchRef: string | null) => void;
  onSearchChange: (value: string) => void;
  onStatusChange: (value: string) => void;
  onPrevPage: () => void;
  onNextPage: () => void;
  onInspect: (businessKey: string) => void;
  onOpenOverview: (businessKey: string) => void;
}) {
  return (
    <Panel kicker="Queue" title={props.currentDevBranch || "Translation queue"}>
      <div className={styles.filters}>
        <label className={ui.field}>
          <span className={ui.fieldLabel}>Target branch</span>
          <select className={ui.select} value={props.currentDevBranch || ""} onChange={(event) => props.onBranchChange(event.target.value)}>
            {props.devBranches.map((branch) => (
              <option key={branch} value={branch}>
                {branch}
              </option>
            ))}
          </select>
        </label>
        <label className={ui.field}>
          <span className={ui.fieldLabel}>Search</span>
          <input className={ui.input} value={props.queueSearch} onChange={(event) => props.onSearchChange(event.target.value)} />
        </label>
        <label className={ui.field}>
          <span className={ui.fieldLabel}>Priority</span>
          <select className={ui.select} value={props.queueStatus} onChange={(event) => props.onStatusChange(event.target.value)}>
            <option value="">All</option>
            <option value="needs_translation">needs_translation</option>
            <option value="needs_review">needs_review</option>
            <option value="fillable">fillable</option>
            <option value="source_mismatch">source_mismatch</option>
          </select>
        </label>
        <div className={ui.field}>
          <span className={ui.fieldLabel}>Page</span>
          <div className={styles.toolbar}>
            <button className={buttonClassName("secondary")} onClick={props.onPrevPage} disabled={props.queuePage <= 1}>
              Prev
            </button>
            <button className={buttonClassName("secondary")} onClick={props.onNextPage} disabled={props.queuePage >= Math.max(1, Math.ceil(props.totalRows / PAGE_SIZE))}>
              Next
            </button>
          </div>
        </div>
      </div>
      <QueueTable rows={props.rows} lang={props.lang} onInspect={props.onInspect} onOpenOverview={props.onOpenOverview} />
    </Panel>
  );
}

function LookupTab(props: {
  lookupKey: string;
  lookupSource: string;
  rows: MasterQueryRow[];
  lang: string;
  onLookupKeyChange: (value: string) => void;
  onLookupSourceChange: (value: string) => void;
  onRunKeyLookup: () => void;
  onRunSourceLookup: () => void;
  onInspect: (businessKey: string) => void;
}) {
  return (
    <Panel kicker="Lookup" title="Key and exact-source lookup">
      <div className={styles.twoColumn}>
        <label className={ui.field}>
          <span className={ui.fieldLabel}>Business key</span>
          <input className={ui.input} value={props.lookupKey} onChange={(event) => props.onLookupKeyChange(event.target.value)} />
          <button className={buttonClassName("secondary")} onClick={props.onRunKeyLookup}>Lookup key</button>
        </label>
        <label className={ui.field}>
          <span className={ui.fieldLabel}>Exact source</span>
          <input className={ui.input} value={props.lookupSource} onChange={(event) => props.onLookupSourceChange(event.target.value)} />
          <button className={buttonClassName("secondary")} onClick={props.onRunSourceLookup}>Lookup source</button>
        </label>
      </div>
      {props.rows.length ? (
        <LookupTable rows={props.rows} lang={props.lang} onInspect={props.onInspect} />
      ) : (
        <EmptyState title="No lookup results yet" body="Run a key or exact-source lookup to populate this panel." />
      )}
    </Panel>
  );
}

function ApplyTab(props: {
  targetBranch: string;
  branchPlaceholder: string;
  applyMode: "import_batch" | "direct";
  importBatches: Array<{ import_batch_id: number }>;
  selectedImportBatchId: number | null;
  directRows: DirectPatchRow[];
  directColumns: ReturnType<typeof buildDirectColumns>;
  importBatchTargetError: string | null;
  directPatchTargetError: string | null;
  onBranchChange: (branchRef: string) => void;
  onModeChange: (mode: "import_batch" | "direct") => void;
  onImportBatchChange: (importBatchId: number) => void;
  onDirectRowsChange: (rows: DirectPatchRow[]) => void;
  onAddRow: () => void;
  onRunImportBatch: () => void;
  onRunDirectPatch: () => void;
}) {
  return (
    <Panel kicker="Apply" title="Import batch and direct patch">
      <div className={styles.filters}>
        <label className={ui.field}>
          <span className={ui.fieldLabel}>Target branch</span>
          <input
            className={ui.input}
            value={props.targetBranch}
            onChange={(event) => props.onBranchChange(event.target.value)}
            placeholder={props.branchPlaceholder}
          />
        </label>
        <label className={ui.field}>
          <span className={ui.fieldLabel}>Mode</span>
          <select className={ui.select} value={props.applyMode} onChange={(event) => props.onModeChange(event.target.value as "import_batch" | "direct")}>
            <option value="import_batch">Import Batch</option>
            <option value="direct">Direct Patch</option>
          </select>
        </label>
      </div>
      {props.applyMode === "import_batch" ? (
        <div className={styles.stack}>
          {props.importBatchTargetError ? (
            <InlineNotice tone="warning" title="Import batch target required">
              {props.importBatchTargetError}
            </InlineNotice>
          ) : null}
          <label className={ui.field}>
            <span className={ui.fieldLabel}>Import batch</span>
            <select className={ui.select} value={props.selectedImportBatchId || ""} onChange={(event) => props.onImportBatchChange(Number(event.target.value))}>
              {props.importBatches.map((item) => (
                <option key={item.import_batch_id} value={item.import_batch_id}>
                  #{item.import_batch_id}
                </option>
              ))}
            </select>
          </label>
          <button
            className={buttonClassName("primary")}
            onClick={props.onRunImportBatch}
            disabled={!props.selectedImportBatchId || Boolean(props.importBatchTargetError)}
          >
            Apply import batch
          </button>
        </div>
      ) : (
        <div className={styles.stack}>
          {props.directPatchTargetError ? (
            <InlineNotice tone="warning" title="Direct patch target required">
              {props.directPatchTargetError}
            </InlineNotice>
          ) : null}
          <div className={styles.toolbar}>
            <button className={buttonClassName("secondary")} onClick={props.onAddRow}>Add row</button>
            <button
              className={buttonClassName("primary")}
              onClick={props.onRunDirectPatch}
              disabled={Boolean(props.directPatchTargetError)}
            >
              Apply direct patch
            </button>
          </div>
          <div className={styles.gridWrap}>
            <DataGrid
              columns={props.directColumns}
              rows={props.directRows}
              rowKeyGetter={(row) => row.id}
              onRowsChange={(rows) => props.onDirectRowsChange([...rows])}
              defaultColumnOptions={{ resizable: true }}
            />
          </div>
        </div>
      )}
    </Panel>
  );
}

function ReplaceTab(props: {
  replaceSource: string;
  devBranches: string[];
  preview: BranchReplacePreview | null;
  onSourceChange: (value: string) => void;
  onPreview: () => void;
  onExecute: () => void;
}) {
  return (
    <Panel kicker="Replace" title="Preview-first release replacement">
      <div className={styles.filters}>
        <label className={ui.field}>
          <span className={ui.fieldLabel}>Source dev branch</span>
          <select className={ui.select} value={props.replaceSource} onChange={(event) => props.onSourceChange(event.target.value)}>
            {props.devBranches.map((branch) => (
              <option key={branch} value={branch}>
                {branch}
              </option>
            ))}
          </select>
        </label>
        <div className={ui.field}>
          <span className={ui.fieldLabel}>Actions</span>
          <div className={styles.toolbar}>
            <button className={buttonClassName("secondary")} onClick={props.onPreview}>Preview replace</button>
            <button className={buttonClassName("primary")} onClick={props.onExecute} disabled={!props.preview}>Execute replace</button>
          </div>
        </div>
      </div>
      {props.preview ? <KeyValuePreview preview={props.preview} /> : <EmptyState title="Preview required" body="Run preview first to inspect impact before enabling execute." />}
    </Panel>
  );
}

function TrashTab(props: {
  deleteKeys: string;
  restoreIds: string;
  onDeleteKeysChange: (value: string) => void;
  onRestoreIdsChange: (value: string) => void;
  onDelete: () => void;
  onRestore: () => void;
}) {
  return (
    <Panel kicker="Trash / Restore" title="Branch delete and explicit variant restore">
      <div className={styles.twoColumn}>
        <label className={ui.field}>
          <span className={ui.fieldLabel}>Delete business keys</span>
          <textarea className={ui.textarea} value={props.deleteKeys} onChange={(event) => props.onDeleteKeysChange(event.target.value)} placeholder="One key per line" />
          <button className={buttonClassName("danger")} onClick={props.onDelete}>Delete from branch</button>
        </label>
        <label className={ui.field}>
          <span className={ui.fieldLabel}>Restore variant IDs</span>
          <textarea className={ui.textarea} value={props.restoreIds} onChange={(event) => props.onRestoreIdsChange(event.target.value)} placeholder={"101\n102"} />
          <button className={buttonClassName("primary")} onClick={props.onRestore}>Restore variants</button>
        </label>
      </div>
    </Panel>
  );
}

function normalizeBranchRef(value: string) {
  return value.trim();
}

function isDevBranchRef(value: string) {
  return value.startsWith("dev/") && value.length > 4;
}

function isMutableBranchRef(value: string) {
  return value === "rel/current" || isDevBranchRef(value);
}

function resolveApplyBranchRef(
  shellBranchRef: string | null,
  bootstrap: NonNullable<ReturnType<typeof useAppShell>["bootstrap"]>,
  branchSummary: ReturnType<typeof useAppShell>["branchSummary"],
) {
  const knownDevBranches = new Set<string>();
  if (bootstrap.candidate_dev_branch?.branch_ref) {
    knownDevBranches.add(bootstrap.candidate_dev_branch.branch_ref);
  }
  bootstrap.dev_branches.forEach((branch) => knownDevBranches.add(branch.branch_ref));
  branchSummary?.branches
    .filter((branch) => branch.branch_ref.startsWith("dev/"))
    .forEach((branch) => knownDevBranches.add(branch.branch_ref));
  if (shellBranchRef && knownDevBranches.has(shellBranchRef)) {
    return shellBranchRef;
  }
  return bootstrap.candidate_dev_branch?.branch_ref || bootstrap.dev_branches[0]?.branch_ref || "";
}
