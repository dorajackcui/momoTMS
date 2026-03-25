import { buildJobArtifactHref, buildJobReportHref } from "@/domains/jobs/api";
import type { JobDetail, JobStageSummary } from "@/domains/jobs/types";
import { formatTimestamp, stringifyValue, titleCase } from "@/shared/lib/format";
import {
  Badge,
  EmptyState,
  KeyValueList,
  Panel,
  buttonClassName,
} from "@/shared/ui/primitives";

import styles from "@/features/job-detail/JobDetailPanel.module.css";

export function readJobStages(summary: Record<string, unknown>): JobStageSummary[] {
  const rawStages = summary.stages;
  if (!Array.isArray(rawStages)) {
    return [];
  }
  return rawStages
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }
      const stage = item as Record<string, unknown>;
      return {
        stage: String(stage.stage || ""),
        elapsed_ms: Number(stage.elapsed_ms || 0),
        meta:
          stage.meta && typeof stage.meta === "object"
            ? (stage.meta as Record<string, unknown>)
            : {},
      };
    })
    .filter((item): item is JobStageSummary => Boolean(item?.stage));
}

export function JobDetailPanel(props: {
  projectId: number | null;
  jobDetail: JobDetail | null;
}) {
  if (!props.jobDetail || !props.projectId) {
    return (
      <EmptyState
        title="Select a run"
        body="Pick a job on the left to inspect input, summary, stages, report preview, and downloadable artifacts."
      />
    );
  }

  const { job, report } = props.jobDetail;
  const artifactHref = buildJobArtifactHref(props.projectId, job);
  const reportHref = buildJobReportHref(props.projectId, job.job_id);
  const stages = readJobStages(job.summary);
  const statusTone =
    job.status === "success"
      ? "accent"
      : job.status === "failed"
        ? "danger"
        : "warning";

  return (
    <div className={styles.layout}>
      <Panel
        kicker="Run Detail"
        title={`#${job.job_id} · ${titleCase(job.job_type)}`}
        description="Every long-running workflow reports input, summary, stages, and preview rows here."
        actions={<Badge tone={statusTone}>{job.status}</Badge>}
      >
        <KeyValueList
          items={[
            ["created_at", formatTimestamp(job.created_at)],
            ["finished_at", formatTimestamp(job.finished_at)],
            ["error", job.error_message || "-"],
          ]}
        />
        <div className={styles.grid}>
          <Panel kicker="Input" title="Request">
            <KeyValueList
              items={Object.entries(job.input).map(([key, value]) => [
                key,
                stringifyValue(value),
              ])}
            />
          </Panel>
          <Panel kicker="Summary" title="Outcome">
            <KeyValueList
              items={Object.entries(job.summary)
                .filter(([key]) => key !== "stages")
                .map(([key, value]) => [key, stringifyValue(value)])}
            />
            <div>
              <a
                className={buttonClassName("secondary")}
                href={reportHref}
                target="_blank"
                rel="noreferrer"
              >
                Open full report
              </a>
              {artifactHref ? (
                <a
                  className={buttonClassName("ghost")}
                  href={artifactHref}
                  target="_blank"
                  rel="noreferrer"
                  style={{ marginLeft: 12 }}
                >
                  Download artifact
                </a>
              ) : null}
            </div>
          </Panel>
        </div>
      </Panel>

      {stages.length > 0 ? (
        <Panel kicker="Stages" title="Execution timeline">
          <div className={styles.tableWrap}>
            <table className={styles.table}>
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
                    <td>{stage.elapsed_ms}</td>
                    <td className={styles.mono}>{stringifyValue(stage.meta)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      ) : null}

      <Panel kicker="Report Preview" title="First rows">
        {report.rows.length === 0 ? (
          <EmptyState
            title="No preview rows"
            body="This run did not record preview rows. Open the full report if you need workflow-specific details."
          />
        ) : (
          <ReportTable rows={report.rows.slice(0, 12)} />
        )}
      </Panel>
    </div>
  );
}

function ReportTable(props: { rows: Array<Record<string, unknown>> }) {
  const columns = Array.from(
    new Set(props.rows.flatMap((row) => Object.keys(row))),
  ).slice(0, 8);
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
            <tr key={`row-${rowIndex}`}>
              {columns.map((column) => (
                <td key={`${rowIndex}-${column}`} className={styles.mono}>
                  {stringifyValue(row[column])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
