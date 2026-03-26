import type { ProjectSchema } from "@/domains/projects/types";
import type { ProjectVariantsResponse } from "@/domains/variants/types";

export type OverviewColumnPreset = "core" | "translation" | "review";
export type OverviewLifecycleFilter = "all" | "active" | "orphan";

export type OverviewGridRow = {
  id: string;
  businessKey: string;
  fileName: string;
  source: string;
  translations: Record<string, string>;
  remarks: Record<string, string>;
  statusSummary: string;
  branchesSummary: string;
  lifecycle: "active" | "orphan";
};

export function buildOverviewRowsFromProjectVariants(
  payload: ProjectVariantsResponse,
): OverviewGridRow[] {
  return payload.rows.map((row) => ({
    id: `variant-${row.variant_id}`,
    businessKey: row.business_key,
    fileName: row.file_name || "-",
    source: row.source,
    translations: Object.fromEntries(
      Object.entries(row.translations).map(([key, value]) => [key, value || ""]),
    ),
    remarks: Object.fromEntries(
      Object.entries(row.remarks).map(([key, value]) => [key, value || ""]),
    ),
    statusSummary: row.state,
    branchesSummary:
      row.bindings.map((binding) => binding.branch_ref).join(", ") || "-",
    lifecycle: row.state,
  }));
}

export function overviewColumnKeys(
  schema: ProjectSchema,
  preset: OverviewColumnPreset,
) {
  const base = ["businessKey", "fileName", "source"];
  if (preset === "core") {
    return [...base, "statusSummary", "branchesSummary"];
  }
  if (preset === "translation") {
    return [
      ...base,
      ...schema.translation_columns.map((lang) => `translation:${lang}`),
      "statusSummary",
      "branchesSummary",
    ];
  }
  return [
    ...base,
    ...schema.translation_columns.map((lang) => `translation:${lang}`),
    ...schema.remark_columns.map((key) => `remark:${key}`),
    "statusSummary",
    "branchesSummary",
  ];
}
