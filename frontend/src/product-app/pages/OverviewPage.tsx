import { PanelEmptyState } from "../components/shared";
import type { BranchSummaryResponse } from "../types";

export function OverviewPage(props: {
  branches: BranchSummaryResponse["branches"];
  onGoToImports: () => void;
  onSelectBranch: (branchRef: string) => void;
}) {
  return (
    <section className="panel" data-testid="overview-page">
      <div className="panel-head">
        <div>
          <p className="panel-kicker">Summary</p>
          <h3>Branch Overview</h3>
        </div>
        <button className="button subtle" onClick={props.onGoToImports}>
          Go to Imports & Jobs
        </button>
      </div>
      {props.branches.length > 0 ? (
        <div className="overview-grid" data-testid="overview-grid">
          {props.branches.map((branch) => (
            <button
              key={branch.branch_ref}
              className="scope-card"
              onClick={() => props.onSelectBranch(branch.branch_ref)}
            >
              <div className="scope-card__top">
                <strong>{branch.branch_ref}</strong>
                {branch.is_candidate_release ? (
                  <span className="badge accent">candidate</span>
                ) : null}
              </div>
              <span className="muted">entries {branch.entry_count}</span>
              <code>{JSON.stringify(branch.status_counts)}</code>
            </button>
          ))}
        </div>
      ) : (
        <PanelEmptyState
          message="No branches are available yet. Create an import batch and run dev import to populate branch views."
          actionLabel="Go to Imports & Jobs"
          onAction={props.onGoToImports}
        />
      )}
    </section>
  );
}
