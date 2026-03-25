import { useState } from "react";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { useAppShell } from "@/app/shell/AppShellContext";
import { createProject } from "@/domains/projects/api";
import { queryKeys } from "@/shared/api/queryKeys";
import {
  Badge,
  EmptyState,
  InlineNotice,
  KeyValueList,
  Panel,
  StatGrid,
  buttonClassName,
  ui,
} from "@/shared/ui/primitives";
import { formatNumber } from "@/shared/lib/format";

import styles from "@/pages/project/ProjectPage.module.css";

export function ProjectPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const shell = useAppShell();
  const [name, setName] = useState("");
  const [translationColumns, setTranslationColumns] = useState("fr, en");
  const [remarkColumns, setRemarkColumns] = useState("context");

  const createMutation = useMutation({
    mutationFn: () =>
      createProject({
        name: name.trim(),
        translation_columns: splitColumns(translationColumns),
        remark_columns: splitColumns(remarkColumns),
      }),
    onSuccess: async (project) => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.projects() });
      shell.setProjectId(project.project_id);
      shell.notify(`Project ${project.name} created.`, "success");
      navigate(shell.buildHref("/app/overview", { project: project.project_id }));
    },
    onError: (error) => {
      shell.notify(error instanceof Error ? error.message : "Create project failed.", "error");
    },
  });

  const currentProject = shell.bootstrap?.project || null;

  return (
    <div className={styles.layout}>
      <Panel
        kicker="Project"
        title={currentProject ? currentProject.name : "Project bootstrap"}
        description="Project-level schema, release summary, active dev branches, and project creation live together here."
        testId="project-page"
      >
        {shell.bootstrap ? (
          <StatGrid
            items={[
              {
                label: "translations",
                value: formatNumber(shell.bootstrap.schema.translation_columns.length),
                hint: shell.bootstrap.schema.translation_columns.join(", ") || "-",
              },
              {
                label: "remarks",
                value: formatNumber(shell.bootstrap.schema.remark_columns.length),
                hint: shell.bootstrap.schema.remark_columns.join(", ") || "-",
              },
              {
                label: "dev branches",
                value: formatNumber(shell.bootstrap.dev_branches.length),
                hint: shell.bootstrap.candidate_dev_branch
                  ? `candidate: ${shell.bootstrap.candidate_dev_branch.branch_ref}`
                  : "no candidate release",
              },
            ]}
          />
        ) : (
          <EmptyState
            title="No active project yet"
            body="Create the first project to define the fixed schema for import, overview, branch operations, runs, and variants."
          />
        )}
      </Panel>

      <div className={styles.grid}>
        <Panel
          kicker="Current Runtime"
          title="Schema and release context"
          description="Project creation stays minimal: name, translation columns, and remark columns only."
        >
          {shell.bootstrap ? (
            <div className={styles.stack}>
              <KeyValueList
                items={[
                  ["project_id", shell.bootstrap.project.project_id],
                  [
                    "translation columns",
                    shell.bootstrap.schema.translation_columns.join(", ") || "-",
                  ],
                  [
                    "remark columns",
                    shell.bootstrap.schema.remark_columns.join(", ") || "-",
                  ],
                  [
                    "candidate dev branch",
                    shell.bootstrap.candidate_dev_branch?.branch_ref || "-",
                  ],
                ]}
              />
              <div className={styles.branchList}>
                {shell.bootstrap.dev_branches.map((branch) => (
                  <article key={branch.branch_ref} className={styles.branchCard}>
                    <div>
                      <strong>{branch.branch_ref}</strong>{" "}
                      {branch.is_candidate_release ? (
                        <Badge tone="accent">candidate</Badge>
                      ) : null}
                    </div>
                    <span className={styles.meta}>
                      version series: {branch.version_series}
                    </span>
                    <span className={styles.meta}>entries: {branch.entry_count}</span>
                  </article>
                ))}
                {shell.bootstrap.dev_branches.length === 0 ? (
                  <EmptyState
                    title="No dev branches yet"
                    body="Create an import batch and apply it in Branch Ops to populate dev branches."
                  />
                ) : null}
              </div>
            </div>
          ) : (
            <InlineNotice tone="info" title="Project creation mode">
              No project exists yet, so this page is acting as the entrypoint to create the first schema.
            </InlineNotice>
          )}
        </Panel>

        <Panel
          kicker="Create Project"
          title="Define the fixed schema"
          description="No schema-edit compatibility work is introduced here. The project template stays fixed after creation."
        >
          <label className={ui.field}>
            <span className={ui.fieldLabel}>Project name</span>
            <input className={ui.input} value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label className={ui.field}>
            <span className={ui.fieldLabel}>Translation columns</span>
            <input
              className={ui.input}
              value={translationColumns}
              onChange={(event) => setTranslationColumns(event.target.value)}
              placeholder="fr, en"
            />
          </label>
          <label className={ui.field}>
            <span className={ui.fieldLabel}>Remark columns</span>
            <input
              className={ui.input}
              value={remarkColumns}
              onChange={(event) => setRemarkColumns(event.target.value)}
              placeholder="context"
            />
          </label>
          <button
            className={buttonClassName("primary")}
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending}
            data-testid="project-create-button"
          >
            Create project
          </button>
        </Panel>
      </div>
    </div>
  );
}

function splitColumns(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
