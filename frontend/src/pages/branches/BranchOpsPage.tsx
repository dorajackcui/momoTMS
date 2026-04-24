import { useEffect, useRef, useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DataGrid } from "react-data-grid";
import { useNavigate } from "react-router-dom";

import { useAppShell } from "@/app/shell/AppShellContext";
import {
  deleteBranchBusinessKeys,
  executeBranchReplace,
  getBranchRows,
  getSameSourceCandidates,
  getScopeRows,
  lookupBranch,
  lookupScope,
  previewBranchReplace,
  runBranchMutation,
} from "@/domains/branches/api";
import type {
  BranchReplacePreview,
  SameSourceCandidateRow,
} from "@/domains/branches/types";
import { getImports } from "@/domains/imports/api";
import { invalidateProject, queryKeys } from "@/shared/api/queryKeys";
import { cx } from "@/shared/lib/cx";
import {
  EmptyState,
  InlineNotice,
  Panel,
  buttonClassName,
  ui,
} from "@/shared/ui/primitives";
import {
  KeyValuePreview,
  LookupTable,
  SameSourceCandidatesTable,
  ScopeRowsTable,
  buildDirectColumns,
} from "@/pages/branches/BranchOpsSections";
import {
  createDirectPatchRow,
  ensureDevBranch,
  parseLineSeparatedList,
  rowsToDirectMutationChanges,
  type DirectPatchRow,
} from "@/pages/branches/model";

import styles from "@/pages/branches/BranchOpsPage.module.css";

type LookupRow = {
  business_key: string;
  scope_ref: string;
  variant_id: number;
  file_name: string | null;
  source: string;
  translations: Record<string, string | null>;
  remarks: Record<string, string | null>;
};

const PAGE_SIZE = 25;
const TABS = [
  { key: "scope", label: "Scope" },
  { key: "lookup", label: "Lookup" },
  { key: "apply", label: "Apply" },
  { key: "replace", label: "Replace" },
  { key: "trash", label: "Trash" },
] as const;

export function BranchOpsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const shell = useAppShell();
  const [scopeSearchKey, setScopeSearchKey] = useState("");
  const [scopeSearchSource, setScopeSearchSource] = useState("");
  const [scopePage, setScopePage] = useState(1);
  const [scopeRef, setScopeRef] = useState(shell.branchRef || "master");
  const [lookupRef, setLookupRef] = useState("master");
  const [lookupKey, setLookupKey] = useState("");
  const [lookupSource, setLookupSource] = useState("");
  const [lookupRequest, setLookupRequest] = useState<{
    scopeRef: string;
    mode: "key" | "source";
    value: string;
  } | null>(null);
  const [historyKey, setHistoryKey] = useState("");
  const [historySource, setHistorySource] = useState("");
  const [historyRequest, setHistoryRequest] = useState<{
    businessKey: string;
    source: string;
  } | null>(null);
  const [applyMode, setApplyMode] = useState<"import_batch" | "direct">("import_batch");
  const [selectedImportBatchId, setSelectedImportBatchId] = useState<number | null>(
    null,
  );
  const [directRows, setDirectRows] = useState<DirectPatchRow[]>([]);
  const [replaceSource, setReplaceSource] = useState("");
  const [replacePreview, setReplacePreview] = useState<BranchReplacePreview | null>(null);
  const [deleteKeys, setDeleteKeys] = useState("");
  const [applyBranchRef, setApplyBranchRef] = useState("");
  const lastApplyProjectIdRef = useRef<number | null>(null);
  const lastAutoApplyBranchRefRef = useRef("");

  const selectedTab = resolveBranchOpsTab(shell.tab);
  const projectId = shell.projectId;
  const bootstrap = shell.bootstrap;
  const schema = bootstrap?.schema || null;
  const preferredDevBranch = bootstrap?.dev_branches[0]?.branch_ref || null;
  const currentDevBranch = ensureDevBranch(shell.branchRef, preferredDevBranch);
  const scopeOptions = [
    "master",
    "rel/current",
    ...(bootstrap?.dev_branches.map((branch) => branch.branch_ref) || []),
  ];

  useEffect(() => {
    if (schema && directRows.length === 0) {
      setDirectRows([createDirectPatchRow(schema)]);
    }
  }, [directRows.length, schema]);

  useEffect(() => {
    if (shell.branchRef && scopeRef !== "master" && scopeRef !== shell.branchRef) {
      setScopeRef(shell.branchRef);
    }
  }, [scopeRef, shell.branchRef]);

  useEffect(() => {
    if (!scopeOptions.includes(lookupRef)) {
      setLookupRef("master");
    }
  }, [lookupRef, scopeOptions]);

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

  const branchRowsQuery = useQuery({
    queryKey:
      projectId && shell.lang
        ? queryKeys.branchRows(projectId, scopeRef, {
            search_business_key: scopeSearchKey,
            search_source: scopeSearchSource,
            page: scopePage,
          })
        : ["branch-rows", "idle"],
    queryFn: () => {
      const params = {
        search_business_key: scopeSearchKey || undefined,
        search_source: scopeSearchSource || undefined,
        page: scopePage,
        page_size: PAGE_SIZE,
      };
      if (scopeRef === "master" || scopeRef === "orphan") {
        return getScopeRows(projectId!, scopeRef, params);
      }
      return getBranchRows(projectId!, scopeRef, params);
    },
    enabled: Boolean(projectId && shell.lang),
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
        ? queryKeys.branchLookup(projectId, lookupRequest.scopeRef, {
            [lookupRequest.mode === "key" ? "business_key" : "source"]:
              lookupRequest.value,
          })
        : ["branch-lookup", "idle"],
    queryFn: async () => {
      if (!projectId || !lookupRequest) {
        return { rows: [] as LookupRow[] };
      }
      const ref = lookupRequest.scopeRef;
      const params = {
        business_key:
          lookupRequest.mode === "key" ? lookupRequest.value : undefined,
        source: lookupRequest.mode === "source" ? lookupRequest.value : undefined,
      };
      const payload =
        ref === "master" || ref === "orphan"
          ? await lookupScope(projectId, ref, params)
          : await lookupBranch(projectId, ref, params);
      return {
        rows: payload.rows.map((row) => ({
          business_key: row.business_key,
          scope_ref: payload.branch_ref,
          variant_id: row.variant_id,
          file_name: row.file_name,
          source: row.source,
          translations: row.translations,
          remarks: row.remarks,
        })),
      };
    },
    enabled: Boolean(projectId && lookupRequest),
  });

  const historyQuery = useQuery({
    queryKey:
      projectId && historyRequest
        ? queryKeys.sameSourceCandidates(
            projectId,
            historyRequest.businessKey,
            historyRequest.source,
          )
        : ["same-source-candidates", "idle"],
    queryFn: async () => {
      if (!projectId || !historyRequest) {
        return { rows: [] as SameSourceCandidateRow[] };
      }
      return getSameSourceCandidates(projectId, {
        business_key: historyRequest.businessKey,
        source: historyRequest.source,
      });
    },
    enabled: Boolean(projectId && historyRequest),
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
      await invalidateProject(queryClient, projectId, {
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
        title="Scope-first reads and workflow actions"
        description="Scope catalog, project lookup, apply, replace, and trash flows are separated here."
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

      {selectedTab === "scope" ? (
        <ScopeTab
          currentScopeRef={scopeRef}
          scopeOptions={scopeOptions}
          scopeSearchKey={scopeSearchKey}
          scopeSearchSource={scopeSearchSource}
          scopePage={scopePage}
          rows={branchRowsQuery.data?.rows || []}
          totalRows={branchRowsQuery.data?.total_rows || 0}
          lang={shell.lang}
          error={branchRowsQuery.error instanceof Error ? branchRowsQuery.error.message : null}
          onScopeChange={(nextScopeRef) => {
            setScopePage(1);
            setScopeRef(nextScopeRef);
            shell.setBranchRef(nextScopeRef === "master" ? null : nextScopeRef);
          }}
          onSearchKeyChange={(value) => {
            setScopeSearchKey(value);
            setScopePage(1);
          }}
          onSearchSourceChange={(value) => {
            setScopeSearchSource(value);
            setScopePage(1);
          }}
          onPrevPage={() => setScopePage((value) => Math.max(1, value - 1))}
          onNextPage={() => setScopePage((value) => value + 1)}
          onInspect={shell.setBusinessKey}
        />
      ) : null}

      {selectedTab === "lookup" ? (
        <LookupTab
          lookupRef={lookupRef}
          scopeOptions={scopeOptions}
          lookupKey={lookupKey}
          lookupSource={lookupSource}
          lookupRows={lookupQuery.data?.rows || []}
          historyKey={historyKey}
          historySource={historySource}
          historyRows={historyQuery.data?.rows || []}
          lang={shell.lang}
          onLookupScopeChange={setLookupRef}
          onLookupKeyChange={setLookupKey}
          onLookupSourceChange={setLookupSource}
          onRunKeyLookup={() =>
            setLookupRequest({
              scopeRef: lookupRef,
              mode: "key",
              value: lookupKey.trim(),
            })
          }
          onRunSourceLookup={() =>
            setLookupRequest({
              scopeRef: lookupRef,
              mode: "source",
              value: lookupSource.trim(),
            })
          }
          onHistoryKeyChange={setHistoryKey}
          onHistorySourceChange={setHistorySource}
          onRunSameSourceLookup={() =>
            setHistoryRequest({
              businessKey: historyKey.trim(),
              source: historySource.trim(),
            })
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
          onDeleteKeysChange={setDeleteKeys}
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
        />
      ) : null}
    </div>
  );
}

function ScopeTab(props: {
  currentScopeRef: string;
  scopeOptions: string[];
  scopeSearchKey: string;
  scopeSearchSource: string;
  scopePage: number;
  rows: Array<{
    variant_id: number;
    business_key: string;
    file_name: string | null;
    source: string;
    translations: Record<string, string | null>;
    state: string;
    pivot_status: string;
    bindings: Array<{ branch_ref: string }>;
  }>;
  totalRows: number;
  lang: string;
  error: string | null;
  onScopeChange: (scopeRef: string) => void;
  onSearchKeyChange: (value: string) => void;
  onSearchSourceChange: (value: string) => void;
  onPrevPage: () => void;
  onNextPage: () => void;
  onInspect: (businessKey: string) => void;
}) {
  return (
    <Panel kicker="Scope" title={props.currentScopeRef}>
      <div className={styles.filters}>
        <label className={ui.field}>
          <span className={ui.fieldLabel}>Scope</span>
          <select
            className={ui.select}
            value={props.currentScopeRef}
            onChange={(event) => props.onScopeChange(event.target.value)}
          >
            {props.scopeOptions.map((scope) => (
              <option key={scope} value={scope}>
                {scope}
              </option>
            ))}
          </select>
        </label>
        <label className={ui.field}>
          <span className={ui.fieldLabel}>Business key search</span>
          <input
            className={ui.input}
            value={props.scopeSearchKey}
            onChange={(event) => props.onSearchKeyChange(event.target.value)}
          />
        </label>
        <label className={ui.field}>
          <span className={ui.fieldLabel}>Source search</span>
          <input
            className={ui.input}
            value={props.scopeSearchSource}
            onChange={(event) => props.onSearchSourceChange(event.target.value)}
          />
        </label>
        <div className={ui.field}>
          <span className={ui.fieldLabel}>Page</span>
          <div className={styles.toolbar}>
            <button
              className={buttonClassName("secondary")}
              onClick={props.onPrevPage}
              disabled={props.scopePage <= 1}
            >
              Prev
            </button>
            <button
              className={buttonClassName("secondary")}
              onClick={props.onNextPage}
              disabled={props.scopePage >= Math.max(1, Math.ceil(props.totalRows / PAGE_SIZE))}
            >
              Next
            </button>
          </div>
        </div>
      </div>
      {props.error ? (
        <InlineNotice tone="error" title="Failed to load scope rows">
          {props.error}
        </InlineNotice>
      ) : null}
      <ScopeRowsTable rows={props.rows} lang={props.lang} onInspect={props.onInspect} />
    </Panel>
  );
}

function LookupTab(props: {
  lookupRef: string;
  scopeOptions: string[];
  lookupKey: string;
  lookupSource: string;
  lookupRows: LookupRow[];
  historyKey: string;
  historySource: string;
  historyRows: SameSourceCandidateRow[];
  lang: string;
  onLookupScopeChange: (value: string) => void;
  onLookupKeyChange: (value: string) => void;
  onLookupSourceChange: (value: string) => void;
  onRunKeyLookup: () => void;
  onRunSourceLookup: () => void;
  onHistoryKeyChange: (value: string) => void;
  onHistorySourceChange: (value: string) => void;
  onRunSameSourceLookup: () => void;
  onInspect: (businessKey: string) => void;
}) {
  return (
    <div className={styles.stack}>
      <Panel kicker="Lookup" title="Scope lookup">
        <div className={styles.filters}>
          <label className={ui.field}>
            <span className={ui.fieldLabel}>Scope</span>
            <select
              className={ui.select}
              value={props.lookupRef}
              onChange={(event) => props.onLookupScopeChange(event.target.value)}
            >
              {props.scopeOptions.map((scope) => (
                <option key={scope} value={scope}>
                  {scope}
                </option>
              ))}
            </select>
          </label>
          <label className={ui.field}>
            <span className={ui.fieldLabel}>Business key</span>
            <input
              className={ui.input}
              value={props.lookupKey}
              onChange={(event) => props.onLookupKeyChange(event.target.value)}
            />
            <button className={buttonClassName("secondary")} onClick={props.onRunKeyLookup}>
              Lookup key
            </button>
          </label>
          <label className={ui.field}>
            <span className={ui.fieldLabel}>Exact source</span>
            <input
              className={ui.input}
              value={props.lookupSource}
              onChange={(event) => props.onLookupSourceChange(event.target.value)}
            />
            <button
              className={buttonClassName("secondary")}
              onClick={props.onRunSourceLookup}
            >
              Lookup source
            </button>
          </label>
        </div>
        {props.lookupRows.length ? (
          <LookupTable rows={props.lookupRows} lang={props.lang} onInspect={props.onInspect} />
        ) : (
          <EmptyState
            title="No lookup results yet"
            body="Run a scope lookup by key or exact source to populate this panel."
          />
        )}
      </Panel>

      <Panel kicker="History" title="Same-source candidates">
        <div className={styles.twoColumn}>
          <label className={ui.field}>
            <span className={ui.fieldLabel}>Business key</span>
            <input
              className={ui.input}
              value={props.historyKey}
              onChange={(event) => props.onHistoryKeyChange(event.target.value)}
            />
          </label>
          <label className={ui.field}>
            <span className={ui.fieldLabel}>Exact source</span>
            <input
              className={ui.input}
              value={props.historySource}
              onChange={(event) => props.onHistorySourceChange(event.target.value)}
            />
          </label>
        </div>
        <div className={styles.toolbar}>
          <button className={buttonClassName("secondary")} onClick={props.onRunSameSourceLookup}>
            Find same-source candidates
          </button>
        </div>
        <SameSourceCandidatesTable
          rows={props.historyRows}
          lang={props.lang}
          onInspect={props.onInspect}
        />
      </Panel>
    </div>
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
  onImportBatchChange: (importBatchId: number | null) => void;
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
          <select
            className={ui.select}
            value={props.applyMode}
            onChange={(event) =>
              props.onModeChange(event.target.value as "import_batch" | "direct")
            }
          >
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
            <select
              className={ui.select}
              value={props.selectedImportBatchId || ""}
              onChange={(event) => props.onImportBatchChange(Number(event.target.value))}
            >
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
            <button className={buttonClassName("secondary")} onClick={props.onAddRow}>
              Add row
            </button>
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
          <select
            className={ui.select}
            value={props.replaceSource}
            onChange={(event) => props.onSourceChange(event.target.value)}
          >
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
            <button className={buttonClassName("secondary")} onClick={props.onPreview}>
              Preview replace
            </button>
            <button
              className={buttonClassName("primary")}
              onClick={props.onExecute}
              disabled={!props.preview}
            >
              Execute replace
            </button>
          </div>
        </div>
      </div>
      {props.preview ? (
        <KeyValuePreview preview={props.preview} />
      ) : (
        <EmptyState
          title="Preview required"
          body="Run preview first to inspect impact before enabling execute."
        />
      )}
    </Panel>
  );
}

function TrashTab(props: {
  deleteKeys: string;
  onDeleteKeysChange: (value: string) => void;
  onDelete: () => void;
}) {
  return (
    <Panel kicker="Trash" title="Branch delete">
      <label className={ui.field}>
        <span className={ui.fieldLabel}>Delete business keys</span>
        <textarea
          className={ui.textarea}
          value={props.deleteKeys}
          onChange={(event) => props.onDeleteKeysChange(event.target.value)}
          placeholder="One key per line"
        />
        <button className={buttonClassName("danger")} onClick={props.onDelete}>
          Delete from branch
        </button>
      </label>
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

function resolveBranchOpsTab(tab: string | null) {
  if (tab === "compare" || tab === "queue" || tab === "scope") {
    return "scope";
  }
  if (tab === "lookup" || tab === "apply" || tab === "replace" || tab === "trash") {
    return tab;
  }
  return "scope";
}

function resolveApplyBranchRef(
  shellBranchRef: string | null,
  bootstrap: NonNullable<ReturnType<typeof useAppShell>["bootstrap"]>,
  branchSummary: ReturnType<typeof useAppShell>["branchSummary"],
) {
  const knownDevBranches = new Set<string>();
  const knownDevBranchList: string[] = [];
  const addKnownDevBranch = (branchRef: string) => {
    if (knownDevBranches.has(branchRef)) {
      return;
    }
    knownDevBranches.add(branchRef);
    knownDevBranchList.push(branchRef);
  };

  bootstrap.dev_branches.forEach((branch) => addKnownDevBranch(branch.branch_ref));
  branchSummary?.branches.forEach((branch) => {
    if (branch.branch_ref.startsWith("dev/")) {
      addKnownDevBranch(branch.branch_ref);
    }
  });

  if (shellBranchRef && knownDevBranches.has(shellBranchRef)) {
    return shellBranchRef;
  }
  return knownDevBranchList[0] || "";
}
