import { useState } from "react";

import { FileUpload } from "@/shared/ui/FileUpload";
import { FolderUpload } from "@/shared/ui/FolderUpload";

import styles from "@/shared/ui/WorkbookUpload.module.css";

export type WorkbookUploadProps = {
  label: string;
  onFiles: (files: File[]) => void;
  disabled?: boolean;
};

export function WorkbookUpload(props: WorkbookUploadProps) {
  const [mode, setMode] = useState<"file" | "folder">("file");

  function handleToggle() {
    setMode((prev) => (prev === "file" ? "folder" : "file"));
    props.onFiles([]);
  }

  return (
    <div>
      {mode === "file" ? (
        <FileUpload
          label={props.label}
          onFiles={props.onFiles}
          disabled={props.disabled}
        />
      ) : (
        <FolderUpload
          label={props.label}
          onFiles={props.onFiles}
          disabled={props.disabled}
        />
      )}
      <button
        type="button"
        className={styles.toggle}
        onClick={handleToggle}
        disabled={props.disabled}
      >
        {mode === "file" ? "or upload folder" : "or upload single file"}
      </button>
    </div>
  );
}
