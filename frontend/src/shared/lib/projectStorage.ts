export const PROJECT_STORAGE_KEY = "momo_tms_selected_project_id";

export function getStoredProjectId(): number | null {
  const raw = window.localStorage.getItem(PROJECT_STORAGE_KEY);
  if (!raw) {
    return null;
  }
  const parsed = Number(raw);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

export function setStoredProjectId(projectId: number) {
  window.localStorage.setItem(PROJECT_STORAGE_KEY, String(projectId));
}

export function clearStoredProjectId() {
  window.localStorage.removeItem(PROJECT_STORAGE_KEY);
}
