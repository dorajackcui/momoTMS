import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { useAppShell } from "@/app/shell/AppShellContext";
import { getJobs, getJobDetail, buildJobArtifactHref } from "@/domains/jobs/api";
import { runFillUpload, runQaUpload } from "@/domains/workflows/api";
import { queryKeys } from "@/shared/api/queryKeys";
import { buttonClassName, InlineNotice, LoadingBlock, StatGrid } from "@/shared/ui/primitives";
import { FolderUpload } from "@/shared/ui/FolderUpload";

import styles from "@/pages/runs/RunsPage.module.css";

type RunsTab = "jobs" | "fill" | "qa" | "export";

export function RunsPage() {
  const shell = useAppShell();
  const queryClient = useQueryClient();
  const projectId = shell.projectId!;

  const [tab, setTab] = useState<RunsTab>("jobs");
  const [expandedJobId, setExpandedJobId] = useState<number | null>(null);

  // --- Fill state ---
  const [fillFiles, setFillFiles] = useState<File[]>([]);
  const [fillLang, setFillLang] = useState(shell.lang);
  // --- QA state ---
  const [qaFiles, setQaFiles] = useState<File[]>([]);
  const [qaLang, setQaLang] = useState(shell.lang);

  const jobsQuery = useQuery({
    queryKey: queryKeys.jobs(projectId),
    queryFn: () => getJobs(projectId),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && data.some((j) => j.status === "running")) return 1000;
      return false;
    },
  });

  const jobDetailQuery = useQuery({
    queryKey: queryKeys.jobDetail(projectId, expandedJobId!),
    queryFn: () => getJobDetail(projectId, expandedJobId!),
    enabled: expandedJobId !== null,
  });

  const fillMut = useMutation({
    mutationFn: () => runFillUpload(projectId, fillLang, fillFiles),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.jobs(projectId) });
      setFillFiles([]);
      setTab("jobs");
    },
  });

  const qaMut = useMutation({
    mutationFn: () => runQaUpload(projectId, qaLang, qaFiles),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.jobs(projectId) });
      setQaFiles([]);
      setTab("jobs");
    },
  });

  const langs = shell.bootstrap?.schema.translation_columns ?? [];

  return (
    <div>
      <nav className={styles.tabs}>
        {(["jobs", "fill", "qa", "export"] as RunsTab[]).map((t) => (
          <button key={t} className={`${styles.tab} ${tab === t ? styles.tabActive : ""}`} onClick={() => setTab(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </nav>

      {tab === "jobs" && (
        <div className={styles.jobList}>
          {jobsQuery.isLoading && <LoadingBlock label="Loading jobs..." />}
          {jobsQuery.data?.map((job) => (
            <div key={job.job_id} className={styles.jobCard}>
              <div className={styles.jobHeader} onClick={() => setExpandedJobId(expandedJobId === job.job_id ? null : job.job_id)}>
                <span>#{job.job_id}</span>
                <span>{job.job_type}</span>
                <span className={job.status === "running" ? styles.running : job.status === "failed" ? styles.failed : styles.success}>
                  {job.status}
                </span>
                <span>{job.created_at}</span>
                {job.artifact_path && (
                  <a href={buildJobArtifactHref(projectId, job) ?? "#"} download onClick={(e) => e.stopPropagation()}>
                    Download
                  </a>
                )}
              </div>
              {expandedJobId === job.job_id && jobDetailQuery.data && (
                <div className={styles.jobDetail}>
                  <StatGrid items={Object.entries(jobDetailQuery.data.report.summary).map(([k, v]) => ({ label: k, value: String(v) }))} />
                  {jobDetailQuery.data.report.rows.length > 0 && (
                    <table className={styles.reportTable}>
                      <thead>
                        <tr>{Object.keys(jobDetailQuery.data.report.rows[0]).map((k) => <th key={k}>{k}</th>)}</tr>
                      </thead>
                      <tbody>
                        {jobDetailQuery.data.report.rows.slice(0, 12).map((row, i) => (
                          <tr key={i}>{Object.values(row).map((v, j) => <td key={j}>{String(v ?? "")}</td>)}</tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === "fill" && (
        <div className={styles.uploadForm}>
          <h3>Fill Translation</h3>
          <label>Target language <select value={fillLang} onChange={(e) => setFillLang(e.target.value)}>
            {langs.map((l) => <option key={l} value={l}>{l}</option>)}
          </select></label>
          <FolderUpload label="Select workbook folder" onFiles={setFillFiles} />
          {fillFiles.length > 0 && <p>{fillFiles.length} files selected</p>}
          <button className={buttonClassName("primary")} disabled={fillFiles.length === 0 || fillMut.isPending} onClick={() => fillMut.mutate()}>
            {fillMut.isPending ? "Running fill..." : "Run Fill"}
          </button>
          {fillMut.isError && <InlineNotice tone="error">{String(fillMut.error)}</InlineNotice>}
        </div>
      )}

      {tab === "qa" && (
        <div className={styles.uploadForm}>
          <h3>QA Scan</h3>
          <label>Target language <select value={qaLang} onChange={(e) => setQaLang(e.target.value)}>
            {langs.map((l) => <option key={l} value={l}>{l}</option>)}
          </select></label>
          <FolderUpload label="Select workbook folder" onFiles={setQaFiles} />
          {qaFiles.length > 0 && <p>{qaFiles.length} files selected</p>}
          <button className={buttonClassName("primary")} disabled={qaFiles.length === 0 || qaMut.isPending} onClick={() => qaMut.mutate()}>
            {qaMut.isPending ? "Running QA..." : "Run QA Scan"}
          </button>
          {qaMut.isError && <InlineNotice tone="error">{String(qaMut.error)}</InlineNotice>}
        </div>
      )}

      {tab === "export" && (
        <div className={styles.uploadForm}>
          <h3>Export Variants</h3>
          <InlineNotice tone="info">Export requires a new backend endpoint (not yet implemented).</InlineNotice>
        </div>
      )}
    </div>
  );
}
