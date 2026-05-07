import { useEffect, useMemo, useState } from "react";
import { DataGrid } from "react-data-grid";
import type { Column } from "react-data-grid";

import type { ProjectSchema } from "@/domains/projects/types";
import type {
  ProjectVariantRow,
  VariantFilterOptionsResponse,
  VariantGridColumnRef,
} from "@/domains/variants/types";
import {
  columnKey,
  hasAnyFilter,
  type VariantGridFilterState,
} from "@/shared/ui/variantGridFilters";

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

function optionValueKey(value: string | null): string {
  return value === null ? "__blank__" : value;
}

function toggleOption(
  values: Array<string | null>,
  value: string | null,
): Array<string | null> {
  const key = optionValueKey(value);
  const exists = values.some((item) => optionValueKey(item) === key);
  return exists
    ? values.filter((item) => optionValueKey(item) !== key)
    : [...values, value];
}

function HeaderFilterButton(props: {
  label: string;
  column: VariantGridColumnRef;
  filters: VariantGridFilterState;
  activeColumnKey: string | null;
  setActiveColumnKey: (key: string | null) => void;
}) {
  const key = columnKey(props.column);
  const committed = props.filters[key] ?? { text: "", values: [] };
  const isOpen = props.activeColumnKey === key;
  const isActive = committed.text.trim() !== "" || committed.values.length > 0;

  return (
    <button
      type="button"
      className={`${styles.filterButton} ${isActive ? styles.filterButtonActive : ""}`}
      aria-label={`Filter ${props.label}`}
      title={`Filter ${props.label}`}
      onClick={(event) => {
        event.stopPropagation();
        props.setActiveColumnKey(isOpen ? null : key);
      }}
    >
      v
    </button>
  );
}

function HeaderFilterPopover(props: {
  label: string;
  column: VariantGridColumnRef;
  filters: VariantGridFilterState;
  onFiltersChange: (filters: VariantGridFilterState) => void;
  onClose: () => void;
  loadFilterOptions: (
    targetColumn: VariantGridColumnRef,
    optionSearch: string,
  ) => Promise<VariantFilterOptionsResponse>;
}) {
  const key = columnKey(props.column);
  const committed = props.filters[key] ?? { text: "", values: [] };
  const [draftText, setDraftText] = useState(committed.text);
  const [draftValues, setDraftValues] = useState<Array<string | null>>(committed.values);
  const [optionSearch, setOptionSearch] = useState("");
  const [options, setOptions] = useState<VariantFilterOptionsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    props.loadFilterOptions(props.column, optionSearch)
      .then((data) => {
        if (!cancelled) {
          setOptions(data);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [optionSearch, props.column.kind, props.column.name]);

  function apply() {
    const next = { ...props.filters };
    const value = { text: draftText.trim(), values: draftValues };
    if (!value.text && value.values.length === 0) {
      delete next[key];
    } else {
      next[key] = value;
    }
    props.onFiltersChange(next);
    props.onClose();
  }

  function clearColumn() {
    const next = { ...props.filters };
    delete next[key];
    props.onFiltersChange(next);
    props.onClose();
  }

  return (
    <div className={styles.filterPopover} onClick={(event) => event.stopPropagation()}>
      <label className={styles.filterLabel}>
        <span>Search</span>
        <input
          aria-label={`Search ${props.label}`}
          value={draftText}
          onChange={(event) => setDraftText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") apply();
          }}
        />
      </label>
      <label className={styles.filterLabel}>
        <span>Find values</span>
        <input
          aria-label={`Find ${props.label} values`}
          value={optionSearch}
          onChange={(event) => setOptionSearch(event.target.value)}
        />
      </label>
      <div className={styles.optionList}>
        {error ? <span className={styles.optionMeta}>{error}</span> : null}
        {options?.values.map((option) => {
          const displayLabel = option.value === null ? "(blank)" : option.label;
          return (
            <label
              key={optionValueKey(option.value)}
              className={styles.optionItem}
              title={displayLabel}
            >
              <input
                type="checkbox"
                checked={draftValues.some((item) => optionValueKey(item) === optionValueKey(option.value))}
                onChange={() => setDraftValues((current) => toggleOption(current, option.value))}
              />
              <span>{displayLabel}</span>
            </label>
          );
        })}
        {options?.has_more ? <span className={styles.optionMeta}>Showing first 100 values</span> : null}
      </div>
      <div className={styles.filterActions}>
        <button type="button" onClick={clearColumn}>Clear column</button>
        <button type="button" onClick={apply} aria-label={`Apply ${props.label} filter`}>Apply</button>
      </div>
    </div>
  );
}

export function VariantGrid(props: VariantGridProps) {
  const {
    schema, rows, totalRows, page, pageSize,
    onPageChange, filters, onFiltersChange, branchFilter, onBranchFilterChange,
    loadFilterOptions,
    stateFilter, onStateFilterChange, branchOptions, showStateFilter = true,
    columnToggles, onColumnToggleChange,
  } = props;

  const [activeColumnKey, setActiveColumnKey] = useState<string | null>(null);
  const totalPages = Math.max(1, Math.ceil(totalRows / pageSize));

  function renderFilterableHeader(label: string, column: VariantGridColumnRef) {
    const key = columnKey(column);
    return (
      <div className={styles.headerCell}>
        <span>{label}</span>
        <HeaderFilterButton
          label={label}
          column={column}
          filters={filters}
          activeColumnKey={activeColumnKey}
          setActiveColumnKey={setActiveColumnKey}
        />
        {activeColumnKey === key ? (
          <HeaderFilterPopover
            label={label}
            column={column}
            filters={filters}
            onFiltersChange={onFiltersChange}
            onClose={() => setActiveColumnKey(null)}
            loadFilterOptions={loadFilterOptions}
          />
        ) : null}
      </div>
    );
  }

  const columns = useMemo(() => {
    const cols: Column<ProjectVariantRow>[] = [
      {
        key: "business_key",
        name: "business_key",
        width: 220,
        frozen: true,
        renderHeaderCell: () => renderFilterableHeader("business_key", { kind: "field", name: "business_key" }),
      },
      {
        key: "file_name",
        name: "file_name",
        width: 160,
        renderHeaderCell: () => renderFilterableHeader("file_name", { kind: "field", name: "file_name" }),
        renderCell: ({ row }) => <>{row.file_name ?? "-"}</>,
      },
      {
        key: "source",
        name: "source",
        width: 260,
        renderHeaderCell: () => renderFilterableHeader("source", { kind: "field", name: "source" }),
      },
    ];

    if (columnToggles.translations) {
      for (const lang of schema.translation_columns) {
        cols.push({
          key: `translation:${lang}`,
          name: lang,
          width: 180,
          renderHeaderCell: () => renderFilterableHeader(lang, { kind: "translation", name: lang }),
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
          renderHeaderCell: () => renderFilterableHeader(key, { kind: "remark", name: key }),
          renderCell: ({ row }) => <>{row.remarks[key] ?? ""}</>,
        });
      }
    }

    if (columnToggles.pivot) {
      cols.push({
        key: "pivot_status",
        name: "pivot_status",
        width: 120,
        renderHeaderCell: () => renderFilterableHeader("pivot_status", { kind: "field", name: "pivot_status" }),
      });
    }

    cols.push(
      {
        key: "branch",
        name: "branch",
        width: 170,
        renderHeaderCell: () => renderFilterableHeader("branch", { kind: "field", name: "branch" }),
        renderCell: ({ row }) => <>{formatBranch(row)}</>,
      },
      {
        key: "state",
        name: "state",
        width: 100,
        renderHeaderCell: () => renderFilterableHeader("state", { kind: "field", name: "state" }),
        renderCell: ({ row }) => (
          <span className={row.state === "orphan" ? styles.orphan : undefined}>
            {row.state}
          </span>
        ),
      },
    );

    return cols;
  }, [schema, columnToggles, filters, activeColumnKey, loadFilterOptions, onFiltersChange]);

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
