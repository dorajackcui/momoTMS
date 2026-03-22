import type { AppRoute } from "./types";

export const PAGE_SIZE = 25;
export const PROJECT_STORAGE_KEY = "momo_tms_selected_project_id";
export const NAV_ITEMS: Array<{ route: AppRoute; label: string }> = [
  { route: "overview", label: "Branch Overview" },
  { route: "compare", label: "Branch Compare" },
  { route: "queue", label: "Translation Queue" },
  { route: "master", label: "Master Query" },
  { route: "imports", label: "Imports & Jobs" },
  { route: "inspection", label: "Inspection" },
];

export function parseRoute(pathname: string): AppRoute {
  if (pathname.startsWith("/app/projects/new")) {
    return "project-new";
  }
  if (pathname.startsWith("/app/compare")) {
    return "compare";
  }
  if (pathname.startsWith("/app/queue")) {
    return "queue";
  }
  if (pathname.startsWith("/app/master")) {
    return "master";
  }
  if (pathname.startsWith("/app/imports")) {
    return "imports";
  }
  if (pathname.startsWith("/app/inspection")) {
    return "inspection";
  }
  return "overview";
}

export function routePath(route: AppRoute): string {
  switch (route) {
    case "overview":
      return "/app/overview";
    case "compare":
      return "/app/compare";
    case "queue":
      return "/app/queue";
    case "master":
      return "/app/master";
    case "imports":
      return "/app/imports";
    case "inspection":
      return "/app/inspection";
    case "project-new":
      return "/app/projects/new";
  }
}

export function navigate(route: AppRoute, setter: (route: AppRoute) => void) {
  const nextPath = routePath(route);
  if (window.location.pathname !== nextPath) {
    window.history.pushState({}, "", nextPath);
  }
  setter(route);
}
