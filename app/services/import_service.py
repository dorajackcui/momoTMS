from __future__ import annotations

from pathlib import Path
from typing import Iterable

from openpyxl import load_workbook

from app.db import get_conn, json_dumps
from app.services.utils import now_iso, src_hash


class ImportService:
    def import_directory(self, input_dir: str, lang: str, target_col_index: int = 3) -> dict[str, int]:
        base = Path(input_dir)
        files = [p for p in base.rglob("*.xlsx") if not p.name.startswith("~$")]
        rows_scanned = 0
        issues = 0

        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO imports(created_at, meta_json) VALUES (?, ?)",
                (now_iso(), json_dumps({"lang": lang, "target_col_index": target_col_index, "input_dir": input_dir})),
            )
            batch_id = int(cur.lastrowid)

        for file in files:
            rel = str(file.relative_to(base))
            workbook = load_workbook(filename=file)
            for sheet in workbook.worksheets:
                for row_idx in range(2, sheet.max_row + 1):
                    rows_scanned += 1
                    key = sheet.cell(row=row_idx, column=1).value
                    src = sheet.cell(row=row_idx, column=2).value
                    status = "ok"
                    msg = None
                    if not key:
                        status = "missing_key"
                        issues += 1
                    if src is None:
                        status = "missing_src"
                        issues += 1

                    with get_conn() as conn:
                        conn.execute(
                            """
                            INSERT INTO import_rows(import_batch_id, file_path, sheet_name, row_index, key, src_hash, status, message)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (batch_id, rel, sheet.title, row_idx, key, src_hash(str(src or "")), status, msg),
                        )

        return {
            "import_batch_id": batch_id,
            "files_scanned": len(files),
            "rows_scanned": rows_scanned,
            "issues": issues,
        }

    def import_report(self, import_batch_id: int) -> list[dict]:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM import_rows WHERE import_batch_id = ? AND status != 'ok'",
                (import_batch_id,),
            ).fetchall()
        return list(rows)
