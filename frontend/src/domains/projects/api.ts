import { fetchJson } from "@/shared/api/http";

import type {
  CreateProjectInput,
  ProductStateResponse,
  ProjectSummary,
} from "@/domains/projects/types";

export function listProjects() {
  return fetchJson<ProjectSummary[]>("/api/projects");
}

export function createProject(payload: CreateProjectInput) {
  return fetchJson<ProjectSummary>("/api/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getProjectState(projectId: number) {
  return fetchJson<ProductStateResponse>(`/api/projects/${projectId}/state`);
}
