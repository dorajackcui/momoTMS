import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { previewImportUpload, confirmImportUpload } from "@/domains/imports/api";
import { previewBootstrap, bootstrapBranch } from "@/domains/branches/api";
import { runFillUpload } from "@/domains/workflows/api";
import type { ImportUploadPreview } from "@/domains/imports/types";
import type { EffectForecastPreview } from "@/domains/branches/types";
import type { JobDetail } from "@/domains/jobs/types";
import { waitForJobDetail } from "@/domains/jobs/api";
import { invalidateProject } from "@/shared/api/queryKeys";
import { buttonClassName, InlineNotice, StatGrid } from "@/shared/ui/primitives";
import { FolderUpload } from "@/shared/ui/FolderUpload";
import { buildJobArtifactHref } from "@/domains/jobs/api";

import styles from "@/pages/dev/DevPage.module.css";

type Step = "upload" | "preview" | "done";

export function CreateBranch(props: {
  projectId: number;
  lang: string;
  onBack: () => void;
  onCreated: (version: string) => void;
}) {
  const { projectId, lang, onBack, onCreated } = props;
  const queryClient = useQueryClient();

  const [step, setStep] = useState<Step>("upload");
  const [version, setVersion] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [uploadPreview, setUploadPreview] = useState<ImportUploadPreview | null>(null);
  const [importBatchId, setImportBatchId] = useState<number | null>(null);
  const [bootstrapPreview, setBootstrapPreview] = useState<EffectForecastPreview | null>(null);
  const [bootstrapResult, setBootstrapResult] = useState<JobDetail | null>(null);
  const [fillResult, setFillResult] = useState<JobDetail | null>(null);

  const previewUploadMut = useMutation({
    mutationFn: () => previewImportUpload(projectId, files),
    onSuccess: (data) => setUploadPreview(data),
  });

  const confirmUploadMut = useMutation({
    mutationFn: async () => {
      const startedDetail = await confirmImportUpload(projectId, uploadPreview!.upload_session_id, null);
      const completedDetail = await waitForJobDetail(projectId, startedDetail.job.job_id);
      if (completedDetail.job.status !== "success") {
        throw new Error(completedDetail.job.error_message || "Import batch creation failed");
      }
      const batchId = readImportBatchId(completedDetail);
      const bsPreview = await previewBootstrap(projectId, { branch_ref: `dev/${version}`, import_batch_id: batchId });
      return { batchId, bsPreview };
    },
    onSuccess: ({ batchId, bsPreview }) => {
      setImportBatchId(batchId);
      setBootstrapPreview(bsPreview);
      setStep("preview");
    },
  });

  const bootstrapMut = useMutation({
    mutationFn: () => bootstrapBranch(projectId, { branch_ref: `dev/${version}`, import_batch_id: importBatchId! }),
    onSuccess: async (data) => {
      setBootstrapResult(data);
      await invalidateProject(queryClient, projectId);
      setStep("done");
    },
  });

  const fillMut = useMutation({
    mutationFn: () => runFillUpload(projectId, lang, files),
    onSuccess: (data) => setFillResult(data),
  });

  const branchRef = `dev/${version}`;

  if (step === "upload") {
    return (
      <div className={styles.page}>
        <button className={buttonClassName("ghost")} onClick={onBack}>← Back</button>
        <h2>Create Branch</h2>
        <label>
          Version number
          <input value={version} onChange={(e) => setVersion(e.target.value)} placeholder="2.2.3" />
        </label>
        <p style={{ color: "var(--muted)", fontSize: 13 }}>Branch will be created as <strong>{branchRef}</strong></p>
        <FolderUpload label="Upload workbook folder" onFiles={(f) => { setFiles(f); previewUploadMut.reset(); setUploadPreview(null); }} />
        {files.length > 0 && <p>{files.length} files selected</p>}

        {!uploadPreview && files.length > 0 && (
          <button className={buttonClassName("secondary")} disabled={!version.trim() || previewUploadMut.isPending} onClick={() => previewUploadMut.mutate()}>
            {previewUploadMut.isPending ? "Previewing upload..." : "Preview Upload"}
          </button>
        )}

        {previewUploadMut.isError && <InlineNotice tone="error">{String(previewUploadMut.error)}</InlineNotice>}

        {uploadPreview && (
          <div>
            <StatGrid items={[
              { label: "Files", value: uploadPreview.file_count },
              { label: "Sheets", value: uploadPreview.sheet_count },
            ]} />
            <button
              className={buttonClassName("primary")}
              disabled={confirmUploadMut.isPending}
              onClick={() => confirmUploadMut.mutate()}
            >
              {confirmUploadMut.isPending ? "Creating batch & previewing bootstrap..." : "Next: Preview Bootstrap"}
            </button>
          </div>
        )}
        {confirmUploadMut.isError && <InlineNotice tone="error">{String(confirmUploadMut.error)}</InlineNotice>}
      </div>
    );
  }

  if (step === "preview") {
    return (
      <div className={styles.page}>
        <h2>Bootstrap Preview — {branchRef}</h2>
        {bootstrapPreview && (
          <>
            <StatGrid items={Object.entries(bootstrapPreview.summary).map(([k, v]) => ({ label: k, value: String(v) }))} />
            <table className={styles.table}>
              <thead>
                <tr>{bootstrapPreview.rows.length > 0 && Object.keys(bootstrapPreview.rows[0]).map((k) => <th key={k}>{k}</th>)}</tr>
              </thead>
              <tbody>
                {bootstrapPreview.rows.slice(0, 30).map((row, i) => (
                  <tr key={i}>{Object.values(row).map((v, j) => <td key={j}>{String(v ?? "")}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        <button
          className={buttonClassName("primary")}
          disabled={bootstrapMut.isPending}
          onClick={() => bootstrapMut.mutate()}
        >
          {bootstrapMut.isPending ? "Bootstrapping..." : "Execute Bootstrap"}
        </button>
        {bootstrapMut.isError && <InlineNotice tone="error">{String(bootstrapMut.error)}</InlineNotice>}
      </div>
    );
  }

  // step === "done"
  return (
    <div className={styles.page}>
      <h2>Branch Created — {branchRef}</h2>
      {bootstrapResult && (
        <StatGrid items={Object.entries(bootstrapResult.report.summary).map(([k, v]) => ({ label: k, value: String(v) }))} />
      )}
      <div className={styles.actions}>
        <button className={buttonClassName("secondary")} disabled={fillMut.isPending} onClick={() => fillMut.mutate()}>
          {fillMut.isPending ? "Filling..." : "Export for Translation"}
        </button>
        <button className={buttonClassName("primary")} onClick={() => onCreated(version)}>
          Go to Branch
        </button>
      </div>
      {fillMut.isError && <InlineNotice tone="error">{String(fillMut.error)}</InlineNotice>}
      {fillResult && (
        <InlineNotice tone="success">
          Fill complete.
          {fillResult.job.artifact_path && (
            <> <a href={buildJobArtifactHref(projectId, fillResult.job) ?? "#"} download>Download ZIP</a></>
          )}
        </InlineNotice>
      )}
    </div>
  );
}

function readImportBatchId(jobDetail: JobDetail): number {
  const raw =
    jobDetail.job.summary.import_batch_id ??
    jobDetail.job.input.import_batch_id;
  const batchId = Number(raw);
  if (!Number.isInteger(batchId) || batchId <= 0) {
    throw new Error("Import job completed without an import_batch_id");
  }
  return batchId;
}
