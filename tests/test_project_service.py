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


def test_create_project_defaults_translation_pivots_to_null() -> None:
    reset_db()
    service = ProjectService()

    project = service.create_project("Pivot Defaults", ["fr", "en"], ["context"])
    schema = service.get_schema(int(project["project_id"]))

    assert schema["translation_pivots"] == {"fr": None, "en": None}


def test_create_project_accepts_sparse_translation_pivots_and_exposes_full_map() -> None:
    reset_db()
    service = ProjectService()

    project = service.create_project(
        "Pivot Sparse",
        ["fr", "en", "de"],
        ["context"],
        {"fr": "en"},
    )
    schema = service.get_schema(int(project["project_id"]))

    assert schema["translation_pivots"] == {"fr": "en", "en": None, "de": None}


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
    ("translation_pivots", "message"),
    [
        ({"fr": "fr"}, "translation_pivots cannot point a language to itself: fr"),
        ({"fr": "jp"}, "translation_pivots contains unknown parent language for fr: jp"),
        ({"jp": "en"}, "translation_pivots contains unknown child language: jp"),
        (
            {"fr": "en", "en": "de"},
            "translation_pivots cannot assign a parent to referenced pivot parent: en",
        ),
        (
            {"fr": "en", "en": "fr"},
            "translation_pivots cannot assign a parent to referenced pivot parent: en",
        ),
    ],
)
def test_create_project_rejects_invalid_translation_pivots(
    translation_pivots: dict[str, str | None],
    message: str,
) -> None:
    reset_db()

    with pytest.raises(ValueError, match=re.escape(message)):
        ProjectService().create_project("Bad Pivot Project", ["fr", "en", "de"], ["context"], translation_pivots)
