import { useEffect, useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { useAppShell } from "@/app/shell/AppShellContext";
import {
  getEntryVariants,
  getProjectVariants,
  restoreVariants,
  reviewPivotVariants,
} from "@/domains/variants/api";
import type { PivotStatus } from "@/domains/variants/types";
import { invalidateProject, queryKeys } from "@/shared/api/queryKeys";
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

const ALL_BRANCHES = "__all__";
const ALL_OWNERS = "__all__";
const ALL_PIVOT_STATUSES = "__all__";

export function VariantsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const shell = useAppShell();
  const [lookupKey, setLookupKey] = useState(shell.businessKey || "");
  const [stateFilter, setStateFilter] = useState<"active" | "orphan" | "all">("all");
  const [branchFilter, setBranchFilter] = useState(shell.branchRef || ALL_BRANCHES);
  const [pivotStatusFilter, setPivotStatusFilter] = useState<PivotStatus | typeof ALL_PIVOT_STATUSES>(
    ALL_PIVOT_STATUSES,
  );
  const [ownerFilter, setOwnerFilter] = useState<string>(ALL_OWNERS);
  const [selectedVariantIds, setSelectedVariantIds] = useState<number[]>([]);

  useEffect(() => {
    setLookupKey(shell.businessKey || "");
  }, [shell.businessKey]);

  useEffect(() => {
    if (shell.branchRef) {
      setBranchFilter(shell.branchRef);
    }
  }, [shell.branchRef]);

  const branchOptions = Array.from(
    new Set([
      "rel/current",
      ...(shell.bootstrap?.dev_branches || []).map((branch) => branch.branch_ref),
      ...(shell.branchSummary?.branches || []).map((branch) => branch.branch_ref),
    ]),
  );

  const variantsQuery = useQuery({
    queryKey:
      shell.projectId !== null
        ? queryKeys.projectVariants(shell.projectId, {
            state: stateFilter,
            branch_ref: branchFilter === ALL_BRANCHES ? undefined : [branchFilter],
            pivot_status:
              pivotStatusFilter === ALL_PIVOT_STATUSES ? undefined : pivotStatusFilter,
            pivot_changed_by_branch_ref:
              ownerFilter === ALL_OWNERS ? undefined : ownerFilter,
          })
        : ["project-variants", "idle"],
    queryFn: () =>
      getProjectVariants(shell.projectId!, {
        state: stateFilter,
        branch_ref: branchFilter === ALL_BRANCHES ? undefined : [branchFilter],
        pivot_status:
          pivotStatusFilter === ALL_PIVOT_STATUSES ? undefined : pivotStatusFilter,
        pivot_changed_by_branch_ref:
          ownerFilter === ALL_OWNERS ? undefined : ownerFilter,
      }),
    enabled: shell.projectId !== null,
  });

  useEffect(() => {
    setSelectedVariantIds((current) =>
      current.filter((variantId) =>
        variantsQuery.data?.rows.some((row) => row.variant_id === variantId),
      ),
    );
  }, [variantsQuery.data]);

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
      await invalidateProject(queryClient, shell.projectId, {
        businessKey: shell.businessKey,
      });
      shell.notify(`Restore job #${detail.job.job_id} completed.`, "success");
      navigate(shell.buildHref("/app/runs", { job: detail.job.job_id }));
    },
    onError: (error) => {
      shell.notify(error instanceof Error ? error.message : "Restore failed.", "error");
    },
  });

  const reviewMutation = useMutation({
    mutationFn: (variantIds: number[]) =>
      reviewPivotVariants(shell.projectId!, branchFilter, variantIds),
    onSuccess: async (detail) => {
      if (!shell.projectId) {
        return;
      }
      setSelectedVariantIds([]);
      await invalidateProject(queryClient, shell.projectId, {
        businessKey: shell.businessKey,
      });
      shell.notify(`Pivot review job #${detail.job.job_id} completed.`, "success");
      navigate(shell.buildHref("/app/runs", { job: detail.job.job_id }));
    },
    onError: (error) => {
      shell.notify(error instanceof Error ? error.message : "Pivot review failed.", "error");
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
        title="Pivot Review Workspace"
        description="Filter project variants by lifecycle, branch, pivot status, and owner; then review changed items in one branch-scoped pass."
      >
        <div className={styles.filters}>
          <label className={ui.field}>
            <span className={ui.fieldLabel}>Business key lookup</span>
            <input
              className={ui.input}
              value={lookupKey}
              onChange={(event) => setLookupKey(event.target.value)}
              placeholder="common.welcome"
            />
          </label>
          <label className={ui.field}>
            <span className={ui.fieldLabel}>State</span>
            <select
              className={ui.select}
              value={stateFilter}
              onChange={(event) =>
                setStateFilter(event.target.value as "active" | "orphan" | "all")
              }
            >
              <option value="active">Active only</option>
              <option value="all">Active + orphan</option>
              <option value="orphan">Orphan only</option>
            </select>
          </label>
          <label className={ui.field}>
            <span className={ui.fieldLabel}>Branch filter</span>
            <select
              className={ui.select}
              value={branchFilter}
              onChange={(event) => setBranchFilter(event.target.value)}
            >
              <option value={ALL_BRANCHES}>All branches</option>
              {branchOptions.map((branch) => (
                <option key={branch} value={branch}>
                  {branch}
                </option>
              ))}
            </select>
          </label>
          <label className={ui.field}>
            <span className={ui.fieldLabel}>Pivot status</span>
            <select
              className={ui.select}
              value={pivotStatusFilter}
              onChange={(event) =>
                setPivotStatusFilter(
                  event.target.value as PivotStatus | typeof ALL_PIVOT_STATUSES,
                )
              }
            >
              <option value={ALL_PIVOT_STATUSES}>All statuses</option>
              <option value="init">init</option>
              <option value="changed">changed</option>
              <option value="reviewed">reviewed</option>
            </select>
          </label>
          <label className={ui.field}>
            <span className={ui.fieldLabel}>Changed owner</span>
            <select
              className={ui.select}
              value={ownerFilter}
              onChange={(event) => setOwnerFilter(event.target.value)}
            >
              <option value={ALL_OWNERS}>Any owner</option>
              {branchOptions.map((branch) => (
                <option key={branch} value={branch}>
                  {branch}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className={ui.toolbar}>
          <button
            className={buttonClassName("primary")}
            onClick={() => shell.setBusinessKey(lookupKey.trim() || null)}
            data-testid="variants-lookup-button"
          >
            Inspect key
          </button>
          <button
            className={buttonClassName("secondary")}
            onClick={() =>
              setSelectedVariantIds(
                (variantsQuery.data?.rows || [])
                  .filter((row) => row.pivot_status === "changed")
                  .map((row) => row.variant_id),
              )
            }
            disabled={!variantsQuery.data?.rows.length}
          >
            Select changed
          </button>
          <button
            className={buttonClassName("ghost")}
            onClick={() => setSelectedVariantIds([])}
            disabled={selectedVariantIds.length === 0}
          >
            Clear selection
          </button>
          <button
            className={buttonClassName("primary")}
            onClick={() => reviewMutation.mutate(selectedVariantIds)}
            disabled={
              branchFilter === ALL_BRANCHES ||
              selectedVariantIds.length === 0 ||
              reviewMutation.isPending
            }
            data-testid="variants-review-button"
          >
            Review selected
          </button>
        </div>

        {shell.bootstrap?.schema.pivot_language === null ? (
          <InlineNotice tone="info" title="No pivot language configured">
            This project does not define a pivot language, so variants stay in `init`
            and manual pivot review is unavailable.
          </InlineNotice>
        ) : null}

        {branchFilter === ALL_BRANCHES ? (
          <InlineNotice tone="info" title="Branch actor required for review">
            Pick one branch filter before reviewing changed items. The selected
            branch becomes the review actor.
          </InlineNotice>
        ) : null}

        {variantsQuery.isError ? (
          <InlineNotice tone="error" title="Failed to load project variants">
            {variantsQuery.error instanceof Error ? variantsQuery.error.message : "Request failed."}
          </InlineNotice>
        ) : null}

        {variantsQuery.data?.rows.length ? (
          <div className={styles.resultList} data-testid="variants-results-list">
            {variantsQuery.data.rows.map((row) => {
              const selected = selectedVariantIds.includes(row.variant_id);
              const canSelect = row.pivot_status === "changed";
              return (
                <article
                  key={row.variant_id}
                  className={cx(
                    styles.resultCard,
                    shell.businessKey === row.business_key && styles.resultCardActive,
                  )}
                >
                  <div className={styles.resultTop}>
                    <label className={styles.checkboxWrap}>
                      <input
                        type="checkbox"
                        checked={selected}
                        disabled={!canSelect}
                        aria-label={`Select ${row.business_key}`}
                        onChange={() => toggleVariantSelection(row.variant_id, setSelectedVariantIds)}
                      />
                      <span />
                    </label>
                    <button
                      className={styles.resultButton}
                      onClick={() => shell.setBusinessKey(row.business_key)}
                    >
                      <strong>{row.business_key}</strong>
                      <span className={styles.meta}>variant #{row.variant_id}</span>
                    </button>
                  </div>
                  <div className={styles.badges}>
                    <Badge tone={pivotTone(row.pivot_status)}>{row.pivot_status}</Badge>
                    <Badge tone={row.state === "orphan" ? "warning" : "info"}>{row.state}</Badge>
                  </div>
                  <p className={styles.meta}>{row.file_name || "No file name"}</p>
                  <p className={styles.meta}>{row.source}</p>
                  <p className={styles.meta}>
                    changed by {row.pivot_changed_by_branch_ref || "-"} ·{" "}
                    {formatTimestamp(row.pivot_changed_at)}
                  </p>
                  <p className={styles.meta}>
                    reviewed at {formatTimestamp(row.pivot_reviewed_at)}
                  </p>
                </article>
              );
            })}
          </div>
        ) : (
          <EmptyState
            title="No variants found"
            body="Try a different branch, lifecycle, pivot status, or owner filter."
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
                      <Badge tone={pivotTone(variant.pivot_status)}>{variant.pivot_status}</Badge>
                      {variant.is_orphaned ? <Badge tone="warning">orphan</Badge> : null}
                      {variant.is_trashed ? <Badge tone="danger">trashed</Badge> : null}
                    </div>
                  </div>
                  <KeyValueList
                    items={[
                      ["source", variant.source],
                      ["pivot_changed_by", variant.pivot_changed_by_branch_ref || "-"],
                      ["pivot_changed_at", formatTimestamp(variant.pivot_changed_at)],
                      ["pivot_reviewed_at", formatTimestamp(variant.pivot_reviewed_at)],
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

function toggleVariantSelection(
  variantId: number,
  setSelectedVariantIds: React.Dispatch<React.SetStateAction<number[]>>,
) {
  setSelectedVariantIds((current) =>
    current.includes(variantId)
      ? current.filter((item) => item !== variantId)
      : [...current, variantId],
  );
}

function pivotTone(status: PivotStatus) {
  if (status === "changed") {
    return "warning";
  }
  if (status === "reviewed") {
    return "accent";
  }
  return "neutral";
}
