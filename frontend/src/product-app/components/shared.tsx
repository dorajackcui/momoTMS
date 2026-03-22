import {
  buildArtifactHref,
  formatTimestamp,
  objectEntries,
  readJobStages,
  stringifyValue,
} from "../utils";
import type { JobDetail } from "../types";

export function DataTable(props: {
  headers: string[];
  rows: string[][];
  emptyText: string;
  dataTestId: string;
}) {
  if (props.rows.length === 0) {
    return (
      <p className="muted" data-testid={props.dataTestId}>
        {props.emptyText}
      </p>
    );
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

export function Pagination(props: {
  page: number;
  totalPages: number;
  onPrev: () => void;
  onNext: () => void;
}) {
  return (
    <div className="pagination">
      <button
        className="button subtle"
        onClick={props.onPrev}
        disabled={props.page <= 1}
      >
        Previous
      </button>
      <span className="muted">
        Page {props.page} / {props.totalPages}
      </span>
      <button
        className="button subtle"
        onClick={props.onNext}
        disabled={props.page >= props.totalPages}
      >
        Next
      </button>
    </div>
  );
}

export function PanelEmptyState(props: {
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
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

export function SummaryKeyValueList(props: {
  title?: string;
  items: Array<[string, string]>;
}) {
  if (props.items.length === 0) {
    return null;
  }
  return (
    <div className="summary-list">
      {props.title ? <p className="eyebrow">{props.title}</p> : null}
      {props.items.map(([label, value]) => (
        <div
          key={`${props.title || "summary"}-${label}`}
          className="summary-row"
        >
          <span className="summary-label">{label}</span>
          <span>{value || "-"}</span>
        </div>
      ))}
    </div>
  );
}

export function JobDetailPanel(props: {
  jobDetail: JobDetail | null;
  projectId: number | null;
}) {
  if (!props.jobDetail || !props.projectId) {
    return (
      <p className="muted">
        Select a job to inspect report output, stages, and downloads.
      </p>
    );
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
            <h3>
              #{props.jobDetail.job.job_id} · {props.jobDetail.job.job_type}
            </h3>
          </div>
          <span
            className={`badge ${
              props.jobDetail.job.status === "done" ? "accent" : "warning"
            }`}
          >
            {props.jobDetail.job.status}
          </span>
        </div>
        <SummaryKeyValueList
          items={[
            ["created_at", formatTimestamp(props.jobDetail.job.created_at)],
            [
              "finished_at",
              props.jobDetail.job.finished_at
                ? formatTimestamp(props.jobDetail.job.finished_at)
                : "-",
            ],
            ["error", props.jobDetail.job.error_message || "-"],
          ]}
        />
        <div className="toolbar">
          <a
            className="button subtle"
            href={reportHref}
            target="_blank"
            rel="noreferrer"
            data-testid="app-job-report-link"
          >
            Open Report
          </a>
          {artifactHref ? (
            <a
              className="button subtle"
              href={artifactHref}
              target="_blank"
              rel="noreferrer"
              data-testid="app-job-artifact-link"
            >
              Download Artifact
            </a>
          ) : null}
        </div>
      </div>

      <SummaryKeyValueList
        title="input"
        items={objectEntries(props.jobDetail.job.input)}
      />
      <SummaryKeyValueList
        title="summary"
        items={objectEntries(props.jobDetail.job.summary, ["stages"])}
      />

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
  const columns = Array.from(new Set(props.rows.flatMap((row) => Object.keys(row)))).slice(0, 8);
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
                <td key={`report-row-${index}-${column}`}>
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
