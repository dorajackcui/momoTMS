import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { useAppShell } from "@/app/shell/AppShellContext";
import { getEntryVariants, restoreVariants } from "@/domains/variants/api";
import { invalidateProjectScope, queryKeys } from "@/shared/api/queryKeys";
import { formatTimestamp } from "@/shared/lib/format";
import {
  Badge,
  EmptyState,
  InlineNotice,
  KeyValueList,
  LoadingBlock,
  buttonClassName,
} from "@/shared/ui/primitives";

import styles from "@/features/variant-drawer/VariantDrawer.module.css";

export function VariantDrawer(props: {
  projectId: number | null;
  businessKey: string | null;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const shell = useAppShell();

  const entryQuery = useQuery({
    queryKey:
      props.projectId && props.businessKey
        ? queryKeys.entryVariants(props.projectId, props.businessKey)
        : ["entry-variants", "idle"],
    queryFn: () => getEntryVariants(props.projectId!, props.businessKey!),
    enabled: props.projectId !== null && Boolean(props.businessKey),
  });

  const restoreMutation = useMutation({
    mutationFn: (variantIds: number[]) => restoreVariants(props.projectId!, variantIds),
    onSuccess: async (detail) => {
      if (!props.projectId || !props.businessKey) {
        return;
      }
      await invalidateProjectScope(queryClient, props.projectId, {
        businessKey: props.businessKey,
      });
      shell.notify(`Restore job #${detail.job.job_id} completed.`, "success");
      shell.setJobId(detail.job.job_id);
      navigate(shell.buildHref("/app/runs", { job: detail.job.job_id }));
    },
    onError: (error) => {
      shell.notify(error instanceof Error ? error.message : "Restore failed.", "error");
    },
  });

  if (!props.projectId || !props.businessKey) {
    return null;
  }

  return (
    <div className={styles.overlay}>
      <aside className={styles.panel}>
        <div className={styles.top}>
          <div>
            <p>Variant history</p>
            <h2>{props.businessKey}</h2>
          </div>
          <button className={buttonClassName("ghost")} onClick={props.onClose}>
            Close
          </button>
        </div>

        {entryQuery.isLoading ? <LoadingBlock label="Loading variant history..." /> : null}
        {entryQuery.isError ? (
          <InlineNotice tone="error" title="Failed to load history">
            {entryQuery.error instanceof Error
              ? entryQuery.error.message
              : "Request failed."}
          </InlineNotice>
        ) : null}

        {entryQuery.data ? (
          <div className={styles.stack}>
            {entryQuery.data.variants.length === 0 ? (
              <EmptyState
                title="No variants found"
                body="This business key has no recorded variants in the current project."
              />
            ) : null}
            {entryQuery.data.variants.map((variant) => (
              <article key={variant.variant_id} className={styles.variantCard}>
                <div className={styles.top}>
                  <div>
                    <strong>variant #{variant.variant_id}</strong>
                    <p className={styles.meta}>{variant.file_name || "No file name"}</p>
                  </div>
                  <div className={styles.toolbar}>
                    {variant.is_orphaned ? <Badge tone="warning">orphan</Badge> : null}
                    {variant.is_trashed ? <Badge tone="danger">trashed</Badge> : null}
                    {!variant.is_trashed ? <Badge tone="accent">active history</Badge> : null}
                  </div>
                </div>
                <KeyValueList
                  items={[
                    ["source", variant.source],
                    ["created_at", formatTimestamp(variant.created_at)],
                    ["updated_at", formatTimestamp(variant.updated_at)],
                    ["orphaned_at", formatTimestamp(variant.orphaned_at)],
                    ["trashed_at", formatTimestamp(variant.trashed_at)],
                    ["restored_at", formatTimestamp(variant.restored_at)],
                  ]}
                />
                <KeyValueList
                  items={Object.entries(variant.translations).map(([key, value]) => [
                    `translation · ${key}`,
                    value || "-",
                  ])}
                />
                <KeyValueList
                  items={Object.entries(variant.remarks).map(([key, value]) => [
                    `remark · ${key}`,
                    value || "-",
                  ])}
                />
                <KeyValueList
                  items={
                    variant.bindings.length > 0
                      ? variant.bindings.map((binding) => [
                          binding.branch_ref,
                          formatTimestamp(binding.updated_at),
                        ])
                      : [["bindings", "No active bindings"]]
                  }
                />
                {variant.is_trashed ? (
                  <div className={styles.toolbar}>
                    <button
                      className={buttonClassName("primary")}
                      disabled={restoreMutation.isPending}
                      onClick={() => restoreMutation.mutate([variant.variant_id])}
                    >
                      Restore this variant
                    </button>
                  </div>
                ) : null}
              </article>
            ))}
          </div>
        ) : null}
      </aside>
    </div>
  );
}
