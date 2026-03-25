from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import UploadFile

from app.services.shared.jobs import JobService, get_jobs_dir
from app.services.shared.utils import now_iso

MANIFEST_FILENAME = "manifest.json"
SESSION_FILES_DIRNAME = "files"
UPLOAD_SESSIONS_DIRNAME = "_upload_sessions"


class UploadSessionService:
    def create_session(
        self,
        files: list[UploadFile],
        relative_paths: list[str],
        project_id: int,
    ) -> dict[str, Any]:
        if len(files) != len(relative_paths):
            raise ValueError("files and relative_paths must have the same length")
        if not files:
            raise ValueError("at least one file is required")

        session_id = uuid4().hex
        session_dir = self._session_dir(session_id)
        files_dir = session_dir / SESSION_FILES_DIRNAME
        files_dir.mkdir(parents=True, exist_ok=True)

        file_count = 0
        try:
            for upload, relative_path in zip(files, relative_paths, strict=True):
                cleaned = self._normalize_relative_path(relative_path)
                output_path = files_dir / cleaned
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with output_path.open("wb") as handle:
                    shutil.copyfileobj(upload.file, handle, length=1024 * 1024)
                if output_path.stat().st_size == 0:
                    raise ValueError(f"empty upload file: {relative_path}")
                file_count += 1
        except Exception:
            shutil.rmtree(session_dir, ignore_errors=True)
            raise

        manifest = {
            "upload_session_id": session_id,
            "project_id": project_id,
            "file_count": file_count,
            "created_at": now_iso(),
        }
        self._write_manifest(session_dir, manifest)
        return manifest

    def require_session(self, upload_session_id: str, project_id: int) -> dict[str, Any]:
        session_dir = self._session_dir(upload_session_id)
        manifest_path = session_dir / MANIFEST_FILENAME
        files_dir = session_dir / SESSION_FILES_DIRNAME
        if not manifest_path.exists() or not files_dir.exists():
            raise KeyError(f"upload session not found: {upload_session_id}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if int(manifest.get("project_id") or 0) != project_id:
            raise KeyError(f"upload session not found: {upload_session_id}")
        return manifest

    def consume_session_into_job(
        self,
        upload_session_id: str,
        job_id: int,
        project_id: int,
        folder_name: str = "import_bundle",
    ) -> str:
        self.require_session(upload_session_id, project_id)
        session_dir = self._session_dir(upload_session_id)
        source_dir = session_dir / SESSION_FILES_DIRNAME
        target_dir = JobService().job_dir(job_id) / folder_name
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_dir), str(target_dir))
        shutil.rmtree(session_dir, ignore_errors=True)
        return str(target_dir)

    def discard_session(self, upload_session_id: str) -> None:
        shutil.rmtree(self._session_dir(upload_session_id), ignore_errors=True)

    def session_input_dir(self, upload_session_id: str) -> Path:
        return self._session_dir(upload_session_id) / SESSION_FILES_DIRNAME

    def _sessions_root(self) -> Path:
        root = get_jobs_dir() / UPLOAD_SESSIONS_DIRNAME
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _session_dir(self, upload_session_id: str) -> Path:
        return self._sessions_root() / upload_session_id

    def _write_manifest(self, session_dir: Path, manifest: dict[str, Any]) -> None:
        (session_dir / MANIFEST_FILENAME).write_text(
            json.dumps(manifest, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def _normalize_relative_path(relative_path: str) -> str:
        cleaned = relative_path.replace("\\", "/").strip("/")
        if not cleaned or cleaned.startswith("../") or "/../" in f"/{cleaned}/":
            raise ValueError(f"invalid relative path: {relative_path}")
        if not cleaned.endswith(".xlsx"):
            raise ValueError(f"unsupported upload file: {relative_path}")
        return cleaned
