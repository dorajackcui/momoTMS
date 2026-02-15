from __future__ import annotations

import csv
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import load_workbook

from app.db import get_conn
from app.services.snapshot_service import SnapshotService
from app.services.utils import src_hash


class FillService:
    def __init__(self) -> None:
        self.snapshots = SnapshotService()

    def _build_translation_map(self, snapshot_id: int, lang: str) -> dict[str, tuple[str, str | None]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT si.key, e.src_hash, t.target_text
                FROM snapshot_items si
                JOIN entries e ON e.entry_id = si.entry_id
                LEFT JOIN translations t ON t.entry_id = si.entry_id AND t.lang = ?
                WHERE si.snapshot_id = ?
                """,
                (lang, snapshot_id),
            ).fetchall()
        return {row["key"]: (row["src_hash"], row["target_text"]) for row in rows}

    def fill_and_export(
        self,
        source_dir: str,
        output_zip: str,
        lang: str,
        release_snapshot_id: int,
        master_snapshot_id: int | None,
        target_col_index: int = 3,
    ) -> dict[str, str | int]:
        release_map = self._build_translation_map(release_snapshot_id, lang)
        master_map = self._build_translation_map(master_snapshot_id, lang) if master_snapshot_id else {}

        root = Path(source_dir)
        work_dir = root.parent / f"{root.name}_filled"
        if work_dir.exists():
            for p in sorted(work_dir.rglob("*"), reverse=True):
                if p.is_file():
                    p.unlink()
                elif p.is_dir():
                    p.rmdir()
        work_dir.mkdir(parents=True, exist_ok=True)

        filled = miss = mismatch = kept = 0
        report_rows: list[list[str | int]] = []

        for path in root.rglob("*.xlsx"):
            rel = path.relative_to(root)
            out_path = work_dir / rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            wb = load_workbook(path)
            for sheet in wb.worksheets:
                for row_idx in range(2, sheet.max_row + 1):
                    key = str(sheet.cell(row=row_idx, column=1).value or "").strip()
                    if not key:
                        continue
                    src = str(sheet.cell(row=row_idx, column=2).value or "")
                    current_tgt = sheet.cell(row=row_idx, column=target_col_index).value
                    src_digest = src_hash(src)

                    candidate = release_map.get(key) or master_map.get(key)
                    if not candidate:
                        miss += 1
                        report_rows.append([rel, sheet.title, row_idx, key, "MISSING_KEY_IN_BASE"])
                        continue
                    cand_src, cand_tgt = candidate
                    if cand_src != src_digest:
                        mismatch += 1
                        report_rows.append([rel, sheet.title, row_idx, key, "SRC_MISMATCH"])
                        continue
                    if current_tgt not in (None, ""):
                        kept += 1
                    sheet.cell(row=row_idx, column=target_col_index).value = cand_tgt
                    filled += 1
            wb.save(out_path)

        report_path = work_dir / "fill_report.csv"
        with report_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["file_path", "sheet", "row", "key", "status"])
            writer.writerows(report_rows)

        with ZipFile(output_zip, "w", compression=ZIP_DEFLATED) as zf:
            for p in work_dir.rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(work_dir))

        return {
            "filled_count": filled,
            "miss_key_count": miss,
            "src_mismatch_count": mismatch,
            "kept_original_count": kept,
            "report_path": str(report_path),
        }
