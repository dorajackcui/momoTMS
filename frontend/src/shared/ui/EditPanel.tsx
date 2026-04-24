import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import type { BranchMutationInput, BranchMutationChange, EffectForecastPreview } from "@/domains/branches/types";
import type { ImportBatchSummary } from "@/domains/imports/types";
import type { JobDetail } from "@/domains/jobs/types";
import type { ProjectSchema } from "@/domains/projects/types";
import { previewBranchMutation, runBranchMutation } from "@/domains/branches/api";
import { buttonClassName, InlineNotice, StatGrid } from "@/shared/ui/primitives";

import styles from "@/shared/ui/EditPanel.module.css";

type MutationType = "range" | "content";
type InputMethod = "import_batch" | "direct";

export type EditPanelProps = {
  projectId: number;
  branchRef: string;
  schema: ProjectSchema;
  allowRange: boolean;
  importBatches: ImportBatchSummary[];
  onJobCreated: (job: JobDetail) => void;
};

export function EditPanel(props: EditPanelProps) {
  const { projectId, branchRef, schema, allowRange, importBatches, onJobCreated } = props;

  const [mutationType, setMutationType] = useState<MutationType>("content");
  const [inputMethod, setInputMethod] = useState<InputMethod>("direct");
  const [selectedBatchId, setSelectedBatchId] = useState<number | null>(null);
  const [directText, setDirectText] = useState("");
  const [preview, setPreview] = useState<EffectForecastPreview | null>(null);

  const previewMut = useMutation({
    mutationFn: () => {
      const input = buildInput();
      if (!input) throw new Error("No input");
      return previewBranchMutation(projectId, branchRef, input);
    },
    onSuccess: (data) => setPreview(data),
  });

  const executeMut = useMutation({
    mutationFn: () => {
      const input = buildInput();
      if (!input) throw new Error("No input");
      return runBranchMutation(projectId, branchRef, input);
    },
    onSuccess: (data) => {
      onJobCreated(data);
      setPreview(null);
      setDirectText("");
    },
  });

  function buildInput(): BranchMutationInput | null {
    if (inputMethod === "import_batch") {
      if (!selectedBatchId) return null;
      return { kind: "import_batch", import_batch_id: selectedBatchId };
    }
    const changes = parseDirectChanges(directText, schema);
    if (changes.length === 0) return null;
    return { kind: "direct", changes };
  }

  const hasInput = inputMethod === "import_batch" ? selectedBatchId !== null : directText.trim().length > 0;

  return (
    <div className={styles.panel}>
      <div className={styles.selectors}>
        {allowRange ? (
          <fieldset className={styles.fieldset}>
            <legend>Mutation type</legend>
            <label><input type="radio" checked={mutationType === "range"} onChange={() => setMutationType("range")} /> Range (add/remove entries)</label>
            <label><input type="radio" checked={mutationType === "content"} onChange={() => setMutationType("content")} /> Content (edit translations/remarks)</label>
          </fieldset>
        ) : (
          <p className={styles.hint}>Content mutation on {branchRef}</p>
        )}
        <fieldset className={styles.fieldset}>
          <legend>Input method</legend>
          <label><input type="radio" checked={inputMethod === "import_batch"} onChange={() => setInputMethod("import_batch")} /> Import batch</label>
          <label><input type="radio" checked={inputMethod === "direct"} onChange={() => setInputMethod("direct")} /> Direct</label>
        </fieldset>
      </div>

      {inputMethod === "import_batch" ? (
        <div className={styles.inputArea}>
          <select value={selectedBatchId ?? ""} onChange={(e) => setSelectedBatchId(e.target.value ? Number(e.target.value) : null)}>
            <option value="">Select import batch...</option>
            {importBatches.map((b) => (
              <option key={b.import_batch_id} value={b.import_batch_id}>
                Batch #{b.import_batch_id} — {b.rows_scanned} rows — {b.created_at}
              </option>
            ))}
          </select>
        </div>
      ) : (
        <div className={styles.inputArea}>
          <textarea
            className={styles.directInput}
            value={directText}
            onChange={(e) => setDirectText(e.target.value)}
            placeholder={`business_key\tsource\t${schema.translation_columns.join("\t")}`}
            rows={8}
          />
          <p className={styles.hint}>
            Tab-separated rows. Header columns may include business_key, source, file_name,
            translation columns ({schema.translation_columns.join(", ")}), and remark columns ({schema.remark_columns.join(", ") || "none"}).
          </p>
        </div>
      )}

      <div className={styles.actions}>
        <button
          className={buttonClassName("secondary")}
          disabled={!hasInput || previewMut.isPending}
          onClick={() => previewMut.mutate()}
        >
          {previewMut.isPending ? "Previewing..." : "Preview"}
        </button>
        {preview && (
          <button
            className={buttonClassName("primary")}
            disabled={executeMut.isPending}
            onClick={() => executeMut.mutate()}
          >
            {executeMut.isPending ? "Executing..." : "Execute"}
          </button>
        )}
      </div>

      {previewMut.isError && (
        <InlineNotice tone="error">{String(previewMut.error)}</InlineNotice>
      )}
      {executeMut.isError && (
        <InlineNotice tone="error">{String(executeMut.error)}</InlineNotice>
      )}

      {preview && (
        <div className={styles.previewResult}>
          <StatGrid items={Object.entries(preview.summary).map(([k, v]) => ({ label: k, value: String(v) }))} />
          <table className={styles.previewTable}>
            <thead>
              <tr>
                {preview.rows.length > 0 && Object.keys(preview.rows[0]).map((k) => <th key={k}>{k}</th>)}
              </tr>
            </thead>
            <tbody>
              {preview.rows.slice(0, 50).map((row, i) => (
                <tr key={i}>
                  {Object.values(row).map((v, j) => <td key={j}>{String(v ?? "")}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function parseDirectChanges(text: string, schema: ProjectSchema): BranchMutationChange[] {
  const lines = text.trim().split(/\r?\n/).filter((l) => l.trim());
  if (lines.length === 0) return [];
  const firstParts = splitTsvLine(lines[0]);
  const hasHeader = firstParts.some((part) => part.trim() === "business_key");
  const headers = hasHeader
    ? firstParts.map((part) => part.trim())
    : ["business_key", "source", ...schema.translation_columns, ...schema.remark_columns];
  const dataLines = hasHeader ? lines.slice(1) : lines;

  return dataLines.map((line) => parseDirectChangeLine(splitTsvLine(line), headers, schema));
}

function parseDirectChangeLine(
  parts: string[],
  headers: string[],
  schema: ProjectSchema,
): BranchMutationChange {
  const change: BranchMutationChange = {
    business_key: "",
    translations_by_lang: {},
    remarks_by_key: {},
  };

  headers.forEach((header, index) => {
    if (index >= parts.length) return;
    const rawValue = parts[index];
    const value = rawValue.trim();
    if (header === "business_key") {
      change.business_key = value;
      return;
    }
    if (header === "source") {
      if (value) change.source = value;
      return;
    }
    if (header === "file_name") {
      if (value) change.file_name = value;
      return;
    }

    const translationColumn = parseKnownColumn(header, "translation", schema.translation_columns);
    if (translationColumn) {
      change.translations_by_lang[translationColumn] = rawValue;
      return;
    }

    const remarkColumn = parseKnownColumn(header, "remark", schema.remark_columns);
    if (remarkColumn) {
      change.remarks_by_key[remarkColumn] = rawValue;
    }
  });

  return change;
}

function parseKnownColumn(
  header: string,
  prefix: "translation" | "remark",
  knownColumns: string[],
): string | null {
  const column = header.startsWith(`${prefix}:`)
    ? header.slice(prefix.length + 1)
    : header;
  return knownColumns.includes(column) ? column : null;
}

function splitTsvLine(line: string): string[] {
  return line.replace(/\r$/, "").split("\t");
}
