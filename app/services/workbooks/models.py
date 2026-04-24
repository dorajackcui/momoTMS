from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

WorkbookWorkflowKind = Literal[
    "create_branch",
    "branch_mutation",
    "branch_trash",
    "project_trash",
]
WorkbookMutationType = Literal["content", "range"]


@dataclass(frozen=True)
class WorkbookWorkflowContext:
    workflow_kind: WorkbookWorkflowKind
    mutation_type: WorkbookMutationType | None = None

    def required_internal_fields(self) -> list[str]:
        if self.workflow_kind in {"branch_trash", "project_trash"}:
            return ["business_key"]
        return ["business_key", "source"]


@dataclass(frozen=True)
class WorkbookRow:
    file_path: str
    sheet_name: str
    row_index: int
    business_key: str
    source: str
    translations: dict[str, str] = field(default_factory=dict)
    remarks: dict[str, str] = field(default_factory=dict)
    status: str = "ok"
    message: str | None = None


@dataclass(frozen=True)
class WorkbookSheetPreview:
    sheet_key: str
    file_path: str
    sheet_name: str
    available_headers: list[str]
    missing_required_headers: list[str]
    sampled_issue_count: int


@dataclass(frozen=True)
class WorkbookPrecheck:
    file_count: int
    sheet_count: int
    missing_required_headers: list[str]
    sampled_issue_count: int
    sheet_previews: list[WorkbookSheetPreview]
