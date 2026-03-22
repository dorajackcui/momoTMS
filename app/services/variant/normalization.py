from __future__ import annotations

from typing import Any

from app.services.shared.io import normalize_non_content_value


def require_non_content_value(field_name: str, value: Any) -> str:
    normalized = normalize_non_content_value(value)
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def normalize_business_keys(business_keys: list[str]) -> list[str]:
    normalized_keys: list[str] = []
    seen: set[str] = set()
    for value in business_keys:
        normalized = normalize_non_content_value(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        normalized_keys.append(normalized)
    return normalized_keys


def normalize_variant_ids(variant_ids: list[int]) -> list[int]:
    normalized_ids: list[int] = []
    seen: set[int] = set()
    for value in variant_ids:
        try:
            variant_id = int(value)
        except (TypeError, ValueError):
            continue
        if variant_id <= 0 or variant_id in seen:
            continue
        seen.add(variant_id)
        normalized_ids.append(variant_id)
    return normalized_ids
