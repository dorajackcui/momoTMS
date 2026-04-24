import { useDeferredValue } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { useAppShell } from "@/app/shell/AppShellContext";
import { getProjectVariants } from "@/domains/variants/api";
import { queryKeys } from "@/shared/api/queryKeys";
import { applySearchPatch, normalizeText, parsePositiveInt } from "@/shared/lib/url";
import { InlineNotice } from "@/shared/ui/primitives";
import { VariantGrid } from "@/shared/ui/VariantGrid";

type WorkspaceStateFilter = "active" | "orphan" | "all";

export function WorkspacePage() {
  const shell = useAppShell();
  const projectId = shell.projectId!;
  const schema = shell.bootstrap!.schema;
  const [searchParams, setSearchParams] = useSearchParams();

  const stateFilter = parseStateFilter(searchParams.get("state"));
  const branchFilter = normalizeText(searchParams.get("branch"));
  const page = parsePositiveInt(searchParams.get("page")) ?? 1;
  const columnFilters: Record<string, string> = {
    search_business_key: normalizeText(searchParams.get("search_business_key")) ?? "",
    search_source: normalizeText(searchParams.get("search_source")) ?? "",
    branch: branchFilter ?? "",
  };
  const columnToggles = {
    translations: searchParams.get("translations") !== "0",
    remarks: searchParams.get("remarks") === "1",
    pivot: searchParams.get("pivot") === "1",
  };
  const branchOptions = [
    "rel/current",
    ...(shell.bootstrap?.dev_branches ?? []).map((branch) => branch.branch_ref),
  ];

  const deferredFilters = useDeferredValue(columnFilters);

  const params = {
    state: stateFilter,
    search_business_key: deferredFilters["search_business_key"] || undefined,
    search_source: deferredFilters["search_source"] || undefined,
    branch_ref: deferredFilters["branch"] ? [deferredFilters["branch"]] : undefined,
    page,
    page_size: 100,
  };

  const query = useQuery({
    queryKey: queryKeys.projectVariants(projectId, params),
    queryFn: () => getProjectVariants(projectId, params),
  });

  function handleColumnFilter(column: string, value: string) {
    setSearchParams(
      (current) => applySearchPatch(current, { [column]: value, page: null }),
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
      pageSize={100}
      onPageChange={handlePageChange}
      columnFilters={columnFilters}
      onColumnFilterChange={handleColumnFilter}
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
