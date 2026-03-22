from __future__ import annotations

from app.services.branch.models import BranchRef
from app.services.shared.io import normalize_content_map, normalize_non_content_map, normalize_non_content_value
from app.services.variant.catalog import VariantCatalogService


class VariantResolutionService:
    def __init__(self, catalog: VariantCatalogService | None = None) -> None:
        self.catalog = catalog or VariantCatalogService()

    def merged_variant_payload(
        self,
        base_variant: dict[str, object] | None,
        change: dict[str, object],
        source: str,
    ) -> dict[str, object]:
        translations = dict(base_variant["translations"]) if base_variant is not None else {}
        translations.update(change.get("translations_by_lang", {}))
        remarks = dict(base_variant["remarks"]) if base_variant is not None else {}
        remarks.update(change.get("remarks_by_key", {}))
        if change.get("file_name") is not None:
            file_name = change.get("file_name")
        elif base_variant is not None:
            file_name = base_variant["file_name"]
        else:
            file_name = None
        return {
            "file_name": normalize_non_content_value(file_name),
            "source": normalize_non_content_value(source),
            "translations": normalize_content_map(translations),
            "remarks": normalize_non_content_map(remarks),
        }

    def variant_matches(self, variant: dict[str, object], payload: dict[str, object]) -> bool:
        return (
            variant["file_name"] == payload["file_name"]
            and variant["source"] == payload["source"]
            and dict(variant["translations"]) == payload["translations"]
            and dict(variant["remarks"]) == payload["remarks"]
        )

    def bound_branch_refs_for_variant(self, bindings: list[dict[str, object]], variant_id: int) -> list[BranchRef]:
        return [
            BranchRef.parse(f"{binding['scope_type']}/{binding['scope_value']}")
            for binding in bindings
            if int(binding["variant_id"]) == variant_id
        ]

    def find_source_variant_in_cache(
        self,
        entry_id: int,
        variants: list[dict[str, object]],
        source: str,
    ) -> dict[str, object] | None:
        normalized_source = normalize_non_content_value(source)
        candidates = [variant for variant in variants if variant["source"] == normalized_source]
        if not candidates:
            return None
        if len(candidates) > 1:
            raise RuntimeError(
                f"duplicate active variants found for entry_id={entry_id}, source={normalized_source!r}"
            )
        return candidates[0]

    def payload_matches_variant(self, variant: dict[str, object], payload: dict[str, object]) -> bool:
        normalized_payload = self.catalog.build_content(
            payload.get("file_name"),
            payload["source"],
            payload.get("translations", {}),
            payload.get("remarks", {}),
        )
        return (
            variant["file_name"] == normalized_payload["file_name"]
            and variant["source"] == normalized_payload["source"]
            and dict(variant["translations"]) == normalized_payload["translations"]
            and dict(variant["remarks"]) == normalized_payload["remarks"]
        )
