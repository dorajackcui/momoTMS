from __future__ import annotations

from typing import Any, Mapping


def safe_to_str(value: Any, strip: bool = True) -> str:
    if value is None:
        return ""
    text = str(value)
    return text.strip() if strip else text


def is_blank_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def normalize_non_content_value(value: Any) -> str:
    return safe_to_str(value, strip=True)


def normalize_content_value(value: Any) -> str:
    text = safe_to_str(value, strip=False)
    return "" if is_blank_value(text) else text


def normalize_non_content_map(values: Mapping[str, Any]) -> dict[str, str]:
    return {key: normalize_non_content_value(value) for key, value in values.items()}


def normalize_content_map(values: Mapping[str, Any]) -> dict[str, str]:
    return {key: normalize_content_value(value) for key, value in values.items()}


def normalize_fill_combined_key(business_key: Any, source: Any) -> tuple[str, str]:
    return (
        normalize_non_content_value(business_key),
        normalize_non_content_value(source),
    )


def has_valid_fill_combined_key(business_key: Any, source: Any) -> bool:
    normalized_key, normalized_source = normalize_fill_combined_key(business_key, source)
    return bool(normalized_key and normalized_source)
