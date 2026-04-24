import { useRef } from "react";
import { buttonClassName } from "@/shared/ui/primitives";

export type FolderUploadProps = {
  label: string;
  onFiles: (files: File[]) => void;
  disabled?: boolean;
};

export function FolderUpload(props: FolderUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  function handleChange() {
    const input = inputRef.current;
    if (!input?.files) return;
    const files = Array.from(input.files).filter(
      (f) => !f.name.startsWith("~$"),
    );
    if (files.length > 0) props.onFiles(files);
    input.value = "";
  }

  return (
    <label>
      <input
        ref={inputRef}
        type="file"
        /* @ts-expect-error webkitdirectory is non-standard */
        webkitdirectory=""
        directory=""
        multiple
        onChange={handleChange}
        style={{ display: "none" }}
        disabled={props.disabled}
      />
      <span className={buttonClassName("secondary")} role="button">
        {props.label}
      </span>
    </label>
  );
}
