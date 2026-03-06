from __future__ import annotations

import inspect
from typing import Any, Callable

from app.services.archive_service import ArchiveService
from app.services.branch_service import BranchService
from app.services.delete_service import DeleteService
from app.services.demo_service import DemoService
from app.services.fill_service import FillService
from app.services.import_service import ImportService
from app.services.job_service import JobService
from app.services.promote_service import PromoteService
from app.services.qa_scan_service import QaScanService
from app.services.snapshot_service import SnapshotService
from app.services.update_service import UpdateService


class WorkbenchService:
    def __init__(self) -> None:
        self.archive = ArchiveService()
        self.branches = BranchService()
        self.delete = DeleteService()
        self.demo = DemoService()
        self.fill = FillService()
        self.imports = ImportService()
        self.jobs = JobService()
        self.promote = PromoteService()
        self.qa = QaScanService()
        self.snapshots = SnapshotService()
        self.updates = UpdateService()

    def get_state(self) -> dict[str, Any]:
        return {
            "branches": {
                branch: self._branch_state(branch)
                for branch in ("dev", "release", "master")
            },
            "samples": self.demo.list_samples(),
            "imports": self.imports.list_batches(),
            "jobs": self.jobs.list_jobs(),
        }

    def import_sample(self, sample_id: str) -> dict[str, Any]:
        sample = self.demo.get_sample(sample_id)
        result = self.imports.import_directory(
            sample["paths"]["import_dir"],
            sample["lang"],
            sample["target_col_index"],
        )
        result["issues_list"] = self.imports.import_report(result["import_batch_id"])
        result["imports"] = self.imports.list_batches()
        return result

    def update_dev(self, sample_id: str) -> dict[str, Any]:
        sample = self.demo.get_sample(sample_id)
        parent_snapshot_id = self.branches.get_head("dev")

        def action() -> dict[str, Any]:
            snapshot_id = self.updates.update_dev_from_directory(
                sample["paths"]["import_dir"],
                sample["lang"],
                sample["update_dev_version"],
                parent_snapshot_id,
                sample["target_col_index"],
            )
            self.branches.set_head("dev", snapshot_id)
            summary = self._snapshot_delta_summary(parent_snapshot_id, snapshot_id)
            report_rows = summary.pop("report_rows")
            return {
                "snapshot_id": snapshot_id,
                "summary": summary,
                "report": {"summary": summary, "rows": report_rows},
            }

        return self._run_job(
            "update_dev",
            {
                "sample_id": sample_id,
                "parent_snapshot_id": parent_snapshot_id,
                "version_tag": sample["update_dev_version"],
            },
            action,
        )

    def active_hotfix(self, payload: dict[str, Any]) -> dict[str, Any]:
        release_snapshot_id = self._require_head("release")

        def action() -> dict[str, Any]:
            snapshot_id = self.updates.update_release_active_single(
                release_snapshot_id,
                payload["key"],
                payload["lang"],
                payload["target_text"],
            )
            self.branches.set_head("release", snapshot_id)
            summary = {
                "key": payload["key"],
                "lang": payload["lang"],
                "snapshot_id": snapshot_id,
            }
            report = {
                "summary": summary,
                "rows": [
                    {
                        "key": payload["key"],
                        "lang": payload["lang"],
                        "status": "UPDATED_TARGET",
                    }
                ],
            }
            return {"snapshot_id": snapshot_id, "summary": summary, "report": report}

        return self._run_job(
            "active_hotfix",
            {
                "release_snapshot_id": release_snapshot_id,
                **payload,
            },
            action,
        )

    def passive_hotfix(self, payload: dict[str, Any]) -> dict[str, Any]:
        release_snapshot_id = self._require_head("release")

        def action() -> dict[str, Any]:
            snapshot_id = self.updates.update_release_passive_single(
                release_snapshot_id,
                payload["key"],
                payload["src"],
                payload["targets_by_lang"],
                payload["version_tag"],
            )
            self.branches.set_head("release", snapshot_id)
            summary = {
                "key": payload["key"],
                "snapshot_id": snapshot_id,
                "updated_languages": sorted(payload["targets_by_lang"]),
            }
            report = {
                "summary": summary,
                "rows": [
                    {
                        "key": payload["key"],
                        "lang": lang,
                        "status": "UPSERTED_TARGET",
                    }
                    for lang in sorted(payload["targets_by_lang"])
                ],
            }
            return {"snapshot_id": snapshot_id, "summary": summary, "report": report}

        return self._run_job(
            "passive_hotfix",
            {
                "release_snapshot_id": release_snapshot_id,
                **payload,
            },
            action,
        )

    def preview_promote(self, release_version: str) -> dict[str, Any]:
        dev_last = self._require_head("dev")
        current_release = self._require_head("release")
        preview = self.promote.preview(dev_last, current_release)
        preview["dev_last_snapshot_id"] = dev_last
        preview["current_release_snapshot_id"] = current_release
        preview["release_version"] = release_version
        return preview

    def execute_promote(self, release_version: str) -> dict[str, Any]:
        dev_last = self._require_head("dev")
        current_release = self._require_head("release")

        def action() -> dict[str, Any]:
            preview = self.promote.preview(dev_last, current_release)
            result = self.promote.promote(dev_last, current_release, release_version)
            snapshot_id = int(result["snapshot_id"])
            self.branches.set_head("release", snapshot_id)
            summary = {
                "target_key_count": result["target_key_count"],
                "added_count": result["added_count"],
                "conflict_src_changed_count": result["conflict_src_changed_count"],
                "carried_over_count": result["carried_over_count"],
                "deprecated_count": result["deprecated_count"],
                "release_version": release_version,
            }
            report = {"summary": summary, "rows": preview["report_rows"]}
            return {"snapshot_id": snapshot_id, "summary": summary, "report": report}

        return self._run_job(
            "promote_execute",
            {
                "dev_last_snapshot_id": dev_last,
                "current_release_snapshot_id": current_release,
                "release_version": release_version,
            },
            action,
        )

    def archive_release(self) -> dict[str, Any]:
        release_snapshot_id = self._require_head("release")
        master_snapshot_id = self._require_head("master")

        def action() -> dict[str, Any]:
            result = self.archive.archive(release_snapshot_id, master_snapshot_id)
            snapshot_id = int(result["snapshot_id"])
            self.branches.set_head("master", snapshot_id)
            summary = {
                "archived_key_count": result["archived_key_count"],
                "added_count": result["added_count"],
                "overwritten_count": result["overwritten_count"],
                "kept_master_only_count": result["kept_master_only_count"],
                "total_key_count": result["total_key_count"],
            }
            report = {"summary": summary, "rows": result["report_rows"]}
            return {"snapshot_id": snapshot_id, "summary": summary, "report": report}

        return self._run_job(
            "archive_release",
            {
                "release_snapshot_id": release_snapshot_id,
                "master_snapshot_id": master_snapshot_id,
            },
            action,
        )

    def delete_keys(self, branch: str, keys: list[str]) -> dict[str, Any]:
        base_snapshot_id = self._require_head(branch)

        def action() -> dict[str, Any]:
            result = self.delete.delete_keys(branch, base_snapshot_id, keys)
            snapshot_id = int(result["snapshot_id"])
            self.branches.set_head(branch, snapshot_id)
            summary = {
                "deleted_count": result["deleted_count"],
                "missing_count": result["missing_count"],
                "remaining_count": result["remaining_count"],
            }
            report = {"summary": summary, "rows": result["report_rows"]}
            return {"snapshot_id": snapshot_id, "summary": summary, "report": report}

        return self._run_job(
            "delete_keys",
            {
                "branch": branch,
                "base_snapshot_id": base_snapshot_id,
                "keys": keys,
            },
            action,
        )

    def fill_sample(self, sample_id: str) -> dict[str, Any]:
        sample = self.demo.get_sample(sample_id)
        release_snapshot_id = self._require_head("release")
        master_snapshot_id = self._require_head("master")

        def action(job_id: int) -> dict[str, Any]:
            output_zip = str(self.jobs.artifact_path(job_id, "filled_export.zip"))
            work_dir = str(self.jobs.job_dir(job_id) / "fill_output")
            result = self.fill.fill_and_export(
                sample["paths"]["fill_dir"],
                output_zip,
                sample["lang"],
                release_snapshot_id,
                master_snapshot_id,
                sample["target_col_index"],
                work_dir=work_dir,
            )
            summary = {
                "filled_count": result["filled_count"],
                "miss_key_count": result["miss_key_count"],
                "src_mismatch_count": result["src_mismatch_count"],
                "kept_original_count": result["kept_original_count"],
            }
            report = {"summary": summary, "rows": result["report_rows"]}
            return {
                "snapshot_id": None,
                "summary": summary,
                "report": report,
                "artifact_path": output_zip,
            }

        return self._run_job(
            "fill_export",
            {
                "sample_id": sample_id,
                "release_snapshot_id": release_snapshot_id,
                "master_snapshot_id": master_snapshot_id,
            },
            action,
        )

    def qa_sample(self, sample_id: str) -> dict[str, Any]:
        sample = self.demo.get_sample(sample_id)

        def action() -> dict[str, Any]:
            result = self.qa.scan_directory(
                sample["paths"]["fill_dir"],
                sample["lang"],
                sample["target_col_index"],
            )
            summary = {
                "scanned_rows": result["scanned_rows"],
                "issue_count": result["issue_count"],
                "rule_counts": result["rule_counts"],
            }
            report = {"summary": summary, "rows": result["report_rows"]}
            return {"snapshot_id": None, "summary": summary, "report": report}

        return self._run_job(
            "qa_report",
            {
                "sample_id": sample_id,
            },
            action,
        )

    def get_job_detail(self, job_id: int) -> dict[str, Any]:
        return {
            "job": self.jobs.get_job(job_id),
            "report": self.jobs.get_report(job_id),
        }

    def _require_head(self, branch: str) -> int:
        snapshot_id = self.branches.get_head(branch)
        if snapshot_id is None:
            raise ValueError(f"branch head not set: {branch}")
        return snapshot_id

    def _branch_state(self, branch: str) -> dict[str, Any]:
        snapshot_id = self.branches.get_head(branch)
        if snapshot_id is None:
            return {
                "branch": branch,
                "snapshot_id": None,
                "action_type": None,
                "created_at": None,
                "parent_snapshot_id": None,
                "key_count": 0,
                "meta": {},
            }
        snapshot = self.snapshots.get_snapshot(snapshot_id)
        if not snapshot:
            raise ValueError(f"branch head points to missing snapshot: {branch} -> {snapshot_id}")
        return {
            "branch": branch,
            "snapshot_id": snapshot["snapshot_id"],
            "action_type": snapshot["action_type"],
            "created_at": snapshot["created_at"],
            "parent_snapshot_id": snapshot["parent_snapshot_id"],
            "key_count": snapshot["key_count"],
            "meta": snapshot["meta"],
        }

    def _snapshot_delta_summary(self, previous_snapshot_id: int | None, current_snapshot_id: int) -> dict[str, Any]:
        previous = self.snapshots.get_snapshot_items(previous_snapshot_id) if previous_snapshot_id else {}
        current = self.snapshots.get_snapshot_items(current_snapshot_id)

        added_keys = sorted(set(current) - set(previous))
        changed_keys = sorted(
            key
            for key in set(current) & set(previous)
            if current[key]["src_hash"] != previous[key]["src_hash"]
        )
        carried_keys = sorted(
            key
            for key in set(current) & set(previous)
            if current[key]["src_hash"] == previous[key]["src_hash"]
        )
        report_rows = [
            {"key": key, "status": "ADDED"} for key in added_keys
        ] + [
            {"key": key, "status": "SRC_CHANGED"} for key in changed_keys
        ] + [
            {"key": key, "status": "CARRIED"} for key in carried_keys
        ]
        return {
            "total_key_count": len(current),
            "added_count": len(added_keys),
            "src_changed_count": len(changed_keys),
            "carried_count": len(carried_keys),
            "report_rows": report_rows,
        }

    def _run_job(
        self,
        job_type: str,
        input_payload: dict[str, Any],
        action: Callable[..., dict[str, Any]],
    ) -> dict[str, Any]:
        job_id = self.jobs.create_job(job_type, input_payload)
        try:
            if inspect.signature(action).parameters:
                result = action(job_id)
            else:
                result = action()
            self.jobs.complete_job(
                job_id,
                summary=result["summary"],
                snapshot_id=result.get("snapshot_id"),
                report_payload=result.get("report"),
                artifact_path=result.get("artifact_path"),
            )
        except Exception as exc:
            self.jobs.fail_job(job_id, str(exc))
            raise
        return self.get_job_detail(job_id)
