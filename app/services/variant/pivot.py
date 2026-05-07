from __future__ import annotations

import sqlite3

from app.services.project.service import ProjectService
from app.services.shared.io import normalize_content_value
from app.services.shared.utils import now_iso
from app.services.variant.entries import EntryService
from app.services.variant.records import VariantRecord
from app.services.variant.repositories import VariantCommandRepository, VariantQueryRepository

PIVOT_STATUS_INIT = "init"
PIVOT_STATUS_CHANGED = "changed"
PIVOT_STATUS_REVIEWED = "reviewed"


def pivot_language_requires_review(
    current_variant: VariantRecord | dict[str, object],
    new_translations: dict[str, str],
    pivot_language: str,
) -> bool:
    current_translations = dict(current_variant.get("translations") or {})
    old_value = normalize_content_value(current_translations.get(pivot_language))
    new_value = normalize_content_value(new_translations.get(pivot_language))
    if old_value == new_value:
        return False
    if current_variant.get("pivot_status") == PIVOT_STATUS_INIT and old_value == "":
        return False
    return True


def pivot_changed_by_branch_ref(variant: VariantRecord | dict[str, object]) -> str | None:
    scope_type = variant.get("pivot_changed_by_scope_type")
    scope_value = variant.get("pivot_changed_by_scope_value")
    if scope_type is None or scope_value is None:
        return None
    return f"{scope_type}/{scope_value}"


class VariantPivotCoordinator:
    def __init__(
        self,
        *,
        entries: EntryService | None = None,
        projects: ProjectService | None = None,
        variant_commands: VariantCommandRepository | None = None,
        variant_queries: VariantQueryRepository | None = None,
    ) -> None:
        self.entries = entries or EntryService()
        self.projects = projects or ProjectService()
        self.variant_commands = variant_commands or VariantCommandRepository()
        self.variant_queries = variant_queries or VariantQueryRepository()

    def refresh_variant(
        self,
        *,
        variant_id: int,
        old_variant: VariantRecord | None,
        new_translations: dict[str, str],
        actor_scope: tuple[str, str] | None,
        timestamp: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        if actor_scope is None:
            return
        current_variant = old_variant or self.variant_queries.get(variant_id, conn=conn)
        if current_variant is None:
            raise KeyError(f"variant not found: {variant_id}")
        project_id = self._project_id_for_entry(int(current_variant["entry_id"]), conn=conn)
        pivot_language = self._pivot_language(project_id)
        if pivot_language is None:
            return
        if not self._pivot_translation_changed(current_variant, new_translations, pivot_language):
            return
        marker = timestamp or now_iso()
        scope_type, scope_value = actor_scope
        self.variant_commands.set_pivot_changed(
            variant_id,
            scope_type,
            scope_value,
            marker,
            conn=conn,
        )

    def review_variant(
        self,
        *,
        variant_id: int,
        timestamp: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        self.variant_commands.set_pivot_reviewed(variant_id, timestamp or now_iso(), conn=conn)

    def _project_id_for_entry(self, entry_id: int, *, conn: sqlite3.Connection | None = None) -> int:
        entry = self.entries.get_entry_by_id(entry_id, conn=conn)
        if entry is None:
            raise KeyError(f"entry not found: {entry_id}")
        return int(entry["project_id"])

    def _pivot_language(self, project_id: int) -> str | None:
        schema = self.projects.get_schema(project_id)
        return schema["pivot_language"]

    def _pivot_translation_changed(
        self,
        current_variant: VariantRecord,
        new_translations: dict[str, str],
        pivot_language: str,
    ) -> bool:
        return pivot_language_requires_review(current_variant, new_translations, pivot_language)
