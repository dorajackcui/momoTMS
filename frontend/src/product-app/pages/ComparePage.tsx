import { DataTable, Pagination, PanelEmptyState } from "../components/shared";
import { presentState } from "../utils";
import type {
  BranchCompareResponse,
  BranchOption,
} from "../types";

export function ComparePage(props: {
  baseScope: string;
  targetScope: string;
  selectedLang: string;
  scopeOptions: BranchOption[];
  devScopeOptions: BranchOption[];
  compareSearch: string;
  compareState: string;
  compareDiff: string;
  compare: BranchCompareResponse | null;
  compareTotalPages: number;
  onGoToImports: () => void;
  onBaseScopeChange: (value: string) => void;
  onTargetScopeChange: (value: string) => void;
  onCompareSearchChange: (value: string) => void;
  onCompareStateChange: (value: string) => void;
  onCompareDiffChange: (value: string) => void;
  onPrevPage: () => void;
  onNextPage: () => void;
}) {
  return (
    <section className="panel" data-testid="compare-page">
      <div className="panel-head">
        <div>
          <p className="panel-kicker">Diff</p>
          <h3>Branch Compare</h3>
        </div>
        <button className="button subtle" onClick={props.onGoToImports}>
          Go to Imports & Jobs
        </button>
      </div>
      <div className="toolbar">
        <label className="field compact">
          <span>Base Branch</span>
          <select
            value={props.baseScope}
            onChange={(event) => props.onBaseScopeChange(event.target.value)}
            data-testid="app-base-scope"
          >
            {props.scopeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field compact">
          <span>Target Branch</span>
          <select
            value={props.targetScope}
            onChange={(event) => props.onTargetScopeChange(event.target.value)}
            disabled={props.devScopeOptions.length === 0}
            data-testid="app-target-scope"
          >
            {props.scopeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field compact">
          <span>Search Key</span>
          <input
            value={props.compareSearch}
            onChange={(event) => props.onCompareSearchChange(event.target.value)}
          />
        </label>
        <label className="field compact">
          <span>State</span>
          <select
            value={props.compareState}
            onChange={(event) => props.onCompareStateChange(event.target.value)}
          >
            <option value="">All</option>
            <option value="aligned">aligned</option>
            <option value="diverged">diverged</option>
            <option value="base_only">base_only</option>
            <option value="target_only">target_only</option>
          </select>
        </label>
        <label className="field compact">
          <span>Diff</span>
          <select
            value={props.compareDiff}
            onChange={(event) => props.onCompareDiffChange(event.target.value)}
          >
            <option value="">All</option>
            <option value="source_changed">source_changed</option>
            <option value="translation_changed">translation_changed</option>
            <option value="remark_changed">remark_changed</option>
            <option value="file_name_changed">file_name_changed</option>
          </select>
        </label>
      </div>
      {props.baseScope === props.targetScope ? (
        <p className="flash error">
          Base branch and target branch must be different.
        </p>
      ) : null}
      {props.devScopeOptions.length === 0 ? (
        <PanelEmptyState
          message="No dev branches are available for compare yet. Run dev import from Imports & Jobs first."
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
            rows={(props.compare?.rows || []).map((row) => [
              row.business_key,
              row.target?.file_name || row.base?.file_name || "-",
              row.target?.source || row.base?.source || "-",
              row.target?.translations?.[props.selectedLang] ||
                row.base?.translations?.[props.selectedLang] ||
                "",
              presentState(row.state, props.baseScope, props.targetScope),
              row.priority_status,
              row.diff_categories.join(", ") || "-",
            ])}
            emptyText="No compare rows for the current filters."
            dataTestId="compare-table"
          />
          <Pagination
            page={props.compare?.page || 1}
            totalPages={props.compareTotalPages}
            onPrev={props.onPrevPage}
            onNext={props.onNextPage}
          />
        </>
      )}
    </section>
  );
}
