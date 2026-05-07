import { useMemo } from "react";
import { DataGrid } from "react-data-grid";
import type { Column } from "react-data-grid";

import type { ProjectSchema } from "@/domains/projects/types";
import type {
  ProjectVariantRow,
  VariantFilterOptionsResponse,
  VariantGridColumnRef,
} from "@/domains/variants/types";
import { hasAnyFilter, type VariantGridFilterState } from "@/shared/ui/variantGridFilters";

import styles from "@/shared/ui/VariantGrid.module.css";

export type VariantGridProps = {
  schema: ProjectSchema;
  rows: ProjectVariantRow[];
  totalRows: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  filters: VariantGridFilterState;
  onFiltersChange: (filters: VariantGridFilterState) => void;
  branchFilter?: string;
  onBranchFilterChange?: (value: string) => void;
  loadFilterOptions: (
    targetColumn: VariantGridColumnRef,
    optionSearch: string,
  ) => Promise<VariantFilterOptionsResponse>;
  stateFilter: "active" | "orphan" | "all";
  onStateFilterChange: (state: "active" | "orphan" | "all") => void;
  branchOptions?: string[];
  showStateFilter?: boolean;
  columnToggles: { translations: boolean; remarks: boolean; pivot: boolean };
  onColumnToggleChange: (group: "translations" | "remarks" | "pivot", on: boolean) => void;
};

function formatBranch(row: ProjectVariantRow): string {
  const refs = row.bindings.map((b) => b.branch_ref);
  if (refs.length === 0) return "-";
  const first = refs[0].replace("rel/current", "rel/c");
  return refs.length > 1 ? `${first} +${refs.length - 1}` : first;
}

export function VariantGrid(props: VariantGridProps) {
  const {
    schema, rows, totalRows, page, pageSize,
    onPageChange, filters, onFiltersChange, branchFilter, onBranchFilterChange,
    loadFilterOptions: _loadFilterOptions,
    stateFilter, onStateFilterChange, branchOptions, showStateFilter = true,
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
  }, [schema, columnToggles]);

  return (
    <div className={styles.grid}>
      <div className={styles.toolbar}>
        {showStateFilter && (
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
        )}
        {branchOptions && (
          <label className={styles.toolbarItem}>
            Branch:
            <select
              value={branchFilter ?? ""}
              onChange={(e) => onBranchFilterChange?.(e.target.value)}
            >
              <option value="">All branches</option>
              {branchOptions.map((branchRef) => (
                <option key={branchRef} value={branchRef}>{branchRef}</option>
              ))}
            </select>
          </label>
        )}
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
        <button
          type="button"
          className={styles.clearButton}
          onClick={() => onFiltersChange({})}
          disabled={!hasAnyFilter(filters)}
        >
          Clear filters
        </button>
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
