from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from app.services.qa_service import validate_pair


class QaScanService:
    def scan_directory(self, source_dir: str, lang: str, target_col_index: int = 3) -> dict[str, Any]:
        root = Path(source_dir)
        scanned_rows = 0
        report_rows: list[dict[str, Any]] = []

        for path in root.rglob("*.xlsx"):
            if path.name.startswith("~$"):
                continue
            workbook = load_workbook(path)
            for sheet in workbook.worksheets:
                for row_idx in range(2, sheet.max_row + 1):
                    key = str(sheet.cell(row=row_idx, column=1).value or "").strip()
                    if not key:
                        continue
                    scanned_rows += 1
                    src = str(sheet.cell(row=row_idx, column=2).value or "")
                    tgt = str(sheet.cell(row=row_idx, column=target_col_index).value or "")
                    for result in validate_pair(src, tgt):
                        if result.ok:
                            continue
                        report_rows.append(
                            {
                                "file_path": str(path.relative_to(root)).replace("\\", "/"),
                                "sheet": sheet.title,
                                "row": row_idx,
                                "key": key,
                                "lang": lang,
                                "rule": result.rule,
                                "src_excerpt": src[:120],
                                "tgt_excerpt": tgt[:120],
                            }
                        )

        rule_counts: dict[str, int] = {}
        for row in report_rows:
            rule = row["rule"]
            rule_counts[rule] = rule_counts.get(rule, 0) + 1

        return {
            "scanned_rows": scanned_rows,
            "issue_count": len(report_rows),
            "rule_counts": rule_counts,
            "report_rows": report_rows,
        }
