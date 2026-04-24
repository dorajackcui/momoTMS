import { useState, type ReactNode } from "react";
import { useMutation } from "@tanstack/react-query";

import { deleteBranchBusinessKeys, projectTrash } from "@/domains/branches/api";
import type { JobDetail } from "@/domains/jobs/types";
import { buttonClassName, InlineNotice } from "@/shared/ui/primitives";

import styles from "@/shared/ui/TrashPanel.module.css";

export type TrashPanelProps = {
  projectId: number;
  branchRef: string;
  showProjectTrash: boolean;
  onJobCreated: (job: JobDetail) => void;
};

type TrashPreview =
  | { operation: "unbind"; keys: string[] }
  | { operation: "project-trash"; keys: string[] };

export function TrashPanel(props: TrashPanelProps) {
  const { projectId, branchRef, showProjectTrash, onJobCreated } = props;

  const [unbindKeys, setUnbindKeys] = useState("");
  const [trashKeys, setTrashKeys] = useState("");
  const [preview, setPreview] = useState<TrashPreview | null>(null);

  const unbindMut = useMutation({
    mutationFn: () => {
      const keys = preview?.operation === "unbind" ? preview.keys : parseKeys(unbindKeys);
      return deleteBranchBusinessKeys(projectId, branchRef, keys);
    },
    onSuccess: (data) => {
      onJobCreated(data);
      setUnbindKeys("");
      setPreview(null);
    },
  });

  const trashMut = useMutation({
    mutationFn: () => {
      const keys = preview?.operation === "project-trash" ? preview.keys : parseKeys(trashKeys);
      return projectTrash(projectId, keys);
    },
    onSuccess: (data) => {
      onJobCreated(data);
      setTrashKeys("");
      setPreview(null);
    },
  });

  return (
    <div className={styles.panel}>
      <section className={styles.section}>
        <h3>Unbind from {branchRef}</h3>
        <p className={styles.hint}>Remove bindings from this branch. Variants with no remaining bindings become orphan.</p>
        <textarea
          className={styles.textarea}
          value={unbindKeys}
          onChange={(e) => { setUnbindKeys(e.target.value); setPreview(null); }}
          placeholder={"One business_key per line"}
          rows={6}
        />
        <button
          className={buttonClassName("secondary")}
          disabled={!unbindKeys.trim()}
          onClick={() => setPreview({ operation: "unbind", keys: parseKeys(unbindKeys) })}
        >
          Preview unbind
        </button>
        {preview?.operation === "unbind" && (
          <PreviewBlock
            title={`Ready to unbind ${preview.keys.length} key(s) from ${branchRef}`}
            keys={preview.keys}
            tone="info"
          >
            <button
              className={buttonClassName("primary")}
              disabled={unbindMut.isPending}
              onClick={() => unbindMut.mutate()}
            >
              {unbindMut.isPending ? "Unbinding..." : "Execute unbind"}
            </button>
          </PreviewBlock>
        )}
        {unbindMut.isError && <InlineNotice tone="error">{String(unbindMut.error)}</InlineNotice>}
      </section>

      {showProjectTrash && (
        <section className={styles.section}>
          <h3>Project Trash</h3>
          <InlineNotice tone="warning" title="Irreversible">
            Trashed variants cannot be restored. Only orphan variants (zero bindings) will be trashed.
          </InlineNotice>
          <textarea
            className={styles.textarea}
            value={trashKeys}
            onChange={(e) => { setTrashKeys(e.target.value); setPreview(null); }}
            placeholder={"One business_key per line"}
            rows={6}
          />
          <button
            className={buttonClassName("danger")}
            disabled={!trashKeys.trim()}
            onClick={() => setPreview({ operation: "project-trash", keys: parseKeys(trashKeys) })}
          >
            Preview project trash
          </button>
          {preview?.operation === "project-trash" && (
            <PreviewBlock
              title={`Ready to permanently trash orphan variants for ${preview.keys.length} key(s)`}
              keys={preview.keys}
              tone="warning"
            >
              <button
                className={buttonClassName("danger")}
                disabled={trashMut.isPending}
                onClick={() => trashMut.mutate()}
              >
                {trashMut.isPending ? "Trashing..." : "Execute permanent trash"}
              </button>
            </PreviewBlock>
          )}
          {trashMut.isError && <InlineNotice tone="error">{String(trashMut.error)}</InlineNotice>}
        </section>
      )}
    </div>
  );
}

function parseKeys(text: string): string[] {
  return text.split("\n").map((l) => l.trim()).filter(Boolean);
}

function PreviewBlock(props: {
  title: string;
  keys: string[];
  tone: "info" | "warning";
  children: ReactNode;
}) {
  return (
    <div className={styles.preview}>
      <InlineNotice tone={props.tone} title="Preview">
        {props.title}
      </InlineNotice>
      <ul className={styles.keyList}>
        {props.keys.slice(0, 20).map((key) => <li key={key}>{key}</li>)}
      </ul>
      {props.keys.length > 20 && <p className={styles.hint}>Showing first 20 keys.</p>}
      {props.children}
    </div>
  );
}
