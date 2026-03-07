from pathlib import Path
import re

import pytest

from app.db import DB_PATH, init_db
from app.services.project.service import ProjectService


def reset_db() -> None:
    if Path(DB_PATH).exists():
        Path(DB_PATH).unlink()
    init_db()


def test_create_project_sets_default_only_for_first_project() -> None:
    reset_db()
    service = ProjectService()

    first = service.create_project(" First Project ", [" fr ", " en "], [" context "])
    second = service.create_project("Second Project", ["fr"], ["context"])

    assert first["name"] == "First Project"
    assert first["is_default"] is True
    assert second["is_default"] is False


@pytest.mark.parametrize(
    ("translation_columns", "remark_columns", "message"),
    [
        (["fr", "fr"], ["context"], "translation_columns contains duplicate column: fr"),
        (["fr"], ["context", "context"], "remark_columns contains duplicate column: context"),
        (["fr"], ["fr"], "schema columns must be distinct across translations and remarks: ['fr']"),
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
