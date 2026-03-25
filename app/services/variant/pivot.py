from __future__ import annotations

import hashlib
import sqlite3
from typing import TypedDict

from app.db import get_conn
from app.services.project.service import ProjectService
from app.services.shared.io import normalize_content_value
from app.services.shared.utils import now_iso
from app.services.variant.entries import EntryService
from app.services.variant.records import VariantRecord
from app.services.variant.repositories import VariantQueryRepository

PIVOT_IN_SYNC = "PIVOT_IN_SYNC"
PIVOT_OUT_OF_SYNC = "PIVOT_OUT_OF_SYNC"
MISSING_CHILD = "MISSING_CHILD"
MISSING_PARENT = "MISSING_PARENT"


class PivotSyncStateRecord(TypedDict):
    variant_id: int
    lang: str
    pivot_lang: str
    pivot_fingerprint_at_sync: str
    pivot_synced_at: str
    created_at: str
    updated_at: str


def fingerprint_translation(value: str) -> str:
    return hashlib.sha256(normalize_content_value(value).encode("utf-8")).hexdigest()


def derive_pivot_sync_status(
    *,
    child_text: str,
    parent_text: str,
    pivot_fingerprint_at_sync: str | None,
) -> str:
    normalized_parent = normalize_content_value(parent_text)
    if not normalized_parent:
        return MISSING_PARENT
    normalized_child = normalize_content_value(child_text)
    if not normalized_child:
        return MISSING_CHILD
    if pivot_fingerprint_at_sync == fingerprint_translation(normalized_parent):
        return PIVOT_IN_SYNC
    return PIVOT_OUT_OF_SYNC


class VariantPivotRepository:
    def list_sync_states(
        self,
        variant_ids: list[int],
        *,
        lang: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> dict[tuple[int, str], PivotSyncStateRecord]:
        if not variant_ids:
            return {}
        placeholders = ", ".join("?" for _ in variant_ids)
        where = [f"variant_id IN ({placeholders})"]
        params: list[object] = [*variant_ids]
        if lang is not None:
            where.append("lang = ?")
            params.append(lang)
        query = f"""
            SELECT *
            FROM variant_translation_sync_state
            WHERE {' AND '.join(where)}
        """
        if conn is not None:
            rows = conn.execute(query, params).fetchall()
        else:
            with get_conn() as local_conn:
                rows = local_conn.execute(query, params).fetchall()
        return {
            (int(row["variant_id"]), row["lang"]): {
                "variant_id": int(row["variant_id"]),
                "lang": row["lang"],
                "pivot_lang": row["pivot_lang"],
                "pivot_fingerprint_at_sync": row["pivot_fingerprint_at_sync"],
                "pivot_synced_at": row["pivot_synced_at"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        }

    def upsert_sync_state(
        self,
        *,
        variant_id: int,
        lang: str,
        pivot_lang: str,
        pivot_fingerprint_at_sync: str,
        pivot_synced_at: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        timestamp = now_iso()
        if conn is not None:
            conn.execute(
                """
                INSERT INTO variant_translation_sync_state(
                    variant_id,
                    lang,
                    pivot_lang,
                    pivot_fingerprint_at_sync,
                    pivot_synced_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(variant_id, lang) DO UPDATE SET
                    pivot_lang = excluded.pivot_lang,
                    pivot_fingerprint_at_sync = excluded.pivot_fingerprint_at_sync,
                    pivot_synced_at = excluded.pivot_synced_at,
                    updated_at = excluded.updated_at
                """,
                (
                    variant_id,
                    lang,
                    pivot_lang,
                    pivot_fingerprint_at_sync,
                    pivot_synced_at,
                    timestamp,
                    timestamp,
                ),
            )
            return
        with get_conn() as local_conn:
            self.upsert_sync_state(
                variant_id=variant_id,
                lang=lang,
                pivot_lang=pivot_lang,
                pivot_fingerprint_at_sync=pivot_fingerprint_at_sync,
                pivot_synced_at=pivot_synced_at,
                conn=local_conn,
            )


class VariantPivotCoordinator:
    def __init__(
        self,
        *,
        entries: EntryService | None = None,
        projects: ProjectService | None = None,
        sync_states: VariantPivotRepository | None = None,
        variant_queries: VariantQueryRepository | None = None,
    ) -> None:
        self.entries = entries or EntryService()
        self.projects = projects or ProjectService()
        self.sync_states = sync_states or VariantPivotRepository()
        self.variant_queries = variant_queries or VariantQueryRepository()

    def initialize_variant(
        self,
        *,
        entry_id: int,
        variant_id: int,
        translations: dict[str, str],
        conn: sqlite3.Connection | None = None,
    ) -> None:
        project_id = self._project_id_for_entry(entry_id, conn=conn)
        topology = self._translation_pivots(project_id)
        timestamp = now_iso()
        for child_lang, pivot_lang in topology.items():
            if pivot_lang is None:
                continue
            parent_text = normalize_content_value(translations.get(pivot_lang))
            pivot_fingerprint_at_sync = fingerprint_translation(parent_text) if parent_text else ""
            self.sync_states.upsert_sync_state(
                variant_id=variant_id,
                lang=child_lang,
                pivot_lang=pivot_lang,
                pivot_fingerprint_at_sync=pivot_fingerprint_at_sync,
                pivot_synced_at=timestamp,
                conn=conn,
            )

    def refresh_variant(
        self,
        *,
        variant_id: int,
        old_variant: VariantRecord | None,
        new_translations: dict[str, str],
        conn: sqlite3.Connection | None = None,
    ) -> None:
        current_variant = old_variant or self.variant_queries.get(variant_id, conn=conn)
        if current_variant is None:
            raise KeyError(f"variant not found: {variant_id}")
        project_id = self._project_id_for_entry(int(current_variant["entry_id"]), conn=conn)
        topology = self._translation_pivots(project_id)
        pivot_children = {child: parent for child, parent in topology.items() if parent is not None}
        if not pivot_children:
            return
        changed_languages = self._changed_languages(current_variant, new_translations)
        if not changed_languages:
            return
        existing_states = self.sync_states.list_sync_states([variant_id], conn=conn)
        timestamp = now_iso()
        for child_lang, pivot_lang in pivot_children.items():
            if child_lang not in changed_languages and pivot_lang not in changed_languages:
                continue
            child_changed = child_lang in changed_languages
            parent_changed = pivot_lang in changed_languages
            new_parent_text = normalize_content_value(new_translations.get(pivot_lang))
            new_child_text = normalize_content_value(new_translations.get(child_lang))
            existing = existing_states.get((variant_id, child_lang))
            if child_changed and new_parent_text and new_child_text:
                pivot_fingerprint_at_sync = fingerprint_translation(new_parent_text)
            elif existing is not None:
                pivot_fingerprint_at_sync = existing["pivot_fingerprint_at_sync"]
            else:
                pivot_fingerprint_at_sync = ""
            if child_changed or parent_changed or existing is None:
                self.sync_states.upsert_sync_state(
                    variant_id=variant_id,
                    lang=child_lang,
                    pivot_lang=pivot_lang,
                    pivot_fingerprint_at_sync=pivot_fingerprint_at_sync,
                    pivot_synced_at=timestamp if child_changed and new_parent_text and new_child_text else (
                        existing["pivot_synced_at"] if existing is not None else timestamp
                    ),
                    conn=conn,
                )

    def _changed_languages(self, current_variant: VariantRecord, new_translations: dict[str, str]) -> set[str]:
        old_map = {lang: normalize_content_value(value) for lang, value in current_variant["translations"].items()}
        new_map = {lang: normalize_content_value(value) for lang, value in new_translations.items()}
        return {lang for lang in set(old_map) | set(new_map) if old_map.get(lang, "") != new_map.get(lang, "")}

    def _project_id_for_entry(self, entry_id: int, *, conn: sqlite3.Connection | None = None) -> int:
        entry = self.entries.get_entry_by_id(entry_id, conn=conn)
        if entry is None:
            raise KeyError(f"entry not found: {entry_id}")
        return int(entry["project_id"])

    def _translation_pivots(self, project_id: int) -> dict[str, str | None]:
        schema = self.projects.get_schema(project_id)
        return dict(schema["translation_pivots"])
