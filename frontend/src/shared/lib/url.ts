export type SearchPatch = Record<
  string,
  string | number | boolean | null | undefined
>;

export function parsePositiveInt(value: string | null): number | null {
  if (!value) {
    return null;
  }
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

export function normalizeText(value: string | null): string | null {
  const normalized = value?.trim();
  return normalized ? normalized : null;
}

export function applySearchPatch(
  current: URLSearchParams,
  patch: SearchPatch,
): URLSearchParams {
  const next = new URLSearchParams(current);
  for (const [key, value] of Object.entries(patch)) {
    if (value === undefined || value === null || value === "") {
      next.delete(key);
      continue;
    }
    next.set(key, String(value));
  }
  return next;
}
