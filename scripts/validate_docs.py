#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_DOCS = [
    Path("docs/README.md"),
    Path("docs/runtime.md"),
    Path("docs/system.md"),
    Path("docs/contracts.md"),
    Path("docs/workflows.md"),
]
MARKDOWN_SCAN_DIRS = [
    Path("docs"),
    Path("archive"),
]
REQUIRED_TEMPLATE_HEADINGS = [
    "## Purpose",
    "## Read This When",
    "## Owns",
    "## Does Not Own",
    "## Update When",
]
ROUTE_DECORATOR_RE = re.compile(r'@router\.(get|post|put|patch|delete)\("([^"]+)"')
DOC_ROUTE_RE = re.compile(r"^- `?(GET|POST|PUT|PATCH|DELETE) (/[^`\n ]+)`?", re.MULTILINE)
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
NPM_SCRIPT_RE = re.compile(r"\bnpm run ([A-Za-z0-9:_-]+)\b")
TEST_PATH_RE = re.compile(r"\btests/[A-Za-z0-9_./-]+\.(?:py|js)\b")
CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")
FENCED_CODE_RE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
REPO_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])("
    r"README\.md|AGENTS\.md|PLANS\.md|code_review\.md|"
    r"(?:app|docs|archive|tests|frontend|scripts)/[A-Za-z0-9_./-]+"
    r")"
)


def iter_markdown_files() -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    candidates = sorted(REPO_ROOT.glob("*.md"))
    for relative_dir in MARKDOWN_SCAN_DIRS:
        candidates.extend(sorted((REPO_ROOT / relative_dir).rglob("*.md")))

    for path in candidates:
        resolved = path.resolve()
        if path.is_file() and resolved not in seen:
            seen.add(resolved)
            files.append(path)
    return sorted(files)


def validate_active_docs() -> list[str]:
    errors: list[str] = []
    actual_docs = {path.relative_to(REPO_ROOT) for path in (REPO_ROOT / "docs").rglob("*.md")}
    expected_docs = set(ACTIVE_DOCS)

    for missing in sorted(expected_docs - actual_docs):
        errors.append(f"missing active doc: {missing}")
    for extra in sorted(actual_docs - expected_docs):
        errors.append(f"unexpected active doc under docs/: {extra}")

    return errors


def validate_template_headings() -> list[str]:
    errors: list[str] = []
    for relative_path in ACTIVE_DOCS:
        path = REPO_ROOT / relative_path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for heading in REQUIRED_TEMPLATE_HEADINGS:
            if heading not in text:
                errors.append(f"{relative_path} -> missing required heading: {heading}")
    return errors


def load_package_scripts() -> set[str]:
    package_json = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    return set(package_json.get("scripts", {}))


def validate_links(files: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK_RE.findall(text):
            target = raw_target.strip()
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            relative_target = target.split("#", 1)[0]
            resolved = (path.parent / relative_target).resolve()
            if not resolved.exists():
                errors.append(f"{path.relative_to(REPO_ROOT)} -> missing link target: {target}")
    return errors


def validate_npm_scripts(files: list[Path]) -> list[str]:
    errors: list[str] = []
    known_scripts = load_package_scripts()
    for path in files:
        text = path.read_text(encoding="utf-8")
        for script_name in sorted(set(NPM_SCRIPT_RE.findall(text))):
            if script_name not in known_scripts:
                errors.append(
                    f"{path.relative_to(REPO_ROOT)} -> documented npm script does not exist: npm run {script_name}"
                )
    return errors


def validate_test_paths(files: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for test_path in sorted(set(TEST_PATH_RE.findall(text))):
            if not (REPO_ROOT / test_path).exists():
                errors.append(f"{path.relative_to(REPO_ROOT)} -> referenced test path does not exist: {test_path}")
    return errors


def _repo_path_scan_text(text: str) -> str:
    contexts: list[str] = []
    contexts.extend(CODE_SPAN_RE.findall(text))
    contexts.extend(match.group(1) for match in FENCED_CODE_RE.finditer(text))
    return "\n".join(contexts)


def validate_repo_paths(files: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in files:
        scan_text = _repo_path_scan_text(path.read_text(encoding="utf-8"))
        for raw_path in sorted(set(REPO_PATH_RE.findall(scan_text))):
            repo_path = raw_path.rstrip(".,:;")
            if TEST_PATH_RE.fullmatch(repo_path):
                continue
            if not (REPO_ROOT / repo_path).exists():
                errors.append(f"{path.relative_to(REPO_ROOT)} -> referenced repo path does not exist: {repo_path}")
    return errors


def collect_router_routes() -> set[str]:
    routes: set[str] = set()
    for router_file in sorted((REPO_ROOT / "app" / "routers").glob("*.py")):
        text = router_file.read_text(encoding="utf-8")
        for method, route in ROUTE_DECORATOR_RE.findall(text):
            routes.add(f"{method.upper()} {route}")
    return routes


def collect_documented_routes() -> set[str]:
    contracts_doc = (REPO_ROOT / "docs" / "contracts.md").read_text(encoding="utf-8")
    return {f"{method} {route}" for method, route in DOC_ROUTE_RE.findall(contracts_doc)}


def validate_routes() -> list[str]:
    errors: list[str] = []
    actual_routes = collect_router_routes()
    documented_routes = collect_documented_routes()

    missing_from_docs = sorted(actual_routes - documented_routes)
    extra_in_docs = sorted(documented_routes - actual_routes)

    for route in missing_from_docs:
        errors.append(f"docs/contracts.md -> missing documented route: {route}")
    for route in extra_in_docs:
        errors.append(f"docs/contracts.md -> route not found in routers: {route}")
    return errors


def main() -> int:
    files = iter_markdown_files()
    checks = [
        ("active docs", validate_active_docs()),
        ("template headings", validate_template_headings()),
        ("links", validate_links(files)),
        ("repo paths", validate_repo_paths(files)),
        ("npm scripts", validate_npm_scripts(files)),
        ("test paths", validate_test_paths(files)),
        ("contracts routes", validate_routes()),
    ]

    errors = [error for _, check_errors in checks for error in check_errors]

    if errors:
        print("Documentation validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Documentation validation passed for {len(ACTIVE_DOCS)} active docs and {len(files)} checked Markdown files.")
    print("- scanned repo-root Markdown plus Markdown under docs/ and archive/")
    print("- docs/ contains exactly the 5 active owner docs")
    print("- each active doc has the owner-template headings")
    print("- local Markdown links resolved")
    print("- repo-relative file and directory references in code spans and fenced command examples resolved")
    print("- documented npm scripts exist")
    print("- referenced test files exist")
    print("- docs/contracts.md route inventory matches router decorators")
    print("- manual review is still required for wording, owner-doc selection, and behavior claims")
    return 0


if __name__ == "__main__":
    sys.exit(main())
