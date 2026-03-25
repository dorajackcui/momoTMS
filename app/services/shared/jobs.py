from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Iterable

from app.db import get_conn, json_dumps, json_loads
from app.services.shared.utils import now_iso

JOBS_DIR = Path("data/jobs")
JOBS_DIR_ENV_VAR = "MOMO_TMS_JOBS_DIR"


def get_jobs_dir(path: Path | str | None = None) -> Path:
    if path is not None:
        return Path(path)
    override = os.getenv(JOBS_DIR_ENV_VAR)
    if override:
        return Path(override)
    return JOBS_DIR


class JobService:
    REPORT_PREVIEW_LIMIT = 12

    def create_job(
        self,
        job_type: str,
        input_payload: dict[str, Any],
        project_id: int,
    ) -> int:
        get_jobs_dir().mkdir(parents=True, exist_ok=True)
        with get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO jobs(project_id, job_type, status, input_json, created_at)
                VALUES (?, ?, 'running', ?, ?)
                """,
                (project_id, job_type, json_dumps(input_payload), now_iso()),
            )
            job_id = int(cur.lastrowid)
        self.job_dir(job_id).mkdir(parents=True, exist_ok=True)
        return job_id

    def complete_job(
        self,
        job_id: int,
        summary: dict[str, Any],
        report_payload: dict[str, Any] | None = None,
        report_rows: Iterable[dict[str, Any]] | None = None,
        artifact_path: str | None = None,
    ) -> None:
        report_path = None
        if report_payload is not None:
            report_path = str(self.write_report(job_id, report_payload))
        elif report_rows is not None:
            report_path = str(self.write_streaming_report(job_id, summary, report_rows))
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = 'success',
                    summary_json = ?,
                    report_path = ?,
                    artifact_path = ?,
                    finished_at = ?,
                    error_message = NULL
                WHERE job_id = ?
                """,
                (
                    json_dumps(summary),
                    report_path,
                    artifact_path,
                    now_iso(),
                    job_id,
                ),
            )

    def complete_job_from_stream(
        self,
        job_id: int,
        report_rows: Iterable[dict[str, Any]],
        artifact_path: str | None = None,
    ) -> dict[str, Any]:
        report_path, summary = self._write_report_from_stream(job_id, report_rows)
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = 'success',
                    summary_json = ?,
                    report_path = ?,
                    artifact_path = ?,
                    finished_at = ?,
                    error_message = NULL
                WHERE job_id = ?
                """,
                (
                    json_dumps(summary),
                    str(report_path),
                    artifact_path,
                    now_iso(),
                    job_id,
                ),
            )
        return summary

    def fail_job(self, job_id: int, message: str) -> None:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = 'failed',
                    error_message = ?,
                    finished_at = ?
                WHERE job_id = ?
                """,
                (message, now_iso(), job_id),
            )

    def list_jobs(self, limit: int = 20, project_id: int | None = None) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if project_id is not None:
            where = "WHERE project_id = ?"
            params.append(project_id)
        params.append(limit)
        with get_conn() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM jobs
                {where}
                ORDER BY job_id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [self._hydrate_job(row) for row in rows]

    def get_job(self, job_id: int, project_id: int | None = None) -> dict[str, Any]:
        params: list[Any] = [job_id]
        query = "SELECT * FROM jobs WHERE job_id = ?"
        if project_id is not None:
            query += " AND project_id = ?"
            params.append(project_id)
        with get_conn() as conn:
            row = conn.execute(query, params).fetchone()
        if not row:
            raise KeyError(f"job not found: {job_id}")
        return self._hydrate_job(row)

    def get_report(self, job_id: int, project_id: int | None = None) -> dict[str, Any]:
        job = self.get_job(job_id, project_id=project_id)
        report_path = job.get("report_path")
        if not report_path:
            return {"summary": job.get("summary", {}), "rows": []}
        return json_loads(Path(report_path).read_text(encoding="utf-8"))

    def get_report_preview(
        self,
        job_id: int,
        project_id: int | None = None,
        limit: int = REPORT_PREVIEW_LIMIT,
    ) -> dict[str, Any]:
        job = self.get_job(job_id, project_id=project_id)
        preview_path = self.report_preview_path(job_id)
        if preview_path.exists():
            preview = json_loads(preview_path.read_text(encoding="utf-8"))
            preview["rows"] = list(preview.get("rows", []))[:limit]
            return preview
        report_path = job.get("report_path")
        if not report_path:
            return {"summary": job.get("summary", {}), "rows": []}
        payload = json_loads(Path(report_path).read_text(encoding="utf-8"))
        return {
            "summary": payload.get("summary", job.get("summary", {})),
            "rows": list(payload.get("rows", []))[:limit],
        }

    def job_dir(self, job_id: int) -> Path:
        return get_jobs_dir() / str(job_id)

    def artifact_path(self, job_id: int, filename: str) -> Path:
        job_dir = self.job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir / filename

    def report_preview_path(self, job_id: int) -> Path:
        return self.artifact_path(job_id, "report_preview.json")

    def write_report(self, job_id: int, report_payload: dict[str, Any]) -> Path:
        report_path = self.artifact_path(job_id, "report.json")
        report_path.write_text(json_dumps(report_payload), encoding="utf-8")
        self._write_report_preview(job_id, report_payload)
        return report_path

    def write_streaming_report(
        self,
        job_id: int,
        summary: dict[str, Any],
        report_rows: Iterable[dict[str, Any]],
    ) -> Path:
        report_path = self.artifact_path(job_id, "report.json")
        preview_rows: list[dict[str, Any]] = []
        with report_path.open("w", encoding="utf-8") as handle:
            handle.write('{"rows":[')
            first = True
            for row in report_rows:
                if len(preview_rows) < self.REPORT_PREVIEW_LIMIT:
                    preview_rows.append(row)
                if not first:
                    handle.write(",")
                handle.write(json.dumps(row, ensure_ascii=False))
                first = False
            handle.write('],"summary":')
            handle.write(json.dumps(summary, ensure_ascii=False))
            handle.write("}")
        self._write_report_preview(job_id, {"summary": summary, "rows": preview_rows})
        return report_path

    def clear_storage(self) -> None:
        jobs_dir = get_jobs_dir()
        if jobs_dir.exists():
            shutil.rmtree(jobs_dir)

    def _hydrate_job(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "job_id": int(row["job_id"]),
            "project_id": int(row["project_id"]),
            "job_type": row["job_type"],
            "status": row["status"],
            "input": json_loads(row["input_json"]),
            "summary": json_loads(row["summary_json"]),
            "report_path": row["report_path"],
            "artifact_path": row["artifact_path"],
            "error_message": row["error_message"],
            "created_at": row["created_at"],
            "finished_at": row["finished_at"],
        }

    def _write_report_preview(self, job_id: int, report_payload: dict[str, Any]) -> None:
        preview_payload = {
            "summary": report_payload.get("summary", {}),
            "rows": list(report_payload.get("rows", []))[: self.REPORT_PREVIEW_LIMIT],
        }
        self.report_preview_path(job_id).write_text(
            json_dumps(preview_payload),
            encoding="utf-8",
        )

    def _write_report_from_stream(
        self,
        job_id: int,
        report_rows: Iterable[dict[str, Any]],
    ) -> tuple[Path, dict[str, Any]]:
        report_path = self.artifact_path(job_id, "report.json")
        preview_rows: list[dict[str, Any]] = []
        summary: dict[str, Any] = {}
        iterator = iter(report_rows)
        with report_path.open("w", encoding="utf-8") as handle:
            handle.write('{"rows":[')
            first = True
            while True:
                try:
                    row = next(iterator)
                except StopIteration as stop:
                    if isinstance(stop.value, dict):
                        summary = dict(stop.value.get("summary", {}))
                    break
                if len(preview_rows) < self.REPORT_PREVIEW_LIMIT:
                    preview_rows.append(row)
                if not first:
                    handle.write(",")
                handle.write(json.dumps(row, ensure_ascii=False))
                first = False
            handle.write('],"summary":')
            handle.write(json.dumps(summary, ensure_ascii=False))
            handle.write("}")
        self._write_report_preview(job_id, {"summary": summary, "rows": preview_rows})
        return report_path, summary
