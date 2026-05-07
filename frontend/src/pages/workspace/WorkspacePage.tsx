import { useCallback, useDeferredValue, useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { useAppShell } from "@/app/shell/AppShellContext";
import { getProjectVariantFilterOptions, queryProjectVariants } from "@/domains/variants/api";
import type { VariantGridColumnRef } from "@/domains/variants/types";
import { queryKeys } from "@/shared/api/queryKeys";
import { applySearchPatch, normalizeText, parsePositiveInt } from "@/shared/lib/url";
import { InlineNotice } from "@/shared/ui/primitives";
import { VariantGrid } from "@/shared/ui/VariantGrid";
import {
  decodeGridFilters,
  encodeGridFilters,
  pruneFiltersForSchema,
  toApiFilters,
  type VariantGridFilterState,
} from "@/shared/ui/variantGridFilters";

type WorkspaceStateFilter = "active" | "orphan" | "all";
const pageSize = 50;

export function WorkspacePage() {
  const shell = useAppShell();
  const projectId = shell.projectId!;
  const schema = shell.bootstrap!.schema;
  const [searchParams, setSearchParams] = useSearchParams();

  const stateFilter = parseStateFilter(searchParams.get("state"));
  const rawBranchFilter = normalizeText(searchParams.get("branch"));
  const branchFilter = rawBranchFilter ? shell.branchRef : null;
  const page = parsePositiveInt(searchParams.get("page")) ?? 1;
  const gridFilterParam = searchParams.get("grid_filters");
  const rawGridFilters = useMemo(() => decodeGridFilters(gridFilterParam), [gridFilterParam]);
  const gridFilters = useMemo(
    () => pruneFiltersForSchema(rawGridFilters, schema),
    [rawGridFilters, schema],
  );
  const columnToggles = {
    translations: searchParams.get("translations") !== "0",
    remarks: searchParams.get("remarks") === "1",
    pivot: searchParams.get("pivot") === "1",
  };
  const branchOptions = [
    "rel/current",
    ...(shell.bootstrap?.dev_branches ?? []).map((branch) => branch.branch_ref),
  ];

  const deferredFilters = useDeferredValue(gridFilters);

  useEffect(() => {
    const rawEncoded = encodeGridFilters(rawGridFilters);
    const prunedEncoded = encodeGridFilters(gridFilters);
    if (rawEncoded === prunedEncoded) return;
    setSearchParams(
      (current) => applySearchPatch(current, { grid_filters: prunedEncoded, page: null }),
      { replace: true },
    );
  }, [gridFilters, rawGridFilters, setSearchParams]);

  const params = useMemo(() => ({
    scope: branchFilter
      ? { kind: "branch" as const, branch_ref: branchFilter }
      : { kind: "project" as const },
    state: stateFilter,
    filters: toApiFilters(deferredFilters),
    page,
    page_size: pageSize,
  }), [branchFilter, deferredFilters, page, stateFilter]);

  const loadFilterOptions = useCallback((targetColumn: VariantGridColumnRef, optionSearch: string) =>
    getProjectVariantFilterOptions(projectId, {
      ...params,
      target_column: targetColumn,
      option_search: optionSearch,
      limit: 100,
    }), [projectId, params]);

  const query = useQuery({
    queryKey: queryKeys.projectVariants(projectId, params),
    queryFn: () => queryProjectVariants(projectId, params),
  });

  function handleColumnFilter(column: string, value: string) {
    setSearchParams(
      (current) => applySearchPatch(current, { [column]: value, page: null }),
      { replace: false },
    );
  }

  function handleGridFiltersChange(filters: VariantGridFilterState) {
    setSearchParams(
      (current) => applySearchPatch(current, { grid_filters: encodeGridFilters(filters), page: null }),
      { replace: false },
    );
  }

  function handleStateFilter(state: WorkspaceStateFilter) {
    setSearchParams(
      (current) => applySearchPatch(current, { state: state === "active" ? null : state, page: null }),
      { replace: false },
    );
  }

  function handlePageChange(nextPage: number) {
    setSearchParams(
      (current) => applySearchPatch(current, { page: nextPage <= 1 ? null : nextPage }),
      { replace: false },
    );
  }

  function handleColumnToggle(group: "translations" | "remarks" | "pivot", on: boolean) {
    const value =
      group === "translations"
        ? on ? null : "0"
        : on ? "1" : null;
    setSearchParams(
      (current) => applySearchPatch(current, { [group]: value }),
      { replace: false },
    );
  }

  if (query.isError) {
    return <InlineNotice tone="error">{String(query.error)}</InlineNotice>;
  }

  return (
    <VariantGrid
      schema={schema}
      rows={query.data?.rows ?? []}
      totalRows={query.data?.total_rows ?? 0}
      page={page}
      pageSize={pageSize}
      onPageChange={handlePageChange}
      filters={gridFilters}
      onFiltersChange={handleGridFiltersChange}
      branchFilter={branchFilter ?? ""}
      onBranchFilterChange={(value) => handleColumnFilter("branch", value)}
      loadFilterOptions={loadFilterOptions}
      stateFilter={stateFilter}
      onStateFilterChange={handleStateFilter}
      branchOptions={branchOptions}
      columnToggles={columnToggles}
      onColumnToggleChange={handleColumnToggle}
    />
  );
}

function parseStateFilter(value: string | null): WorkspaceStateFilter {
  return value === "orphan" || value === "all" ? value : "active";
}
