import { useState } from "react";

import { useAppShell } from "@/app/shell/AppShellContext";
import { buttonClassName } from "@/shared/ui/primitives";
import { CreateBranch } from "@/pages/dev/CreateBranch";
import { BranchDetail } from "@/pages/dev/BranchDetail";
import { ImportBatches } from "@/pages/dev/ImportBatches";

import styles from "@/pages/dev/DevPage.module.css";

type DevView =
  | { kind: "list" }
  | { kind: "create" }
  | { kind: "batches" }
  | { kind: "detail"; version: string };

export function DevPage() {
  const shell = useAppShell();
  const projectId = shell.projectId!;
  const devBranches = shell.bootstrap?.dev_branches ?? [];

  const [view, setView] = useState<DevView>({ kind: "list" });

  if (view.kind === "create") {
    return (
      <CreateBranch
        projectId={projectId}
        lang={shell.lang}
        onBack={() => setView({ kind: "list" })}
        onCreated={(version) => {
          shell.refreshShell();
          setView({ kind: "detail", version });
        }}
      />
    );
  }

  if (view.kind === "batches") {
    return (
      <ImportBatches
        projectId={projectId}
        onBack={() => setView({ kind: "list" })}
      />
    );
  }

  if (view.kind === "detail") {
    return (
      <BranchDetail
        projectId={projectId}
        version={view.version}
        onBack={() => setView({ kind: "list" })}
      />
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.actions}>
        <button className={buttonClassName("primary")} onClick={() => setView({ kind: "create" })}>
          + Create Branch
        </button>
        <button className={buttonClassName("secondary")} onClick={() => setView({ kind: "batches" })}>
          Import Batches
        </button>
      </div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Branch</th>
            <th>Status</th>
            <th>Entries</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {devBranches.length === 0 ? (
            <tr><td colSpan={4}>No dev branches yet</td></tr>
          ) : (
            devBranches.map((b) => (
              <tr key={b.version}>
                <td>{b.branch_ref}</td>
                <td>{b.bootstrap_state}</td>
                <td>{b.entry_count}</td>
                <td>
                  <button className={buttonClassName("ghost")} onClick={() => setView({ kind: "detail", version: b.version })}>
                    Open
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
