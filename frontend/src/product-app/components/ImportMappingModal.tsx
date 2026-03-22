import type {
  ImportPreview,
  ImportSheetMapping,
} from "../types";

type ImportMappingIssue = {
  sheet_key: string;
  missing: string[];
};

export function ImportMappingModal(props: {
  importPreview: ImportPreview | null;
  importMappings: Record<string, ImportSheetMapping>;
  importMappingIssues: ImportMappingIssue[];
  translationColumns: string[];
  remarkColumns: string[];
  onClose: () => void;
  onConfirmImport: () => void;
  onUpdateImportMapping: (
    sheetKey: string,
    kind: "business_key" | "source" | "translation" | "remark",
    fieldKey: string,
    value: string,
  ) => void;
}) {
  if (!props.importPreview) {
    return null;
  }

  return (
    <div className="modal-shell" data-testid="app-import-modal">
      <div className="modal-backdrop" onClick={props.onClose} />
      <div className="modal-card">
        <div className="panel-head">
          <div>
            <p className="panel-kicker">Template Validation</p>
            <h3>Create Import Batch</h3>
          </div>
          <button className="button subtle" onClick={props.onClose}>
            Close
          </button>
        </div>
        <p className="muted">
          {props.importPreview.file_count} files ·{" "}
          {props.importPreview.sheet_count} sheets
        </p>
        <div className="modal-body">
          {props.importPreview.sheet_previews.map((sheet) => {
            const issue = props.importMappingIssues.find(
              (item) => item.sheet_key === sheet.sheet_key,
            );
            return (
              <article key={sheet.sheet_key} className="mapping-card">
                <strong>
                  {sheet.file_path} · {sheet.sheet_name}
                </strong>
                <p className="muted">
                  Derived file_name: {sheet.derived_file_name}
                </p>
                <p className="muted">
                  Headers: {sheet.available_headers.join(", ") || "none"}
                </p>
                {issue ? (
                  <p className="flash error">
                    Missing mappings: {issue.missing.join(", ")}
                  </p>
                ) : (
                  <p className="flash">Ready to create import batch.</p>
                )}
                <div className="mapping-grid">
                  <label className="field compact">
                    <span>Business Key</span>
                    <select
                      value={props.importMappings[sheet.sheet_key]?.business_key || ""}
                      onChange={(event) =>
                        props.onUpdateImportMapping(
                          sheet.sheet_key,
                          "business_key",
                          "",
                          event.target.value,
                        )
                      }
                    >
                      <option value="">Select header</option>
                      {sheet.available_headers.map((header) => (
                        <option
                          key={`${sheet.sheet_key}-business-${header}`}
                          value={header}
                        >
                          {header}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field compact">
                    <span>Source</span>
                    <select
                      value={props.importMappings[sheet.sheet_key]?.source || ""}
                      onChange={(event) =>
                        props.onUpdateImportMapping(
                          sheet.sheet_key,
                          "source",
                          "",
                          event.target.value,
                        )
                      }
                    >
                      <option value="">Select header</option>
                      {sheet.available_headers.map((header) => (
                        <option
                          key={`${sheet.sheet_key}-source-${header}`}
                          value={header}
                        >
                          {header}
                        </option>
                      ))}
                    </select>
                  </label>
                  {props.translationColumns.map((lang) => (
                    <label
                      key={`${sheet.sheet_key}-translation-${lang}`}
                      className="field compact"
                    >
                      <span>Translation · {lang}</span>
                      <select
                        value={
                          props.importMappings[sheet.sheet_key]?.translation_columns?.[
                            lang
                          ] || ""
                        }
                        onChange={(event) =>
                          props.onUpdateImportMapping(
                            sheet.sheet_key,
                            "translation",
                            lang,
                            event.target.value,
                          )
                        }
                      >
                        <option value="">Select header</option>
                        {sheet.available_headers.map((header) => (
                          <option
                            key={`${sheet.sheet_key}-translation-${lang}-${header}`}
                            value={header}
                          >
                            {header}
                          </option>
                        ))}
                      </select>
                    </label>
                  ))}
                  {props.remarkColumns.map((remarkKey) => (
                    <label
                      key={`${sheet.sheet_key}-remark-${remarkKey}`}
                      className="field compact"
                    >
                      <span>Remark · {remarkKey}</span>
                      <select
                        value={
                          props.importMappings[sheet.sheet_key]?.remark_columns?.[
                            remarkKey
                          ] || ""
                        }
                        onChange={(event) =>
                          props.onUpdateImportMapping(
                            sheet.sheet_key,
                            "remark",
                            remarkKey,
                            event.target.value,
                          )
                        }
                      >
                        <option value="">Select header</option>
                        {sheet.available_headers.map((header) => (
                          <option
                            key={`${sheet.sheet_key}-remark-${remarkKey}-${header}`}
                            value={header}
                          >
                            {header}
                          </option>
                        ))}
                      </select>
                    </label>
                  ))}
                </div>
              </article>
            );
          })}
        </div>
        <div className="toolbar">
          <button className="button subtle" onClick={props.onClose}>
            Cancel
          </button>
          <button
            className="button accent"
            onClick={props.onConfirmImport}
            disabled={props.importMappingIssues.length > 0}
            data-testid="app-confirm-import"
          >
            Create Import Batch
          </button>
        </div>
      </div>
    </div>
  );
}
