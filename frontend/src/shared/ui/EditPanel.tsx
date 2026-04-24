import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import type { BranchMutationInput, BranchMutationChange, EffectForecastPreview } from "@/domains/branches/types";
import type { ImportBatchSummary } from "@/domains/imports/types";
import type { JobDetail } from "@/domains/jobs/types";
import { previewBranchMutation, runBranchMutation } from "@/domains/branches/api";
import { buttonClassName, InlineNotice, StatGrid } from "@/shared/ui/primitives";

import styles from "@/shared/ui/EditPanel.module.css";

type MutationType = "range" | "content";
type InputMethod = "import_batch" | "direct";

export type EditPanelProps = {
  projectId: number;
  branchRef: string;
  allowRange: boolean;
  importBatches: ImportBatchSummary[];
  onJobCreated: (job: JobDetail) => void;
};

export function EditPanel(props: EditPanelProps) {
  const { projectId, branchRef, allowRange, importBatches, onJobCreated } = props;

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
    const changes = parseDirectChanges(directText);
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
            placeholder={"business_key\\tsource\\ttranslation_lang\\n..."}
            rows={8}
          />
          <p className={styles.hint}>Tab-separated: business_key, source, then translation columns</p>
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

function parseDirectChanges(text: string): BranchMutationChange[] {
  const lines = text.trim().split("\n").filter((l) => l.trim());
  if (lines.length === 0) return [];
  return lines.map((line) => {
    const parts = line.split("\t");
    return {
      business_key: parts[0]?.trim() ?? "",
      source: parts[1]?.trim() || undefined,
      translations_by_lang: {},
      remarks_by_key: {},
    };
  });
}
