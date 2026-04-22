import type { Column } from "react-data-grid";

import type {
  BranchReplacePreview,
  MasterQueryRow,
  SameSourceCandidateRow,
} from "@/domains/branches/types";
import type { ProjectVariantRow } from "@/domains/variants/types";
import { stringifyValue } from "@/shared/lib/format";
import { Badge, EmptyState, buttonClassName } from "@/shared/ui/primitives";
import type { DirectPatchRow } from "@/pages/branches/model";

import styles from "@/pages/branches/BranchOpsPage.module.css";

export function ScopeRowsTable(props: {
  rows: ProjectVariantRow[];
  lang: string;
  onInspect: (businessKey: string) => void;
}) {
  if (props.rows.length === 0) {
    return (
      <EmptyState
        title="No scope rows"
        body="Try a different branch or loosen the current filters."
      />
    );
  }
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>business_key</th>
            <th>variant_id</th>
            <th>file_name</th>
            <th>source</th>
            <th>{props.lang}</th>
            <th>state</th>
            <th>pivot</th>
            <th>bindings</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row) => (
            <tr key={row.variant_id}>
              <td>{row.business_key}</td>
              <td>{row.variant_id}</td>
              <td>{row.file_name || "-"}</td>
              <td>{row.source || "-"}</td>
              <td>{row.translations?.[props.lang] || "-"}</td>
              <td>{row.state}</td>
              <td>{row.pivot_status}</td>
              <td>{row.bindings.map((binding) => binding.branch_ref).join(", ") || "-"}</td>
              <td>
                <button
                  className={buttonClassName("ghost")}
                  onClick={() => props.onInspect(row.business_key)}
                >
                  Inspect history
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SameSourceCandidatesTable(props: {
  rows: SameSourceCandidateRow[];
  lang: string;
  onInspect: (businessKey: string) => void;
}) {
  if (props.rows.length === 0) {
    return (
      <EmptyState
        title="No history candidates"
        body="No same-source history candidates matched the provided key and source."
      />
    );
  }
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>business_key</th>
            <th>variant_id</th>
            <th>file_name</th>
            <th>source</th>
            <th>{props.lang}</th>
            <th>state</th>
            <th>pivot</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row) => (
            <tr key={row.variant_id}>
              <td>{row.business_key}</td>
              <td>{row.variant_id}</td>
              <td>{row.file_name || "-"}</td>
              <td>{row.source}</td>
              <td>{row.translations[props.lang] || "-"}</td>
              <td>{row.state}</td>
              <td>{row.pivot_status}</td>
              <td>
                <button
                  className={buttonClassName("ghost")}
                  onClick={() => props.onInspect(row.business_key)}
                >
                  Inspect history
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function LookupTable(props: {
  rows: MasterQueryRow[];
  lang: string;
  onInspect: (businessKey: string) => void;
}) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>business_key</th>
            <th>scope</th>
            <th>file_name</th>
            <th>source</th>
            <th>{props.lang}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row) => (
            <tr key={`${row.business_key}-${row.variant_id}`}>
              <td>{row.business_key}</td>
              <td>{row.scope_ref}</td>
              <td>{row.file_name || "-"}</td>
              <td>{row.source}</td>
              <td>{row.translations[props.lang] || "-"}</td>
              <td>
                <button
                  className={buttonClassName("ghost")}
                  onClick={() => props.onInspect(row.business_key)}
                >
                  Inspect history
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function KeyValuePreview(props: { preview: BranchReplacePreview }) {
  const summaryEntries = Object.entries(props.preview.summary);
  const previewRows = props.preview.rows;

  return (
    <div className={styles.stack}>
      <div className={styles.toolbar}>
        <Badge tone="info">{props.preview.request_echo.source_branch_ref}</Badge>
        <Badge tone="accent">{props.preview.request_echo.target_branch_ref}</Badge>
      </div>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <tbody>
            <tr>
              <th>preview_kind</th>
              <td>{props.preview.preview_kind}</td>
            </tr>
            <tr>
              <th>workflow_kind</th>
              <td>{props.preview.workflow_kind}</td>
            </tr>
            {summaryEntries.map(([key, value]) => (
              <tr key={key}>
                <th>{key}</th>
                <td>{stringifyValue(value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {previewRows.length > 0 ? (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                {Object.keys(previewRows[0]).map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {previewRows.slice(0, 10).map((row, rowIndex) => (
                <tr key={`preview-${rowIndex}`}>
                  {Object.keys(previewRows[0]).map((column) => (
                    <td key={`${rowIndex}-${column}`}>{stringifyValue(row[column])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

export function buildDirectColumns(schema: {
  translation_columns: string[];
  remark_columns: string[];
}): Column<DirectPatchRow>[] {
  const columns: Column<DirectPatchRow>[] = [
    { key: "business_key", name: "business_key", width: 180, editable: true },
    { key: "source", name: "source", width: 220, editable: true },
    { key: "file_name", name: "file_name", width: 180, editable: true },
  ];
  for (const lang of schema.translation_columns) {
    columns.push({
      key: `translation:${lang}`,
      name: lang,
      width: 160,
      editable: true,
    });
  }
  for (const key of schema.remark_columns) {
    columns.push({
      key: `remark:${key}`,
      name: `remark:${key}`,
      width: 160,
      editable: true,
    });
  }
  return columns;
}
