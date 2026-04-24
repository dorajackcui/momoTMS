import { useState } from "react";
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

export function TrashPanel(props: TrashPanelProps) {
  const { projectId, branchRef, showProjectTrash, onJobCreated } = props;

  const [unbindKeys, setUnbindKeys] = useState("");
  const [trashKeys, setTrashKeys] = useState("");

  const unbindMut = useMutation({
    mutationFn: () => {
      const keys = parseKeys(unbindKeys);
      return deleteBranchBusinessKeys(projectId, branchRef, keys);
    },
    onSuccess: (data) => {
      onJobCreated(data);
      setUnbindKeys("");
    },
  });

  const trashMut = useMutation({
    mutationFn: () => {
      const keys = parseKeys(trashKeys);
      return projectTrash(projectId, keys);
    },
    onSuccess: (data) => {
      onJobCreated(data);
      setTrashKeys("");
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
          onChange={(e) => setUnbindKeys(e.target.value)}
          placeholder={"One business_key per line"}
          rows={6}
        />
        <button
          className={buttonClassName("secondary")}
          disabled={!unbindKeys.trim() || unbindMut.isPending}
          onClick={() => unbindMut.mutate()}
        >
          {unbindMut.isPending ? "Unbinding..." : "Unbind"}
        </button>
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
            onChange={(e) => setTrashKeys(e.target.value)}
            placeholder={"One business_key per line"}
            rows={6}
          />
          <button
            className={buttonClassName("danger")}
            disabled={!trashKeys.trim() || trashMut.isPending}
            onClick={() => trashMut.mutate()}
          >
            {trashMut.isPending ? "Trashing..." : "Trash permanently"}
          </button>
          {trashMut.isError && <InlineNotice tone="error">{String(trashMut.error)}</InlineNotice>}
        </section>
      )}
    </div>
  );
}

function parseKeys(text: string): string[] {
  return text.split("\n").map((l) => l.trim()).filter(Boolean);
}
