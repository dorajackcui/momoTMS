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
