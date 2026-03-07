from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from app.db import get_conn, json_dumps, json_loads
from app.services.utils import now_iso

JOBS_DIR = Path("data/jobs")


class JobService:
    def create_job(self, job_type: str, input_payload: dict[str, Any]) -> int:
        JOBS_DIR.mkdir(parents=True, exist_ok=True)
        with get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO jobs(job_type, status, input_json, created_at)
                VALUES (?, 'running', ?, ?)
                """,
                (job_type, json_dumps(input_payload), now_iso()),
            )
            job_id = int(cur.lastrowid)
        self.job_dir(job_id).mkdir(parents=True, exist_ok=True)
        return job_id

    def complete_job(
        self,
        job_id: int,
        summary: dict[str, Any],
        report_payload: dict[str, Any] | None = None,
        artifact_path: str | None = None,
    ) -> None:
        report_path = None
        if report_payload is not None:
            report_path = str(self.write_report(job_id, report_payload))
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

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM jobs
                ORDER BY job_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._hydrate_job(row) for row in rows]

    def get_job(self, job_id: int) -> dict[str, Any]:
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            raise KeyError(f"job not found: {job_id}")
        return self._hydrate_job(row)

    def get_report(self, job_id: int) -> dict[str, Any]:
        job = self.get_job(job_id)
        report_path = job.get("report_path")
        if not report_path:
            return {"summary": job.get("summary", {}), "rows": []}
        return json_loads(Path(report_path).read_text(encoding="utf-8"))

    def job_dir(self, job_id: int) -> Path:
        return JOBS_DIR / str(job_id)

    def artifact_path(self, job_id: int, filename: str) -> Path:
        job_dir = self.job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        return job_dir / filename

    def write_report(self, job_id: int, report_payload: dict[str, Any]) -> Path:
        report_path = self.artifact_path(job_id, "report.json")
        report_path.write_text(json_dumps(report_payload), encoding="utf-8")
        return report_path

    def clear_storage(self) -> None:
        if JOBS_DIR.exists():
            shutil.rmtree(JOBS_DIR)

    def _hydrate_job(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "job_id": int(row["job_id"]),
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
