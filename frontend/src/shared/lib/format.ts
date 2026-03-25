import type { JobSummary } from "@/domains/jobs/types";

export function formatTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  return value.replace("T", " ").replace("+00:00", "Z");
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return new Intl.NumberFormat().format(value);
}

export function titleCase(value: string): string {
  return value
    .replace(/[_/]/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
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

export function summarizeJob(job: JobSummary): string {
  const entries = Object.entries(job.summary)
    .filter(([key]) => key !== "stages")
    .slice(0, 2);
  if (entries.length === 0) {
    return "No summary metrics";
  }
  return entries.map(([key, value]) => `${key}: ${stringifyValue(value)}`).join(" · ");
}

export function groupBy<T, K extends string | number>(
  items: T[],
  keySelector: (item: T) => K,
): Record<K, T[]> {
  return items.reduce(
    (accumulator, item) => {
      const key = keySelector(item);
      accumulator[key] = [...(accumulator[key] || []), item];
      return accumulator;
    },
    {} as Record<K, T[]>,
  );
}
