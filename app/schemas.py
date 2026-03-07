from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProjectSummary(BaseModel):
    project_id: int
    name: str
    is_default: bool
    created_at: str


class ProjectSchemaSummary(BaseModel):
    schema_id: int
    project_id: int
    fixed_columns: dict[str, str]
    translation_columns: list[str]
    remark_columns: list[str]
    created_at: str


class StringMembership(BaseModel):
    membership_type: str
    membership_value: str


class StringDetail(BaseModel):
    string_id: int
    project_id: int
    business_key: str
    file_name: str | None = None
    source: str
    translations: dict[str, str | None] = Field(default_factory=dict)
    remarks: dict[str, str | None] = Field(default_factory=dict)
    memberships: list[StringMembership] = Field(default_factory=list)
    deleted_at: str | None = None
    trash_until: str | None = None
    restored_at: str | None = None
    created_at: str
    updated_at: str


class DevVersionSummary(BaseModel):
    project_id: int
    version: str
    version_line: str
    is_candidate_release: bool
    member_count: int
    created_at: str
    promoted_at: str | None = None


class DevVersionDetail(DevVersionSummary):
    members: list[StringDetail] = Field(default_factory=list)


class ImportBatchSummary(BaseModel):
    import_batch_id: int
    created_at: str
    meta: dict[str, Any] = Field(default_factory=dict)
    rows_scanned: int
    files_scanned: int
    issues: int


class ReportPayload(BaseModel):
    summary: dict[str, Any] = Field(default_factory=dict)
    rows: list[dict[str, Any]] = Field(default_factory=list)


class JobSummary(BaseModel):
    job_id: int
    job_type: str
    status: str
    input: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    report_path: str | None = None
    artifact_path: str | None = None
    error_message: str | None = None
    created_at: str
    finished_at: str | None = None


class JobDetail(BaseModel):
    job: JobSummary
    report: ReportPayload


class SampleOption(BaseModel):
    sample_id: str
    label: str
    description: str
    lang: str
    dev_version: str
    active_hotfix: dict[str, Any] = Field(default_factory=dict)
    passive_hotfix: dict[str, Any] = Field(default_factory=dict)
    trash_keys: list[str] = Field(default_factory=list)
    paths: dict[str, str] = Field(default_factory=dict)


class PromotePreview(BaseModel):
    version: str
    version_line: str
    target_key_count: int
    added_to_rel_count: int
    already_in_rel_count: int
    removed_from_rel_count: int
    cleanup_dev_membership_count: int
    report_rows: list[dict[str, Any]] = Field(default_factory=list)


class StateResponse(BaseModel):
    project: ProjectSummary
    schema: ProjectSchemaSummary
    rel_summary: dict[str, Any] = Field(default_factory=dict)
    candidate_dev_version: DevVersionSummary | None = None
    dev_versions: list[DevVersionSummary] = Field(default_factory=list)
    trash_count: int
    imports: list[ImportBatchSummary] = Field(default_factory=list)
    jobs: list[JobSummary] = Field(default_factory=list)
    samples: list[SampleOption] = Field(default_factory=list)


class ImportDirectoryRequest(BaseModel):
    input_dir: str


class DevImportRequest(BaseModel):
    import_batch_id: int
    version: str
    mark_as_candidate: bool = True


class RelHotfixActiveRequest(BaseModel):
    business_key: str
    lang: str
    target_text: str


class RelHotfixPassiveRequest(BaseModel):
    business_key: str
    source: str
    translations_by_lang: dict[str, str] = Field(default_factory=dict)
    remarks_by_key: dict[str, str] = Field(default_factory=dict)
    file_name: str | None = None


class PromotePreviewRequest(BaseModel):
    version: str


class PromoteExecuteRequest(BaseModel):
    version: str


class TrashDeleteRequest(BaseModel):
    business_keys: list[str]


class TrashRestoreRequest(BaseModel):
    business_keys: list[str]


class FillRequest(BaseModel):
    source_dir: str
    lang: str
    output_name: str | None = None


class QaRequest(BaseModel):
    source_dir: str
    lang: str
