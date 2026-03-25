import type { ReactNode } from "react";

import { cx } from "@/shared/lib/cx";

import styles from "@/shared/ui/primitives.module.css";

type ButtonTone = "primary" | "secondary" | "ghost" | "danger";
type BadgeTone = "accent" | "info" | "warning" | "danger" | "neutral";
type NoticeTone = "info" | "success" | "warning" | "error";

export { styles as ui };

export function buttonClassName(tone: ButtonTone = "secondary") {
  return cx(
    styles.button,
    tone === "primary" && styles.buttonPrimary,
    tone === "secondary" && styles.buttonSecondary,
    tone === "ghost" && styles.buttonGhost,
    tone === "danger" && styles.buttonDanger,
  );
}

export function badgeClassName(tone: BadgeTone = "neutral") {
  return cx(
    styles.badge,
    tone === "accent" && styles.badgeAccent,
    tone === "info" && styles.badgeInfo,
    tone === "warning" && styles.badgeWarning,
    tone === "danger" && styles.badgeDanger,
    tone === "neutral" && styles.badgeNeutral,
  );
}

export function Panel(props: {
  kicker?: string;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  testId?: string;
}) {
  return (
    <section className={cx(styles.panel, props.className)} data-testid={props.testId}>
      <div className={styles.panelHeading}>
        <div className={styles.panelCopy}>
          {props.kicker ? <p className={styles.eyebrow}>{props.kicker}</p> : null}
          <h2 className={styles.title}>{props.title}</h2>
          {props.description ? (
            <p className={styles.description}>{props.description}</p>
          ) : null}
        </div>
        {props.actions}
      </div>
      {props.children}
    </section>
  );
}

export function Badge(props: { tone?: BadgeTone; children: ReactNode }) {
  return <span className={badgeClassName(props.tone)}>{props.children}</span>;
}

export function InlineNotice(props: {
  title?: string;
  tone?: NoticeTone;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div
      className={cx(
        styles.notice,
        props.tone === "info" && styles.noticeInfo,
        props.tone === "success" && styles.noticeSuccess,
        props.tone === "warning" && styles.noticeWarning,
        props.tone === "error" && styles.noticeError,
      )}
    >
      {props.title ? <p className={styles.noticeTitle}>{props.title}</p> : null}
      <div className={styles.noticeBody}>{props.children}</div>
      {props.action}
    </div>
  );
}

export function EmptyState(props: {
  title: string;
  body: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className={styles.empty}>
      <h3 className={styles.emptyTitle}>{props.title}</h3>
      <div className={styles.emptyBody}>{props.body}</div>
      {props.action}
    </div>
  );
}

export function StatGrid(props: {
  items: Array<{ label: string; value: ReactNode; hint?: ReactNode }>;
}) {
  return (
    <div className={styles.stats}>
      {props.items.map((item) => (
        <div key={item.label} className={styles.statCard}>
          <span className={styles.statLabel}>{item.label}</span>
          <span className={styles.statValue}>{item.value}</span>
          {item.hint ? <span className={styles.statHint}>{item.hint}</span> : null}
        </div>
      ))}
    </div>
  );
}

export function KeyValueList(props: {
  items: Array<[string, ReactNode]>;
}) {
  if (props.items.length === 0) {
    return null;
  }
  return (
    <div className={styles.keyValues}>
      {props.items.map(([label, value]) => (
        <div key={label} className={styles.keyValueRow}>
          <span className={styles.keyValueLabel}>{label}</span>
          <span>{value || "-"}</span>
        </div>
      ))}
    </div>
  );
}

export function LoadingBlock(props: { label: string }) {
  return (
    <div className={styles.spinnerBlock}>
      <span className={styles.spinner} />
      <span>{props.label}</span>
    </div>
  );
}
