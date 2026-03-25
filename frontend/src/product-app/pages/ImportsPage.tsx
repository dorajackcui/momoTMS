import type { RefObject } from "react";

import { JobDetailPanel, PanelEmptyState, SummaryKeyValueList } from "../components/shared";
import { formatTimestamp, stringifyValue, summarizeJob } from "../utils";
import type {
  BranchReplacePreview,
  ImportBatchSummary,
  JobDetail,
  JobSummary,
  ProductBootstrapResponse,
} from "../types";

const folderInputAttributes = {
  webkitdirectory: "",
  directory: "",
} as Record<string, string>;

export function ImportsPage(props: {
  bootstrap: ProductBootstrapResponse | null;
  selectedLang: string;
  imports: ImportBatchSummary[];
  jobs: JobSummary[];
  selectedImportBatch: string;
  selectedImportSummary: ImportBatchSummary | null;
  devVersionInput: string;
  candidateRelease: boolean;
  promoteVersion: string;
  queueTargetScope: string;
  promotePreview: BranchReplacePreview | null;
  selectedJobId: number | null;
  jobDetail: JobDetail | null;
  importInputRef: RefObject<HTMLInputElement | null>;
  fillInputRef: RefObject<HTMLInputElement | null>;
  qaInputRef: RefObject<HTMLInputElement | null>;
  onImportBatchChange: (value: string) => void;
  onDevVersionInputChange: (value: string) => void;
  onCandidateReleaseChange: (value: boolean) => void;
  onPromoteVersionChange: (value: string) => void;
  onImportFilesSelected: (files: File[]) => void;
  onRunDevImport: () => void;
  onFillFilesSelected: (files: File[]) => void;
  onQaFilesSelected: (files: File[]) => void;
  onRunPromotePreview: () => void;
  onRunPromoteExecute: () => void;
  onInspectJob: (jobId: number) => void;
  projectId: number | null;
}) {
  const translationColumns = props.bootstrap?.schema.translation_columns || [];
  const remarkColumns = props.bootstrap?.schema.remark_columns || [];

  return (
    <section className="imports-layout" data-testid="imports-page">
      <section className="panel">
        <div className="panel-head">
          <div>
            <p className="panel-kicker">Template</p>
            <h3>Imports & Jobs</h3>
          </div>
        </div>
        <div className="schema-summary">
          <span className="badge accent">
            translations: {translationColumns.join(", ") || "-"}
          </span>
          <span className="badge accent">
            remarks: {remarkColumns.join(", ") || "-"}
          </span>
          <p className="muted">
            Upload opens a guided mapping modal with auto-suggested headers.
            `file_name` still comes from the workbook path, not from an Excel
            column.
          </p>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <div>
            <p className="panel-kicker">Step 1</p>
            <h3>Upload and Validate</h3>
          </div>
        </div>
        <div className="stack">
          <label className="field">
            <span>Import Folder</span>
            <input
              ref={props.importInputRef}
              type="file"
              {...folderInputAttributes}
              multiple
              onChange={(event) => {
                const files = Array.from(event.target.files || []);
                if (files.length > 0) {
                  props.onImportFilesSelected(files);
                }
              }}
              data-testid="app-import-folder"
            />
          </label>
          <p className="muted">
            After preview, choose the header for `business_key`, `source`,
            and any translation or remark columns you want to update for each
            sheet. Unmapped translation or remark fields stay unchanged. Extra
            columns are ignored.
          </p>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <div>
            <p className="panel-kicker">Step 2</p>
            <h3>Run Dev Import</h3>
          </div>
        </div>
        <div className="stack">
          {props.imports.length > 0 ? (
            <>
              <label className="field">
                <span>Import Batch</span>
                <select
                  value={props.selectedImportBatch}
                  onChange={(event) =>
                    props.onImportBatchChange(event.target.value)
                  }
                  data-testid="app-import-batch"
                >
                  {props.imports.map((item) => (
                    <option
                      key={item.import_batch_id}
                      value={item.import_batch_id}
                    >
                      #{item.import_batch_id}
                    </option>
                  ))}
                </select>
              </label>
              <div className="job-list" data-testid="app-import-batches">
                {props.imports.map((item) => (
                  <button
                    key={item.import_batch_id}
                    className={`job-card ${
                      props.selectedImportBatch === String(item.import_batch_id)
                        ? "active"
                        : ""
                    }`}
                    onClick={() =>
                      props.onImportBatchChange(String(item.import_batch_id))
                    }
                  >
                    <strong>batch #{item.import_batch_id}</strong>
                    <span className="muted">
                      {formatTimestamp(item.created_at)}
                    </span>
                    <span className="muted">
                      {item.files_scanned} files · {item.rows_scanned} rows ·{" "}
                      {item.issues} issues
                    </span>
                  </button>
                ))}
              </div>
              {props.selectedImportSummary ? (
                <SummaryKeyValueList
                  title="selected batch"
                  items={[
                    [
                      "created_at",
                      formatTimestamp(props.selectedImportSummary.created_at),
                    ],
                    [
                      "files_scanned",
                      String(props.selectedImportSummary.files_scanned),
                    ],
                    [
                      "rows_scanned",
                      String(props.selectedImportSummary.rows_scanned),
                    ],
                    ["issues", String(props.selectedImportSummary.issues)],
                  ]}
                />
              ) : null}
              <label className="field">
                <span>Dev Version</span>
                <input
                  value={props.devVersionInput}
                  onChange={(event) =>
                    props.onDevVersionInputChange(event.target.value)
                  }
                  placeholder="2.3.2"
                  data-testid="app-dev-version-input"
                />
              </label>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={props.candidateRelease}
                  onChange={(event) =>
                    props.onCandidateReleaseChange(event.target.checked)
                  }
                />
                <span>Mark as candidate release</span>
              </label>
              <button
                className="button accent"
                onClick={props.onRunDevImport}
                data-testid="app-run-dev-import"
              >
                Run Dev Import
              </button>
            </>
          ) : (
            <PanelEmptyState message="No import batches yet. Upload a folder to create the first import batch." />
          )}
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <div>
            <p className="panel-kicker">Step 3</p>
            <h3>Fill, QA, and Replace</h3>
          </div>
        </div>
        <div className="imports-actions-grid">
          <div className="stack">
            <label className="field">
              <span>Fill Folder</span>
              <input
                ref={props.fillInputRef}
                type="file"
                {...folderInputAttributes}
                multiple
                onChange={(event) => {
                  const files = Array.from(event.target.files || []);
                  if (files.length > 0) {
                    props.onFillFilesSelected(files);
                  }
                }}
                data-testid="app-fill-folder"
              />
            </label>
            <p className="muted">
              Fill results appear in the selected job detail panel.
            </p>
          </div>
          <div className="stack">
            <label className="field">
              <span>QA Folder</span>
              <input
                ref={props.qaInputRef}
                type="file"
                {...folderInputAttributes}
                multiple
                onChange={(event) => {
                  const files = Array.from(event.target.files || []);
                  if (files.length > 0) {
                    props.onQaFilesSelected(files);
                  }
                }}
                data-testid="app-qa-folder"
              />
            </label>
            <p className="muted">
              QA report details appear in the selected job detail panel.
            </p>
          </div>
          <div className="stack">
            <label className="field">
              <span>Replace Source Version</span>
              <input
                value={props.promoteVersion}
                onChange={(event) =>
                  props.onPromoteVersionChange(event.target.value)
                }
                placeholder={
                  props.queueTargetScope.replace(/^dev\//, "") || "2.3.2"
                }
              />
            </label>
            <div className="toolbar">
              <button
                className="button"
                onClick={props.onRunPromotePreview}
                data-testid="app-replace-preview"
              >
                Preview
              </button>
              <button
                className="button accent"
                onClick={props.onRunPromoteExecute}
                data-testid="app-replace-execute"
              >
                Execute
              </button>
            </div>
            {props.promotePreview ? (
              <SummaryKeyValueList
                title="replace preview"
                items={Object.entries(props.promotePreview)
                  .filter(([key]) => key !== "report_rows")
                  .map(([key, value]) => [key, stringifyValue(value)])}
              />
            ) : (
              <p className="muted">
                Preview summarizes replace impact before execution.
              </p>
            )}
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <div>
            <p className="panel-kicker">Jobs</p>
            <h3>Recent Jobs</h3>
          </div>
        </div>
        <div className="imports-jobs-grid">
          <div className="job-list" data-testid="app-jobs-list">
            {props.jobs.length > 0 ? (
              props.jobs.map((job) => (
                <button
                  key={job.job_id}
                  className={`job-card ${
                    props.selectedJobId === job.job_id ? "active" : ""
                  }`}
                  onClick={() => props.onInspectJob(job.job_id)}
                >
                  <strong>
                    #{job.job_id} · {job.job_type}
                  </strong>
                  <span className="muted">{job.status}</span>
                  <span className="muted">
                    {formatTimestamp(job.created_at)}
                  </span>
                  <span className="muted">{summarizeJob(job)}</span>
                </button>
              ))
            ) : (
              <PanelEmptyState message="No jobs yet. Run import, dev import, fill, QA, or replace to populate this list." />
            )}
          </div>
          <div className="job-detail" data-testid="app-job-detail">
            <JobDetailPanel
              jobDetail={props.jobDetail}
              projectId={props.projectId}
            />
          </div>
        </div>
      </section>
    </section>
  );
}
