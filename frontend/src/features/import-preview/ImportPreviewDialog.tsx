import type {
  ImportSheetMapping,
  ImportUploadPreview,
} from "@/domains/imports/types";
import {
  InlineNotice,
  Panel,
  buttonClassName,
  ui,
} from "@/shared/ui/primitives";

import styles from "@/features/import-preview/ImportPreviewDialog.module.css";

type MappingIssue = {
  sheet_key: string;
  missing: string[];
};

export function ImportPreviewDialog(props: {
  preview: ImportUploadPreview;
  mappings: Record<string, ImportSheetMapping>;
  issues: MappingIssue[];
  onClose: () => void;
  onConfirm: () => void;
  onUpdateMapping: (
    sheetKey: string,
    kind: "business_key" | "source" | "translation" | "remark",
    fieldKey: string,
    value: string,
  ) => void;
}) {
  return (
    <div className={styles.overlay} data-testid="intake-import-dialog">
      <div className={styles.backdrop} onClick={props.onClose} />
      <div className={styles.card}>
        <Panel
          kicker="Import Mapping"
          title="Review workbook headers"
          description={`${props.preview.file_count} files · ${props.preview.sheet_count} sheets uploaded. Confirm the required headers before creating the import batch.`}
          actions={
            <div className={ui.toolbar}>
              <button className={buttonClassName("ghost")} onClick={props.onClose}>
                Close
              </button>
              <button
                className={buttonClassName("primary")}
                onClick={props.onConfirm}
                disabled={props.issues.length > 0}
                data-testid="intake-confirm-import"
              >
                Create import batch
              </button>
            </div>
          }
        >
          <div className={styles.body}>
            {props.preview.sheet_previews.map((sheet) => {
              const issue = props.issues.find((item) => item.sheet_key === sheet.sheet_key);
              const mapping = props.mappings[sheet.sheet_key];
              return (
                <article key={sheet.sheet_key} className={styles.sheetCard}>
                  <div>
                    <strong>
                      {sheet.file_path} · {sheet.sheet_name}
                    </strong>
                    <p className={styles.meta}>
                      Derived `file_name`: {sheet.derived_file_name}
                    </p>
                    <p className={styles.meta}>
                      Available headers: {sheet.available_headers.join(", ") || "none"}
                    </p>
                  </div>
                  {issue ? (
                    <InlineNotice tone="error" title="Missing required mapping">
                      Choose headers for {issue.missing.join(", ")} before continuing.
                    </InlineNotice>
                  ) : (
                    <InlineNotice tone="success" title="Ready">
                      This sheet has the required key and source mappings.
                    </InlineNotice>
                  )}
                  <div className={styles.mappingGrid}>
                    <MappingSelect
                      label="Business key"
                      value={mapping?.business_key || ""}
                      headers={sheet.available_headers}
                      onChange={(value) =>
                        props.onUpdateMapping(sheet.sheet_key, "business_key", "", value)
                      }
                    />
                    <MappingSelect
                      label="Source"
                      value={mapping?.source || ""}
                      headers={sheet.available_headers}
                      onChange={(value) =>
                        props.onUpdateMapping(sheet.sheet_key, "source", "", value)
                      }
                    />
                    {props.preview.schema.translation_columns.map((lang) => (
                      <MappingSelect
                        key={`${sheet.sheet_key}-${lang}`}
                        label={`Translation · ${lang}`}
                        value={mapping?.translation_columns?.[lang] || ""}
                        headers={sheet.available_headers}
                        onChange={(value) =>
                          props.onUpdateMapping(sheet.sheet_key, "translation", lang, value)
                        }
                      />
                    ))}
                    {props.preview.schema.remark_columns.map((remarkKey) => (
                      <MappingSelect
                        key={`${sheet.sheet_key}-${remarkKey}`}
                        label={`Remark · ${remarkKey}`}
                        value={mapping?.remark_columns?.[remarkKey] || ""}
                        headers={sheet.available_headers}
                        onChange={(value) =>
                          props.onUpdateMapping(sheet.sheet_key, "remark", remarkKey, value)
                        }
                      />
                    ))}
                  </div>
                </article>
              );
            })}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function MappingSelect(props: {
  label: string;
  value: string;
  headers: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className={ui.field}>
      <span className={ui.fieldLabel}>{props.label}</span>
      <select
        className={ui.select}
        value={props.value}
        onChange={(event) => props.onChange(event.target.value)}
      >
        <option value="">Select header</option>
        {props.headers.map((header) => (
          <option key={`${props.label}-${header}`} value={header}>
            {header}
          </option>
        ))}
      </select>
    </label>
  );
}
