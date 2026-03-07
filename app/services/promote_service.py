from __future__ import annotations

from typing import Any

from app.services.dev_version_service import DevVersionService
from app.services.project_service import DEFAULT_PROJECT_ID
from app.services.string_service import StringService


class PromoteService:
    def __init__(self) -> None:
        self.dev_versions = DevVersionService()
        self.strings = StringService()

    def preview(self, version: str, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        version_info = self.dev_versions.get_version(version, project_id)
        target_strings = version_info["members"]
        target_keys = {item["business_key"] for item in target_strings}
        rel_strings = self.strings.get_membership_strings("rel", "current", project_id)
        rel_keys = {item["business_key"] for item in rel_strings}

        added = sorted(target_keys - rel_keys)
        already = sorted(target_keys & rel_keys)
        removed = sorted(rel_keys - target_keys)
        versions_in_line = self.dev_versions.versions_in_line(version_info["version_line"], project_id)
        cleanup_count = 0
        for version_value in versions_in_line:
            cleanup_count += self.strings.membership_count("dev", version_value, project_id)

        report_rows: list[dict[str, Any]] = []
        for key in added:
            report_rows.append({"business_key": key, "status": "ADD_TO_REL"})
        for key in already:
            report_rows.append({"business_key": key, "status": "KEEP_IN_REL"})
        for key in removed:
            report_rows.append({"business_key": key, "status": "REMOVE_FROM_REL"})

        return {
            "version": version,
            "version_line": version_info["version_line"],
            "target_key_count": len(target_keys),
            "added_to_rel_count": len(added),
            "already_in_rel_count": len(already),
            "removed_from_rel_count": len(removed),
            "cleanup_dev_membership_count": cleanup_count,
            "report_rows": report_rows,
        }

    def execute(self, version: str, project_id: int = DEFAULT_PROJECT_ID) -> dict[str, Any]:
        preview = self.preview(version, project_id)
        version_info = self.dev_versions.get_version(version, project_id)
        target_strings = version_info["members"]
        self.strings.clear_rel_memberships(project_id)
        for item in target_strings:
            self.strings.ensure_membership(int(item["string_id"]), "rel", "current")

        versions_in_line = self.dev_versions.versions_in_line(version_info["version_line"], project_id)
        removed_membership_count = self.strings.remove_dev_memberships(versions_in_line, project_id)
        self.dev_versions.mark_promoted(versions_in_line, project_id)
        summary = {
            "version": version,
            "version_line": version_info["version_line"],
            "target_key_count": preview["target_key_count"],
            "added_to_rel_count": preview["added_to_rel_count"],
            "already_in_rel_count": preview["already_in_rel_count"],
            "removed_from_rel_count": preview["removed_from_rel_count"],
            "cleaned_dev_membership_count": removed_membership_count,
        }
        return {"summary": summary, "report_rows": preview["report_rows"]}
