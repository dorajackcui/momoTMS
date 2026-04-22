from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Literal

PreviewKind = Literal["input_precheck", "effect_forecast"]
PreviewWorkflowKind = Literal["import_upload", "branch_bootstrap", "branch_mutation", "branch_replace"]
PreviewBindingEffect = Literal["none", "bind", "rebind"]
PreviewVariantResolution = Literal["stay_current", "reuse_existing", "create_new"]
PreviewRowOutcome = Literal["applied", "noop", "missing", "invalid"]

_SEMANTIC_VOCAB: dict[str, tuple[str, ...]] = {
    "binding_effect": ("none", "bind", "rebind"),
    "variant_resolution": ("stay_current", "reuse_existing", "create_new"),
    "row_outcome": ("applied", "noop", "missing", "invalid"),
}

_COUNT_SUFFIXES: dict[str, dict[str, str]] = {
    "binding_effect": {
        "none": "none_count",
        "bind": "bind_count",
        "rebind": "rebind_count",
    },
    "variant_resolution": {
        "stay_current": "stay_current_count",
        "reuse_existing": "reuse_existing_count",
        "create_new": "create_new_count",
    },
    "row_outcome": {
        "applied": "applied_count",
        "noop": "noop_count",
        "missing": "missing_count",
        "invalid": "invalid_count",
    },
}


def effect_forecast_row(
    base: dict[str, object],
    *,
    row_outcome: PreviewRowOutcome,
    binding_effect: PreviewBindingEffect | None = None,
    variant_resolution: PreviewVariantResolution | None = None,
) -> dict[str, object]:
    row = dict(base)
    if binding_effect is not None:
        row["binding_effect"] = binding_effect
    if variant_resolution is not None:
        row["variant_resolution"] = variant_resolution
    row["row_outcome"] = row_outcome
    return row


@dataclass
class EffectPreviewSummaryBuilder:
    _binding_effect_counts: Counter[str] = field(default_factory=Counter, init=False, repr=False)
    _variant_resolution_counts: Counter[str] = field(default_factory=Counter, init=False, repr=False)
    _row_outcome_counts: Counter[str] = field(default_factory=Counter, init=False, repr=False)

    def add_row(self, row: dict[str, object]) -> None:
        row_outcome = row.get("row_outcome")
        if row_outcome not in _SEMANTIC_VOCAB["row_outcome"]:
            raise ValueError(
                f"invalid row_outcome: {row_outcome!r}; expected one of {_SEMANTIC_VOCAB['row_outcome']!r}"
            )
        self._row_outcome_counts[str(row_outcome)] += 1

        for semantic_key in ("binding_effect", "variant_resolution"):
            value = row.get(semantic_key)
            if value is None:
                continue
            allowed_values = _SEMANTIC_VOCAB[semantic_key]
            if value not in allowed_values:
                raise ValueError(
                    f"invalid {semantic_key}: {value!r}; expected one of {allowed_values!r}"
                )
            counter = getattr(self, f"_{semantic_key}_counts")
            counter[str(value)] += 1

    def as_dict(self) -> dict[str, dict[str, int]]:
        def grouped_counts(semantic_key: str, counter: Counter[str]) -> dict[str, int]:
            return {
                suffix: counter.get(value, 0)
                for value, suffix in _COUNT_SUFFIXES[semantic_key].items()
            }

        return {
            "binding_effect_counts": grouped_counts("binding_effect", self._binding_effect_counts),
            "variant_resolution_counts": grouped_counts("variant_resolution", self._variant_resolution_counts),
            "row_outcome_counts": grouped_counts("row_outcome", self._row_outcome_counts),
        }
