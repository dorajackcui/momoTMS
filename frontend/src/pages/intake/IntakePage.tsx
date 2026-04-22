import { useEffect, useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { useAppShell } from "@/app/shell/AppShellContext";
import {
  confirmImportUpload,
  getImportReport,
  getImports,
  previewImportUpload,
} from "@/domains/imports/api";
import type {
  ImportSheetMapping,
  ImportUploadPreview,
} from "@/domains/imports/types";
import { getJobDetail } from "@/domains/jobs/api";
import { ImportPreviewDialog } from "@/features/import-preview/ImportPreviewDialog";
import { invalidateProject, queryKeys } from "@/shared/api/queryKeys";
import { formatTimestamp, stringifyValue } from "@/shared/lib/format";
import {
  EmptyState,
  InlineNotice,
  KeyValueList,
  Panel,
  buttonClassName,
  ui,
} from "@/shared/ui/primitives";
import { cx } from "@/shared/lib/cx";

import styles from "@/pages/intake/IntakePage.module.css";

const folderInputAttributes = {
  webkitdirectory: "",
  directory: "",
} as Record<string, string>;

export function IntakePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const shell = useAppShell();
  const [selectedImportBatchId, setSelectedImportBatchId] = useState<number | null>(
    null,
  );
  const [preview, setPreview] = useState<ImportUploadPreview | null>(null);
  const [mappings, setMappings] = useState<Record<string, ImportSheetMapping>>({});

  const importsQuery = useQuery({
    queryKey: shell.projectId ? queryKeys.imports(shell.projectId) : ["imports", "idle"],
    queryFn: () => getImports(shell.projectId!),
    enabled: shell.projectId !== null,
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

  const reportQuery = useQuery({
    queryKey:
      shell.projectId && selectedImportBatchId
        ? queryKeys.importReport(shell.projectId, selectedImportBatchId)
        : ["import-report", "idle"],
    queryFn: () => getImportReport(shell.projectId!, selectedImportBatchId!),
    enabled: Boolean(shell.projectId && selectedImportBatchId),
  });

  const previewMutation = useMutation({
    mutationFn: (files: File[]) => previewImportUpload(shell.projectId!, files),
    onSuccess: (result) => {
      setPreview(result);
      setMappings(buildInitialMappings(result));
    },
    onError: (error) => {
      shell.notify(error instanceof Error ? error.message : "Preview failed.", "error");
    },
  });

  const confirmMutation = useMutation({
    mutationFn: async () => {
      if (!preview || !shell.projectId) {
        throw new Error("Import preview is required.");
      }
      const started = await confirmImportUpload(
        shell.projectId,
        preview.upload_session_id,
        JSON.stringify(mappings),
      );
      let current = started;
      while (current.job.status === "running") {
        await new Promise((resolve) => window.setTimeout(resolve, 500));
        current = await getJobDetail(shell.projectId, current.job.job_id);
      }
      if (current.job.status !== "success") {
        throw new Error(
          current.job.error_message ||
            `Import job #${current.job.job_id} failed.`,
        );
      }
      return current;
    },
    onSuccess: async (detail) => {
      if (!shell.projectId) {
        return;
      }
      await invalidateProject(queryClient, shell.projectId);
      setPreview(null);
      setMappings({});
      const importBatchId = Number(detail.job.summary.import_batch_id || 0) || null;
      if (importBatchId) {
        setSelectedImportBatchId(importBatchId);
      }
      shell.notify(`Import batch is ready. Continue in Branch Ops / Apply.`, "success");
      navigate(shell.buildHref("/app/branches", { tab: "apply" }));
    },
    onError: (error) => {
      shell.notify(error instanceof Error ? error.message : "Import failed.", "error");
    },
  });

  if (!shell.hasProjects || !shell.projectId || !shell.bootstrap) {
    return (
      <Panel kicker="Intake" title="Upload preview and import batching">
        <EmptyState
          title="No project selected"
          body="Create a project first so intake can validate workbook headers against the fixed project schema."
        />
      </Panel>
    );
  }

  const mappingIssues = listMissingMappings(preview, mappings);

  return (
    <div className={styles.layout}>
      <Panel
        kicker="Intake"
        title="Upload preview and import history"
        description="This page owns upload preview, mapping confirmation, batch history, and import reports. Downstream branch execution lives in Branch Ops."
        testId="intake-page"
      >
        <KeyValueList
          items={[
            [
              "translation columns",
              shell.bootstrap.schema.translation_columns.join(", ") || "-",
            ],
            ["remark columns", shell.bootstrap.schema.remark_columns.join(", ") || "-"],
          ]}
        />
        <label className={ui.field}>
          <span className={ui.fieldLabel}>Upload folder</span>
          <input
            className={ui.input}
            type="file"
            multiple
            {...folderInputAttributes}
            onChange={(event) => {
              const files = Array.from(event.target.files || []);
              if (files.length > 0) {
                previewMutation.mutate(files);
                event.target.value = "";
              }
            }}
            data-testid="intake-folder-input"
          />
        </label>
        <InlineNotice tone="info" title="Schema-driven import mapping">
          `business_key` and `source` are required. Unmapped translation or remark
          fields remain unchanged during import apply.
        </InlineNotice>
      </Panel>

      <div className={styles.columns}>
        <Panel
          kicker="History"
          title="Recent import batches"
          description="Pick a batch to inspect the persisted import report."
        >
          {importsQuery.isError ? (
            <InlineNotice tone="error" title="Failed to load import batches">
              {importsQuery.error instanceof Error
                ? importsQuery.error.message
                : "Request failed."}
            </InlineNotice>
          ) : null}
          {importsQuery.data && importsQuery.data.length > 0 ? (
            <div className={styles.list} data-testid="intake-batch-list">
              {importsQuery.data.map((item) => (
                <button
                  key={item.import_batch_id}
                  className={cx(
                    styles.itemButton,
                    selectedImportBatchId === item.import_batch_id &&
                      styles.itemButtonActive,
                  )}
                  onClick={() => setSelectedImportBatchId(item.import_batch_id)}
                >
                  <strong>batch #{item.import_batch_id}</strong>
                  <span className={styles.meta}>
                    {formatTimestamp(item.created_at)}
                  </span>
                  <span className={styles.meta}>
                    {item.files_scanned} files · {item.rows_scanned} rows · {item.issues} issues
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No import batches yet"
              body="Upload a workbook folder to create the first persisted batch."
            />
          )}
        </Panel>

        <Panel
          kicker="Report"
          title={
            selectedImportBatchId
              ? `Import batch #${selectedImportBatchId}`
              : "Pick a batch"
          }
          description="The selected batch report previews persisted row-level outcomes."
        >
          {reportQuery.isError ? (
            <InlineNotice tone="error" title="Failed to load import report">
              {reportQuery.error instanceof Error
                ? reportQuery.error.message
                : "Request failed."}
            </InlineNotice>
          ) : null}
          {reportQuery.data ? (
            reportQuery.data.rows.length > 0 ? (
              <ReportPreview rows={reportQuery.data.rows.slice(0, 10)} />
            ) : (
              <EmptyState
                title="No report rows"
                body="This batch does not expose row previews."
              />
            )
          ) : (
            <EmptyState
              title="No batch selected"
              body="Choose an import batch on the left to inspect its report."
            />
          )}
        </Panel>
      </div>

      {preview ? (
        <ImportPreviewDialog
          preview={preview}
          mappings={mappings}
          issues={mappingIssues}
          onClose={() => {
            if (!confirmMutation.isPending) {
              setPreview(null);
            }
          }}
          onConfirm={() => confirmMutation.mutate()}
          onUpdateMapping={(sheetKey, kind, fieldKey, value) => {
            setMappings((current) => {
              const existing = current[sheetKey];
              if (!existing) {
                return current;
              }
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
          }}
        />
      ) : null}
    </div>
  );
}

function buildInitialMappings(preview: ImportUploadPreview) {
  return Object.fromEntries(
    preview.sheet_previews.map((sheet) => [
      sheet.sheet_key,
      {
        business_key: String(sheet.suggested_mapping?.business_key || ""),
        source: String(sheet.suggested_mapping?.source || ""),
        translation_columns: Object.fromEntries(
          Object.entries(sheet.suggested_mapping?.translation_columns || {}).map(
            ([key, value]) => [key, String(value || "")],
          ),
        ),
        remark_columns: Object.fromEntries(
          Object.entries(sheet.suggested_mapping?.remark_columns || {}).map(
            ([key, value]) => [key, String(value || "")],
          ),
        ),
      },
    ]),
  );
}

function listMissingMappings(
  preview: ImportUploadPreview | null,
  mappings: Record<string, ImportSheetMapping>,
) {
  if (!preview) {
    return [];
  }
  return preview.sheet_previews
    .map((sheet) => {
      const mapping = mappings[sheet.sheet_key];
      const missing: string[] = [];
      if (!mapping?.business_key) {
        missing.push("business_key");
      }
      if (!mapping?.source) {
        missing.push("source");
      }
      return { sheet_key: sheet.sheet_key, missing };
    })
    .filter((item) => item.missing.length > 0);
}

function ReportPreview(props: { rows: Array<Record<string, unknown>> }) {
  const columns = Array.from(new Set(props.rows.flatMap((row) => Object.keys(row)))).slice(
    0,
    8,
  );
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row, rowIndex) => (
            <tr key={`report-row-${rowIndex}`}>
              {columns.map((column) => (
                <td key={`${rowIndex}-${column}`}>{stringifyValue(row[column])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
