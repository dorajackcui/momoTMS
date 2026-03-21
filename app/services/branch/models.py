from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.services.shared.io import normalize_non_content_value

DEV_SERIES_AUTHORITY: dict[str, int] = {
    "2.4.x": 2,
    "2.5.x": 1,
}


class BranchKind(str, Enum):
    REL = "rel"
    DEV = "dev"


def parse_dev_version(version: str) -> tuple[int, int, int]:
    normalized_version = normalize_non_content_value(version)
    if not normalized_version:
        raise ValueError("branch value is required")
    parts = normalized_version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"invalid dev branch version: {version}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def derive_version_series(version: str) -> str:
    major, minor, _patch = parse_dev_version(version)
    version_series = f"{major}.{minor}.x"
    if version_series not in DEV_SERIES_AUTHORITY:
        raise ValueError(f"unsupported dev version series: {version_series}")
    return version_series


@dataclass(frozen=True)
class BranchRef:
    branch_kind: BranchKind
    branch_value: str

    def __post_init__(self) -> None:
        normalized_value = normalize_non_content_value(self.branch_value)
        if not normalized_value:
            raise ValueError("branch value is required")
        object.__setattr__(self, "branch_value", normalized_value)
        if self.branch_kind == BranchKind.REL:
            if normalized_value != "current":
                raise ValueError(f"invalid release branch: {self}")
            return
        derive_version_series(normalized_value)

    @classmethod
    def parse(cls, branch_ref: str) -> BranchRef:
        if "/" not in branch_ref:
            raise ValueError(f"invalid branch ref: {branch_ref}")
        branch_kind_raw, branch_value = branch_ref.split("/", 1)
        try:
            branch_kind = BranchKind(branch_kind_raw)
        except ValueError as exc:
            raise ValueError(f"invalid branch ref: {branch_ref}") from exc
        return cls(branch_kind=branch_kind, branch_value=branch_value)

    @classmethod
    def rel_current(cls) -> BranchRef:
        return cls(branch_kind=BranchKind.REL, branch_value="current")

    @classmethod
    def dev(cls, version: str) -> BranchRef:
        return cls(branch_kind=BranchKind.DEV, branch_value=version)

    @property
    def is_rel(self) -> bool:
        return self.branch_kind == BranchKind.REL

    @property
    def is_dev(self) -> bool:
        return self.branch_kind == BranchKind.DEV

    @property
    def version(self) -> str | None:
        return self.branch_value if self.is_dev else None

    @property
    def version_series(self) -> str | None:
        if not self.is_dev:
            return None
        return derive_version_series(self.branch_value)

    @property
    def version_parts(self) -> tuple[int, int, int] | None:
        if not self.is_dev:
            return None
        return parse_dev_version(self.branch_value)

    def as_tuple(self) -> tuple[str, str]:
        return self.branch_kind.value, self.branch_value

    def __str__(self) -> str:
        return f"{self.branch_kind.value}/{self.branch_value}"
