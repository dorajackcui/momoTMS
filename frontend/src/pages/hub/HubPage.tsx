import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useAppShell } from "@/app/shell/AppShellContext";
import { createProject, deleteProject } from "@/domains/projects/api";
import type { CreateProjectInput, ProjectSummary } from "@/domains/projects/types";
import { queryKeys } from "@/shared/api/queryKeys";
import { buttonClassName, EmptyState, LoadingBlock } from "@/shared/ui/primitives";

import styles from "@/pages/hub/HubPage.module.css";

export function HubPage() {
  const shell = useAppShell();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ProjectSummary | null>(null);
  const [confirmName, setConfirmName] = useState("");

  const [name, setName] = useState("");
  const [translationCols, setTranslationCols] = useState("");
  const [remarkCols, setRemarkCols] = useState("");
  const [keyHeader, setKeyHeader] = useState("key");
  const [sourceHeader, setSourceHeader] = useState("MsgStr");
  const [pivotLang, setPivotLang] = useState("");
  const [pivotedLangs, setPivotedLangs] = useState("");

  const createMut = useMutation({
    mutationFn: () => {
      const payload: CreateProjectInput = {
        name,
        business_key_header: keyHeader.trim() || undefined,
        source_header: sourceHeader.trim() || undefined,
        translation_columns: translationCols.split(",").map((s) => s.trim()).filter(Boolean),
        remark_columns: remarkCols.split(",").map((s) => s.trim()).filter(Boolean),
        pivot_language: pivotLang.trim() || null,
        pivoted_languages: pivotedLangs.split(",").map((s) => s.trim()).filter(Boolean),
      };
      return createProject(payload);
    },
    onSuccess: async (project) => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.projects() });
      shell.setProjectId(project.project_id);
      navigate(shell.buildHref("/app/workspace", { project: project.project_id }));
    },
  });

  const deleteMut = useMutation({
    mutationFn: () => {
      if (!deleteTarget) throw new Error("no delete target");
      return deleteProject(deleteTarget.project_id, deleteTarget.name);
    },
    onSuccess: async () => {
      if (deleteTarget && shell.projectId === deleteTarget.project_id) {
        navigate(shell.buildHref("/app", { project: null }));
      }
      await queryClient.invalidateQueries({ queryKey: queryKeys.projects() });
      setDeleteTarget(null);
      setConfirmName("");
    },
  });

  function openDeleteDialog(e: React.MouseEvent, project: ProjectSummary) {
    e.stopPropagation();
    setDeleteTarget(project);
    setConfirmName("");
  }

  function closeDeleteDialog() {
    if (deleteMut.isPending) return;
    setDeleteTarget(null);
    setConfirmName("");
  }

  if (shell.projectsLoading) {
    return <LoadingBlock label="Loading projects..." />;
  }

  return (
    <div className={styles.hub}>
      <header className={styles.header}>
        <h1 className={styles.title}>Momo TMS</h1>
        <button className={buttonClassName("primary")} onClick={() => setShowCreate(true)}>
          + Create Project
        </button>
      </header>

      {showCreate && (
        <div className={styles.createForm}>
          <h2>Create Project</h2>
          <label>Project name <input value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label>Key column header <input value={keyHeader} onChange={(e) => setKeyHeader(e.target.value)} placeholder="key" /></label>
          <label>Source column header <input value={sourceHeader} onChange={(e) => setSourceHeader(e.target.value)} placeholder="MsgStr" /></label>
          <label>Translation columns (comma-separated) <input value={translationCols} onChange={(e) => setTranslationCols(e.target.value)} placeholder="zh-Hans, en, ja" /></label>
          <label>Remark columns (comma-separated) <input value={remarkCols} onChange={(e) => setRemarkCols(e.target.value)} placeholder="context, max_length" /></label>
          <label>Pivot language (optional) <input value={pivotLang} onChange={(e) => setPivotLang(e.target.value)} placeholder="zh-Hans" /></label>
          <label>Pivoted languages (comma-separated) <input value={pivotedLangs} onChange={(e) => setPivotedLangs(e.target.value)} placeholder="en, ja" /></label>
          <div className={styles.formActions}>
            <button className={buttonClassName("primary")} disabled={!name.trim() || !translationCols.trim() || createMut.isPending} onClick={() => createMut.mutate()}>
              {createMut.isPending ? "Creating..." : "Create"}
            </button>
            <button className={buttonClassName("ghost")} onClick={() => setShowCreate(false)}>Cancel</button>
          </div>
        </div>
      )}

      {shell.projects.length === 0 && !showCreate ? (
        <EmptyState title="No projects" body="Create a project to get started." />
      ) : (
        <div className={styles.cards}>
          {shell.projects.map((p) => (
            <button
              key={p.project_id}
              className={styles.card}
              onClick={() => {
                shell.setProjectId(p.project_id);
                navigate(shell.buildHref("/app/workspace", { project: p.project_id }));
              }}
            >
              <div className={styles.cardHeader}>
                <span className={styles.cardName}>{p.name}</span>
                <span
                  className={styles.deleteIconBtn}
                  role="button"
                  tabIndex={0}
                  title="Delete project"
                  onClick={(e) => openDeleteDialog(e, p)}
                  onKeyDown={(e) => { if (e.key === "Enter") openDeleteDialog(e as unknown as React.MouseEvent, p); }}
                >
                  ✕
                </span>
              </div>
              <span className={styles.cardMeta}>Created {p.created_at}</span>
            </button>
          ))}
        </div>
      )}

      {deleteTarget && (
        <div className={styles.confirmOverlay} onClick={closeDeleteDialog}>
          <div className={styles.confirmPanel} onClick={(e) => e.stopPropagation()}>
            <h3>Delete project</h3>
            <p className={styles.confirmWarning}>
              This will permanently delete <strong>{deleteTarget.name}</strong> and all its data. This action cannot be undone.
            </p>
            <label>
              Type <strong>{deleteTarget.name}</strong> to confirm
              <input
                value={confirmName}
                onChange={(e) => setConfirmName(e.target.value)}
                placeholder={deleteTarget.name}
                autoFocus
              />
            </label>
            <div className={styles.confirmActions}>
              <button className={buttonClassName("ghost")} onClick={closeDeleteDialog} disabled={deleteMut.isPending}>
                Cancel
              </button>
              <button
                className={buttonClassName("danger")}
                disabled={confirmName !== deleteTarget.name || deleteMut.isPending}
                onClick={() => deleteMut.mutate()}
              >
                {deleteMut.isPending ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
