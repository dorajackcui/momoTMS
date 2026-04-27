# Single File Upload Support

## Purpose

Add single Excel file upload as the default upload mode in the workbook workflow panel, keeping folder upload as a secondary option. This addresses the common case where operators import one workbook rather than a folder of workbooks.

## Scope

Frontend only. The backend already handles single-file uploads — a single file is just `files=[1]` + `relative_paths=[filename]`. No changes to `UploadSessionService`, routers, parser, or `postFolderForm`.

## Changes

### New: `FileUpload.tsx`

Single-file upload component parallel to `FolderUpload`:

- `<input type="file" accept=".xlsx">` — no `webkitdirectory`, no `multiple`.
- Same props interface as `FolderUpload`: `{ label, onFiles, disabled }`.
- `onFiles` returns `File[]` of length 1, keeping callback signature consistent.
- Filters `~$` temporary files.

### New: `WorkbookUpload.tsx`

Composition component encapsulating mode switching:

- Default mode: renders `FileUpload` with the configured label.
- Below the upload button, a text link toggles modes:
  - In file mode: "or upload folder"
  - In folder mode: "or upload single file"
- Switching modes clears any previously selected files.
- Exposes the same props as `FolderUpload`: `{ label, onFiles, disabled }`.

### Modified: `WorkbookWorkflowPanel.tsx`

- Replace `FolderUpload` with `WorkbookUpload`.
- File count display: single file shows the filename; folder shows "N files selected".
- All other logic unchanged.

## Transport Compatibility

`postFolderForm` already handles single files correctly. When a file is selected via the standard file picker (not `webkitdirectory`), `webkitRelativePath` is an empty string. The existing fallback `|| file.name` produces the correct `relative_paths` value.

## UX Flow

```
Default state:
  [Upload workbook]        ← single file picker (.xlsx)
  or upload folder         ← text link

After clicking "or upload folder":
  [Upload folder]          ← folder picker
  or upload single file    ← text link

After selecting a file:
  example.xlsx             ← filename for single file, "N files selected" for folder
  [Check Workbook] [Execute]
```

## Testing

- Single file upload produces correct `files` and `relative_paths` in the form submission.
- Folder upload still works after switching modes.
- Mode switch clears previously selected files.
- `~$` temporary files are filtered in both modes.
- Backend precheck and execute succeed with single-file uploads.
