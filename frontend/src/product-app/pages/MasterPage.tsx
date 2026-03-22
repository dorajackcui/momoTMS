import { DataTable } from "../components/shared";
import type { MasterRow } from "../types";

export function MasterPage(props: {
  selectedLang: string;
  masterKey: string;
  masterSource: string;
  masterRows: MasterRow[];
  masterMode: "key" | "source";
  onGoToImports: () => void;
  onMasterKeyChange: (value: string) => void;
  onMasterSourceChange: (value: string) => void;
  onLookupByKey: () => void;
  onLookupBySource: () => void;
}) {
  return (
    <section className="panel" data-testid="master-page">
      <div className="panel-head">
        <div>
          <p className="panel-kicker">Lookup</p>
          <h3>Master Query</h3>
        </div>
        <button className="button subtle" onClick={props.onGoToImports}>
          Go to Imports & Jobs
        </button>
      </div>
      <div className="toolbar">
        <label className="field compact">
          <span>Business Key</span>
          <input
            value={props.masterKey}
            onChange={(event) => props.onMasterKeyChange(event.target.value)}
            data-testid="app-master-key"
          />
        </label>
        <button
          className="button"
          onClick={props.onLookupByKey}
          data-testid="master-key-button"
        >
          Lookup Key
        </button>
        <label className="field compact">
          <span>Exact Source</span>
          <input
            value={props.masterSource}
            onChange={(event) => props.onMasterSourceChange(event.target.value)}
            data-testid="app-master-source"
          />
        </label>
        <button
          className="button"
          onClick={props.onLookupBySource}
          data-testid="master-source-button"
        >
          Lookup Source
        </button>
      </div>
      <p className="muted">
        Mode: {props.masterMode === "key" ? "business_key" : "source"}
      </p>
      <DataTable
        headers={[
          "business_key",
          "branch",
          "file_name",
          "source",
          `translations:${props.selectedLang}`,
        ]}
        rows={props.masterRows.map((row) => [
          row.business_key,
          row.branch_ref,
          row.file_name || "-",
          row.source,
          row.translations[props.selectedLang] || "",
        ])}
        emptyText="No active matches."
        dataTestId="master-table"
      />
    </section>
  );
}
