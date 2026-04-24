# Workbook Intake Branch Workflows Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a workbook-upload write path for create branch, branch mutation, branch trash, and project trash while keeping upload transport, workbook parsing, and workflow execution separate.

**Architecture:** Add a project workbook header contract, introduce a neutral workbook intake package that stages/uploads/parses/persists workbook rows, then expose workflow-specific workbook execute APIs that dispatch to bootstrap, mutation, or trash services. The frontend consumes one reusable workbook workflow panel and removes direct TSV and import-batch input choices from product write flows.

**Tech Stack:** FastAPI, Pydantic, SQLite, openpyxl read-only workbooks, pytest, React 19, TypeScript, TanStack Query, Vite, Playwright.

---

## Scope Check

This plan touches backend contracts, backend workflow orchestration, frontend write flows, and docs. These are tightly coupled because the frontend must move to the new workbook workflow API and the old product input methods must be cleaned up at the same time. The work is split into independently testable tasks that should be committed one at a time.

## File Structure

Backend files:

- `app/db.py`: add project schema workbook header fields through `fixed_columns_json`.
- `app/schemas.py`: add request and response models for project creation schema fields and workbook workflow APIs.
- `app/services/project/service.py`: store and return configurable `business_key` and `source` workbook headers.
- `app/services/workbooks/models.py`: new dataclasses and literals for workbook workflow kinds, mutation types, parsed rows, precheck issues, and batch summaries.
- `app/services/workbooks/parser.py`: new workbook parser that reads staged files with workflow-specific required columns and sample-limited validation.
- `app/services/workbooks/batches.py`: new neutral reader/writer over existing `imports` and `import_rows`.
- `app/services/workbooks/intake.py`: new orchestration service for precheck and persisted batch creation.
- `app/services/workbooks/workflows.py`: new service that runs one async job for intake plus target workflow.
- `app/services/branch/content_batch_mutation.py`: new content-only batch mutation applier.
- `app/services/branch/mutations.py`: wire content-vs-range batch mutation execution.
- `app/services/workflows/trash.py`: add batch-backed trash entrypoints.
- `app/services/workflows/application.py`: delegate workbook workflow execution.
- `app/routers/workbook_workflows.py`: new public workbook workflow routes.
- `app/main.py`: include the new router.

Frontend files:

- `frontend/src/domains/workbooks/types.ts`: new workbook workflow API types.
- `frontend/src/domains/workbooks/api.ts`: new preview and execute API calls.
- `frontend/src/shared/ui/WorkbookWorkflowPanel.tsx`: reusable upload/precheck/execute panel.
- `frontend/src/shared/ui/WorkbookWorkflowPanel.module.css`: panel styling.
- `frontend/src/pages/dev/CreateBranch.tsx`: replace page-specific import/bootstrap flow.
- `frontend/src/shared/ui/EditPanel.tsx`: replace Direct/Import batch controls with workbook mutation controls.
- `frontend/src/pages/release/ReleasePage.tsx`: ensure Release edit uses the new edit panel.
- `frontend/src/shared/ui/TrashPanel.tsx`: replace textarea key entry with workbook workflow panel.
- `frontend/src/domains/branches/types.ts`: remove frontend dependency on product-facing direct/import-batch mutation input where no longer used.
- `frontend/src/domains/branches/api.ts`: remove or stop using old mutation input helpers from product flows.

Tests and docs:

- `tests/test_workbook_intake.py`: new parser/intake/service tests.
- `tests/test_branch_service.py`: content-batch mutation and trash-batch service coverage.
- `tests/test_variant_api.py`: workbook workflow route coverage.
- `tests/e2e/product-app.spec.js`: update user-facing write-flow tests.
- `docs/contracts.md`: update public route and request contract.
- `docs/workflows.md`: update workbook workflow and mutation semantics.
- `docs/README.md`: update only if owner-doc routing changes; this plan does not require that.

---

### Task 1: Project Workbook Header Contract

**Files:**

- Modify: `app/schemas.py`
- Modify: `app/services/project/service.py`
- Test: `tests/test_variant_api.py`

- [ ] **Step 1: Add failing API test for configured key/source headers**

Append this test near `test_project_creation_and_bootstrap_expose_single_pivot_schema` in `tests/test_variant_api.py`:

```python
def test_project_creation_exposes_workbook_header_contract() -> None:
    reset_demo()

    with TestClient(app) as client:
        create_response = client.post(
            "/api/projects",
            json={
                "name": "Workbook Header Project",
                "business_key_header": "key",
                "source_header": "source_text",
                "translation_columns": ["fr"],
                "remark_columns": ["context"],
            },
        )
        assert create_response.status_code == 200
        project_id = create_response.json()["project_id"]

        state_response = client.get(f"/api/projects/{project_id}/state")
        assert state_response.status_code == 200
        schema = state_response.json()["schema"]

    assert schema["fixed_columns"]["business_key"] == "key"
    assert schema["fixed_columns"]["source"] == "source_text"
    assert schema["translation_columns"] == ["fr"]
    assert schema["remark_columns"] == ["context"]
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_variant_api.py::test_project_creation_exposes_workbook_header_contract
```

Expected: FAIL with a validation error or assertion because `business_key_header` and `source_header` are ignored.

- [ ] **Step 3: Extend create project request schema**

In `app/schemas.py`, update `CreateProjectRequest`:

```python
class CreateProjectRequest(BaseModel):
    name: str
    translation_columns: list[str] = Field(default_factory=list)
    remark_columns: list[str] = Field(default_factory=list)
    pivot_language: str | None = None
    pivoted_languages: list[str] = Field(default_factory=list)
    business_key_header: str = "business_key"
    source_header: str = "source"
```

- [ ] **Step 4: Store configurable fixed columns**

In `app/services/project/service.py`, change `create_project` signature:

```python
def create_project(
    self,
    name: str,
    translation_columns: list[str],
    remark_columns: list[str],
    pivot_language: str | None = None,
    pivoted_languages: list[str] | None = None,
    business_key_header: str = "business_key",
    source_header: str = "source",
) -> dict[str, Any]:
```

Inside the method, after `normalized_remark_columns`, add:

```python
        fixed_columns = {
            "file_name": "file_name",
            "business_key": normalize_non_content_value(business_key_header) or "business_key",
            "source": normalize_non_content_value(source_header) or "source",
        }
        if fixed_columns["business_key"] == fixed_columns["source"]:
            raise ValueError("business_key_header and source_header must be distinct")
```

Replace:

```python
        fixed_names = set(self.FIXED_COLUMNS.values())
```

with:

```python
        fixed_names = set(fixed_columns.values())
```

Replace:

```python
                    _json_dumps(self.FIXED_COLUMNS),
```

with:

```python
                    _json_dumps(fixed_columns),
```

- [ ] **Step 5: Pass request fields from router path**

In `app/routers/projects_state.py`, find the `ProjectService().create_project(...)` call and pass:

```python
business_key_header=payload.business_key_header,
source_header=payload.source_header,
```

The final call should include:

```python
ProjectService().create_project(
    payload.name,
    payload.translation_columns,
    payload.remark_columns,
    payload.pivot_language,
    payload.pivoted_languages,
    business_key_header=payload.business_key_header,
    source_header=payload.source_header,
)
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_variant_api.py::test_project_creation_exposes_workbook_header_contract tests\test_variant_api.py::test_project_creation_and_bootstrap_expose_single_pivot_schema
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```powershell
git add app/schemas.py app/services/project/service.py app/routers/projects_state.py tests/test_variant_api.py
git commit -m "feat: store workbook header contract"
```

---

### Task 2: Workbook Parser And Precheck

**Files:**

- Create: `app/services/workbooks/__init__.py`
- Create: `app/services/workbooks/models.py`
- Create: `app/services/workbooks/parser.py`
- Test: `tests/test_workbook_intake.py`

- [ ] **Step 1: Add failing parser tests**

Create `tests/test_workbook_intake.py` with:

```python
from pathlib import Path

from openpyxl import Workbook

from app.services.demo.service import DemoService
from app.services.project.service import ProjectService
from app.services.workbooks.models import WorkbookWorkflowContext
from app.services.workbooks.parser import WorkbookParser


def reset_demo() -> None:
    DemoService().reset()


def write_workbook(root: Path, relative_path: str, rows: list[list[object]]) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    for row in rows:
        sheet.append(row)
    output = root / relative_path
    output.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output)
    workbook.close()
    return output


def test_parser_uses_project_workbook_headers(tmp_path) -> None:
    reset_demo()
    project = ProjectService().create_project(
        "Parser Contract Project",
        ["fr"],
        ["context"],
        business_key_header="key",
        source_header="source_text",
    )
    root = tmp_path / "input"
    write_workbook(
        root,
        "bundle/messages.xlsx",
        [
            ["key", "source_text", "fr", "context"],
            ["hello.key", "Hello", "Bonjour", "Greeting"],
        ],
    )

    context = WorkbookWorkflowContext(workflow_kind="create_branch")
    preview = WorkbookParser().precheck_directory(root, int(project["project_id"]), context)
    rows = list(WorkbookParser().iter_rows(root, int(project["project_id"]), context))

    assert preview.missing_required_headers == []
    assert preview.file_count == 1
    assert preview.sheet_count == 1
    assert rows[0].business_key == "hello.key"
    assert rows[0].source == "Hello"
    assert rows[0].translations == {"fr": "Bonjour"}
    assert rows[0].remarks == {"context": "Greeting"}


def test_trash_parser_requires_key_only(tmp_path) -> None:
    reset_demo()
    project = ProjectService().create_project(
        "Trash Parser Project",
        ["fr"],
        ["context"],
        business_key_header="key",
        source_header="source_text",
    )
    root = tmp_path / "trash"
    write_workbook(root, "trash.xlsx", [["key"], ["obsolete.key"]])

    context = WorkbookWorkflowContext(workflow_kind="branch_trash")
    preview = WorkbookParser().precheck_directory(root, int(project["project_id"]), context)
    rows = list(WorkbookParser().iter_rows(root, int(project["project_id"]), context))

    assert preview.missing_required_headers == []
    assert rows[0].business_key == "obsolete.key"
    assert rows[0].source == ""


def test_content_mutation_parser_requires_source(tmp_path) -> None:
    reset_demo()
    project = ProjectService().create_project(
        "Content Parser Project",
        ["fr"],
        ["context"],
        business_key_header="key",
        source_header="source_text",
    )
    root = tmp_path / "content"
    write_workbook(root, "content.xlsx", [["key", "fr"], ["hello.key", "Bonjour"]])

    context = WorkbookWorkflowContext(workflow_kind="branch_mutation", mutation_type="content")
    preview = WorkbookParser().precheck_directory(root, int(project["project_id"]), context)

    assert preview.missing_required_headers == ["source_text"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_workbook_intake.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.workbooks'`.

- [ ] **Step 3: Add workbook models**

Create `app/services/workbooks/__init__.py` as an empty file.

Create `app/services/workbooks/models.py`:

```python
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
```

- [ ] **Step 4: Add parser implementation**

Create `app/services/workbooks/parser.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

from openpyxl import load_workbook

from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.shared.io import normalize_content_value, normalize_non_content_value
from app.services.workbooks.models import (
    WorkbookPrecheck,
    WorkbookRow,
    WorkbookSheetPreview,
    WorkbookWorkflowContext,
)


class WorkbookParser:
    SAMPLE_ROW_LIMIT = 50

    def __init__(self, projects: ProjectService | None = None) -> None:
        self.projects = projects or ProjectService()

    def precheck_directory(
        self,
        input_dir: str | Path,
        project_id: int = DEFAULT_PROJECT_ID,
        context: WorkbookWorkflowContext | None = None,
    ) -> WorkbookPrecheck:
        context = context or WorkbookWorkflowContext(workflow_kind="create_branch")
        base = Path(input_dir)
        files = self._list_workbooks(base)
        sheet_previews: list[WorkbookSheetPreview] = []
        all_missing: list[str] = []
        sampled_issue_count = 0

        for file_path in files:
            rel_path = self._relative_path(base, file_path)
            workbook = load_workbook(filename=file_path, read_only=True, data_only=True)
            try:
                for sheet in workbook.worksheets:
                    row_iter = sheet.iter_rows(values_only=True)
                    headers = list(next(row_iter, ()))
                    mapping = self._resolve_mapping(headers, project_id, context, strict=False)
                    missing = list(mapping["missing_required_headers"])
                    all_missing.extend(header for header in missing if header not in all_missing)
                    sampled_issue_count += self._sample_issue_count(row_iter, mapping, context)
                    sheet_previews.append(
                        WorkbookSheetPreview(
                            sheet_key=f"{rel_path}::{sheet.title}",
                            file_path=rel_path,
                            sheet_name=sheet.title,
                            available_headers=list(mapping["available_headers"]),
                            missing_required_headers=missing,
                            sampled_issue_count=sampled_issue_count,
                        )
                    )
            finally:
                workbook.close()

        return WorkbookPrecheck(
            file_count=len(files),
            sheet_count=len(sheet_previews),
            missing_required_headers=all_missing,
            sampled_issue_count=sampled_issue_count,
            sheet_previews=sheet_previews,
        )

    def iter_rows(
        self,
        input_dir: str | Path,
        project_id: int = DEFAULT_PROJECT_ID,
        context: WorkbookWorkflowContext | None = None,
    ) -> Iterator[WorkbookRow]:
        context = context or WorkbookWorkflowContext(workflow_kind="create_branch")
        base = Path(input_dir)
        for file_path in self._list_workbooks(base):
            rel_path = self._relative_path(base, file_path)
            workbook = load_workbook(filename=file_path, read_only=True, data_only=True)
            try:
                for sheet in workbook.worksheets:
                    row_iter = sheet.iter_rows(values_only=True)
                    headers = list(next(row_iter, ()))
                    mapping = self._resolve_mapping(headers, project_id, context, strict=True)
                    for row_index, values in enumerate(row_iter, start=2):
                        yield self._extract_row(rel_path, sheet.title, row_index, values, mapping, context)
            finally:
                workbook.close()

    def _sample_issue_count(self, row_iter: Any, mapping: dict[str, Any], context: WorkbookWorkflowContext) -> int:
        issue_count = 0
        for index, values in enumerate(row_iter):
            if index >= self.SAMPLE_ROW_LIMIT:
                break
            row = self._extract_row("", "", index + 2, values, mapping, context)
            if row.status != "ok":
                issue_count += 1
        return issue_count

    def _resolve_mapping(
        self,
        headers: list[Any],
        project_id: int,
        context: WorkbookWorkflowContext,
        *,
        strict: bool,
    ) -> dict[str, Any]:
        schema = self.projects.get_schema(project_id)
        normalized = self._normalize_headers(headers)
        required_headers = [
            schema["fixed_columns"][field]
            for field in context.required_internal_fields()
        ]
        missing = [header for header in required_headers if header not in normalized]
        if strict and missing:
            raise ValueError(f"workbook missing required header: {missing[0]}")
        return {
            "available_headers": list(normalized.keys()),
            "missing_required_headers": missing,
            "business_key": normalized.get(schema["fixed_columns"]["business_key"]),
            "source": normalized.get(schema["fixed_columns"]["source"]),
            "translation_columns": {
                lang: normalized[lang]
                for lang in schema["translation_columns"]
                if lang in normalized
            },
            "remark_columns": {
                key: normalized[key]
                for key in schema["remark_columns"]
                if key in normalized
            },
        }

    def _extract_row(
        self,
        file_path: str,
        sheet_name: str,
        row_index: int,
        values: tuple[Any, ...],
        mapping: dict[str, Any],
        context: WorkbookWorkflowContext,
    ) -> WorkbookRow:
        business_key = self._cell(values, mapping.get("business_key"), is_content=False)
        source = self._cell(values, mapping.get("source"), is_content=False)
        translations = {
            lang: self._cell(values, index, is_content=True)
            for lang, index in mapping["translation_columns"].items()
        }
        remarks = {
            key: self._cell(values, index, is_content=False)
            for key, index in mapping["remark_columns"].items()
        }
        status = "ok"
        message = None
        if not business_key:
            status = "missing_business_key"
            message = "business_key is required"
        elif "source" in context.required_internal_fields() and not source:
            status = "missing_source"
            message = "source is required"
        return WorkbookRow(
            file_path=file_path,
            sheet_name=sheet_name,
            row_index=row_index,
            business_key=business_key,
            source=source,
            translations=translations,
            remarks=remarks,
            status=status,
            message=message,
        )

    def _cell(self, values: tuple[Any, ...], index: int | None, *, is_content: bool) -> str:
        if not index:
            return ""
        value = values[index - 1] if len(values) >= index else None
        return normalize_content_value(value) if is_content else normalize_non_content_value(value)

    def _normalize_headers(self, headers: list[Any]) -> dict[str, int]:
        normalized: dict[str, int] = {}
        for index, value in enumerate(headers):
            header = normalize_non_content_value(value)
            if header and header not in normalized:
                normalized[header] = index + 1
        return normalized

    def _list_workbooks(self, base: Path) -> list[Path]:
        if not base.exists() or not base.is_dir():
            raise ValueError(f"input directory not found: {base}")
        return [path for path in sorted(base.rglob("*.xlsx")) if not path.name.startswith("~$")]

    def _relative_path(self, base: Path, file_path: Path) -> str:
        return str(file_path.relative_to(base)).replace("\\", "/")
```

- [ ] **Step 5: Run parser tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_workbook_intake.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add app/services/workbooks tests/test_workbook_intake.py
git commit -m "feat: add workbook parser precheck"
```

---

### Task 3: Workbook Batch Reader And Writer

**Files:**

- Create: `app/services/workbooks/batches.py`
- Modify: `tests/test_workbook_intake.py`

- [ ] **Step 1: Add failing batch persistence test**

Append to `tests/test_workbook_intake.py`:

```python
from app.services.workbooks.batches import WorkbookBatchService


def test_workbook_batch_service_persists_rows_for_batch_reader(tmp_path) -> None:
    reset_demo()
    project = ProjectService().create_project(
        "Batch Project",
        ["fr"],
        ["context"],
        business_key_header="key",
        source_header="source_text",
    )
    root = tmp_path / "batch"
    write_workbook(
        root,
        "bundle/messages.xlsx",
        [
            ["key", "source_text", "fr", "context"],
            ["hello.key", "Hello", "Bonjour", "Greeting"],
        ],
    )

    context = WorkbookWorkflowContext(workflow_kind="branch_mutation", mutation_type="range")
    batch = WorkbookBatchService().create_batch_from_directory(root, int(project["project_id"]), context)
    rows = list(WorkbookBatchService().iter_rows(batch["workbook_batch_id"], int(project["project_id"])))

    assert batch["workbook_batch_id"] > 0
    assert batch["rows_scanned"] == 1
    assert batch["issues"] == 0
    assert rows[0]["business_key"] == "hello.key"
    assert rows[0]["source"] == "Hello"
    assert rows[0]["payload"]["translations"] == {"fr": "Bonjour"}
```

- [ ] **Step 2: Run the failing batch test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_workbook_intake.py::test_workbook_batch_service_persists_rows_for_batch_reader
```

Expected: FAIL with `ModuleNotFoundError` for `app.services.workbooks.batches`.

- [ ] **Step 3: Implement neutral batch service over existing import tables**

Create `app/services/workbooks/batches.py`:

```python
from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any, Iterator

from app.db import get_conn, json_dumps, json_loads
from app.services.project.service import DEFAULT_PROJECT_ID, ProjectService
from app.services.shared.utils import now_iso
from app.services.workbooks.models import WorkbookWorkflowContext
from app.services.workbooks.parser import WorkbookParser


class WorkbookBatchService:
    INSERT_CHUNK_SIZE = 1000
    READ_CHUNK_SIZE = 1000

    def __init__(
        self,
        *,
        parser: WorkbookParser | None = None,
        projects: ProjectService | None = None,
    ) -> None:
        self.parser = parser or WorkbookParser()
        self.projects = projects or ProjectService()

    def create_batch_from_directory(
        self,
        input_dir: str | Path,
        project_id: int = DEFAULT_PROJECT_ID,
        context: WorkbookWorkflowContext | None = None,
    ) -> dict[str, Any]:
        context = context or WorkbookWorkflowContext(workflow_kind="create_branch")
        self.projects.require_project(project_id)
        started = perf_counter()
        with get_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO imports(project_id, created_at, meta_json)
                VALUES (?, ?, ?)
                """,
                (
                    project_id,
                    now_iso(),
                    json_dumps(
                        {
                            "kind": "workbook_batch",
                            "workflow_kind": context.workflow_kind,
                            "mutation_type": context.mutation_type,
                            "input_dir": str(input_dir),
                            "project_id": project_id,
                        }
                    ),
                ),
            )
            batch_id = int(cur.lastrowid)

        rows_scanned = 0
        issues = 0
        pending: list[tuple[Any, ...]] = []
        for row in self.parser.iter_rows(input_dir, project_id, context):
            rows_scanned += 1
            if row.status != "ok":
                issues += 1
            payload = {
                "file_name": row.file_path,
                "business_key": row.business_key,
                "source": row.source,
                "translations": row.translations,
                "remarks": row.remarks,
            }
            pending.append(
                (
                    batch_id,
                    row.file_path,
                    row.sheet_name,
                    row.row_index,
                    row.business_key,
                    row.source,
                    row.status,
                    row.message,
                    json_dumps(payload),
                )
            )
            if len(pending) >= self.INSERT_CHUNK_SIZE:
                self._flush(pending)
        self._flush(pending)

        return {
            "workbook_batch_id": batch_id,
            "import_batch_id": batch_id,
            "project_id": project_id,
            "rows_scanned": rows_scanned,
            "issues": issues,
            "elapsed_ms": int((perf_counter() - started) * 1000),
        }

    def iter_rows(
        self,
        workbook_batch_id: int,
        project_id: int = DEFAULT_PROJECT_ID,
        *,
        ok_only: bool = False,
    ) -> Iterator[dict[str, Any]]:
        self.require_batch_project(workbook_batch_id, project_id)
        last_id = 0
        while True:
            rows = self._load_chunk(workbook_batch_id, last_id, ok_only=ok_only)
            if not rows:
                break
            last_id = int(rows[-1]["import_row_id"])
            for row in rows:
                yield row

    def require_batch_project(self, workbook_batch_id: int, project_id: int) -> None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT project_id FROM imports WHERE import_batch_id = ?",
                (workbook_batch_id,),
            ).fetchone()
        if not row or int(row["project_id"]) != project_id:
            raise KeyError(f"workbook batch not found: {workbook_batch_id}")

    def _load_chunk(self, workbook_batch_id: int, after_row_id: int, *, ok_only: bool) -> list[dict[str, Any]]:
        query = """
            SELECT import_row_id, file_path, sheet_name, row_index, business_key, source, status, message, payload_json
            FROM import_rows
            WHERE import_batch_id = ?
              AND import_row_id > ?
        """
        params: list[Any] = [workbook_batch_id, after_row_id]
        if ok_only:
            query += " AND status = 'ok'"
        query += " ORDER BY import_row_id LIMIT ?"
        params.append(self.READ_CHUNK_SIZE)
        with get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "import_row_id": int(row["import_row_id"]),
                "file_path": row["file_path"],
                "sheet_name": row["sheet_name"],
                "row_index": int(row["row_index"]),
                "business_key": row["business_key"],
                "source": row["source"] or "",
                "status": row["status"],
                "message": row["message"],
                "payload": json_loads(row["payload_json"]),
            }
            for row in rows
        ]

    def _flush(self, rows: list[tuple[Any, ...]]) -> None:
        if not rows:
            return
        with get_conn() as conn:
            conn.executemany(
                """
                INSERT INTO import_rows(
                    import_batch_id,
                    file_path,
                    sheet_name,
                    row_index,
                    business_key,
                    source,
                    status,
                    message,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        rows.clear()
```

- [ ] **Step 4: Run workbook intake tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_workbook_intake.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add app/services/workbooks/batches.py tests/test_workbook_intake.py
git commit -m "feat: persist workbook batches"
```

---

### Task 4: Content-Only Batch Mutation Service

**Files:**

- Create: `app/services/branch/content_batch_mutation.py`
- Modify: `app/services/branch/mutations.py`
- Modify: `tests/test_branch_service.py`

- [ ] **Step 1: Add failing service test for content mutation source match**

Append to `tests/test_branch_service.py`:

```python
from app.services.workbooks.batches import WorkbookBatchService
from app.services.workbooks.models import WorkbookWorkflowContext


def test_workbook_content_mutation_requires_current_bound_source(tmp_path) -> None:
    reset_demo()
    services = branch_services()
    entry = services.entries.get_or_create_entry("content.batch", project_id=1)
    variant_id = services.catalog.create_variant(
        int(entry["entry_id"]),
        services.catalog.build_content(
            "content.xlsx",
            "Current source",
            {"fr": "Original"},
            {"context": "Original context"},
        ),
    )
    services.bindings.bind(int(entry["entry_id"]), BranchRef.dev("2.4.3"), variant_id)

    root = tmp_path / "content-batch"
    write_import_workbook(
        root,
        "bundle/content.xlsx",
        [
            ["business_key", "source", "fr", "context"],
            ["content.batch", "Current source", "Updated", "Updated context"],
            ["content.batch", "Other source", "Wrong", "Wrong context"],
        ],
    )
    batch = WorkbookBatchService().create_batch_from_directory(
        root,
        1,
        WorkbookWorkflowContext(workflow_kind="branch_mutation", mutation_type="content"),
    )

    result = BranchMutationService().apply(
        BranchRef.dev("2.4.3"),
        {
            "kind": "workbook_batch",
            "mutation_type": "content",
            "workbook_batch_id": batch["workbook_batch_id"],
        },
    )

    statuses = [row["status"] for row in result["report_rows"]]
    updated = services.catalog.get_variant(variant_id)

    assert statuses == ["UPDATED_BOUND_VARIANT", "SOURCE_MISMATCH"]
    assert updated["translations"]["fr"] == "Updated"
    assert updated["remarks"]["context"] == "Updated context"
```

- [ ] **Step 2: Run failing service test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_branch_service.py::test_workbook_content_mutation_requires_current_bound_source
```

Expected: FAIL because `workbook_batch` input kind is not supported.

- [ ] **Step 3: Implement content-only batch applier**

Create `app/services/branch/content_batch_mutation.py`:

```python
from __future__ import annotations

from collections import Counter
from time import perf_counter
from typing import Any

import sqlite3

from app.services.branch.models import BranchRef
from app.services.branch.mutation_semantics import MutationSemanticSummaryBuilder, semantics_row
from app.services.branch.policy import AuthorityPolicy
from app.services.branch.variant_resolution import VariantResolutionService
from app.services.variant.bindings import BindingLookupService
from app.services.variant.catalog import VariantCatalogService
from app.services.variant.entries import EntryService
from app.services.workbooks.batches import WorkbookBatchService


class ContentBatchMutationApplier:
    def __init__(
        self,
        *,
        batches: WorkbookBatchService | None = None,
        entries: EntryService | None = None,
        catalog: VariantCatalogService | None = None,
        binding_lookup: BindingLookupService | None = None,
        resolution: VariantResolutionService | None = None,
    ) -> None:
        self.batches = batches or WorkbookBatchService()
        self.entries = entries or EntryService()
        self.catalog = catalog or VariantCatalogService()
        self.binding_lookup = binding_lookup or BindingLookupService()
        self.resolution = resolution or VariantResolutionService(catalog=self.catalog)

    def apply(
        self,
        branch_ref: BranchRef,
        workbook_batch_id: int,
        project_id: int,
        conn: sqlite3.Connection,
    ) -> dict[str, Any]:
        started = perf_counter()
        status_counts: Counter[str] = Counter()
        semantic_counts = MutationSemanticSummaryBuilder()
        report_rows: list[dict[str, Any]] = []
        filtered_count = 0

        for row in self.batches.iter_rows(workbook_batch_id, project_id, ok_only=True):
            report_row = self._apply_row(branch_ref, row, project_id, conn)
            status_counts.update([report_row["status"]])
            semantic_counts.add_row(report_row)
            filtered_count += int(bool(report_row.get("content_filtered_by_authority")))
            report_rows.append(report_row)

        summary = {
            "branch_ref": str(branch_ref),
            "input_kind": "workbook_batch",
            "mutation_type": "content",
            "workbook_batch_id": workbook_batch_id,
            "processed_count": len(report_rows),
            "updated_bound_variant_count": status_counts["UPDATED_BOUND_VARIANT"],
            "source_mismatch_count": status_counts["SOURCE_MISMATCH"],
            "missing_in_scope_count": status_counts["MISSING_IN_SCOPE"],
            "noop_count": status_counts["NOOP"],
            "content_filtered_by_authority_count": filtered_count,
            **semantic_counts.as_dict(),
            "stages": [
                {
                    "stage": "apply_content_mutation",
                    "elapsed_ms": int((perf_counter() - started) * 1000),
                    "meta": {"processed_count": len(report_rows)},
                }
            ],
        }
        return {"summary": summary, "report_rows": report_rows}

    def _apply_row(
        self,
        branch_ref: BranchRef,
        row: dict[str, Any],
        project_id: int,
        conn: sqlite3.Connection,
    ) -> dict[str, Any]:
        payload = row["payload"]
        business_key = payload["business_key"]
        requested_source = payload["source"]
        entry = self.entries.get_entry(business_key, project_id=project_id, conn=conn)
        if entry is None:
            return self._report(row, "MISSING_IN_SCOPE", "none", "none", "stay_current", "missing")

        entry_id = int(entry["entry_id"])
        binding = self.binding_lookup.get_binding(entry_id, branch_ref, conn=conn)
        if binding is None:
            return self._report(row, "MISSING_IN_SCOPE", "none", "none", "stay_current", "missing")

        current_variant = self.catalog.get_variant(int(binding["variant_id"]), conn=conn)
        if current_variant["source"] != requested_source:
            return self._report(row, "SOURCE_MISMATCH", "none", "none", "stay_current", "missing")

        change = {
            "business_key": business_key,
            "source": requested_source,
            "translations_by_lang": payload.get("translations", {}),
            "remarks_by_key": payload.get("remarks", {}),
            "file_name": payload.get("file_name"),
        }
        merged = self.resolution.merged_variant_payload(current_variant, change, requested_source)
        if self.resolution.variant_matches(current_variant, merged):
            return self._report(row, "NOOP", "none", "none", "stay_current", "noop", variant_id=int(current_variant["variant_id"]))

        bound_refs = self.resolution.bound_branch_refs_for_variant(
            self.binding_lookup.list_bindings_for_entry(entry_id, conn=conn),
            int(current_variant["variant_id"]),
        )
        decision = AuthorityPolicy.evaluate_content_edit(branch_ref, bound_refs, content_changed=True)
        if decision.filtered:
            return self._report(
                row,
                "NOOP",
                "none",
                "filtered",
                "stay_current",
                "noop",
                variant_id=int(current_variant["variant_id"]),
                content_filtered_by_authority=True,
            )

        self.catalog.update_variant(int(current_variant["variant_id"]), merged, actor_scope=branch_ref.as_tuple(), conn=conn)
        return self._report(
            row,
            "UPDATED_BOUND_VARIANT",
            "none",
            "update",
            "stay_current",
            "applied",
            variant_id=int(current_variant["variant_id"]),
        )

    def _report(
        self,
        row: dict[str, Any],
        status: str,
        binding_effect: str,
        content_effect: str,
        variant_resolution: str,
        row_outcome: str,
        *,
        variant_id: int | None = None,
        content_filtered_by_authority: bool = False,
    ) -> dict[str, Any]:
        report = {
            "business_key": row["business_key"],
            "file_path": row["file_path"],
            "sheet_name": row["sheet_name"],
            "row_index": row["row_index"],
            "status": status,
        }
        if variant_id is not None:
            report["variant_id"] = variant_id
        if content_filtered_by_authority:
            report["content_filtered_by_authority"] = True
        return semantics_row(
            report,
            mutation_class="content",
            binding_effect=binding_effect,
            content_effect=content_effect,
            variant_resolution=variant_resolution,
            row_outcome=row_outcome,
        )
```

- [ ] **Step 4: Wire workbook batch input into BranchMutationService**

In `app/services/branch/mutations.py`, import:

```python
from app.services.branch.content_batch_mutation import ContentBatchMutationApplier
```

In `__init__`, after `self.import_batch = ...`, add:

```python
        self.content_batch = ContentBatchMutationApplier(
            entries=self.entries,
            catalog=self.catalog,
            binding_lookup=self.binding_lookup,
            resolution=self.resolution,
        )
```

In `apply`, after the direct branch:

```python
            if input_kind == "workbook_batch":
                mutation_type = str(input_payload["mutation_type"])
                if mutation_type == "content":
                    return self.content_batch.apply(
                        branch_ref,
                        int(input_payload["workbook_batch_id"]),
                        project_id,
                        conn=conn,
                    )
                return self.import_batch.apply(
                    branch_ref,
                    int(input_payload["workbook_batch_id"]),
                    project_id,
                    conn=conn,
                    version_series=(dev_branch or {}).get("version_series"),
                )
```

This keeps range mutation on the existing import-batch applier while content mutation uses the stricter content-only applier.

- [ ] **Step 5: Allow policy validation for workbook batch input**

In `app/services/branch/policy.py`, update validation so `workbook_batch` is allowed for the same branches that allow import-batch mutation. Add a focused test if the current policy has dedicated tests; otherwise the service test above verifies the route through policy.

Expected minimal logic:

```python
if input_kind == "workbook_batch":
    input_kind = "import_batch"
```

inside `validate_input_kind` before comparing allowed kinds.

- [ ] **Step 6: Run focused mutation test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_branch_service.py::test_workbook_content_mutation_requires_current_bound_source
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```powershell
git add app/services/branch/content_batch_mutation.py app/services/branch/mutations.py app/services/branch/policy.py tests/test_branch_service.py
git commit -m "feat: add content-only workbook mutation"
```

---

### Task 5: Workbook Trash Execution

**Files:**

- Modify: `app/services/workflows/trash.py`
- Modify: `tests/test_branch_service.py`

- [ ] **Step 1: Add failing service tests for workbook trash**

Append to `tests/test_branch_service.py`:

```python
def test_workbook_branch_trash_uses_key_only_rows(tmp_path) -> None:
    reset_demo()
    root = tmp_path / "branch-trash"
    write_import_workbook(root, "trash.xlsx", [["business_key"], ["common.welcome"]])
    batch = WorkbookBatchService().create_batch_from_directory(
        root,
        1,
        WorkbookWorkflowContext(workflow_kind="branch_trash"),
    )

    result = TrashService().delete_from_workbook_batch(
        BranchRef.rel_current(),
        batch["workbook_batch_id"],
        project_id=1,
    )

    assert result["summary"]["orphaned_variant_count"] == 1
    assert result["report_rows"][0]["business_key"] == "common.welcome"


def test_workbook_project_trash_uses_key_only_rows(tmp_path) -> None:
    reset_demo()
    TrashService().delete(BranchRef.rel_current(), ["common.welcome"])
    root = tmp_path / "project-trash"
    write_import_workbook(root, "trash.xlsx", [["business_key"], ["common.welcome"]])
    batch = WorkbookBatchService().create_batch_from_directory(
        root,
        1,
        WorkbookWorkflowContext(workflow_kind="project_trash"),
    )

    result = TrashService().project_trash_from_workbook_batch(
        batch["workbook_batch_id"],
        project_id=1,
    )

    assert result["summary"]["trashed_count"] == 1
    assert result["report_rows"][0]["status"] == "TRASHED"
```

- [ ] **Step 2: Run failing trash tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_branch_service.py::test_workbook_branch_trash_uses_key_only_rows tests\test_branch_service.py::test_workbook_project_trash_uses_key_only_rows
```

Expected: FAIL because the two trash batch methods do not exist.

- [ ] **Step 3: Implement trash batch entrypoints**

In `app/services/workflows/trash.py`, import:

```python
from app.services.workbooks.batches import WorkbookBatchService
```

In `TrashService.__init__`, add:

```python
        self.workbook_batches = WorkbookBatchService()
```

Add methods:

```python
    def delete_from_workbook_batch(
        self,
        branch_ref: BranchRef,
        workbook_batch_id: int,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        keys = [
            row["business_key"]
            for row in self.workbook_batches.iter_rows(workbook_batch_id, project_id, ok_only=True)
            if row["business_key"]
        ]
        return self.delete(branch_ref, keys, project_id=project_id)

    def project_trash_from_workbook_batch(
        self,
        workbook_batch_id: int,
        *,
        project_id: int = DEFAULT_PROJECT_ID,
    ) -> dict[str, Any]:
        keys = [
            row["business_key"]
            for row in self.workbook_batches.iter_rows(workbook_batch_id, project_id, ok_only=True)
            if row["business_key"]
        ]
        return self.project_trash(keys, project_id=project_id)
```

If `TrashService` does not currently define `__init__`, add:

```python
    def __init__(self) -> None:
        self.workbook_batches = WorkbookBatchService()
```

- [ ] **Step 4: Run focused trash tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_branch_service.py::test_workbook_branch_trash_uses_key_only_rows tests\test_branch_service.py::test_workbook_project_trash_uses_key_only_rows
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add app/services/workflows/trash.py tests/test_branch_service.py
git commit -m "feat: apply trash from workbook batch"
```

---

### Task 6: Workbook Workflow API

**Files:**

- Modify: `app/schemas.py`
- Create: `app/routers/workbook_workflows.py`
- Create: `app/services/workbooks/workflows.py`
- Modify: `app/services/workflows/application.py`
- Modify: `app/main.py`
- Test: `tests/test_variant_api.py`

- [ ] **Step 1: Add failing API test for create branch workbook execute**

Append to `tests/test_variant_api.py`:

```python
def test_workbook_workflow_create_branch_executes_single_job() -> None:
    reset_demo()
    workbook_bytes = build_workbook_bytes(
        ["business_key", "source", "fr"],
        [["workbook.create", "Workbook source", "Workbook target"]],
    )

    with TestClient(app) as client:
        preview = client.post(
            "/api/projects/1/workbooks/intake/preview",
            data={"workflow_kind": "create_branch", "branch_ref": "dev/2.4.3"},
            files=[
                (
                    "files",
                    (
                        "create.xlsx",
                        workbook_bytes,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    ),
                ),
                ("relative_paths", (None, "create.xlsx")),
            ],
        )
        assert preview.status_code == 200
        preview_payload = preview.json()
        assert preview_payload["upload_session_id"]
        assert preview_payload["missing_required_headers"] == []

        execute = client.post(
            "/api/projects/1/workbooks/intake/execute",
            json={
                "upload_session_id": preview_payload["upload_session_id"],
                "workflow_kind": "create_branch",
                "branch_ref": "dev/2.4.3",
            },
        )
        assert execute.status_code == 200
        detail = wait_for_job(client, execute.json())

    assert detail["job"]["status"] == "success"
    assert detail["job"]["job_type"] == "workbook_create_branch"
    assert detail["job"]["summary"]["created_and_bound_variant_count"] == 1
    assert detail["job"]["summary"]["workbook_batch_id"] > 0
```

- [ ] **Step 2: Run failing API test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_variant_api.py::test_workbook_workflow_create_branch_executes_single_job
```

Expected: FAIL with 404 for `/workbooks/intake/preview`.

- [ ] **Step 3: Add schemas**

In `app/schemas.py`, add:

```python
class WorkbookIntakePreview(BaseModel):
    upload_session_id: str
    workflow_kind: Literal["create_branch", "branch_mutation", "branch_trash", "project_trash"]
    mutation_type: Literal["content", "range"] | None = None
    file_count: int
    sheet_count: int
    missing_required_headers: list[str] = Field(default_factory=list)
    sampled_issue_count: int = 0
    sheet_previews: list[dict[str, Any]] = Field(default_factory=list)


class WorkbookIntakeExecuteRequest(BaseModel):
    upload_session_id: str
    workflow_kind: Literal["create_branch", "branch_mutation", "branch_trash", "project_trash"]
    branch_ref: str | None = None
    mutation_type: Literal["content", "range"] | None = None
```

- [ ] **Step 4: Implement workbook workflow service**

Create `app/services/workbooks/workflows.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.branch.models import BranchRef
from app.services.branch.mutations import BranchMutationService
from app.services.branch.bootstrap import BranchBootstrapService
from app.services.project.service import DEFAULT_PROJECT_ID
from app.services.shared.background_jobs import submit_background_job
from app.services.shared.jobs import JobService
from app.services.shared.uploads import UploadSessionService
from app.services.workbooks.batches import WorkbookBatchService
from app.services.workbooks.models import WorkbookWorkflowContext
from app.services.workflows.trash import TrashService


class WorkbookWorkflowService:
    def __init__(self) -> None:
        self.batches = WorkbookBatchService()
        self.bootstrap = BranchBootstrapService()
        self.mutations = BranchMutationService()
        self.trash = TrashService()
        self.jobs = JobService()
        self.uploads = UploadSessionService()

    def execute_uploaded_session(
        self,
        *,
        upload_session_id: str,
        workflow_kind: str,
        project_id: int = DEFAULT_PROJECT_ID,
        branch_ref: str | None = None,
        mutation_type: str | None = None,
    ) -> dict[str, Any]:
        self.uploads.require_session(upload_session_id, project_id)
        job_type = f"workbook_{workflow_kind}"
        job_id = self.jobs.create_job(
            job_type,
            {
                "upload_session_id": upload_session_id,
                "workflow_kind": workflow_kind,
                "branch_ref": branch_ref,
                "mutation_type": mutation_type,
                "project_id": project_id,
            },
            project_id=project_id,
        )

        def run() -> None:
            try:
                input_dir = self.uploads.consume_session_into_job(
                    upload_session_id,
                    job_id,
                    project_id,
                    "workbook_input",
                )
                result = self._execute_directory(
                    Path(input_dir),
                    workflow_kind=workflow_kind,
                    project_id=project_id,
                    branch_ref=branch_ref,
                    mutation_type=mutation_type,
                    job_id=job_id,
                )
                if result.get("already_completed_job"):
                    return
                self.jobs.complete_job(
                    job_id,
                    summary=result["summary"],
                    report_payload=result["report"],
                    artifact_path=result.get("artifact_path"),
                )
            except Exception as exc:
                self.jobs.fail_job(job_id, str(exc))

        submit_background_job(run)
        return self.get_job_detail(job_id, project_id=project_id)

    def _execute_directory(
        self,
        input_dir: Path,
        *,
        workflow_kind: str,
        project_id: int,
        branch_ref: str | None,
        mutation_type: str | None,
        job_id: int,
    ) -> dict[str, Any]:
        context = WorkbookWorkflowContext(workflow_kind=workflow_kind, mutation_type=mutation_type)  # type: ignore[arg-type]
        batch = self.batches.create_batch_from_directory(input_dir, project_id, context)
        workbook_batch_id = int(batch["workbook_batch_id"])
        if workflow_kind == "create_branch":
            if not branch_ref:
                raise ValueError("branch_ref is required")
            result = self.bootstrap.bootstrap(
                BranchRef.parse(branch_ref),
                workbook_batch_id,
                project_id=project_id,
                job_id=job_id,
            )
            result["summary"]["workbook_batch_id"] = workbook_batch_id
            return {"already_completed_job": True, **result}
        if workflow_kind == "branch_mutation":
            if not branch_ref:
                raise ValueError("branch_ref is required")
            if mutation_type not in {"content", "range"}:
                raise ValueError("mutation_type must be content or range")
            result = self.mutations.apply(
                BranchRef.parse(branch_ref),
                {
                    "kind": "workbook_batch",
                    "mutation_type": mutation_type,
                    "workbook_batch_id": workbook_batch_id,
                },
                project_id=project_id,
            )
            return self._wrap(workbook_batch_id, result)
        if workflow_kind == "branch_trash":
            if not branch_ref:
                raise ValueError("branch_ref is required")
            result = self.trash.delete_from_workbook_batch(
                BranchRef.parse(branch_ref),
                workbook_batch_id,
                project_id=project_id,
            )
            return self._wrap(workbook_batch_id, result)
        if workflow_kind == "project_trash":
            result = self.trash.project_trash_from_workbook_batch(workbook_batch_id, project_id=project_id)
            return self._wrap(workbook_batch_id, result)
        raise ValueError(f"unsupported workbook workflow: {workflow_kind}")

    def _wrap(self, workbook_batch_id: int, result: dict[str, Any]) -> dict[str, Any]:
        summary = dict(result["summary"])
        summary["workbook_batch_id"] = workbook_batch_id
        return {
            "summary": summary,
            "report": {"summary": summary, "rows": result.get("report_rows", [])},
        }

    def get_job_detail(self, job_id: int, project_id: int | None = None) -> dict[str, Any]:
        return {
            "job": self.jobs.get_job(job_id, project_id=project_id),
            "report": self.jobs.get_report_preview(job_id, project_id=project_id),
        }
```

- [ ] **Step 5: Add router**

Create `app/routers/workbook_workflows.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from app.routers.common import handle_errors
from app.schemas import JobDetail, WorkbookIntakeExecuteRequest, WorkbookIntakePreview
from app.services.shared.uploads import UploadSessionService
from app.services.workbooks.models import WorkbookWorkflowContext
from app.services.workbooks.parser import WorkbookParser
from app.services.workbooks.workflows import WorkbookWorkflowService

router = APIRouter()


@router.post("/api/projects/{project_id}/workbooks/intake/preview", response_model=WorkbookIntakePreview)
def workbook_intake_preview(
    project_id: int,
    workflow_kind: str = Form(...),
    branch_ref: str | None = Form(default=None),
    mutation_type: str | None = Form(default=None),
    files: list[UploadFile] = File(...),
    relative_paths: list[str] = Form(...),
) -> WorkbookIntakePreview:
    def run() -> WorkbookIntakePreview:
        sessions = UploadSessionService()
        session = sessions.create_session(files, relative_paths, project_id)
        try:
            context = WorkbookWorkflowContext(workflow_kind=workflow_kind, mutation_type=mutation_type)  # type: ignore[arg-type]
            precheck = WorkbookParser().precheck_directory(
                sessions.session_input_dir(session["upload_session_id"]),
                project_id,
                context,
            )
            return WorkbookIntakePreview(
                upload_session_id=session["upload_session_id"],
                workflow_kind=workflow_kind,
                mutation_type=mutation_type,
                file_count=precheck.file_count,
                sheet_count=precheck.sheet_count,
                missing_required_headers=precheck.missing_required_headers,
                sampled_issue_count=precheck.sampled_issue_count,
                sheet_previews=[
                    {
                        "sheet_key": sheet.sheet_key,
                        "file_path": sheet.file_path,
                        "sheet_name": sheet.sheet_name,
                        "available_headers": sheet.available_headers,
                        "missing_required_headers": sheet.missing_required_headers,
                        "sampled_issue_count": sheet.sampled_issue_count,
                    }
                    for sheet in precheck.sheet_previews
                ],
            )
        except Exception:
            sessions.discard_session(session["upload_session_id"])
            raise

    return handle_errors(run)


@router.post("/api/projects/{project_id}/workbooks/intake/execute", response_model=JobDetail)
def workbook_intake_execute(project_id: int, payload: WorkbookIntakeExecuteRequest) -> JobDetail:
    return handle_errors(
        lambda: JobDetail(
            **WorkbookWorkflowService().execute_uploaded_session(
                upload_session_id=payload.upload_session_id,
                workflow_kind=payload.workflow_kind,
                branch_ref=payload.branch_ref,
                mutation_type=payload.mutation_type,
                project_id=project_id,
            )
        )
    )
```

- [ ] **Step 6: Register router**

In `app/routers/__init__.py`, export `workbook_workflows_router`:

```python
from app.routers.workbook_workflows import router as workbook_workflows_router
```

In `app/main.py`, include it in the import tuple and add:

```python
app.include_router(workbook_workflows_router)
```

after `imports_jobs_router`.

- [ ] **Step 7: Run focused API test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_variant_api.py::test_workbook_workflow_create_branch_executes_single_job
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```powershell
git add app/schemas.py app/routers/__init__.py app/routers/workbook_workflows.py app/main.py app/services/workbooks/workflows.py tests/test_variant_api.py
git commit -m "feat: add workbook workflow API"
```

---

### Task 7: API Coverage For Mutation And Trash Workflows

**Files:**

- Modify: `tests/test_variant_api.py`
- Modify: `app/services/workbooks/workflows.py`
- Modify: `app/routers/workbook_workflows.py`

- [ ] **Step 1: Add route tests for branch mutation and trash**

Append to `tests/test_variant_api.py`:

```python
def test_workbook_workflow_content_mutation_and_branch_trash_routes() -> None:
    reset_demo()
    create_bound_variant(
        project_id=1,
        business_key="workbook.content",
        source="Current source",
        translations={"fr": "Original"},
        branch_refs=[BranchRef.dev("2.4.3")],
    )
    mutation_bytes = build_workbook_bytes(
        ["business_key", "source", "fr"],
        [["workbook.content", "Current source", "Updated"]],
    )
    trash_bytes = build_workbook_bytes(["business_key"], [["workbook.content"]])

    with TestClient(app) as client:
        mutation_preview = client.post(
            "/api/projects/1/workbooks/intake/preview",
            data={
                "workflow_kind": "branch_mutation",
                "branch_ref": "dev/2.4.3",
                "mutation_type": "content",
            },
            files=[
                ("files", ("mutation.xlsx", mutation_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
                ("relative_paths", (None, "mutation.xlsx")),
            ],
        )
        assert mutation_preview.status_code == 200
        mutation_execute = client.post(
            "/api/projects/1/workbooks/intake/execute",
            json={
                "upload_session_id": mutation_preview.json()["upload_session_id"],
                "workflow_kind": "branch_mutation",
                "branch_ref": "dev/2.4.3",
                "mutation_type": "content",
            },
        )
        mutation_detail = wait_for_job(client, mutation_execute.json())

        trash_preview = client.post(
            "/api/projects/1/workbooks/intake/preview",
            data={"workflow_kind": "branch_trash", "branch_ref": "dev/2.4.3"},
            files=[
                ("files", ("trash.xlsx", trash_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
                ("relative_paths", (None, "trash.xlsx")),
            ],
        )
        assert trash_preview.status_code == 200
        trash_execute = client.post(
            "/api/projects/1/workbooks/intake/execute",
            json={
                "upload_session_id": trash_preview.json()["upload_session_id"],
                "workflow_kind": "branch_trash",
                "branch_ref": "dev/2.4.3",
            },
        )
        trash_detail = wait_for_job(client, trash_execute.json())

    assert mutation_detail["job"]["status"] == "success"
    assert mutation_detail["report"]["rows"][0]["status"] == "UPDATED_BOUND_VARIANT"
    assert trash_detail["job"]["status"] == "success"
    assert trash_detail["report"]["summary"]["orphaned_variant_count"] == 1
```

- [ ] **Step 2: Run route tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_variant_api.py::test_workbook_workflow_content_mutation_and_branch_trash_routes
```

Expected: PASS after Task 6 if the router and services are wired correctly. If it fails with a validation error for `workflow_kind`, add explicit validation in the router using `WorkbookWorkflowContext(...)` and return `400` through `handle_errors`.

- [ ] **Step 3: Add bad precheck test for missing source on content mutation**

Append:

```python
def test_workbook_content_mutation_preview_requires_source_header() -> None:
    reset_demo()
    workbook_bytes = build_workbook_bytes(["business_key", "fr"], [["hello", "Bonjour"]])

    with TestClient(app) as client:
        preview = client.post(
            "/api/projects/1/workbooks/intake/preview",
            data={
                "workflow_kind": "branch_mutation",
                "branch_ref": "dev/2.4.3",
                "mutation_type": "content",
            },
            files=[
                ("files", ("bad.xlsx", workbook_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
                ("relative_paths", (None, "bad.xlsx")),
            ],
        )

    assert preview.status_code == 200
    assert preview.json()["missing_required_headers"] == ["source"]
```

- [ ] **Step 4: Run workbook API tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_variant_api.py::test_workbook_workflow_create_branch_executes_single_job tests\test_variant_api.py::test_workbook_workflow_content_mutation_and_branch_trash_routes tests\test_variant_api.py::test_workbook_content_mutation_preview_requires_source_header
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add tests/test_variant_api.py app/services/workbooks/workflows.py app/routers/workbook_workflows.py
git commit -m "test: cover workbook workflow routes"
```

---

### Task 8: Frontend Workbook Workflow API And Shared Panel

**Files:**

- Create: `frontend/src/domains/workbooks/types.ts`
- Create: `frontend/src/domains/workbooks/api.ts`
- Create: `frontend/src/shared/ui/WorkbookWorkflowPanel.tsx`
- Create: `frontend/src/shared/ui/WorkbookWorkflowPanel.module.css`

- [ ] **Step 1: Add API types**

Create `frontend/src/domains/workbooks/types.ts`:

```typescript
import type { JobDetail } from "@/domains/jobs/types";

export type WorkbookWorkflowKind =
  | "create_branch"
  | "branch_mutation"
  | "branch_trash"
  | "project_trash";

export type WorkbookMutationType = "content" | "range";

export type WorkbookSheetPreview = {
  sheet_key: string;
  file_path: string;
  sheet_name: string;
  available_headers: string[];
  missing_required_headers: string[];
  sampled_issue_count: number;
};

export type WorkbookIntakePreview = {
  upload_session_id: string;
  workflow_kind: WorkbookWorkflowKind;
  mutation_type: WorkbookMutationType | null;
  file_count: number;
  sheet_count: number;
  missing_required_headers: string[];
  sampled_issue_count: number;
  sheet_previews: WorkbookSheetPreview[];
};

export type WorkbookExecuteRequest = {
  upload_session_id: string;
  workflow_kind: WorkbookWorkflowKind;
  branch_ref?: string;
  mutation_type?: WorkbookMutationType;
};

export type WorkbookExecuteResult = JobDetail;
```

- [ ] **Step 2: Add API calls**

Create `frontend/src/domains/workbooks/api.ts`:

```typescript
import { fetchJson, postFolderForm } from "@/shared/api/http";

import type {
  WorkbookExecuteRequest,
  WorkbookExecuteResult,
  WorkbookIntakePreview,
  WorkbookMutationType,
  WorkbookWorkflowKind,
} from "@/domains/workbooks/types";

export function previewWorkbookWorkflow(
  projectId: number,
  files: File[],
  request: {
    workflow_kind: WorkbookWorkflowKind;
    branch_ref?: string;
    mutation_type?: WorkbookMutationType;
  },
) {
  return postFolderForm<WorkbookIntakePreview>(
    `/api/projects/${projectId}/workbooks/intake/preview`,
    files,
    request,
  );
}

export function executeWorkbookWorkflow(
  projectId: number,
  request: WorkbookExecuteRequest,
) {
  return fetchJson<WorkbookExecuteResult>(
    `/api/projects/${projectId}/workbooks/intake/execute`,
    {
      method: "POST",
      body: JSON.stringify(request),
    },
  );
}
```

- [ ] **Step 3: Add shared panel component**

Create `frontend/src/shared/ui/WorkbookWorkflowPanel.tsx`:

```tsx
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { executeWorkbookWorkflow, previewWorkbookWorkflow } from "@/domains/workbooks/api";
import type { WorkbookIntakePreview, WorkbookMutationType, WorkbookWorkflowKind } from "@/domains/workbooks/types";
import type { JobDetail } from "@/domains/jobs/types";
import { waitForJobDetail } from "@/domains/jobs/api";
import { buttonClassName, InlineNotice, StatGrid } from "@/shared/ui/primitives";
import { FolderUpload } from "@/shared/ui/FolderUpload";

import styles from "@/shared/ui/WorkbookWorkflowPanel.module.css";

export type WorkbookWorkflowPanelProps = {
  projectId: number;
  workflowKind: WorkbookWorkflowKind;
  branchRef?: string;
  mutationType?: WorkbookMutationType;
  title: string;
  uploadLabel?: string;
  executeLabel: string;
  disabled?: boolean;
  onJobCompleted: (job: JobDetail) => void;
};

export function WorkbookWorkflowPanel(props: WorkbookWorkflowPanelProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [preview, setPreview] = useState<WorkbookIntakePreview | null>(null);
  const [completedJob, setCompletedJob] = useState<JobDetail | null>(null);

  const previewMut = useMutation({
    mutationFn: () =>
      previewWorkbookWorkflow(props.projectId, files, {
        workflow_kind: props.workflowKind,
        branch_ref: props.branchRef,
        mutation_type: props.mutationType,
      }),
    onSuccess: (data) => setPreview(data),
  });

  const executeMut = useMutation({
    mutationFn: async () => {
      if (!preview) throw new Error("Preview is required before execute");
      const started = await executeWorkbookWorkflow(props.projectId, {
        upload_session_id: preview.upload_session_id,
        workflow_kind: props.workflowKind,
        branch_ref: props.branchRef,
        mutation_type: props.mutationType,
      });
      const completed = await waitForJobDetail(props.projectId, started.job.job_id);
      if (completed.job.status !== "success") {
        throw new Error(completed.job.error_message || "Workbook workflow failed");
      }
      return completed;
    },
    onSuccess: (job) => {
      setCompletedJob(job);
      props.onJobCompleted(job);
    },
  });

  const canPreview = files.length > 0 && !props.disabled;
  const canExecute = preview !== null && preview.missing_required_headers.length === 0 && !props.disabled;

  return (
    <section className={styles.panel}>
      <div className={styles.header}>
        <h3>{props.title}</h3>
      </div>
      <FolderUpload
        label={props.uploadLabel ?? "Upload workbook"}
        disabled={props.disabled}
        onFiles={(nextFiles) => {
          setFiles(nextFiles);
          setPreview(null);
          setCompletedJob(null);
          previewMut.reset();
          executeMut.reset();
        }}
      />
      {files.length > 0 && <p className={styles.meta}>{files.length} files selected</p>}
      <div className={styles.actions}>
        <button
          className={buttonClassName("secondary")}
          disabled={!canPreview || previewMut.isPending}
          onClick={() => previewMut.mutate()}
        >
          {previewMut.isPending ? "Checking workbook..." : "Check Workbook"}
        </button>
        {preview && (
          <button
            className={buttonClassName("primary")}
            disabled={!canExecute || executeMut.isPending}
            onClick={() => executeMut.mutate()}
          >
            {executeMut.isPending ? "Running..." : props.executeLabel}
          </button>
        )}
      </div>
      {previewMut.isError && <InlineNotice tone="error">{String(previewMut.error)}</InlineNotice>}
      {executeMut.isError && <InlineNotice tone="error">{String(executeMut.error)}</InlineNotice>}
      {preview && (
        <div className={styles.preview}>
          <StatGrid
            items={[
              { label: "Files", value: preview.file_count },
              { label: "Sheets", value: preview.sheet_count },
              { label: "Sample issues", value: preview.sampled_issue_count },
            ]}
          />
          {preview.missing_required_headers.length > 0 && (
            <InlineNotice tone="error">
              Missing required headers: {preview.missing_required_headers.join(", ")}
            </InlineNotice>
          )}
        </div>
      )}
      {completedJob && (
        <div className={styles.preview}>
          <StatGrid items={Object.entries(completedJob.job.summary).map(([label, value]) => ({ label, value: String(value) }))} />
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 4: Add panel styles**

Create `frontend/src/shared/ui/WorkbookWorkflowPanel.module.css`:

```css
.panel {
  display: grid;
  gap: 16px;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.header h3 {
  margin: 0;
}

.meta {
  color: var(--muted);
  font-size: 13px;
  margin: 0;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.preview {
  display: grid;
  gap: 12px;
}
```

- [ ] **Step 5: Run frontend typecheck**

Run:

```powershell
npm run typecheck --workspace=apps/desktop
```

If the repo does not have the desktop workspace active for this frontend package, run:

```powershell
npm run build:app
```

Expected: TypeScript compiles or exposes import path issues to fix in this task.

- [ ] **Step 6: Commit**

Run:

```powershell
git add frontend/src/domains/workbooks frontend/src/shared/ui/WorkbookWorkflowPanel.tsx frontend/src/shared/ui/WorkbookWorkflowPanel.module.css
git commit -m "feat: add workbook workflow frontend panel"
```

---

### Task 9: Replace Create Branch And Branch Edit UI

**Files:**

- Modify: `frontend/src/pages/dev/CreateBranch.tsx`
- Modify: `frontend/src/shared/ui/EditPanel.tsx`
- Modify: `frontend/src/pages/dev/BranchDetail.tsx`
- Modify: `frontend/src/pages/release/ReleasePage.tsx`
- Test: `tests/e2e/product-app.spec.js`

- [ ] **Step 1: Update Create Branch to use workbook panel**

Replace the upload/import/bootstrap state machine in `frontend/src/pages/dev/CreateBranch.tsx` with this component shape:

```tsx
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import type { JobDetail } from "@/domains/jobs/types";
import { invalidateProject } from "@/shared/api/queryKeys";
import { buttonClassName, InlineNotice, StatGrid } from "@/shared/ui/primitives";
import { WorkbookWorkflowPanel } from "@/shared/ui/WorkbookWorkflowPanel";

import styles from "@/pages/dev/DevPage.module.css";

export function CreateBranch(props: {
  projectId: number;
  lang: string;
  onBack: () => void;
  onCreated: (version: string) => void;
}) {
  const { projectId, onBack, onCreated } = props;
  const queryClient = useQueryClient();
  const [version, setVersion] = useState("");
  const [result, setResult] = useState<JobDetail | null>(null);
  const branchRef = `dev/${version}`;

  async function handleCompleted(job: JobDetail) {
    setResult(job);
    await invalidateProject(queryClient, projectId);
  }

  return (
    <div className={styles.page}>
      <button className={buttonClassName("ghost")} onClick={onBack}>← Back</button>
      <h2>Create Branch</h2>
      <label>
        Version number
        <input value={version} onChange={(e) => setVersion(e.target.value)} placeholder="2.2.3" />
      </label>
      <p style={{ color: "var(--muted)", fontSize: 13 }}>Branch will be created as <strong>{branchRef}</strong></p>
      {!version.trim() && <InlineNotice tone="warning">Enter a version before uploading the workbook.</InlineNotice>}
      <WorkbookWorkflowPanel
        projectId={projectId}
        workflowKind="create_branch"
        branchRef={branchRef}
        title="Create branch from workbook"
        uploadLabel="Upload workbook"
        executeLabel="Create Branch"
        disabled={!version.trim()}
        onJobCompleted={handleCompleted}
      />
      {result && (
        <div className={styles.actions}>
          <StatGrid items={Object.entries(result.job.summary).map(([label, value]) => ({ label, value: String(value) }))} />
          <button className={buttonClassName("primary")} onClick={() => onCreated(version)}>
            Go to Branch
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Replace EditPanel input methods with mutation type + workbook panel**

Replace `frontend/src/shared/ui/EditPanel.tsx` content with:

```tsx
import { useState } from "react";

import type { JobDetail } from "@/domains/jobs/types";
import type { ProjectSchema } from "@/domains/projects/types";
import type { WorkbookMutationType } from "@/domains/workbooks/types";
import { buttonClassName } from "@/shared/ui/primitives";
import { WorkbookWorkflowPanel } from "@/shared/ui/WorkbookWorkflowPanel";

import styles from "@/shared/ui/EditPanel.module.css";

export type EditPanelProps = {
  projectId: number;
  branchRef: string;
  schema: ProjectSchema;
  allowRange: boolean;
  importBatches?: unknown[];
  onJobCreated: (job: JobDetail) => void;
};

export function EditPanel(props: EditPanelProps) {
  const [mutationType, setMutationType] = useState<WorkbookMutationType>("content");
  const rangeDisabled = !props.allowRange;

  return (
    <div className={styles.panel}>
      <fieldset className={styles.fieldset}>
        <legend>Mutation type</legend>
        <label>
          <input
            type="radio"
            checked={mutationType === "content"}
            onChange={() => setMutationType("content")}
          />
          Content
        </label>
        <label>
          <input
            type="radio"
            checked={mutationType === "range"}
            disabled={rangeDisabled}
            onChange={() => setMutationType("range")}
          />
          Range
        </label>
      </fieldset>
      <WorkbookWorkflowPanel
        projectId={props.projectId}
        workflowKind="branch_mutation"
        branchRef={props.branchRef}
        mutationType={mutationType}
        title={`${mutationType === "content" ? "Content" : "Range"} mutation from workbook`}
        uploadLabel="Upload workbook"
        executeLabel="Apply Mutation"
        onJobCompleted={props.onJobCreated}
      />
    </div>
  );
}
```

This leaves `schema` in props because callers already provide it; remove it from props only after all call sites are updated.

- [ ] **Step 3: Update BranchDetail call site**

In `frontend/src/pages/dev/BranchDetail.tsx`, keep the `EditPanel` call but remove `importBatches` usage after TypeScript confirms it is unused. The call should be:

```tsx
<EditPanel
  projectId={projectId}
  branchRef={branchRef}
  schema={schema}
  allowRange={true}
  onJobCreated={handleJobCreated}
/>
```

- [ ] **Step 4: Update Release edit call site**

In `frontend/src/pages/release/ReleasePage.tsx`, ensure the `EditPanel` call uses:

```tsx
<EditPanel
  projectId={projectId}
  branchRef="rel/current"
  schema={schema}
  allowRange={true}
  onJobCreated={handleJobCreated}
/>
```

If Release currently passes `importBatches`, remove that prop.

- [ ] **Step 5: Update e2e assertions**

In `tests/e2e/product-app.spec.js`, update tests that look for `Input method`, `Direct`, TSV textareas, or import batch selectors. Replace them with assertions for:

```javascript
await expect(page.getByText("Mutation type")).toBeVisible();
await expect(page.getByText("Content")).toBeVisible();
await expect(page.getByText("Range")).toBeVisible();
await expect(page.getByText("Upload workbook")).toBeVisible();
```

For create branch mocked routes, replace old `/imports/upload-folder/preview`, `/imports/upload-folder`, and `/branches/bootstrap/preview` route mocks with:

```javascript
await page.route("**/api/projects/1/workbooks/intake/preview", async (route) => {
  await route.fulfill({
    json: {
      upload_session_id: "session-for-create-branch",
      workflow_kind: "create_branch",
      mutation_type: null,
      file_count: 1,
      sheet_count: 1,
      missing_required_headers: [],
      sampled_issue_count: 0,
      sheet_previews: [],
    },
  });
});

await page.route("**/api/projects/1/workbooks/intake/execute", async (route) => {
  await route.fulfill({
    json: buildJobDetail({
      job_id: 900,
      job_type: "workbook_create_branch",
      status: "running",
    }),
  });
});
```

- [ ] **Step 6: Run frontend build**

Run:

```powershell
npm run build:app
```

Expected: PASS.

- [ ] **Step 7: Run focused e2e suite**

Run:

```powershell
npm run test:e2e
```

Expected: PASS or failures only where tests still refer to removed Direct/Import batch UI. Fix those references in this task.

- [ ] **Step 8: Commit**

Run:

```powershell
git add frontend/src/pages/dev/CreateBranch.tsx frontend/src/shared/ui/EditPanel.tsx frontend/src/pages/dev/BranchDetail.tsx frontend/src/pages/release/ReleasePage.tsx tests/e2e/product-app.spec.js
git commit -m "feat: use workbook upload for branch edit flows"
```

---

### Task 10: Replace Trash UI And Update Docs

**Files:**

- Modify: `frontend/src/shared/ui/TrashPanel.tsx`
- Modify: `docs/contracts.md`
- Modify: `docs/workflows.md`
- Test: `tests/e2e/product-app.spec.js`

- [ ] **Step 1: Replace textarea trash panel with workbook workflow panel**

In `frontend/src/shared/ui/TrashPanel.tsx`, replace textarea-based key entry with two `WorkbookWorkflowPanel` usages:

```tsx
import type { JobDetail } from "@/domains/jobs/types";
import { WorkbookWorkflowPanel } from "@/shared/ui/WorkbookWorkflowPanel";

export function TrashPanel(props: {
  projectId: number;
  branchRef: string;
  showProjectTrash: boolean;
  onJobCreated: (job: JobDetail) => void;
}) {
  return (
    <div>
      <WorkbookWorkflowPanel
        projectId={props.projectId}
        workflowKind="branch_trash"
        branchRef={props.branchRef}
        title={`Delete from ${props.branchRef}`}
        uploadLabel="Upload key workbook"
        executeLabel="Delete From Branch"
        onJobCompleted={props.onJobCreated}
      />
      {props.showProjectTrash && (
        <WorkbookWorkflowPanel
          projectId={props.projectId}
          workflowKind="project_trash"
          title="Trash orphan variants"
          uploadLabel="Upload key workbook"
          executeLabel="Trash Orphans"
          onJobCompleted={props.onJobCreated}
        />
      )}
    </div>
  );
}
```

Preserve existing CSS module imports only if the final component still uses them.

- [ ] **Step 2: Update e2e trash expectations**

In `tests/e2e/product-app.spec.js`, replace assertions for key textarea placeholders with:

```javascript
await expect(page.getByText("Upload key workbook")).toBeVisible();
await expect(page.getByText("Delete From Branch")).toBeVisible();
```

Mock `/api/projects/1/workbooks/intake/preview` and `/api/projects/1/workbooks/intake/execute` for trash tests using the same payload shape from Task 9, with `workflow_kind: "branch_trash"`.

- [ ] **Step 3: Update `docs/contracts.md`**

Update `docs/contracts.md` sections:

```markdown
Workbook workflow input:

- `POST /api/projects/{project_id}/workbooks/intake/preview` accepts multipart workbook uploads plus workflow context and returns lightweight precheck data.
- `POST /api/projects/{project_id}/workbooks/intake/execute` accepts `upload_session_id`, `workflow_kind`, optional `branch_ref`, and optional `mutation_type`, then starts one async job that parses the workbook and applies the workflow.
- Product write flows no longer expose Direct or Import batch as input methods.
- Branch content mutation and branch range mutation both require configured key and source workbook headers.
- Branch trash and project trash require only the configured key workbook header.
```

Add the two workbook routes to the HTTP route inventory.

- [ ] **Step 4: Update `docs/workflows.md`**

Update workflow docs with:

```markdown
Workbook write workflow:

- create branch, branch mutation, branch trash, and project trash use workflow-specific workbook uploads
- upload precheck is lightweight and validates files, sheets, headers, and sampled row issues
- execute starts one async job that persists workbook rows and applies the target workflow
- content mutation requires configured key + source and only updates the currently bound branch variant
- content mutation never binds, rebinds, creates variants, or changes branch range
- range mutation requires configured key + source and may bind, rebind, or create variants according to branch policy
- trash workflows require configured key only
```

Remove or rewrite product-facing guidance that presents Direct TSV or Import batch selection as the main branch edit input.

- [ ] **Step 5: Run docs validation**

Run:

```powershell
.\.venv\Scripts\python.exe scripts\validate_docs.py
```

Expected: It may still fail on pre-existing design archive references. It must not report new failures for `docs/contracts.md` or `docs/workflows.md`.

- [ ] **Step 6: Run frontend build**

Run:

```powershell
npm run build:app
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```powershell
git add frontend/src/shared/ui/TrashPanel.tsx tests/e2e/product-app.spec.js docs/contracts.md docs/workflows.md
git commit -m "feat: use workbook upload for trash flows"
```

---

### Task 11: Cleanup Legacy Product Input Paths

**Files:**

- Modify: `frontend/src/domains/imports/api.ts`
- Modify: `frontend/src/domains/imports/types.ts`
- Modify: `frontend/src/domains/branches/api.ts`
- Modify: `frontend/src/domains/branches/types.ts`
- Modify: `frontend/src/shared/api/queryKeys.ts`
- Modify: `docs/contracts.md`
- Modify: `docs/workflows.md`
- Test: `tests/e2e/product-app.spec.js`

- [ ] **Step 1: Search for old product input labels**

Run:

```powershell
Select-String -Path frontend\src\**\*.tsx,frontend\src\**\*.ts,tests\e2e\*.js -Pattern 'Direct|Import batch|Input method|import_batch|previewBranchMutation|confirmImportUpload|previewImportUpload'
```

Expected: remaining hits are either backend-compatible domain helpers, tests for removed compatibility, or code that this task removes.

- [ ] **Step 2: Remove unused frontend imports helpers from product flows**

If `previewImportUpload` and `confirmImportUpload` are no longer imported by any `.tsx` file, leave `frontend/src/domains/imports/api.ts` only for import list/report pages. The branch write UI must not import these helpers.

Remove unused branch mutation preview helpers from `frontend/src/domains/branches/api.ts` only if no page uses them:

```typescript
export function previewBranchMutation(...)
```

If tests or debug pages still use the helper, keep the function but remove product page imports.

- [ ] **Step 3: Remove obsolete query keys**

In `frontend/src/shared/api/queryKeys.ts`, remove query keys for old bootstrap preview or mutation preview only when no caller remains. Keep job/import report keys used by Runs.

- [ ] **Step 4: Add e2e absence checks**

In the main product app e2e test that visits Dev edit and Release edit, add:

```javascript
await expect(page.getByText("Input method")).toHaveCount(0);
await expect(page.getByText("Direct")).toHaveCount(0);
await expect(page.getByText("Import batch")).toHaveCount(0);
```

If `toHaveCount` is not available in the local Playwright version, use:

```javascript
await expect(page.getByText("Input method")).not.toBeVisible();
await expect(page.getByText("Direct")).not.toBeVisible();
await expect(page.getByText("Import batch")).not.toBeVisible();
```

- [ ] **Step 5: Run frontend tests**

Run:

```powershell
npm run build:app
npm run test:e2e
```

Expected: PASS.

- [ ] **Step 6: Run backend workflow tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_workbook_intake.py tests\test_branch_service.py tests\test_variant_api.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```powershell
git add frontend/src tests/e2e docs/contracts.md docs/workflows.md
git commit -m "chore: remove legacy branch input UI"
```

---

### Task 12: Final Verification

**Files:**

- No source edits expected unless verification finds failures.

- [ ] **Step 1: Run backend regression suite**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend build**

Run:

```powershell
npm run build:app
```

Expected: PASS.

- [ ] **Step 3: Run e2e suite**

Run:

```powershell
npm run test:e2e
```

Expected: PASS.

- [ ] **Step 4: Run docs validator**

Run:

```powershell
.\.venv\Scripts\python.exe scripts\validate_docs.py
```

Expected: no new failures from changed active docs. If existing design archive failures remain, record the exact unchanged failure categories in the final summary.

- [ ] **Step 5: Inspect final diff**

Run:

```powershell
git status --short
git log --oneline -12
```

Expected: working tree clean after all task commits.

---

## Self-Review

Spec coverage:

- Project-level key/source header contract is implemented in Task 1.
- Upload and parser separation is implemented in Tasks 2, 3, and 6.
- Large workbook chunking and bounded previews are implemented in Tasks 2, 3, and 6.
- Create branch workbook workflow is implemented in Task 6 and verified in Task 7.
- Content mutation key+source semantics and no rebind behavior are implemented in Task 4.
- Range mutation keeps existing policy through the import-batch applier in Task 4.
- Trash key-only workflow is implemented in Task 5 and exposed in Task 7.
- Frontend workbook panels and mutation type selector are implemented in Tasks 8, 9, and 10.
- Legacy UI cleanup is implemented in Task 11.
- Active docs updates are implemented in Task 10.

Type consistency:

- Backend workflow names are `create_branch`, `branch_mutation`, `branch_trash`, and `project_trash`.
- Mutation types are `content` and `range`.
- Public precheck response uses `upload_session_id`, `missing_required_headers`, `sampled_issue_count`, and `sheet_previews`.
- Persisted workbook batch IDs reuse existing import IDs internally and are exposed as `workbook_batch_id`.
