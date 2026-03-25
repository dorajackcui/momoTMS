import type { Column } from "react-data-grid";

import type { BranchReplacePreview, MasterQueryRow } from "@/domains/branches/types";
import { stringifyValue } from "@/shared/lib/format";
import { Badge, EmptyState, buttonClassName } from "@/shared/ui/primitives";
import type { DirectPatchRow } from "@/pages/branches/model";

import styles from "@/pages/branches/BranchOpsPage.module.css";

export function CompareTable(props: {
  rows: Array<{
    business_key: string;
    state: string;
    priority_status: string;
    diff_categories: string[];
    base: {
      source: string;
      file_name: string | null;
      translations: Record<string, string | null>;
    } | null;
    target: {
      source: string;
      file_name: string | null;
      translations: Record<string, string | null>;
    } | null;
  }>;
  lang: string;
  onInspect: (businessKey: string) => void;
}) {
  if (props.rows.length === 0) {
    return (
      <EmptyState
        title="No compare rows"
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
            <th>file_name</th>
            <th>source</th>
            <th>{props.lang}</th>
            <th>state</th>
            <th>priority</th>
            <th>diffs</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row) => (
            <tr key={row.business_key}>
              <td>{row.business_key}</td>
              <td>{row.target?.file_name || row.base?.file_name || "-"}</td>
              <td>{row.target?.source || row.base?.source || "-"}</td>
              <td>
                {row.target?.translations?.[props.lang] ||
                  row.base?.translations?.[props.lang] ||
                  "-"}
              </td>
              <td>{row.state}</td>
              <td>{row.priority_status}</td>
              <td>{row.diff_categories.join(", ") || "-"}</td>
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

export function QueueTable(props: {
  rows: Array<{
    business_key: string;
    file_name: string | null;
    source: string;
    target_text: string;
    state: string;
    priority_status: string;
    diff_categories: string[];
  }>;
  lang: string;
  onInspect: (businessKey: string) => void;
  onOpenOverview: (businessKey: string) => void;
}) {
  if (props.rows.length === 0) {
    return (
      <EmptyState
        title="No queue rows"
        body="The current queue filters did not return any rows."
      />
    );
  }
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>business_key</th>
            <th>file_name</th>
            <th>source</th>
            <th>{props.lang}</th>
            <th>state</th>
            <th>priority</th>
            <th>diffs</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row) => (
            <tr key={row.business_key}>
              <td>{row.business_key}</td>
              <td>{row.file_name || "-"}</td>
              <td>{row.source}</td>
              <td>{row.target_text || "-"}</td>
              <td>{row.state}</td>
              <td>{row.priority_status}</td>
              <td>{row.diff_categories.join(", ") || "-"}</td>
              <td>
                <div className={styles.toolbar}>
                  <button
                    className={buttonClassName("ghost")}
                    onClick={() => props.onInspect(row.business_key)}
                  >
                    Drawer
                  </button>
                  <button
                    className={buttonClassName("secondary")}
                    onClick={() => props.onOpenOverview(row.business_key)}
                  >
                    Overview
                  </button>
                </div>
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
            <th>branch</th>
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
              <td>{row.branch_ref}</td>
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
  return (
    <div className={styles.stack}>
      <div className={styles.toolbar}>
        <Badge tone="info">{props.preview.source_branch_ref}</Badge>
        <Badge tone="accent">{props.preview.target_branch_ref}</Badge>
      </div>
      <div className={styles.tableWrap}>
        <table className={styles.table}>
          <tbody>
            {Object.entries(props.preview)
              .filter(([key]) => key !== "report_rows")
              .map(([key, value]) => (
                <tr key={key}>
                  <th>{key}</th>
                  <td>{stringifyValue(value)}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
      {props.preview.report_rows.length > 0 ? (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                {Object.keys(props.preview.report_rows[0]).map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {props.preview.report_rows.slice(0, 10).map((row, rowIndex) => (
                <tr key={`preview-${rowIndex}`}>
                  {Object.keys(props.preview.report_rows[0]).map((column) => (
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
