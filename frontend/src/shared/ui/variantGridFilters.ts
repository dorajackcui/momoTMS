import type {
  ProjectSchema,
} from "@/domains/projects/types";
import type {
  VariantGridColumnFilter,
  VariantGridColumnRef,
  VariantGridValueMode,
} from "@/domains/variants/types";

export type VariantGridColumnFilterState = {
  text: string;
  valueMode: VariantGridValueMode;
  valueSearch: string;
  values: Array<string | null>;
};

export type VariantGridFilterState = Record<string, VariantGridColumnFilterState>;

const allowedFieldColumns = new Set([
  "business_key",
  "file_name",
  "source",
  "branch",
  "state",
  "pivot_status",
]);

export function columnKey(column: VariantGridColumnRef): string {
  return `${column.kind}:${column.name}`;
}

export function parseColumnKey(value: string): VariantGridColumnRef | null {
  const index = value.indexOf(":");
  if (index <= 0) return null;
  const kind = value.slice(0, index);
  const name = value.slice(index + 1);
  if ((kind !== "field" && kind !== "translation" && kind !== "remark") || !name) {
    return null;
  }
  return { kind, name };
}

export function toApiFilters(filters: VariantGridFilterState): VariantGridColumnFilter[] {
  return Object.entries(filters).flatMap(([key, filter]) => {
    const column = parseColumnKey(key);
    if (!column) return [];
    const text = filter.text.trim();
    const valueMode = filter.valueMode ?? (filter.values.length > 0 ? "include" : "all");
    const valueSearch = (filter.valueSearch ?? "").trim();
    const values = filter.values;
    const hasValueSelection = valueMode !== "all" || valueSearch || values.length > 0;
    if (!text && !hasValueSelection) return [];
    return [{
      column,
      text,
      value_mode: valueMode,
      value_search: valueSearch,
      values,
    }];
  });
}

export function pruneFiltersForSchema(
  filters: VariantGridFilterState,
  schema: ProjectSchema,
): VariantGridFilterState {
  const translationColumns = new Set(schema.translation_columns);
  const remarkColumns = new Set(schema.remark_columns);
  const result: VariantGridFilterState = {};

  for (const [key, filter] of Object.entries(filters)) {
    const column = parseColumnKey(key);
    if (!column) continue;
    if (column.kind === "field" && !allowedFieldColumns.has(column.name)) continue;
    if (column.kind === "translation" && !translationColumns.has(column.name)) continue;
    if (column.kind === "remark" && !remarkColumns.has(column.name)) continue;
    result[key] = filter;
  }

  return result;
}

export function hasAnyFilter(filters: VariantGridFilterState): boolean {
  return toApiFilters(filters).length > 0;
}

export function encodeGridFilters(filters: VariantGridFilterState): string | null {
  const entries = Object.entries(filters)
    .map(([key, filter]) => [
      key,
      {
        text: filter.text.trim(),
        valueMode: filter.valueMode ?? (filter.values.length > 0 ? "include" : "all"),
        valueSearch: (filter.valueSearch ?? "").trim(),
        values: filter.values,
      },
    ] as const)
    .filter(([, filter]) =>
      filter.text ||
      filter.valueMode !== "all" ||
      filter.valueSearch ||
      filter.values.length > 0
    );
  return entries.length > 0 ? JSON.stringify(Object.fromEntries(entries)) : null;
}

export function decodeGridFilters(value: string | null): VariantGridFilterState {
  if (!value) return {};
  try {
    const parsed = JSON.parse(value) as Record<string, VariantGridColumnFilterState>;
    const result: VariantGridFilterState = {};
    for (const [key, filter] of Object.entries(parsed)) {
      if (!parseColumnKey(key)) continue;
      const valueMode = filter.valueMode === "all" || filter.valueMode === "include" || filter.valueMode === "exclude"
        ? filter.valueMode
        : undefined;
      const values = Array.isArray(filter.values)
        ? filter.values.filter((item): item is string | null => item === null || typeof item === "string")
        : [];
      result[key] = {
        text: typeof filter.text === "string" ? filter.text : "",
        valueMode: valueMode ?? (values.length > 0 ? "include" : "all"),
        valueSearch: typeof filter.valueSearch === "string" ? filter.valueSearch : "",
        values,
      };
    }
    return result;
  } catch {
    return {};
  }
}
