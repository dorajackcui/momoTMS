import { createContext, useContext } from "react";

import type { BranchListResponse } from "@/domains/branches/types";
import type { ProductStateResponse, ProjectSummary } from "@/domains/projects/types";

export type NoticeTone = "info" | "success" | "warning" | "error";

export type AppNotice = {
  message: string;
  tone: NoticeTone;
} | null;

export type AppShellContextValue = {
  projects: ProjectSummary[];
  projectId: number | null;
  lang: string;
  branchRef: string | null;
  tab: string | null;
  jobId: number | null;
  businessKey: string | null;
  hasProjects: boolean;
  bootstrap: ProductStateResponse | null;
  branchSummary: BranchListResponse | null;
  projectsLoading: boolean;
  shellLoading: boolean;
  shellError: string | null;
  notice: AppNotice;
  buildHref: (
    pathname: string,
    patch?: Record<string, string | number | boolean | null | undefined>,
  ) => { pathname: string; search: string };
  setProjectId: (projectId: number) => void;
  setLang: (lang: string) => void;
  setBranchRef: (branchRef: string | null) => void;
  setTab: (tab: string | null) => void;
  setJobId: (jobId: number | null) => void;
  setBusinessKey: (businessKey: string | null) => void;
  notify: (message: string, tone?: NoticeTone) => void;
  clearNotice: () => void;
  refreshShell: () => Promise<void>;
};

const AppShellContext = createContext<AppShellContextValue | null>(null);

export function AppShellProvider(props: {
  value: AppShellContextValue;
  children: React.ReactNode;
}) {
  return (
    <AppShellContext.Provider value={props.value}>
      {props.children}
    </AppShellContext.Provider>
  );
}

export function useAppShell() {
  const value = useContext(AppShellContext);
  if (!value) {
    throw new Error("useAppShell must be used within AppShellProvider");
  }
  return value;
}
