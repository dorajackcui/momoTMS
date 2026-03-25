import type {
  BranchCompareResponse,
  DevBranchDetail,
} from "@/domains/branches/types";
import type { ProjectSchema } from "@/domains/projects/types";

export type OverviewColumnPreset = "core" | "translation" | "review";
export type OverviewLifecycleFilter = "all" | "active" | "sampled";

export type OverviewGridRow = {
  id: string;
  businessKey: string;
  fileName: string;
  source: string;
  translations: Record<string, string>;
  remarks: Record<string, string>;
  statusSummary: string;
  branchBadge: string;
  lifecycle: "active" | "sampled";
};

export function buildOverviewRowsFromDevBranch(
  detail: DevBranchDetail,
): OverviewGridRow[] {
  return detail.entries.map((entry) => ({
    id: `${detail.branch_ref}-${entry.variant_id}`,
    businessKey: entry.business_key,
    fileName: entry.file_name || "-",
    source: entry.source,
    translations: Object.fromEntries(
      Object.entries(entry.translations).map(([key, value]) => [key, value || ""]),
    ),
    remarks: Object.fromEntries(
      Object.entries(entry.remarks).map(([key, value]) => [key, value || ""]),
    ),
    statusSummary: "Active row",
    branchBadge: detail.branch_ref,
    lifecycle: "active",
  }));
}

export function buildOverviewRowsFromCompare(
  compare: BranchCompareResponse,
): OverviewGridRow[] {
  return compare.rows.map((row) => {
    const target = row.target || row.base;
    return {
      id: `${compare.target_branch_ref}-${row.business_key}`,
      businessKey: row.business_key,
      fileName: target?.file_name || "-",
      source: target?.source || "",
      translations: Object.fromEntries(
        Object.entries(target?.translations || {}).map(([key, value]) => [
          key,
          value || "",
        ]),
      ),
      remarks: Object.fromEntries(
        Object.entries(target?.remarks || {}).map(([key, value]) => [key, value || ""]),
      ),
      statusSummary: row.state,
      branchBadge: "sampled active rows",
      lifecycle: "sampled",
    };
  });
}

export function filterOverviewRows(
  rows: OverviewGridRow[],
  filters: {
    businessKey: string;
    source: string;
    lifecycle: OverviewLifecycleFilter;
  },
) {
  const normalizedKey = filters.businessKey.trim().toLowerCase();
  const normalizedSource = filters.source.trim().toLowerCase();
  return rows.filter((row) => {
    if (filters.lifecycle !== "all" && row.lifecycle !== filters.lifecycle) {
      return false;
    }
    if (
      normalizedKey &&
      !row.businessKey.toLowerCase().includes(normalizedKey)
    ) {
      return false;
    }
    if (
      normalizedSource &&
      !row.source.toLowerCase().includes(normalizedSource)
    ) {
      return false;
    }
    return true;
  });
}

export function overviewColumnKeys(
  schema: ProjectSchema,
  preset: OverviewColumnPreset,
) {
  const base = ["businessKey", "fileName", "source"];
  if (preset === "core") {
    return [...base, "statusSummary", "branchBadge"];
  }
  if (preset === "translation") {
    return [
      ...base,
      ...schema.translation_columns.map((lang) => `translation:${lang}`),
      "statusSummary",
      "branchBadge",
    ];
  }
  return [
    ...base,
    ...schema.translation_columns.map((lang) => `translation:${lang}`),
    ...schema.remark_columns.map((key) => `remark:${key}`),
    "statusSummary",
    "branchBadge",
  ];
}
