import {
  PanelEmptyState,
  SummaryKeyValueList,
} from "../components/shared";
import { formatTimestamp } from "../utils";
import type {
  EntryVariantsResponse,
  OrphanVariantSummary,
} from "../types";

export function InspectionPage(props: {
  inspectionLookupKey: string;
  inspectionEntry: EntryVariantsResponse | null;
  orphanVariants: OrphanVariantSummary[];
  onInspectionLookupKeyChange: (value: string) => void;
  onInspectEntry: (businessKey: string) => void;
  onRefreshLists: () => void;
}) {
  return (
    <section className="imports-layout" data-testid="app-inspection-page">
      <section className="panel">
        <div className="panel-head">
          <div>
            <p className="panel-kicker">Debug</p>
            <h3>Inspection</h3>
          </div>
        </div>
        <div className="toolbar">
          <label className="field compact">
            <span>Business Key</span>
            <input
              value={props.inspectionLookupKey}
              onChange={(event) =>
                props.onInspectionLookupKeyChange(event.target.value)
              }
              data-testid="app-inspection-key"
            />
          </label>
          <button
            className="button"
            onClick={() => props.onInspectEntry(props.inspectionLookupKey)}
            data-testid="app-inspection-lookup"
          >
            Inspect Entry
          </button>
          <button className="button subtle" onClick={props.onRefreshLists}>
            Refresh Lists
          </button>
        </div>
      </section>

      <section className="inspection-grid">
        <section className="panel">
          <div className="panel-head">
            <div>
              <p className="panel-kicker">Lifecycle</p>
              <h3>Orphan Variants</h3>
            </div>
          </div>
          <div className="job-list" data-testid="app-orphan-list">
            {props.orphanVariants.length > 0 ? (
              props.orphanVariants.map((item) => (
                <button
                  key={`orphan-${item.variant_id}`}
                  className={`job-card ${
                    props.inspectionEntry?.business_key === item.business_key
                      ? "active"
                      : ""
                  }`}
                  onClick={() => props.onInspectEntry(item.business_key)}
                >
                  <strong>{item.business_key}</strong>
                  <span className="muted">{item.file_name || "-"}</span>
                  <span className="muted">
                    {formatTimestamp(item.orphaned_at)}
                  </span>
                </button>
              ))
            ) : (
              <PanelEmptyState message="No orphan variants in this project." />
            )}
          </div>
        </section>
      </section>

      <section className="panel" data-testid="app-inspection-detail">
        <div className="panel-head">
          <div>
            <p className="panel-kicker">Entry</p>
            <h3>{props.inspectionEntry?.business_key || "Variant Detail"}</h3>
          </div>
        </div>
        {props.inspectionEntry ? (
          <div className="stack">
            {props.inspectionEntry.variants.map((variant) => (
              <article key={variant.variant_id} className="mapping-card">
                <div className="scope-card__top">
                  <strong>variant #{variant.variant_id}</strong>
                  <div className="toolbar">
                    {variant.is_orphaned ? (
                      <span className="badge warning">orphan</span>
                    ) : null}
                    {variant.is_trashed ? (
                      <span className="badge danger">trashed</span>
                    ) : null}
                  </div>
                </div>
                <SummaryKeyValueList
                  items={[
                    ["file_name", variant.file_name || "-"],
                    ["source", variant.source],
                    ["orphaned_at", variant.orphaned_at || "-"],
                    ["updated_at", formatTimestamp(variant.updated_at)],
                  ]}
                />
                <SummaryKeyValueList
                  title="translations"
                  items={Object.entries(variant.translations)}
                />
                <SummaryKeyValueList
                  title="remarks"
                  items={Object.entries(variant.remarks)}
                />
                <SummaryKeyValueList
                  title="bindings"
                  items={
                    variant.bindings.length > 0
                      ? variant.bindings.map((binding) => [
                          binding.branch_ref,
                          formatTimestamp(binding.updated_at),
                        ])
                      : [["state", "No active bindings"]]
                  }
                />
              </article>
            ))}
          </div>
        ) : (
          <PanelEmptyState message="Look up a business key or pick an orphan row to inspect bindings and lifecycle flags." />
        )}
      </section>
    </section>
  );
}
