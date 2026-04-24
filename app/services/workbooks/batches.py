from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any, Iterator

from app.db import get_conn, json_dumps, json_loads
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.shared.utils import now_iso
from app.services.workbooks.models import WorkbookWorkflowContext
from app.services.workbooks.parser import WorkbookParser


class WorkbookBatchService:
    INSERT_CHUNK_SIZE = 1000
    READ_CHUNK_SIZE = 1000

    def __init__(
        self,
        *,
        parser: WorkbookParser | None = None,
        projects: ProjectService | None = None,
    ) -> None:
        self.parser = parser or WorkbookParser()
        self.projects = projects or ProjectService()

    def create_batch_from_directory(
        self,
        input_dir: str | Path,
        project_id: int = DEFAULT_PROJECT_ID,
        context: WorkbookWorkflowContext | None = None,
    ) -> dict[str, Any]:
        context = context or WorkbookWorkflowContext(workflow_kind="create_branch")
        self.projects.require_project(project_id)
        started = perf_counter()
        with get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO imports(project_id, created_at, meta_json)
                VALUES (?, ?, ?)
                """,
                (
                    project_id,
                    now_iso(),
                    json_dumps(
                        {
                            "kind": "workbook_batch",
                            "workflow_kind": context.workflow_kind,
                            "mutation_type": context.mutation_type,
                            "input_dir": str(input_dir),
                            "project_id": project_id,
                        }
                    ),
                ),
            )
            batch_id = int(cur.lastrowid)

        rows_scanned = 0
        issues = 0
        pending: list[tuple[Any, ...]] = []
        for row in self.parser.iter_rows(input_dir, project_id, context):
            rows_scanned += 1
            if row.status != "ok":
                issues += 1
            payload = {
                "file_name": row.file_path,
                "business_key": row.business_key,
                "source": row.source,
                "translations": row.translations,
                "remarks": row.remarks,
            }
            pending.append(
                (
                    batch_id,
                    row.file_path,
                    row.sheet_name,
                    row.row_index,
                    row.business_key,
                    row.source,
                    row.status,
                    row.message,
                    json_dumps(payload),
                )
            )
            if len(pending) >= self.INSERT_CHUNK_SIZE:
                self._flush(pending)
        self._flush(pending)

        return {
            "workbook_batch_id": batch_id,
            "import_batch_id": batch_id,
            "project_id": project_id,
            "rows_scanned": rows_scanned,
            "issues": issues,
            "elapsed_ms": int((perf_counter() - started) * 1000),
        }

    def iter_rows(
        self,
        workbook_batch_id: int,
        project_id: int = DEFAULT_PROJECT_ID,
        *,
        ok_only: bool = False,
    ) -> Iterator[dict[str, Any]]:
        self.require_batch_project(workbook_batch_id, project_id)
        last_id = 0
        while True:
            rows = self._load_chunk(workbook_batch_id, last_id, ok_only=ok_only)
            if not rows:
                break
            last_id = int(rows[-1]["import_row_id"])
            for row in rows:
                yield row

    def require_batch_project(self, workbook_batch_id: int, project_id: int) -> None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT project_id FROM imports WHERE import_batch_id = ?",
                (workbook_batch_id,),
            ).fetchone()
        if not row or int(row["project_id"]) != project_id:
            raise KeyError(f"workbook batch not found: {workbook_batch_id}")

    def _load_chunk(self, workbook_batch_id: int, after_row_id: int, *, ok_only: bool) -> list[dict[str, Any]]:
        query = """
            SELECT import_row_id, file_path, sheet_name, row_index, business_key, source, status, message, payload_json
            FROM import_rows
            WHERE import_batch_id = ?
              AND import_row_id > ?
        """
        params: list[Any] = [workbook_batch_id, after_row_id]
        if ok_only:
            query += " AND status = 'ok'"
        query += " ORDER BY import_row_id LIMIT ?"
        params.append(self.READ_CHUNK_SIZE)
        with get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "import_row_id": int(row["import_row_id"]),
                "file_path": row["file_path"],
                "sheet_name": row["sheet_name"],
                "row_index": int(row["row_index"]),
                "business_key": row["business_key"],
                "source": row["source"] or "",
                "status": row["status"],
                "message": row["message"],
                "payload": json_loads(row["payload_json"]),
            }
            for row in rows
        ]

    def _flush(self, rows: list[tuple[Any, ...]]) -> None:
        if not rows:
            return
        with get_conn() as conn:
            conn.executemany(
                """
                INSERT INTO import_rows(
                    import_batch_id,
                    file_path,
                    sheet_name,
                    row_index,
                    business_key,
                    source,
                    status,
                    message,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        rows.clear()
