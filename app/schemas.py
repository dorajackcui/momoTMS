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
