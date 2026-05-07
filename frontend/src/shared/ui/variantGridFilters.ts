import type {
  VariantGridColumnFilter,
  VariantGridColumnRef,
} from "@/domains/variants/types";

export type VariantGridColumnFilterState = {
  text: string;
  values: Array<string | null>;
};

export type VariantGridFilterState = Record<string, VariantGridColumnFilterState>;

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
    const values = filter.values;
    if (!text && values.length === 0) return [];
    return [{ column, text, values }];
  });
}

export function hasAnyFilter(filters: VariantGridFilterState): boolean {
  return toApiFilters(filters).length > 0;
}

export function encodeGridFilters(filters: VariantGridFilterState): string | null {
  const entries = Object.entries(filters)
    .map(([key, filter]) => [key, { text: filter.text.trim(), values: filter.values }] as const)
    .filter(([, filter]) => filter.text || filter.values.length > 0);
  return entries.length > 0 ? JSON.stringify(Object.fromEntries(entries)) : null;
}

export function decodeGridFilters(value: string | null): VariantGridFilterState {
  if (!value) return {};
  try {
    const parsed = JSON.parse(value) as Record<string, VariantGridColumnFilterState>;
    const result: VariantGridFilterState = {};
    for (const [key, filter] of Object.entries(parsed)) {
      if (!parseColumnKey(key)) continue;
      result[key] = {
        text: typeof filter.text === "string" ? filter.text : "",
        values: Array.isArray(filter.values)
          ? filter.values.filter((item): item is string | null => item === null || typeof item === "string")
          : [],
      };
    }
    return result;
  } catch {
    return {};
  }
}
