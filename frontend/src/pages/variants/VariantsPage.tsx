import { useEffect, useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { useAppShell } from "@/app/shell/AppShellContext";
import { getEntryVariants, getProjectVariants, restoreVariants } from "@/domains/variants/api";
import { invalidateProjectScope, queryKeys } from "@/shared/api/queryKeys";
import { cx } from "@/shared/lib/cx";
import { formatTimestamp } from "@/shared/lib/format";
import {
  Badge,
  EmptyState,
  InlineNotice,
  KeyValueList,
  Panel,
  buttonClassName,
  ui,
} from "@/shared/ui/primitives";

import styles from "@/pages/variants/VariantsPage.module.css";

export function VariantsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const shell = useAppShell();
  const [lookupKey, setLookupKey] = useState(shell.businessKey || "");

  useEffect(() => {
    setLookupKey(shell.businessKey || "");
  }, [shell.businessKey]);

  const orphanQuery = useQuery({
    queryKey:
      shell.projectId !== null
        ? queryKeys.projectVariants(shell.projectId, {
            state: "orphan",
          })
        : ["project-variants", "idle"],
    queryFn: () =>
      getProjectVariants(shell.projectId!, {
        state: "orphan",
      }),
    enabled: shell.projectId !== null,
  });

  const entryQuery = useQuery({
    queryKey:
      shell.projectId && shell.businessKey
        ? queryKeys.entryVariants(shell.projectId, shell.businessKey)
        : ["entry-variants", "idle"],
    queryFn: () => getEntryVariants(shell.projectId!, shell.businessKey!),
    enabled: Boolean(shell.projectId && shell.businessKey),
  });

  const restoreMutation = useMutation({
    mutationFn: (variantIds: number[]) => restoreVariants(shell.projectId!, variantIds),
    onSuccess: async (detail) => {
      if (!shell.projectId) {
        return;
      }
      await invalidateProjectScope(queryClient, shell.projectId, {
        businessKey: shell.businessKey,
      });
      shell.notify(`Restore job #${detail.job.job_id} completed.`, "success");
      navigate(shell.buildHref("/app/runs", { job: detail.job.job_id }));
    },
    onError: (error) => {
      shell.notify(error instanceof Error ? error.message : "Restore failed.", "error");
    },
  });

  if (!shell.hasProjects || !shell.projectId) {
    return (
      <Panel kicker="Variants" title="Variant explorer">
        <EmptyState
          title="No project selected"
          body="Variants become explorable once a project exists and the shell has a project-scoped context."
        />
      </Panel>
    );
  }

  return (
    <div className={styles.layout}>
      <Panel
        kicker="Variants"
        title="Variant Explorer"
        description="Use orphan history and business-key lookup to inspect full variant timelines. The global drawer stays in sync with `business_key` URL state."
      >
        <label className={ui.field}>
          <span className={ui.fieldLabel}>Business key lookup</span>
          <input
            className={ui.input}
            value={lookupKey}
            onChange={(event) => setLookupKey(event.target.value)}
            placeholder="common.welcome"
          />
        </label>
        <div className={ui.toolbar}>
          <button
            className={buttonClassName("primary")}
            onClick={() => shell.setBusinessKey(lookupKey.trim() || null)}
            data-testid="variants-lookup-button"
          >
            Inspect key
          </button>
        </div>
        {orphanQuery.isError ? (
          <InlineNotice tone="error" title="Failed to load orphan variants">
            {orphanQuery.error instanceof Error ? orphanQuery.error.message : "Request failed."}
          </InlineNotice>
        ) : null}
        {orphanQuery.data?.rows.length ? (
          <div className={styles.stack} data-testid="variants-orphan-list">
            {orphanQuery.data.rows.map((item) => (
              <button
                key={item.variant_id}
                className={cx(
                  styles.listButton,
                  shell.businessKey === item.business_key && styles.listButtonActive,
                )}
                onClick={() => shell.setBusinessKey(item.business_key)}
              >
                <strong>{item.business_key}</strong>
                <span className={styles.meta}>{item.file_name || "-"}</span>
                <span className={styles.meta}>{formatTimestamp(item.orphaned_at)}</span>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No orphan variants"
            body="This project currently has no orphaned variant records."
          />
        )}
      </Panel>

      <Panel
        kicker="Timeline"
        title={shell.businessKey || "Variant timeline"}
        description="History stays read-heavy here, and the timeline is driven directly by `business_key` URL state."
        testId="variants-page"
      >
        {entryQuery.isError ? (
          <InlineNotice tone="error" title="Failed to load variant timeline">
            {entryQuery.error instanceof Error ? entryQuery.error.message : "Request failed."}
          </InlineNotice>
        ) : null}
        {entryQuery.data ? (
          entryQuery.data.variants.length > 0 ? (
            <div className={styles.timeline}>
              {entryQuery.data.variants.map((variant) => (
                <article key={variant.variant_id} className={styles.card}>
                  <div className={styles.top}>
                    <div>
                      <strong>variant #{variant.variant_id}</strong>
                      <p className={styles.meta}>{variant.file_name || "No file name"}</p>
                    </div>
                    <div className={styles.toolbar}>
                      {variant.is_orphaned ? <Badge tone="warning">orphan</Badge> : null}
                      {variant.is_trashed ? <Badge tone="danger">trashed</Badge> : null}
                    </div>
                  </div>
                  <KeyValueList
                    items={[
                      ["source", variant.source],
                      ["created_at", formatTimestamp(variant.created_at)],
                      ["updated_at", formatTimestamp(variant.updated_at)],
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
                  <div className={styles.toolbar}>
                    <button
                      className={buttonClassName("ghost")}
                      onClick={() => shell.setBusinessKey(entryQuery.data.business_key)}
                    >
                      Keep this key selected
                    </button>
                    {variant.is_trashed ? (
                      <button
                        className={buttonClassName("primary")}
                        onClick={() => restoreMutation.mutate([variant.variant_id])}
                        disabled={restoreMutation.isPending}
                      >
                        Restore variant
                      </button>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No variants found"
              body="The selected business key exists in URL state, but no variant history was returned for it."
            />
          )
        ) : (
          <EmptyState
            title="Choose a business key"
            body="Use the lookup field or pick an orphan variant on the left to populate the timeline."
          />
        )}
      </Panel>
    </div>
  );
}
