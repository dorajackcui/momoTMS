from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from app.services.demo.service import DemoService
from app.services.imports.service import ImportService
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.workflows.dev_versions import DevVersionService
from app.services.workflows.fill import FillService
from app.services.shared.jobs import JobService
from app.services.workflows.promote import PromoteService
from app.services.workflows.qa import QaScanService
from app.services.workflows.rel import RelService
from app.services.variant.compatibility import StringService
from app.services.workflows.trash import TrashService


class WorkbenchService:
    def __init__(self) -> None:
        self.demo_service = DemoService()
        self.dev_version_service = DevVersionService()
        self.fill_service = FillService()
        self.import_service = ImportService()
        self.job_service = JobService()
        self.project_service = ProjectService()
        self.promote_service = PromoteService()
        self.qa_scan_service = QaScanService()
        self.rel_service = RelService()
        self.string_service = StringService()
        self.trash_service = TrashService()

    def get_state(self, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        return {
            "project": self.project_service.require_project(project_id),
            "schema": self.project_service.get_schema(project_id),
            "rel_summary": self.rel_service.summary(project_id),
            "candidate_dev_version": self.dev_version_service.get_candidate_release(project_id),
            "dev_versions": self.dev_version_service.list_versions(project_id=project_id, active_only=True),
            "trash_count": self.string_service.trash_count(project_id),
            "imports": self.import_service.list_batches(project_id=project_id),
            "jobs": self.job_service.list_jobs(project_id=project_id),
            "samples": self.demo_service.list_samples(),
        }

    def import_directory(self, input_dir: str, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        return self._run_job(
            "import_directory",
            {"input_dir": input_dir, "project_id": project_id},
            lambda _job_id: self._import_action(input_dir, project_id=project_id),
            project_id=project_id,
        )

    def preview_import_uploaded_folder(
        self,
        files: list[tuple[str, bytes]],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self._validate_uploaded_folder(files)
        return self.import_service.preview_files(files, project_id=project_id)

    def import_uploaded_folder(
        self,
        files: list[tuple[str, bytes]],
        project_id: int = DEFAULT_PROJECT_ID,
        mapping_overrides: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return self._run_job(
            "import_upload_folder",
            {
                "file_count": len(files),
                "mapping_override_count": len(mapping_overrides or {}),
                "project_id": project_id,
            },
            lambda job_id: self._import_action(
                self._stage_uploaded_folder(job_id, files, "import_bundle"),
                project_id=project_id,
                mapping_overrides=mapping_overrides,
            ),
            project_id=project_id,
        )

    def dev_import(
        self,
        import_batch_id: int,
        version: str,
        mark_as_candidate: bool = True,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        return self._run_job(
            "dev_import",
            {
                "import_batch_id": import_batch_id,
                "version": version,
                "mark_as_candidate": mark_as_candidate,
                "project_id": project_id,
            },
            lambda _job_id: self._dev_import_action(import_batch_id, version, mark_as_candidate, project_id=project_id),
            project_id=project_id,
        )

    def active_hotfix(
        self,
        business_key: str,
        lang: str,
        target_text: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        return self._run_job(
            "rel_hotfix_active",
            {
                "business_key": business_key,
                "lang": lang,
                "target_text": target_text,
                "project_id": project_id,
            },
            lambda _job_id: self._wrap_report(
                self.rel_service.active_hotfix(business_key, lang, target_text, project_id=project_id)
            ),
            project_id=project_id,
        )

    def passive_hotfix(
        self,
        business_key: str,
        source: str,
        translations_by_lang: dict[str, str],
        remarks_by_key: dict[str, str],
        file_name: str | None = None,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        return self._run_job(
            "rel_hotfix_passive",
            {
                "business_key": business_key,
                "source": source,
                "translations_by_lang": translations_by_lang,
                "remarks_by_key": remarks_by_key,
                "file_name": file_name,
                "project_id": project_id,
            },
            lambda _job_id: self._wrap_report(
                self.rel_service.passive_hotfix(
                    business_key,
                    source,
                    translations_by_lang,
                    remarks_by_key,
                    file_name=file_name,
                    project_id=project_id,
                )
            ),
            project_id=project_id,
        )

    def preview_promote(self, version: str, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        return self.promote_service.preview(version, project_id)

    def execute_promote(self, version: str, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        return self._run_job(
            "promote_execute",
            {"version": version, "project_id": project_id},
            lambda _job_id: self._wrap_report(self.promote_service.execute(version, project_id)),
            project_id=project_id,
        )

    def trash_delete(self, business_keys: list[str], project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        return self._run_job(
            "trash_delete",
            {"business_keys": business_keys, "project_id": project_id},
            lambda _job_id: self._wrap_report(self.trash_service.delete(business_keys, project_id=project_id)),
            project_id=project_id,
        )

    def trash_restore(self, business_keys: list[str], project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        return self._run_job(
            "trash_restore",
            {"business_keys": business_keys, "project_id": project_id},
            lambda _job_id: self._wrap_report(self.trash_service.restore(business_keys, project_id=project_id)),
            project_id=project_id,
        )

    def fill(
        self,
        source_dir: str,
        lang: str,
        output_name: str | None = None,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        return self._run_job(
            "fill_export",
            {
                "source_dir": source_dir,
                "lang": lang,
                "output_name": output_name,
                "project_id": project_id,
            },
            lambda job_id: self._fill_action(job_id, source_dir, lang, output_name, project_id=project_id),
            project_id=project_id,
        )

    def fill_uploaded_folder(
        self,
        files: list[tuple[str, bytes]],
        lang: str,
        output_name: str | None = None,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        return self._run_job(
            "fill_upload_folder",
            {
                "file_count": len(files),
                "lang": lang,
                "output_name": output_name,
                "project_id": project_id,
            },
            lambda job_id: self._fill_action(
                job_id,
                self._stage_uploaded_folder(job_id, files, "fill_source"),
                lang,
                output_name,
                project_id=project_id,
            ),
            project_id=project_id,
        )

    def qa(self, source_dir: str, lang: str, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        return self._run_job(
            "qa_report",
            {
                "source_dir": source_dir,
                "lang": lang,
                "project_id": project_id,
            },
            lambda _job_id: self._qa_action(source_dir, lang, project_id=project_id),
            project_id=project_id,
        )

    def qa_uploaded_folder(
        self,
        files: list[tuple[str, bytes]],
        lang: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        return self._run_job(
            "qa_upload_folder",
            {
                "file_count": len(files),
                "lang": lang,
                "project_id": project_id,
            },
            lambda job_id: self._qa_action(
                self._stage_uploaded_folder(job_id, files, "qa_source"),
                lang,
                project_id=project_id,
            ),
            project_id=project_id,
        )

    def get_job_detail(self, job_id: int, project_id: int | None = None) -> dict[str, Any]:
        return {
            "job": self.job_service.get_job(job_id, project_id=project_id),
            "report": self.job_service.get_report(job_id, project_id=project_id),
        }

    def _import_action(
        self,
        input_dir: str,
        project_id: int = DEFAULT_PROJECT_ID,
        mapping_overrides: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        summary = self.import_service.import_directory(
            input_dir,
            project_id=project_id,
            mapping_overrides=mapping_overrides,
        )
        report = self.import_service.import_report(summary["import_batch_id"], issues_only=False)
        return {"summary": summary, "report": report}

    def _dev_import_action(
        self,
        import_batch_id: int,
        version: str,
        mark_as_candidate: bool,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        result = self.dev_version_service.import_batch(
            import_batch_id,
            version,
            mark_as_candidate,
            project_id=project_id,
        )
        return self._wrap_report(result)

    def _fill_action(
        self,
        job_id: int,
        source_dir: str,
        lang: str,
        output_name: str | None,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        artifact_name = output_name or "filled_export.zip"
        artifact_path = str(self.job_service.artifact_path(job_id, artifact_name))
        work_dir = str(self.job_service.job_dir(job_id) / "fill_output")
        result = self.fill_service.fill_and_export(
            source_dir,
            artifact_path,
            lang,
            project_id=project_id,
            work_dir=work_dir,
        )
        summary = {
            "filled_count": result["filled_count"],
            "miss_key_count": result["miss_key_count"],
            "src_mismatch_count": result["src_mismatch_count"],
            "kept_original_count": result["kept_original_count"],
            "skipped_invalid_combined_key_count": result["skipped_invalid_combined_key_count"],
            "skipped_blank_content_count": result["skipped_blank_content_count"],
            "output_zip": artifact_path,
        }
        return {
            "summary": summary,
            "report": {"summary": summary, "rows": result["report_rows"]},
            "artifact_path": artifact_path,
        }

    def _qa_action(self, source_dir: str, lang: str, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        result = self.qa_scan_service.scan_directory(source_dir, lang, project_id=project_id)
        summary = {
            "scanned_rows": result["scanned_rows"],
            "issue_count": result["issue_count"],
            "rule_counts": result["rule_counts"],
        }
        return {
            "summary": summary,
            "report": {"summary": summary, "rows": result["report_rows"]},
        }

    def _stage_uploaded_folder(
        self,
        job_id: int,
        files: list[tuple[str, bytes]],
        folder_name: str,
    ) -> str:
        self._validate_uploaded_folder(files)
        root = self.job_service.job_dir(job_id) / folder_name
        root.mkdir(parents=True, exist_ok=True)
        for relative_path, payload in files:
            cleaned = relative_path.replace("\\", "/").strip("/")
            output_path = root / cleaned
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(payload)
        return str(root)

    def _validate_uploaded_folder(self, files: list[tuple[str, bytes]]) -> None:
        if not files:
            raise ValueError("at least one file is required")
        for relative_path, payload in files:
            cleaned = relative_path.replace("\\", "/").strip("/")
            if not cleaned or cleaned.startswith("../") or "/../" in f"/{cleaned}/":
                raise ValueError(f"invalid relative path: {relative_path}")
            if not cleaned.endswith(".xlsx"):
                raise ValueError(f"unsupported upload file: {relative_path}")
            if not payload:
                raise ValueError(f"empty upload file: {relative_path}")

    def _wrap_report(self, result: dict[str, Any]) -> dict[str, Any]:
        return {
            "summary": result["summary"],
            "report": {
                "summary": result["summary"],
                "rows": result.get("report_rows", []),
            },
            "artifact_path": result.get("artifact_path"),
        }

    def _run_job(
        self,
        job_type: str,
        input_payload: dict[str, Any],
        action: Callable[[int], dict[str, Any]],
        project_id: int,
    ) -> dict[str, Any]:
        job_id = self.job_service.create_job(job_type, input_payload, project_id=project_id)
        try:
            result = action(job_id)
            self.job_service.complete_job(
                job_id,
                summary=result["summary"],
                report_payload=result.get("report"),
                artifact_path=result.get("artifact_path"),
            )
        except Exception as exc:
            self.job_service.fail_job(job_id, str(exc))
            raise
        return self.get_job_detail(job_id)
