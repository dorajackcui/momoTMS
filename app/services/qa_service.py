from __future__ import annotations

import re
from dataclasses import dataclass

PLACEHOLDER_PATTERN = re.compile(r"\{[^{}]*\}")
TAG_PATTERN = re.compile(r"</?([A-Za-z0-9_\-]+)>")


@dataclass
class QaResult:
    rule: str
    ok: bool


def count_placeholders(text: str) -> int:
    return len(PLACEHOLDER_PATTERN.findall(text or ""))


def count_pipes(text: str) -> int:
    return (text or "").count("|")


def tags_well_formed(text: str) -> bool:
    stack: list[str] = []
    for match in TAG_PATTERN.finditer(text or ""):
        raw = match.group(0)
        name = match.group(1)
        if raw.startswith("</"):
            if not stack or stack[-1] != name:
                return False
            stack.pop()
        else:
            stack.append(name)
    return not stack


def validate_pair(src: str, tgt: str) -> list[QaResult]:
    results: list[QaResult] = []
    results.append(QaResult("PLACEHOLDER_COUNT", count_placeholders(src) == count_placeholders(tgt)))
    results.append(QaResult("PIPE_COUNT", count_pipes(src) == count_pipes(tgt)))
    results.append(QaResult("TAG_WELL_FORMED", tags_well_formed(tgt)))
    return results
