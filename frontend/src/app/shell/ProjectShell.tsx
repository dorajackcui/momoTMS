import { NavLink, Outlet } from "react-router-dom";

import { useAppShell } from "@/app/shell/AppShellContext";
import { LoadingBlock, InlineNotice } from "@/shared/ui/primitives";

import styles from "@/app/shell/ProjectShell.module.css";

const tabs = [
  { to: "/app/workspace", label: "Workspace" },
  { to: "/app/release", label: "Release" },
  { to: "/app/dev", label: "Dev" },
  { to: "/app/runs", label: "Runs" },
] as const;

export function ProjectShell() {
  const shell = useAppShell();

  if (!shell.projectId) {
    return null;
  }

  const projectName = shell.bootstrap?.project.name ?? `Project #${shell.projectId}`;

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <NavLink to={shell.buildHref("/app")} className={styles.backLink}>
            ← Hub
          </NavLink>
          <span className={styles.projectName}>{projectName}</span>
          {shell.bootstrap?.schema && (
            <details className={styles.schemaPopover}>
              <summary className={styles.infoIcon} title="Project schema">ⓘ</summary>
              <div className={styles.schemaContent}>
                <p><strong>Translations:</strong> {shell.bootstrap.schema.translation_columns.join(", ")}</p>
                <p><strong>Remarks:</strong> {shell.bootstrap.schema.remark_columns.join(", ") || "none"}</p>
                {shell.bootstrap.schema.pivot_language && (
                  <p><strong>Pivot:</strong> {shell.bootstrap.schema.pivot_language} → {shell.bootstrap.schema.pivoted_languages.join(", ")}</p>
                )}
              </div>
            </details>
          )}
        </div>
        <nav className={styles.tabs}>
          {tabs.map((tab) => (
            <NavLink
              key={tab.to}
              to={shell.buildHref(tab.to)}
              className={({ isActive }) =>
                `${styles.tab} ${isActive ? styles.tabActive : ""}`
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
      </header>

      {shell.notice && (
        <InlineNotice tone={shell.notice.tone}>
          {shell.notice.message}
          <button onClick={shell.clearNotice}>×</button>
        </InlineNotice>
      )}

      {shell.shellLoading ? (
        <LoadingBlock label="Loading project..." />
      ) : shell.shellError ? (
        <InlineNotice tone="error">{shell.shellError}</InlineNotice>
      ) : (
        <main className={styles.content}>
          <Outlet />
        </main>
      )}
    </div>
  );
}
