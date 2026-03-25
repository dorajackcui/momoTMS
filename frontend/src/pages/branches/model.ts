import type { ProjectSchema } from "@/domains/projects/types";

export type DirectPatchRow = {
  id: string;
  business_key: string;
  source: string;
  file_name: string;
  [key: string]: string;
};

export function createDirectPatchRow(schema: ProjectSchema): DirectPatchRow {
  const row: DirectPatchRow = {
    id: crypto.randomUUID(),
    business_key: "",
    source: "",
    file_name: "",
  };
  for (const lang of schema.translation_columns) {
    row[`translation:${lang}`] = "";
  }
  for (const key of schema.remark_columns) {
    row[`remark:${key}`] = "";
  }
  return row;
}

export function rowsToDirectMutationChanges(
  rows: DirectPatchRow[],
  schema: ProjectSchema,
) {
  return rows
    .filter((row) => row.business_key.trim())
    .map((row) => ({
      business_key: row.business_key.trim(),
      source: row.source.trim() || undefined,
      file_name: row.file_name.trim() || undefined,
      translations_by_lang: Object.fromEntries(
        schema.translation_columns
          .map((lang) => [lang, row[`translation:${lang}`] || ""] as const)
          .filter(([, value]) => value !== ""),
      ),
      remarks_by_key: Object.fromEntries(
        schema.remark_columns
          .map((key) => [key, row[`remark:${key}`] || ""] as const)
          .filter(([, value]) => value !== ""),
      ),
    }));
}

export function parseLineSeparatedList(value: string) {
  return value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function parseVariantIdList(value: string) {
  return parseLineSeparatedList(value)
    .map((item) => Number(item))
    .filter((item) => Number.isInteger(item) && item > 0);
}

export function ensureDevBranch(branchRef: string | null, fallback: string | null) {
  if (branchRef?.startsWith("dev/")) {
    return branchRef;
  }
  return fallback;
}
