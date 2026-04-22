from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Literal

MutationClass = Literal["range", "content"]
BindingEffect = Literal["none", "bind", "rebind"]
ContentEffect = Literal["none", "create", "update", "filtered"]
RowOutcome = Literal["applied", "noop", "missing"]

_SEMANTIC_VOCAB: dict[str, tuple[str, ...]] = {
    "mutation_class": ("range", "content"),
    "binding_effect": ("none", "bind", "rebind"),
    "content_effect": ("none", "create", "update", "filtered"),
    "row_outcome": ("applied", "noop", "missing"),
}

_COUNT_SUFFIXES: dict[str, dict[str, str]] = {
    "mutation_class": {
        "range": "range_count",
        "content": "content_count",
    },
    "binding_effect": {
        "none": "none_count",
        "bind": "bind_count",
        "rebind": "rebind_count",
    },
    "content_effect": {
        "none": "none_count",
        "create": "create_count",
        "update": "update_count",
        "filtered": "filtered_count",
    },
    "row_outcome": {
        "applied": "applied_count",
        "noop": "noop_count",
        "missing": "missing_count",
    },
}


@dataclass(frozen=True)
class MutationSemantics:
    mutation_class: MutationClass
    binding_effect: BindingEffect
    content_effect: ContentEffect
    row_outcome: RowOutcome

    def as_dict(self) -> dict[str, str]:
        return {
            "mutation_class": self.mutation_class,
            "binding_effect": self.binding_effect,
            "content_effect": self.content_effect,
            "row_outcome": self.row_outcome,
        }


def semantics_row(
    base: dict[str, object],
    *,
    mutation_class: MutationClass,
    binding_effect: BindingEffect,
    content_effect: ContentEffect,
    row_outcome: RowOutcome,
) -> dict[str, object]:
    row = dict(base)
    row.update(
        MutationSemantics(
            mutation_class=mutation_class,
            binding_effect=binding_effect,
            content_effect=content_effect,
            row_outcome=row_outcome,
        ).as_dict()
    )
    return row


@dataclass
class MutationSemanticSummaryBuilder:
    _mutation_class_counts: Counter[str] = field(default_factory=Counter, init=False, repr=False)
    _binding_effect_counts: Counter[str] = field(default_factory=Counter, init=False, repr=False)
    _content_effect_counts: Counter[str] = field(default_factory=Counter, init=False, repr=False)
    _row_outcome_counts: Counter[str] = field(default_factory=Counter, init=False, repr=False)

    def add_row(self, row: dict[str, object]) -> None:
        for semantic_key, allowed_values in _SEMANTIC_VOCAB.items():
            try:
                value = row[semantic_key]
            except KeyError as exc:
                raise KeyError(f"missing required semantic key: {semantic_key}") from exc

            if value not in allowed_values:
                raise ValueError(
                    f"invalid {semantic_key}: {value!r}; expected one of {allowed_values!r}"
                )

            counter = getattr(self, f"_{semantic_key}_counts")
            counter[str(value)] += 1

    def as_dict(self) -> dict[str, dict[str, int]]:
        def grouped_counts(
            semantic_key: str,
            counter: Counter[str],
        ) -> dict[str, int]:
            return {
                suffix: counter.get(value, 0)
                for value, suffix in _COUNT_SUFFIXES[semantic_key].items()
            }

        return {
            "mutation_class_counts": grouped_counts(
                "mutation_class", self._mutation_class_counts
            ),
            "binding_effect_counts": grouped_counts(
                "binding_effect", self._binding_effect_counts
            ),
            "content_effect_counts": grouped_counts(
                "content_effect", self._content_effect_counts
            ),
            "row_outcome_counts": grouped_counts("row_outcome", self._row_outcome_counts),
        }
