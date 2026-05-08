import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";
import { DataGrid } from "react-data-grid";
import type { Column } from "react-data-grid";

import type { ProjectSchema } from "@/domains/projects/types";
import type {
  ProjectVariantRow,
  VariantFilterOptionsResponse,
  VariantGridColumnRef,
  VariantGridValueMode,
} from "@/domains/variants/types";
import {
  columnKey,
  hasAnyFilter,
  type VariantGridColumnFilterState,
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

function defaultColumnFilter(): VariantGridColumnFilterState {
  return { text: "", valueMode: "all", valueSearch: "", values: [] };
}

function isColumnFilterActive(filter: VariantGridColumnFilterState): boolean {
  return (
    filter.text.trim() !== "" ||
    filter.valueMode !== "all" ||
    filter.valueSearch.trim() !== "" ||
    filter.values.length > 0
  );
}

function HeaderFilterButton(props: {
  label: string;
  column: VariantGridColumnRef;
  filters: VariantGridFilterState;
  activeColumnKey: string | null;
  setActiveFilter: (filter: ActiveFilter | null) => void;
}) {
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const key = columnKey(props.column);
  const committed = props.filters[key] ?? defaultColumnFilter();
  const isOpen = props.activeColumnKey === key;
  const isActive = isColumnFilterActive(committed);

  return (
    <button
      type="button"
      className={`${styles.filterButton} ${isActive ? styles.filterButtonActive : ""}`}
      aria-label={`Filter ${props.label}`}
      title={`Filter ${props.label}`}
      ref={buttonRef}
      onClick={(event) => {
        event.stopPropagation();
        const rect = buttonRef.current?.getBoundingClientRect();
        props.setActiveFilter(isOpen || !rect ? null : { key, anchorRect: rect });
      }}
    >
      <span className={styles.filterIcon} aria-hidden="true" />
    </button>
  );
}

function HeaderFilterPopover(props: {
  label: string;
  column: VariantGridColumnRef;
  anchorRect: DOMRectReadOnly;
  filters: VariantGridFilterState;
  onFiltersChange: (filters: VariantGridFilterState) => void;
  onClose: () => void;
  loadFilterOptions: (
    targetColumn: VariantGridColumnRef,
    optionSearch: string,
  ) => Promise<VariantFilterOptionsResponse>;
}) {
  const key = columnKey(props.column);
  const committed = props.filters[key] ?? defaultColumnFilter();
  const [draftText, setDraftText] = useState(committed.text);
  const [draftValues, setDraftValues] = useState<Array<string | null>>(committed.values);
  const [draftValueMode, setDraftValueMode] = useState<VariantGridValueMode>(committed.valueMode);
  const [draftValueSearch, setDraftValueSearch] = useState(committed.valueSearch);
  const [optionSearch, setOptionSearch] = useState(committed.valueSearch);
  const [options, setOptions] = useState<VariantFilterOptionsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const popoverStyle = useMemo<CSSProperties>(() => {
    const width = 260;
    const padding = 8;
    const viewportWidth = window.innerWidth;
    let left = props.anchorRect.left;
    if (left + width > viewportWidth - padding) {
      left = props.anchorRect.right - width;
    }
    left = Math.max(padding, Math.min(left, viewportWidth - width - padding));
    return {
      left,
      top: Math.max(padding, props.anchorRect.bottom - 2),
    };
  }, [props.anchorRect]);

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
  }, [optionSearch, props.column.kind, props.column.name, props.loadFilterOptions]);

  function optionIsChecked(value: string | null): boolean {
    const selected = draftValues.some((item) => optionValueKey(item) === optionValueKey(value));
    if (draftValueMode === "all") return true;
    if (draftValueMode === "exclude") return !selected;
    return selected;
  }

  function toggleDraftOption(value: string | null) {
    if (draftValueMode === "all") {
      setDraftValueMode("exclude");
      setDraftValueSearch(optionSearch.trim());
      setDraftValues([value]);
      return;
    }
    setDraftValues((current) => toggleOption(current, value));
  }

  function selectAllValues() {
    setDraftValueMode("all");
    setDraftValues([]);
    setDraftValueSearch(optionSearch.trim());
  }

  function invertValues() {
    if (draftValueMode === "all") {
      setDraftValueMode("include");
      setDraftValues([]);
      setDraftValueSearch("");
      return;
    }
    if (draftValueMode === "include") {
      if (draftValues.length === 0) {
        setDraftValueMode("all");
        setDraftValueSearch(optionSearch.trim());
      } else {
        setDraftValueMode("exclude");
        setDraftValueSearch(optionSearch.trim());
      }
      return;
    }
    setDraftValueMode("include");
    setDraftValueSearch("");
  }

  function apply() {
    const next = { ...props.filters };
    const value = {
      text: draftText.trim(),
      valueMode: draftValueMode,
      valueSearch: draftValueMode === "all" || draftValueMode === "exclude"
        ? draftValueSearch.trim()
        : "",
      values: draftValues,
    };
    if (!isColumnFilterActive(value)) {
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

  return createPortal(
    <div
      className={styles.filterPopover}
      style={popoverStyle}
      onClick={(event) => event.stopPropagation()}
    >
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
      <div className={styles.optionTools}>
        <button
          type="button"
          onClick={selectAllValues}
          aria-label={`Select all ${props.label} values`}
        >
          Select All
        </button>
        <button
          type="button"
          onClick={invertValues}
          aria-label={`Invert ${props.label} values`}
        >
          Invert
        </button>
      </div>
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
                checked={optionIsChecked(option.value)}
                onChange={() => toggleDraftOption(option.value)}
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
    </div>,
    document.body,
  );
}

type ActiveFilter = {
  key: string;
  anchorRect: DOMRectReadOnly;
};

export function VariantGrid(props: VariantGridProps) {
  const {
    schema, rows, totalRows, page, pageSize,
    onPageChange, filters, onFiltersChange, branchFilter, onBranchFilterChange,
    loadFilterOptions,
    stateFilter, onStateFilterChange, branchOptions, showStateFilter = true,
    columnToggles, onColumnToggleChange,
  } = props;

  const [activeFilter, setActiveFilter] = useState<ActiveFilter | null>(null);
  const activeColumnKey = activeFilter?.key ?? null;
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
          setActiveFilter={setActiveFilter}
        />
        {activeColumnKey === key && activeFilter ? (
          <HeaderFilterPopover
            label={label}
            column={column}
            anchorRect={activeFilter.anchorRect}
            filters={filters}
            onFiltersChange={onFiltersChange}
            onClose={() => setActiveFilter(null)}
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
