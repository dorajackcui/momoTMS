from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ImportRequest(BaseModel):
    input_dir: str = Field(..., description="Directory containing Excel files")
    lang: str
    target_col_index: int = 3


class ImportResponse(BaseModel):
    import_batch_id: int
    files_scanned: int
    rows_scanned: int
    issues: int


class SnapshotCreateRequest(BaseModel):
    branch: Literal["dev", "release", "master"]
    parent_snapshot_id: int | None = None
    action_type: str
    meta: dict[str, Any] = Field(default_factory=dict)


class SnapshotResponse(BaseModel):
    snapshot_id: int
    branch: str
    action_type: str


class PromoteRequest(BaseModel):
    dev_last_snapshot_id: int
    current_release_snapshot_id: int
    release_version: str


class PromoteReport(BaseModel):
    snapshot_id: int
    target_key_count: int
    added_count: int
    conflict_src_changed_count: int
    carried_over_count: int
    deprecated_count: int


class PromotePreview(BaseModel):
    dev_last_snapshot_id: int
    current_release_snapshot_id: int
    release_version: str
    target_key_count: int
    added_count: int
    conflict_src_changed_count: int
    carried_over_count: int
    deprecated_count: int
    report_rows: list[dict[str, Any]]


class FillRequest(BaseModel):
    source_dir: str
    output_zip: str
    lang: str
    release_snapshot_id: int
    master_snapshot_id: int | None = None
    target_col_index: int = 3


class FillReport(BaseModel):
    filled_count: int
    miss_key_count: int
    src_mismatch_count: int
    kept_original_count: int
    report_path: str
    report_rows: list[dict[str, Any]] = Field(default_factory=list)
    output_zip: str | None = None


class ActiveSingleRequest(BaseModel):
    release_snapshot_id: int
    key: str
    lang: str
    target_text: str


class PassiveSingleRequest(BaseModel):
    release_snapshot_id: int
    key: str
    src: str
    version_tag: str
    targets_by_lang: dict[str, str]


class QaIssue(BaseModel):
    file_path: str
    sheet: str
    row: int
    key: str
    lang: str
    rule: str
    src_excerpt: str
    tgt_excerpt: str


class BranchState(BaseModel):
    branch: Literal["dev", "release", "master"]
    snapshot_id: int | None = None
    action_type: str | None = None
    created_at: str | None = None
    parent_snapshot_id: int | None = None
    key_count: int = 0
    meta: dict[str, Any] = Field(default_factory=dict)


class SampleOption(BaseModel):
    sample_id: str
    label: str
    description: str
    lang: str
    target_col_index: int
    update_dev_version: str
    promote_release_version: str
    active_hotfix: dict[str, Any]
    passive_hotfix: dict[str, Any]
    delete_keys: list[str]


class JobSummary(BaseModel):
    job_id: int
    job_type: str
    status: str
    input: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    report_path: str | None = None
    artifact_path: str | None = None
    snapshot_id: int | None = None
    error_message: str | None = None
    created_at: str
    finished_at: str | None = None


class ReportPayload(BaseModel):
    summary: dict[str, Any] = Field(default_factory=dict)
    rows: list[dict[str, Any]] = Field(default_factory=list)


class JobDetail(BaseModel):
    job: JobSummary
    report: ReportPayload


class WorkbenchState(BaseModel):
    branches: dict[str, BranchState]
    samples: list[SampleOption]
    imports: list[dict[str, Any]]
    jobs: list[JobSummary]


class SampleActionRequest(BaseModel):
    sample_id: str


class WorkbenchActiveHotfixRequest(BaseModel):
    key: str
    lang: str
    target_text: str


class WorkbenchPassiveHotfixRequest(BaseModel):
    key: str
    src: str
    version_tag: str
    targets_by_lang: dict[str, str]


class PromotePreviewRequest(BaseModel):
    release_version: str


class DeleteKeysRequest(BaseModel):
    branch: Literal["dev", "release", "master"] = "release"
    keys: list[str]
