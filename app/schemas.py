from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProjectSummary(BaseModel):
    project_id: int
    name: str
    is_default: bool
    created_at: str


class CreateProjectRequest(BaseModel):
    name: str
    translation_columns: list[str] = Field(default_factory=list)
    remark_columns: list[str] = Field(default_factory=list)


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
    entry_id: int | None = None
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
    project_id: int
    created_at: str
    meta: dict[str, Any] = Field(default_factory=dict)
    rows_scanned: int
    files_scanned: int
    issues: int


class ImportSheetPreview(BaseModel):
    sheet_key: str
    file_path: str
    derived_file_name: str
    sheet_name: str
    available_headers: list[str] = Field(default_factory=list)
    suggested_mapping: dict[str, Any] = Field(default_factory=dict)
    missing_targets: list[str] = Field(default_factory=list)
    auto_match_ready: bool


class ImportUploadPreview(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project_schema: ProjectSchemaSummary = Field(alias="schema")
    file_count: int
    sheet_count: int
    sheet_previews: list[ImportSheetPreview] = Field(default_factory=list)


class ReportPayload(BaseModel):
    summary: dict[str, Any] = Field(default_factory=dict)
    rows: list[dict[str, Any]] = Field(default_factory=list)


class JobSummary(BaseModel):
    job_id: int
    project_id: int
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


class JobStageSummary(BaseModel):
    stage: str
    elapsed_ms: int
    meta: dict[str, Any] = Field(default_factory=dict)


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


class ProductStateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project: ProjectSummary
    project_schema: ProjectSchemaSummary = Field(alias="schema")
    rel_summary: dict[str, Any] = Field(default_factory=dict)
    candidate_dev_version: DevVersionSummary | None = None
    dev_versions: list[DevVersionSummary] = Field(default_factory=list)
    imports: list[ImportBatchSummary] = Field(default_factory=list)
    jobs: list[JobSummary] = Field(default_factory=list)


class CompatStateResponse(ProductStateResponse):
    trash_count: int
    samples: list[SampleOption] = Field(default_factory=list)


class BranchScopeSummary(BaseModel):
    scope_type: str
    scope_value: str
    entry_count: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    version_line: str | None = None
    is_candidate_release: bool | None = None


class ScopeSummaryResponse(BaseModel):
    scopes: list[BranchScopeSummary] = Field(default_factory=list)


class BranchSide(BaseModel):
    scope_type: str
    scope_value: str
    variant_id: int
    file_name: str | None = None
    source: str
    translations: dict[str, str | None] = Field(default_factory=dict)
    remarks: dict[str, str | None] = Field(default_factory=dict)


class TranslationPriorityRow(BaseModel):
    business_key: str
    priority_status: str
    state: str
    diff_categories: list[str] = Field(default_factory=list)
    file_name: str | None = None
    source: str = ""
    target_text: str = ""


class BranchCompareRow(BaseModel):
    business_key: str
    state: str
    diff_categories: list[str] = Field(default_factory=list)
    priority_status: str
    base: BranchSide | None = None
    target: BranchSide | None = None


class BranchCompare(BaseModel):
    base_scope: str
    target_scope: str
    status_counts: dict[str, int] = Field(default_factory=dict)
    rows: list[BranchCompareRow] = Field(default_factory=list)
    priority_rows: list[TranslationPriorityRow] = Field(default_factory=list)
    total_rows: int = 0
    total_priority_rows: int = 0
    page: int = 1
    page_size: int = 0


class TranslationQueueResult(BaseModel):
    target_scope: str
    lang: str | None = None
    status_counts: dict[str, int] = Field(default_factory=dict)
    rows: list[TranslationPriorityRow] = Field(default_factory=list)
    total_rows: int = 0
    page: int = 1
    page_size: int = 0


class MasterQueryRow(BaseModel):
    business_key: str
    scope_type: str
    scope_value: str
    variant_id: int
    file_name: str | None = None
    source: str
    translations: dict[str, str | None] = Field(default_factory=dict)
    remarks: dict[str, str | None] = Field(default_factory=dict)


class MasterEntryResult(BaseModel):
    business_key: str
    entry_id: int
    results: list[MasterQueryRow] = Field(default_factory=list)


class MasterSearchResult(BaseModel):
    source: str
    results: list[MasterQueryRow] = Field(default_factory=list)


class VariantBindingSummary(BaseModel):
    scope_type: str
    scope_value: str
    created_at: str
    updated_at: str


class LastActiveScopeSummary(BaseModel):
    scope_type: str
    scope_value: str


class EntryVariantInspection(BaseModel):
    variant_id: int
    file_name: str | None = None
    source: str
    translations: dict[str, str | None] = Field(default_factory=dict)
    remarks: dict[str, str | None] = Field(default_factory=dict)
    bindings: list[VariantBindingSummary] = Field(default_factory=list)
    is_retained: bool = False
    is_orphaned: bool = False
    is_trashed: bool = False
    orphaned_at: str | None = None
    trashed_at: str | None = None
    trash_until: str | None = None
    restored_at: str | None = None
    last_active_scope: LastActiveScopeSummary | None = None
    created_at: str
    updated_at: str


class EntryVariantsResponse(BaseModel):
    project_id: int
    entry_id: int
    business_key: str
    variants: list[EntryVariantInspection] = Field(default_factory=list)


class RetainedVariantSummary(BaseModel):
    project_id: int
    entry_id: int
    business_key: str
    variant_id: int
    file_name: str | None = None
    source: str
    translations: dict[str, str | None] = Field(default_factory=dict)
    remarks: dict[str, str | None] = Field(default_factory=dict)
    last_active_scope: LastActiveScopeSummary
    retained_at: str
    updated_at: str


class RetainedVariantsResponse(BaseModel):
    project_id: int
    results: list[RetainedVariantSummary] = Field(default_factory=list)


class OrphanVariantSummary(BaseModel):
    project_id: int
    entry_id: int
    business_key: str
    variant_id: int
    file_name: str | None = None
    source: str
    translations: dict[str, str | None] = Field(default_factory=dict)
    remarks: dict[str, str | None] = Field(default_factory=dict)
    orphaned_at: str
    updated_at: str


class OrphanVariantsResponse(BaseModel):
    project_id: int
    results: list[OrphanVariantSummary] = Field(default_factory=list)


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


class ScopedTrashDeleteRequest(BaseModel):
    scope_ref: str
    business_keys: list[str]


class VariantTrashRestoreRequest(BaseModel):
    variant_ids: list[int]


class PromotePreviewRequest(BaseModel):
    version: str


class PromoteExecuteRequest(BaseModel):
    version: str


class FillRequest(BaseModel):
    source_dir: str
    lang: str
    output_name: str | None = None


class QaRequest(BaseModel):
    source_dir: str
    lang: str
