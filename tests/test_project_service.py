from pathlib import Path
import re

import pytest

from app.db import get_db_path, init_db
from app.services.project.service import ProjectService


def reset_db() -> None:
    db_path = get_db_path()
    if Path(db_path).exists():
        Path(db_path).unlink()
    init_db()


def test_create_project_sets_default_only_for_first_project() -> None:
    reset_db()
    service = ProjectService()

    first = service.create_project(" First Project ", [" fr ", " en "], [" context "])
    second = service.create_project("Second Project", ["fr"], ["context"])

    assert first["name"] == "First Project"
    assert first["is_default"] is True
    assert second["is_default"] is False


def test_create_project_defaults_to_no_project_pivot() -> None:
    reset_db()
    service = ProjectService()

    project = service.create_project("Pivot Defaults", ["fr", "en"], ["context"])
    schema = service.get_schema(int(project["project_id"]))

    assert schema["pivot_language"] is None
    assert schema["pivoted_languages"] == []


def test_create_project_accepts_single_pivot_language_and_pivoted_languages() -> None:
    reset_db()
    service = ProjectService()

    project = service.create_project(
        "Pivot Sparse",
        ["fr", "en", "de"],
        ["context"],
        "en",
        ["fr"],
    )
    schema = service.get_schema(int(project["project_id"]))

    assert schema["pivot_language"] == "en"
    assert schema["pivoted_languages"] == ["fr"]


def test_preview_and_resolve_headers_allow_sparse_import_language_mapping() -> None:
    reset_db()
    service = ProjectService()

    project = service.create_project("Sparse Import", ["fr", "en"], ["context"])
    project_id = int(project["project_id"])
    preview = service.preview_headers(["business_key", "source", "fr"], project_id)
    mapping = service.resolve_headers(["business_key", "source", "fr"], project_id)

    assert preview["missing_targets"] == []
    assert preview["auto_match_ready"] is True
    assert mapping["business_key"] == 1
    assert mapping["source"] == 2
    assert mapping["translation_columns"] == {"fr": 3}
    assert mapping["remark_columns"] == {}


@pytest.mark.parametrize(
    ("translation_columns", "remark_columns", "message"),
    [
        (["fr", "fr"], ["context"], "translation_columns contains duplicate column: fr"),
        (["fr"], ["context", "context"], "remark_columns contains duplicate column: context"),
        (["fr"], ["fr"], "schema columns must be distinct across translations and remarks: ['fr']"),
        (["file_name"], ["context"], "schema columns cannot reuse fixed business headers"),
        (["business_key"], ["context"], "schema columns cannot reuse fixed business headers"),
        (["fr"], ["source"], "schema columns cannot reuse fixed business headers"),
        (["fr", " "], ["context"], "translation_columns contains a blank column name"),
    ],
)
def test_create_project_rejects_invalid_schema_columns(
    translation_columns: list[str],
    remark_columns: list[str],
    message: str,
) -> None:
    reset_db()

    with pytest.raises(ValueError, match=re.escape(message)):
        ProjectService().create_project("Bad Project", translation_columns, remark_columns)


@pytest.mark.parametrize(
    ("pivot_language", "pivoted_languages", "message"),
    [
        (
            None,
            ["fr"],
            "pivoted_languages requires pivot_language",
        ),
        (
            "jp",
            [],
            "pivot_language must be one of translation_columns: jp",
        ),
        (
            "en",
            ["jp"],
            "pivoted_languages contains unknown language: jp",
        ),
        (
            "en",
            ["en"],
            "pivoted_languages cannot include pivot_language: en",
        ),
        (
            "en",
            ["fr", "fr"],
            "pivoted_languages contains duplicate language: fr",
        ),
    ],
)
def test_create_project_rejects_invalid_pivot_configuration(
    pivot_language: str | None,
    pivoted_languages: list[str],
    message: str,
) -> None:
    reset_db()

    with pytest.raises(ValueError, match=re.escape(message)):
        ProjectService().create_project(
            "Bad Pivot Project",
            ["fr", "en", "de"],
            ["context"],
            pivot_language,
            pivoted_languages,
        )


def test_delete_project_removes_project_and_all_child_data() -> None:
    reset_db()
    service = ProjectService()
    project = service.create_project("Delete Me", ["fr", "en"], ["context"])
    project_id = int(project["project_id"])

    service.delete_project(project_id, "Delete Me")

    with pytest.raises(KeyError, match="project not found"):
        service.get_project(project_id)


def test_delete_project_rejects_name_mismatch() -> None:
    reset_db()
    service = ProjectService()
    project = service.create_project("Real Name", ["fr"], ["context"])
    project_id = int(project["project_id"])

    with pytest.raises(ValueError, match="project name does not match"):
        service.delete_project(project_id, "Wrong Name")

    result = service.get_project(project_id)
    assert result["name"] == "Real Name"


def test_delete_project_raises_on_missing_project() -> None:
    reset_db()
    service = ProjectService()

    with pytest.raises(KeyError, match="project not found"):
        service.delete_project(999, "Anything")
