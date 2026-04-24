import { useMemo } from "react";
import { DataGrid } from "react-data-grid";
import type { Column } from "react-data-grid";

import type { ProjectSchema } from "@/domains/projects/types";
import type { ProjectVariantRow } from "@/domains/variants/types";

import styles from "@/shared/ui/VariantGrid.module.css";

export type VariantGridProps = {
  schema: ProjectSchema;
  rows: ProjectVariantRow[];
  totalRows: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  columnFilters: Record<string, string>;
  onColumnFilterChange: (column: string, value: string) => void;
  stateFilter: "active" | "orphan" | "all";
  onStateFilterChange: (state: "active" | "orphan" | "all") => void;
  columnToggles: { translations: boolean; remarks: boolean; pivot: boolean };
  onColumnToggleChange: (group: "translations" | "remarks" | "pivot", on: boolean) => void;
};

function formatBranch(row: ProjectVariantRow): string {
  const refs = row.bindings.map((b) => b.branch_ref);
  if (refs.length === 0) return "-";
  const first = refs[0].replace("rel/current", "rel/c");
  return refs.length > 1 ? `${first} +${refs.length - 1}` : first;
}

function HeaderFilter(props: {
  column: string;
  value: string;
  onChange: (column: string, value: string) => void;
}) {
  return (
    <input
      className={styles.headerFilter}
      value={props.value}
      onChange={(e) => props.onChange(props.column, e.target.value)}
      placeholder="Filter..."
      onClick={(e) => e.stopPropagation()}
    />
  );
}

export function VariantGrid(props: VariantGridProps) {
  const {
    schema, rows, totalRows, page, pageSize,
    onPageChange, columnFilters, onColumnFilterChange,
    stateFilter, onStateFilterChange,
    columnToggles, onColumnToggleChange,
  } = props;

  const totalPages = Math.max(1, Math.ceil(totalRows / pageSize));

  const columns = useMemo(() => {
    const cols: Column<ProjectVariantRow>[] = [
      {
        key: "business_key",
        name: "business_key",
        width: 220,
        frozen: true,
        headerCellClass: styles.filterableHeader,
        renderHeaderCell: () => (
          <div className={styles.headerCell}>
            <span>business_key</span>
            <HeaderFilter column="search_business_key" value={columnFilters["search_business_key"] ?? ""} onChange={onColumnFilterChange} />
          </div>
        ),
      },
      {
        key: "file_name",
        name: "file_name",
        width: 160,
        renderCell: ({ row }) => <>{row.file_name ?? "-"}</>,
      },
      {
        key: "source",
        name: "source",
        width: 260,
        headerCellClass: styles.filterableHeader,
        renderHeaderCell: () => (
          <div className={styles.headerCell}>
            <span>source</span>
            <HeaderFilter column="search_source" value={columnFilters["search_source"] ?? ""} onChange={onColumnFilterChange} />
          </div>
        ),
      },
    ];

    if (columnToggles.translations) {
      for (const lang of schema.translation_columns) {
        cols.push({
          key: `translation:${lang}`,
          name: lang,
          width: 180,
          renderCell: ({ row }) => <>{row.translations[lang] ?? ""}</>,
        });
      }
    }

    if (columnToggles.remarks) {
      for (const key of schema.remark_columns) {
        cols.push({
          key: `remark:${key}`,
          name: key,
          width: 160,
          renderCell: ({ row }) => <>{row.remarks[key] ?? ""}</>,
        });
      }
    }

    if (columnToggles.pivot) {
      cols.push({
        key: "pivot_status",
        name: "pivot_status",
        width: 120,
      });
    }

    cols.push(
      {
        key: "branch",
        name: "branch",
        width: 170,
        renderCell: ({ row }) => <>{formatBranch(row)}</>,
      },
      {
        key: "state",
        name: "state",
        width: 100,
        renderCell: ({ row }) => (
          <span className={row.state === "orphan" ? styles.orphan : undefined}>
            {row.state}
          </span>
        ),
      },
    );

    return cols;
  }, [schema, columnToggles, columnFilters, onColumnFilterChange]);

  return (
    <div className={styles.grid}>
      <div className={styles.toolbar}>
        <label className={styles.toolbarItem}>
          State:
          <select
            value={stateFilter}
            onChange={(e) => onStateFilterChange(e.target.value as "active" | "orphan" | "all")}
          >
            <option value="active">Active</option>
            <option value="orphan">Orphan</option>
            <option value="all">All</option>
          </select>
        </label>
        <label className={styles.toggle}>
          <input type="checkbox" checked={columnToggles.translations} onChange={(e) => onColumnToggleChange("translations", e.target.checked)} />
          Translations
        </label>
        <label className={styles.toggle}>
          <input type="checkbox" checked={columnToggles.remarks} onChange={(e) => onColumnToggleChange("remarks", e.target.checked)} />
          Remarks
        </label>
        <label className={styles.toggle}>
          <input type="checkbox" checked={columnToggles.pivot} onChange={(e) => onColumnToggleChange("pivot", e.target.checked)} />
          Pivot
        </label>
      </div>
      <DataGrid
        columns={columns}
        rows={rows}
        rowKeyGetter={(row: ProjectVariantRow) => row.variant_id}
        className={styles.dataGrid}
      />
      <div className={styles.pagination}>
        <span>{totalRows} rows</span>
        <span>Page {page} of {totalPages}</span>
        <button disabled={page <= 1} onClick={() => onPageChange(page - 1)}>Prev</button>
        <button disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>Next</button>
      </div>
    </div>
  );
}
