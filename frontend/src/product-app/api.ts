export async function fetchJson<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    headers:
      options.body && !(options.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : undefined,
    ...options,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(payload.detail || "Request failed");
  }
  return response.json() as Promise<T>;
}

export async function postFolderForm<T>(
  url: string,
  files: File[],
  extraFields: Record<string, string> = {},
): Promise<T> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file, file.name);
    form.append(
      "relative_paths",
      (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name,
    );
  }
  Object.entries(extraFields).forEach(([key, value]) => form.append(key, value));
  return fetchJson<T>(url, { method: "POST", body: form });
}
