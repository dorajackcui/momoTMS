export class ApiError extends Error {
  status: number;
  detail: string;
  payload: unknown;

  constructor(status: number, detail: string, payload: unknown) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.payload = payload;
  }
}

type QueryValue =
  | string
  | number
  | boolean
  | null
  | undefined
  | Array<string | number | boolean>;

export function buildQueryString(
  values: Record<string, QueryValue>,
): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    if (Array.isArray(value)) {
      for (const item of value) {
        params.append(key, String(item));
      }
      continue;
    }
    params.set(key, String(value));
  }
  return params.toString();
}

export async function fetchJson<T>(
  url: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(url, {
    headers:
      options.body && !(options.body instanceof FormData)
        ? {
            "Content-Type": "application/json",
            ...(options.headers || {}),
          }
        : options.headers,
    ...options,
  });

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      payload = await response.text().catch(() => null);
    }
    const detail =
      typeof payload === "object" &&
      payload !== null &&
      "detail" in payload &&
      typeof (payload as { detail?: unknown }).detail === "string"
        ? String((payload as { detail: string }).detail)
        : `Request failed with ${response.status}`;
    throw new ApiError(response.status, detail, payload);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function postFolderForm<T>(
  url: string,
  files: File[],
  extraFields: Record<string, string | number | boolean | undefined> = {},
): Promise<T> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file, file.name);
    form.append(
      "relative_paths",
      (file as File & { webkitRelativePath?: string }).webkitRelativePath ||
        file.name,
    );
  }
  for (const [key, value] of Object.entries(extraFields)) {
    if (value === undefined) {
      continue;
    }
    form.append(key, String(value));
  }
  return fetchJson<T>(url, { method: "POST", body: form });
}
