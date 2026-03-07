from __future__ import annotations

from typing import Any, Callable

from app.services.demo_service import DemoService
from app.services.dev_version_service import DevVersionService
from app.services.fill_service import FillService
from app.services.import_service import ImportService
from app.services.job_service import JobService
from app.services.project_service import ProjectService
from app.services.promote_service import PromoteService
from app.services.qa_scan_service import QaScanService
from app.services.rel_service import RelService
from app.services.string_service import StringService
from app.services.trash_service import TrashService


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

    def get_state(self) -> dict[str, Any]:
        return {
            "project": self.project_service.get_default_project(),
            "schema": self.project_service.get_schema(),
            "rel_summary": self.rel_service.summary(),
            "candidate_dev_version": self.dev_version_service.get_candidate_release(),
            "dev_versions": self.dev_version_service.list_versions(active_only=True),
            "trash_count": self.string_service.trash_count(),
            "imports": self.import_service.list_batches(),
            "jobs": self.job_service.list_jobs(),
            "samples": self.demo_service.list_samples(),
        }

    def import_directory(self, input_dir: str) -> dict[str, Any]:
        return self._run_job(
            "import_directory",
            {"input_dir": input_dir},
            lambda _job_id: self._import_action(input_dir),
        )

    def dev_import(
        self,
        import_batch_id: int,
        version: str,
        mark_as_candidate: bool = True,
    ) -> dict[str, Any]:
        return self._run_job(
            "dev_import",
            {
                "import_batch_id": import_batch_id,
                "version": version,
                "mark_as_candidate": mark_as_candidate,
            },
            lambda _job_id: self._dev_import_action(import_batch_id, version, mark_as_candidate),
        )

    def active_hotfix(self, business_key: str, lang: str, target_text: str) -> dict[str, Any]:
        return self._run_job(
            "rel_hotfix_active",
            {
                "business_key": business_key,
                "lang": lang,
                "target_text": target_text,
            },
            lambda _job_id: self._wrap_report(
                self.rel_service.active_hotfix(business_key, lang, target_text)
            ),
        )

    def passive_hotfix(
        self,
        business_key: str,
        source: str,
        translations_by_lang: dict[str, str],
        remarks_by_key: dict[str, str],
        file_name: str | None = None,
    ) -> dict[str, Any]:
        return self._run_job(
            "rel_hotfix_passive",
            {
                "business_key": business_key,
                "source": source,
                "translations_by_lang": translations_by_lang,
                "remarks_by_key": remarks_by_key,
                "file_name": file_name,
            },
            lambda _job_id: self._wrap_report(
                self.rel_service.passive_hotfix(
                    business_key,
                    source,
                    translations_by_lang,
                    remarks_by_key,
                    file_name=file_name,
                )
            ),
        )

    def preview_promote(self, version: str) -> dict[str, Any]:
        return self.promote_service.preview(version)

    def execute_promote(self, version: str) -> dict[str, Any]:
        return self._run_job(
            "promote_execute",
            {"version": version},
            lambda _job_id: self._wrap_report(self.promote_service.execute(version)),
        )

    def trash_delete(self, business_keys: list[str]) -> dict[str, Any]:
        return self._run_job(
            "trash_delete",
            {"business_keys": business_keys},
            lambda _job_id: self._wrap_report(self.trash_service.delete(business_keys)),
        )

    def trash_restore(self, business_keys: list[str]) -> dict[str, Any]:
        return self._run_job(
            "trash_restore",
            {"business_keys": business_keys},
            lambda _job_id: self._wrap_report(self.trash_service.restore(business_keys)),
        )

    def fill(self, source_dir: str, lang: str, output_name: str | None = None) -> dict[str, Any]:
        return self._run_job(
            "fill_export",
            {
                "source_dir": source_dir,
                "lang": lang,
                "output_name": output_name,
            },
            lambda job_id: self._fill_action(job_id, source_dir, lang, output_name),
        )

    def qa(self, source_dir: str, lang: str) -> dict[str, Any]:
        return self._run_job(
            "qa_report",
            {
                "source_dir": source_dir,
                "lang": lang,
            },
            lambda _job_id: self._qa_action(source_dir, lang),
        )

    def get_job_detail(self, job_id: int) -> dict[str, Any]:
        return {
            "job": self.job_service.get_job(job_id),
            "report": self.job_service.get_report(job_id),
        }

    def _import_action(self, input_dir: str) -> dict[str, Any]:
        summary = self.import_service.import_directory(input_dir)
        report = self.import_service.import_report(summary["import_batch_id"], issues_only=False)
        return {"summary": summary, "report": report}

    def _dev_import_action(
        self,
        import_batch_id: int,
        version: str,
        mark_as_candidate: bool,
    ) -> dict[str, Any]:
        result = self.dev_version_service.import_batch(import_batch_id, version, mark_as_candidate)
        return self._wrap_report(result)

    def _fill_action(
        self,
        job_id: int,
        source_dir: str,
        lang: str,
        output_name: str | None,
    ) -> dict[str, Any]:
        artifact_name = output_name or "filled_export.zip"
        artifact_path = str(self.job_service.artifact_path(job_id, artifact_name))
        work_dir = str(self.job_service.job_dir(job_id) / "fill_output")
        result = self.fill_service.fill_and_export(source_dir, artifact_path, lang, work_dir=work_dir)
        summary = {
            "filled_count": result["filled_count"],
            "miss_key_count": result["miss_key_count"],
            "src_mismatch_count": result["src_mismatch_count"],
            "kept_original_count": result["kept_original_count"],
            "output_zip": artifact_path,
        }
        return {
            "summary": summary,
            "report": {"summary": summary, "rows": result["report_rows"]},
            "artifact_path": artifact_path,
        }

    def _qa_action(self, source_dir: str, lang: str) -> dict[str, Any]:
        result = self.qa_scan_service.scan_directory(source_dir, lang)
        summary = {
            "scanned_rows": result["scanned_rows"],
            "issue_count": result["issue_count"],
            "rule_counts": result["rule_counts"],
        }
        return {
            "summary": summary,
            "report": {"summary": summary, "rows": result["report_rows"]},
        }

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
    ) -> dict[str, Any]:
        job_id = self.job_service.create_job(job_type, input_payload)
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
