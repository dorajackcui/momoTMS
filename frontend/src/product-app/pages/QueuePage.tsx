import { DataTable, Pagination, PanelEmptyState } from "../components/shared";
import { presentState } from "../utils";
import type {
  BranchOption,
  TranslationQueueResponse,
} from "../types";

export function QueuePage(props: {
  queueTargetScope: string;
  selectedLang: string;
  devScopeOptions: BranchOption[];
  queueSearch: string;
  queueStatus: string;
  queue: TranslationQueueResponse | null;
  queueTotalPages: number;
  onGoToImports: () => void;
  onQueueTargetScopeChange: (value: string) => void;
  onQueueSearchChange: (value: string) => void;
  onQueueStatusChange: (value: string) => void;
  onPrevPage: () => void;
  onNextPage: () => void;
}) {
  return (
    <section className="panel" data-testid="queue-page">
      <div className="panel-head">
        <div>
          <p className="panel-kicker">Operations</p>
          <h3>Translation Queue</h3>
        </div>
        <button className="button subtle" onClick={props.onGoToImports}>
          Go to Imports & Jobs
        </button>
      </div>
      <div className="toolbar">
        <label className="field compact">
          <span>Target Branch</span>
          <select
            value={props.queueTargetScope}
            onChange={(event) =>
              props.onQueueTargetScopeChange(event.target.value)
            }
            disabled={props.devScopeOptions.length === 0}
            data-testid="app-queue-target"
          >
            {props.devScopeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field compact">
          <span>Search Key</span>
          <input
            value={props.queueSearch}
            onChange={(event) => props.onQueueSearchChange(event.target.value)}
          />
        </label>
        <label className="field compact">
          <span>Status</span>
          <select
            value={props.queueStatus}
            onChange={(event) => props.onQueueStatusChange(event.target.value)}
          >
            <option value="">All</option>
            <option value="fillable">fillable</option>
            <option value="needs_translation">needs_translation</option>
            <option value="needs_review">needs_review</option>
            <option value="source_mismatch">source_mismatch</option>
            <option value="already_translated">already_translated</option>
          </select>
        </label>
      </div>
      {props.devScopeOptions.length === 0 ? (
        <PanelEmptyState
          message="No dev branches are available for translation queue yet. Run dev import from Imports & Jobs first."
          actionLabel="Go to Imports & Jobs"
          onAction={props.onGoToImports}
        />
      ) : (
        <>
          <DataTable
            headers={[
              "business_key",
              "file_name",
              "source",
              `target:${props.selectedLang}`,
              "state",
              "priority",
              "diffs",
            ]}
            rows={(props.queue?.rows || []).map((row) => [
              row.business_key,
              row.file_name || "-",
              row.source,
              row.target_text,
              presentState(row.state, "rel/current", props.queueTargetScope),
              row.priority_status,
              row.diff_categories.join(", ") || "-",
            ])}
            emptyText="No queue rows for the current filters."
            dataTestId="queue-table"
          />
          <Pagination
            page={props.queue?.page || 1}
            totalPages={props.queueTotalPages}
            onPrev={props.onPrevPage}
            onNext={props.onNextPage}
          />
        </>
      )}
    </section>
  );
}
