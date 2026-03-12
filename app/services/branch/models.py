from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.shared.io import normalize_non_content_value


class ScopeType(str, Enum):
    REL = "rel"
    DEV = "dev"


@dataclass(frozen=True)
class ScopeRef:
    scope_type: ScopeType
    scope_value: str

    def __post_init__(self) -> None:
        normalized_value = normalize_non_content_value(self.scope_value)
        if not normalized_value:
            raise ValueError("scope_value is required")
        object.__setattr__(self, "scope_value", normalized_value)
        if self.scope_type == ScopeType.REL and normalized_value != "current":
            raise ValueError(f"invalid release scope: {self}")

    @classmethod
    def parse(cls, scope_ref: str) -> ScopeRef:
        if "/" not in scope_ref:
            raise ValueError(f"invalid scope ref: {scope_ref}")
        scope_type_raw, scope_value = scope_ref.split("/", 1)
        try:
            scope_type = ScopeType(scope_type_raw)
        except ValueError as exc:
            raise ValueError(f"invalid scope ref: {scope_ref}") from exc
        return cls(scope_type=scope_type, scope_value=scope_value)

    @classmethod
    def rel_current(cls) -> ScopeRef:
        return cls(scope_type=ScopeType.REL, scope_value="current")

    @classmethod
    def dev(cls, version: str) -> ScopeRef:
        return cls(scope_type=ScopeType.DEV, scope_value=version)

    @property
    def is_rel(self) -> bool:
        return self.scope_type == ScopeType.REL

    @property
    def is_dev(self) -> bool:
        return self.scope_type == ScopeType.DEV

    def as_tuple(self) -> tuple[str, str]:
        return self.scope_type.value, self.scope_value

    def __str__(self) -> str:
        return f"{self.scope_type.value}/{self.scope_value}"
