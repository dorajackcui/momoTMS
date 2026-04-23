from __future__ import annotations

from typing import Annotated, Any, Literal

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
    pivot_language: str | None = None
    pivoted_languages: list[str] = Field(default_factory=list)


class ProjectSchemaSummary(BaseModel):
    schema_id: int
    project_id: int
    fixed_columns: dict[str, str]
    translation_columns: list[str]
    remark_columns: list[str]
    pivot_language: str | None = None
    pivoted_languages: list[str] = Field(default_factory=list)
    created_at: str


class BindingSummary(BaseModel):
    branch_ref: str
    created_at: str
    updated_at: str


class EntryVariantView(BaseModel):
    variant_id: int
    entry_id: int
    project_id: int
    business_key: str
    file_name: str | None = None
    source: str
    translations: dict[str, str | None] = Field(default_factory=dict)
    remarks: dict[str, str | None] = Field(default_factory=dict)
    bindings: list[BindingSummary] = Field(default_factory=list)
    trashed_at: str | None = None
    created_at: str
    updated_at: str


class DevBranchSummary(BaseModel):
    project_id: int
    version: str
    version_series: str
    branch_ref: str
    entry_count: int
    bootstrap_state: Literal["not_bootstrapped", "bootstrapped"] = "not_bootstrapped"
    bootstrapped_at: str | None = None
    bootstrap_job_id: int | None = None
    bootstrap_import_batch_id: int | None = None
    created_at: str


class DevBranchDetail(DevBranchSummary):
    entries: list[EntryVariantView] = Field(default_factory=list)


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

    upload_session_id: str
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


class EffectForecastPreview(BaseModel):
    preview_kind: Literal["effect_forecast"]
    workflow_kind: Literal["branch_bootstrap", "branch_mutation", "branch_replace"]
    request_echo: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    rows: list[dict[str, Any]] = Field(default_factory=list)


class BranchBootstrapPreview(EffectForecastPreview):
    workflow_kind: Literal["branch_bootstrap"]


class BranchMutationPreview(EffectForecastPreview):
    workflow_kind: Literal["branch_mutation"]


class BranchReplacePreview(EffectForecastPreview):
    workflow_kind: Literal["branch_replace"]


class PivotReviewPreview(BaseModel):
    preview_kind: Literal["effect_forecast"]
    workflow_kind: Literal["pivot_review"]
    request_echo: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    rows: list[dict[str, Any]] = Field(default_factory=list)


class ProductStateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    project: ProjectSummary
    project_schema: ProjectSchemaSummary = Field(alias="schema")
    release_summary: dict[str, Any] = Field(default_factory=dict)
    dev_branches: list[DevBranchSummary] = Field(default_factory=list)
    imports: list[ImportBatchSummary] = Field(default_factory=list)
    jobs: list[JobSummary] = Field(default_factory=list)


class BranchSummaryItem(BaseModel):
    branch_ref: str
    entry_count: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    version_series: str | None = None


class BranchListResponse(BaseModel):
    branches: list[BranchSummaryItem] = Field(default_factory=list)


class ScopeRowsResponse(BaseModel):
    scope_ref: str
    rows: list["ProjectVariantRow"] = Field(default_factory=list)
    total_rows: int = 0
    page: int = 1
    page_size: int = 0


class BranchRowsResponse(BaseModel):
    branch_ref: str
    rows: list["ProjectVariantRow"] = Field(default_factory=list)
    total_rows: int = 0
    page: int = 1
    page_size: int = 0


class ScopeLookupResponse(BaseModel):
    scope_ref: str
    mode: Literal["business_key", "source"]
    value: str
    rows: list["ProjectVariantRow"] = Field(default_factory=list)


class BranchLookupResponse(BaseModel):
    branch_ref: str
    mode: Literal["business_key", "source"]
    value: str
    rows: list["ProjectVariantRow"] = Field(default_factory=list)


class BranchSide(BaseModel):
    branch_ref: str
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


class BranchCompareResponse(BaseModel):
    base_branch_ref: str
    target_branch_ref: str
    status_counts: dict[str, int] = Field(default_factory=dict)
    rows: list[BranchCompareRow] = Field(default_factory=list)
    priority_rows: list[TranslationPriorityRow] = Field(default_factory=list)
    total_rows: int = 0
    total_priority_rows: int = 0
    page: int = 1
    page_size: int = 0


class BranchQueueResponse(BaseModel):
    target_branch_ref: str
    lang: str | None = None
    status_counts: dict[str, int] = Field(default_factory=dict)
    rows: list[TranslationPriorityRow] = Field(default_factory=list)
    total_rows: int = 0
    page: int = 1
    page_size: int = 0


class MasterQueryRow(BaseModel):
    business_key: str
    scope_ref: str
    variant_id: int
    file_name: str | None = None
    source: str
    translations: dict[str, str | None] = Field(default_factory=dict)
    remarks: dict[str, str | None] = Field(default_factory=dict)


class MasterEntryResponse(BaseModel):
    business_key: str
    entry_id: int
    results: list[MasterQueryRow] = Field(default_factory=list)


class MasterSearchResponse(BaseModel):
    source: str
    results: list[MasterQueryRow] = Field(default_factory=list)


class ProjectVariantRow(BaseModel):
    variant_id: int
    entry_id: int
    business_key: str
    file_name: str | None = None
    source: str
    translations: dict[str, str | None] = Field(default_factory=dict)
    remarks: dict[str, str | None] = Field(default_factory=dict)
    bindings: list[BindingSummary] = Field(default_factory=list)
    state: Literal["active", "orphan"]
    orphaned_at: str | None = None
    pivot_status: Literal["init", "changed", "reviewed"]
    pivot_changed_by_branch_ref: str | None = None
    pivot_changed_at: str | None = None
    pivot_reviewed_at: str | None = None
    created_at: str
    updated_at: str


class ProjectVariantsResponse(BaseModel):
    rows: list[ProjectVariantRow] = Field(default_factory=list)
    total_rows: int = 0
    page: int = 1
    page_size: int = 0


class SameSourceCandidateRow(BaseModel):
    variant_id: int
    entry_id: int
    business_key: str
    file_name: str | None = None
    source: str
    translations: dict[str, str | None] = Field(default_factory=dict)
    remarks: dict[str, str | None] = Field(default_factory=dict)
    bindings: list[BindingSummary] = Field(default_factory=list)
    state: Literal["active", "orphan"]
    orphaned_at: str | None = None
    pivot_status: Literal["init", "changed", "reviewed"]
    pivot_changed_by_branch_ref: str | None = None
    pivot_changed_at: str | None = None
    pivot_reviewed_at: str | None = None
    created_at: str
    updated_at: str


class SameSourceCandidatesResponse(BaseModel):
    business_key: str
    source: str
    rows: list[SameSourceCandidateRow] = Field(default_factory=list)


class EntryVariantInspection(BaseModel):
    variant_id: int
    file_name: str | None = None
    source: str
    translations: dict[str, str | None] = Field(default_factory=dict)
    remarks: dict[str, str | None] = Field(default_factory=dict)
    bindings: list[BindingSummary] = Field(default_factory=list)
    is_orphaned: bool = False
    is_trashed: bool = False
    orphaned_at: str | None = None
    trashed_at: str | None = None
    pivot_status: Literal["init", "changed", "reviewed"]
    pivot_changed_by_branch_ref: str | None = None
    pivot_changed_at: str | None = None
    pivot_reviewed_at: str | None = None
    created_at: str
    updated_at: str


class EntryVariantsResponse(BaseModel):
    project_id: int
    entry_id: int
    business_key: str
    variants: list[EntryVariantInspection] = Field(default_factory=list)


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


class ImportUploadSessionRequest(BaseModel):
    upload_session_id: str
    column_mapping_json: str | None = None


class BranchMutationChange(BaseModel):
    business_key: str
    source: str | None = None
    translations_by_lang: dict[str, str] = Field(default_factory=dict)
    remarks_by_key: dict[str, str] = Field(default_factory=dict)
    file_name: str | None = None


class BranchDirectMutationInput(BaseModel):
    kind: Literal["direct"]
    changes: list[BranchMutationChange] = Field(default_factory=list)


class BranchImportBatchMutationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["import_batch"]
    import_batch_id: int


BranchMutationInput = Annotated[
    BranchDirectMutationInput | BranchImportBatchMutationInput,
    Field(discriminator="kind"),
]


class BranchMutationRequest(BaseModel):
    branch_ref: str
    input: BranchMutationInput


class BranchReplaceRequest(BaseModel):
    source_branch_ref: str
    target_branch_ref: str


class BranchBootstrapRequest(BaseModel):
    branch_ref: str
    import_batch_id: int


class BranchTrashDeleteRequest(BaseModel):
    branch_ref: str
    business_keys: list[str]


class ProjectTrashRequest(BaseModel):
    business_keys: list[str]

class PivotReviewRequest(BaseModel):
    branch_ref: str
    variant_ids: list[int] = Field(default_factory=list)


class FillRequest(BaseModel):
    source_dir: str
    lang: str
    output_name: str | None = None


class QaRequest(BaseModel):
    source_dir: str
    lang: str
