import { useDeferredValue, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useAppShell } from "@/app/shell/AppShellContext";
import { getProjectVariants } from "@/domains/variants/api";
import { queryKeys } from "@/shared/api/queryKeys";
import { InlineNotice } from "@/shared/ui/primitives";
import { VariantGrid } from "@/shared/ui/VariantGrid";

export function WorkspacePage() {
  const shell = useAppShell();
  const projectId = shell.projectId!;
  const schema = shell.bootstrap!.schema;

  const [stateFilter, setStateFilter] = useState<"active" | "orphan" | "all">("active");
  const [columnFilters, setColumnFilters] = useState<Record<string, string>>({});
  const [columnToggles, setColumnToggles] = useState({ translations: true, remarks: false, pivot: false });
  const [page, setPage] = useState(1);

  const deferredFilters = useDeferredValue(columnFilters);

  const params = {
    state: stateFilter === "all" ? undefined : stateFilter,
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
    setColumnFilters((prev) => ({ ...prev, [column]: value }));
    setPage(1);
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
      onPageChange={setPage}
      columnFilters={columnFilters}
      onColumnFilterChange={handleColumnFilter}
      stateFilter={stateFilter}
      onStateFilterChange={(s) => { setStateFilter(s); setPage(1); }}
      columnToggles={columnToggles}
      onColumnToggleChange={(g, on) => setColumnToggles((prev) => ({ ...prev, [g]: on }))}
    />
  );
}
