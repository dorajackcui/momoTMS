import { PROJECT_STORAGE_KEY } from "./routes";
import type {
  BranchOption,
  ImportPreview,
  ImportSheetMapping,
  JobStageSummary,
  JobSummary,
} from "./types";

export function buildBranchOptions(
  branches: Array<{ branch_ref: string; is_candidate_release?: boolean | null }>,
): BranchOption[] {
  return branches.map((branch) => ({
    value: branch.branch_ref,
    label: `${branch.branch_ref}${branch.is_candidate_release ? " · candidate" : ""}`,
  }));
}

export function splitColumns(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function buildInitialImportMappings(
  preview: ImportPreview,
): Record<string, ImportSheetMapping> {
  const mappings: Record<string, ImportSheetMapping> = {};
  for (const sheet of preview.sheet_previews) {
    const suggested = sheet.suggested_mapping || {};
    mappings[sheet.sheet_key] = {
      business_key: String(suggested.business_key || ""),
      source: String(suggested.source || ""),
      translation_columns: Object.fromEntries(
        Object.entries(suggested.translation_columns || {}).map(([key, value]) => [
          key,
          String(value || ""),
        ]),
      ),
      remark_columns: Object.fromEntries(
        Object.entries(suggested.remark_columns || {}).map(([key, value]) => [
          key,
          String(value || ""),
        ]),
      ),
    };
  }
  return mappings;
}

export function listMissingImportMappings(
  preview: ImportPreview | null,
  mappings: Record<string, ImportSheetMapping>,
): Array<{ sheet_key: string; missing: string[] }> {
  if (!preview) {
    return [];
  }
  const issues: Array<{ sheet_key: string; missing: string[] }> = [];
  for (const sheet of preview.sheet_previews) {
    const mapping = mappings[sheet.sheet_key];
    const missing: string[] = [];
    if (!mapping?.business_key) {
      missing.push("business_key");
    }
    if (!mapping?.source) {
      missing.push("source");
    }
    if (missing.length > 0) {
      issues.push({ sheet_key: sheet.sheet_key, missing });
    }
  }
  return issues;
}

export function presentState(
  value: string,
  baseScope: string,
  targetScope: string,
): string {
  const isReleaseCompare =
    baseScope === "rel/current" && targetScope.startsWith("dev/");
  if (!isReleaseCompare) {
    return value;
  }
  if (value === "base_only") {
    return "rel_only";
  }
  if (value === "target_only") {
    return "dev_only";
  }
  return value;
}

export function asMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed";
}

export function getStoredProjectId(): number | null {
  const raw = window.localStorage.getItem(PROJECT_STORAGE_KEY);
  if (!raw) {
    return null;
  }
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function setStoredProjectId(projectId: number) {
  window.localStorage.setItem(PROJECT_STORAGE_KEY, String(projectId));
}

export function clearStoredProjectId() {
  window.localStorage.removeItem(PROJECT_STORAGE_KEY);
}

export function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return value.replace("T", " ").replace("+00:00", "Z");
}

export function stringifyValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return String(value);
  }
  return JSON.stringify(value);
}

export function objectEntries(
  value: Record<string, unknown>,
  exclude: string[] = [],
): Array<[string, string]> {
  return Object.entries(value)
    .filter(([key]) => !exclude.includes(key))
    .map(([key, item]) => [key, stringifyValue(item)]);
}

export function readJobStages(summary: Record<string, unknown>): JobStageSummary[] {
  const stages = summary.stages;
  if (!Array.isArray(stages)) {
    return [];
  }
  return stages
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }
      const stage = item as Record<string, unknown>;
      return {
        stage: String(stage.stage || ""),
        elapsed_ms: Number(stage.elapsed_ms || 0),
        meta: (stage.meta as Record<string, unknown>) || {},
      };
    })
    .filter((item): item is JobStageSummary => Boolean(item && item.stage));
}

export function summarizeJob(job: JobSummary): string {
  const summaryEntries = objectEntries(job.summary, ["stages"]).slice(0, 2);
  if (summaryEntries.length === 0) {
    return "No summary metrics";
  }
  return summaryEntries
    .map(([key, value]) => `${key}: ${value}`)
    .join(" · ");
}

export function buildArtifactHref(
  projectId: number,
  job: JobSummary,
): string | null {
  if (!job.artifact_path) {
    return null;
  }
  const artifactName = job.artifact_path.split("/").pop();
  if (!artifactName) {
    return null;
  }
  return `/api/projects/${projectId}/jobs/${job.job_id}/artifact/${encodeURIComponent(
    artifactName,
  )}`;
}
