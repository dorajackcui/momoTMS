import { useRef } from "react";
import { buttonClassName } from "@/shared/ui/primitives";

export type FileUploadProps = {
  label: string;
  onFiles: (files: File[]) => void;
  disabled?: boolean;
};

export function FileUpload(props: FileUploadProps) {
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
        accept=".xlsx"
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
