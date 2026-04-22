from __future__ import annotations

from typing import Any, Callable

from app.services.branch.bootstrap import BranchBootstrapService
from app.services.branch.models import BranchRef
from app.services.branch.policy import BranchMutationPolicy
from app.services.branch.mutations import BranchMutationService
from app.services.branch.replace import BranchReplaceService
from app.services.imports.service import ImportService
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.shared.background_jobs import submit_background_job
from app.services.shared.jobs import JobService
from app.services.shared.uploads import UploadSessionService
from app.services.workflows.trash_restore import TrashRestoreService
from app.services.workflows.fill import FillService
from app.services.workflows.pivot_review import PivotReviewService
from app.services.workflows.qa import QaScanService


class WorkflowApplicationService:
    def __init__(self) -> None:
        self.branch_bootstrap_service = BranchBootstrapService()
        self.branch_mutation_service = BranchMutationService()
        self.branch_replace_service = BranchReplaceService()
        self.fill_service = FillService()
        self.import_service = ImportService()
        self.job_service = JobService()
        self.upload_session_service = UploadSessionService()
        self.qa_scan_service = QaScanService()
        self.trash_restore_service = TrashRestoreService()
        self.pivot_review_service = PivotReviewService()

    def import_directory(self, input_dir: str, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        self.import_service.projects.require_project(project_id)
        return self._run_job_async(
            "import_directory",
            {"input_dir": input_dir, "project_id": project_id},
            lambda _job_id: self._import_action(input_dir, project_id=project_id),
            project_id=project_id,
        )

    def preview_import_staged_folder(
        self,
        input_dir: str,
        upload_session_id: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.import_service.projects.require_project(project_id)
        preview = self.import_service.preview_directory(input_dir, project_id=project_id)
        preview["upload_session_id"] = upload_session_id
        return preview

    def import_uploaded_session(
        self,
        upload_session_id: str,
        project_id: int = DEFAULT_PROJECT_ID,
        mapping_overrides: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self.import_service.projects.require_project(project_id)
        self.upload_session_service.require_session(upload_session_id, project_id)
        return self._run_job_async(
            "import_upload_folder",
            {
                "upload_session_id": upload_session_id,
                "mapping_override_count": len(mapping_overrides or {}),
                "project_id": project_id,
            },
            lambda job_id: self._import_action(
                self.upload_session_service.consume_session_into_job(
                    upload_session_id,
                    job_id,
                    project_id,
                    "import_bundle",
                ),
                project_id=project_id,
                mapping_overrides=mapping_overrides,
            ),
            project_id=project_id,
        )

    def branch_mutation(
        self,
        branch_ref: str,
        input_payload: dict[str, Any],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        self.branch_mutation_service.projects.require_project(project_id)
        parsed_branch_ref = BranchRef.parse(branch_ref)
        BranchMutationPolicy.for_branch(parsed_branch_ref).validate_input_kind(str(input_payload["kind"]))
        if str(input_payload["kind"]) == "import_batch":
            return self._run_streaming_job_async(
                "branch_mutation",
                {
                    "branch_ref": branch_ref,
                    "input": input_payload,
                    "project_id": project_id,
                },
                lambda: self.branch_mutation_service.apply_streaming(
                    parsed_branch_ref,
                    input_payload,
                    project_id=project_id,
                ),
                project_id=project_id,
            )
        return self._run_job(
            "branch_mutation",
            {
                "branch_ref": branch_ref,
                "input": input_payload,
                "project_id": project_id,
            },
            lambda _job_id: self._wrap_report(
                self.branch_mutation_service.apply(
                    parsed_branch_ref,
                    input_payload,
                    project_id=project_id,
                )
            ),
            project_id=project_id,
        )

    def branch_bootstrap(
        self,
        branch_ref: str,
        import_batch_id: int,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        parsed_branch_ref = BranchRef.parse(branch_ref)
        if not parsed_branch_ref.is_dev:
            raise ValueError(f"bootstrap only supports dev branches: {parsed_branch_ref}")
        self.branch_bootstrap_service.projects.require_project(project_id)
        self.branch_bootstrap_service.imports.require_batch_project(import_batch_id, project_id)
        self.branch_bootstrap_service.registry.ensure_dev_branch(
            parsed_branch_ref.branch_value,
            project_id=project_id,
        )
        self.branch_bootstrap_service.registry.require_not_bootstrapped(
            parsed_branch_ref.branch_value,
            project_id=project_id,
        )
        job_id = self.job_service.create_job(
            "branch_bootstrap",
            {
                "branch_ref": branch_ref,
                "input_kind": "bootstrap",
                "import_batch_id": int(import_batch_id),
                "project_id": project_id,
            },
            project_id=project_id,
        )

        def run() -> None:
            try:
                self.branch_bootstrap_service.bootstrap(
                    parsed_branch_ref,
                    import_batch_id,
                    project_id=project_id,
                    job_id=job_id,
                )
            except Exception as exc:
                self.job_service.fail_job(job_id, str(exc))

        submit_background_job(run)
        return self.get_job_detail(job_id, project_id=project_id)

    def branch_replace_preview(
        self,
        source_branch_ref: str,
        target_branch_ref: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        return self.branch_replace_service.preview(
            BranchRef.parse(source_branch_ref),
            BranchRef.parse(target_branch_ref),
            project_id=project_id,
        )

    def branch_replace_execute(
        self,
        source_branch_ref: str,
        target_branch_ref: str,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        return self._run_job(
            "branch_replace_execute",
            {
                "source_branch_ref": source_branch_ref,
                "target_branch_ref": target_branch_ref,
                "project_id": project_id,
            },
            lambda _job_id: self._wrap_report(
                self.branch_replace_service.execute(
                    BranchRef.parse(source_branch_ref),
                    BranchRef.parse(target_branch_ref),
                    project_id=project_id,
                )
            ),
            project_id=project_id,
        )

    def trash_delete(
        self,
        branch_ref: str,
        business_keys: list[str],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        return self._run_job(
            "trash_delete",
            {"branch_ref": branch_ref, "business_keys": business_keys, "project_id": project_id},
            lambda _job_id: self._wrap_report(
                self.trash_restore_service.delete(
                    BranchRef.parse(branch_ref),
                    business_keys,
                    project_id=project_id,
                )
            ),
            project_id=project_id,
        )

    def trash_restore(
        self,
        variant_ids: list[int],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        return self._run_job(
            "trash_restore",
            {"variant_ids": variant_ids, "project_id": project_id},
            lambda _job_id: self._wrap_report(
                self.trash_restore_service.restore(
                    variant_ids,
                    project_id=project_id,
                )
            ),
            project_id=project_id,
        )

    def pivot_review(
        self,
        branch_ref: str,
        variant_ids: list[int],
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        parsed_branch_ref = BranchRef.parse(branch_ref)
        return self._run_job(
            "pivot_review",
            {"branch_ref": branch_ref, "variant_ids": variant_ids, "project_id": project_id},
            lambda _job_id: self._wrap_report(
                self.pivot_review_service.review(
                    parsed_branch_ref,
                    variant_ids,
                    project_id=project_id,
                )
            ),
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
            lambda _job_id: self._qa_action(
                self._stage_uploaded_folder(_job_id, files, "qa_source"),
                lang,
                project_id=project_id,
            ),
            project_id=project_id,
        )

    def get_job_detail(self, job_id: int, project_id: int | None = None) -> dict[str, Any]:
        return {
            "job": self.job_service.get_job(job_id, project_id=project_id),
            "report": self.job_service.get_report_preview(job_id, project_id=project_id),
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
        report = self.import_service.import_report(
            summary["import_batch_id"],
            issues_only=False,
            limit=self.job_service.REPORT_PREVIEW_LIMIT,
        )
        return {"summary": summary, "report": report}

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
            "stages": result.get("stages", []),
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
            "stages": result.get("stages", []),
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

    def _run_job_async(
        self,
        job_type: str,
        input_payload: dict[str, Any],
        action: Callable[[int], dict[str, Any]],
        project_id: int,
    ) -> dict[str, Any]:
        job_id = self.job_service.create_job(job_type, input_payload, project_id=project_id)

        def run() -> None:
            try:
                result = action(job_id)
                self.job_service.complete_job(
                    job_id,
                    summary=result["summary"],
                    report_payload=result.get("report"),
                    report_rows=result.get("report_rows"),
                    artifact_path=result.get("artifact_path"),
                )
            except Exception as exc:
                self.job_service.fail_job(job_id, str(exc))

        submit_background_job(run)
        return self.get_job_detail(job_id, project_id=project_id)

    def _run_streaming_job_async(
        self,
        job_type: str,
        input_payload: dict[str, Any],
        row_stream_factory: Callable[[], Any],
        project_id: int,
    ) -> dict[str, Any]:
        job_id = self.job_service.create_job(job_type, input_payload, project_id=project_id)

        def run() -> None:
            try:
                self.job_service.complete_job_from_stream(job_id, row_stream_factory())
            except Exception as exc:
                self.job_service.fail_job(job_id, str(exc))

        submit_background_job(run)
        return self.get_job_detail(job_id, project_id=project_id)
