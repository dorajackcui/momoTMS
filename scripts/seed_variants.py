#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import init_db
from app.services.branch.models import BranchRef
from app.services.bulk.writer import BulkVariantWriter
from app.services.project.service import ProjectService


def _resolve_project_id(args: argparse.Namespace) -> int:
    service = ProjectService()
    if args.project_id is not None:
        service.require_project(args.project_id)
        return int(args.project_id)
    projects = service.list_projects()
    for p in projects:
        if p["name"] == args.project_name:
            return int(p["project_id"])
    raise KeyError(f"project not found: {args.project_name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk-seed variants into an empty project")
    project_group = parser.add_mutually_exclusive_group(required=True)
    project_group.add_argument("--project-id", type=int, help="Target project ID")
    project_group.add_argument("--project-name", type=str, help="Target project name")
    parser.add_argument("--branch", type=str, required=True, help="Target branch, e.g. rel/current or dev/2.4.1")
    parser.add_argument("--workbook", type=str, required=True, help="Path to .xlsx workbook")
    parser.add_argument("--chunk-size", type=int, default=5000, help="Rows per write chunk (default: 5000)")
    args = parser.parse_args()

    workbook_path = Path(args.workbook)
    if not workbook_path.exists():
        print(f"ERROR: workbook not found: {workbook_path}", file=sys.stderr)
        sys.exit(1)

    try:
        branch_ref = BranchRef.parse(args.branch)
    except ValueError as exc:
        print(f"ERROR: invalid branch: {exc}", file=sys.stderr)
        sys.exit(1)

    init_db()

    try:
        project_id = _resolve_project_id(args)
    except (KeyError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    writer = BulkVariantWriter()
    try:
        result = writer.seed(
            project_id=project_id,
            branch_ref=branch_ref,
            workbook_path=str(workbook_path),
            chunk_size=args.chunk_size,
        )
    except (ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Seed complete:")
    print(f"  entries created:  {result['entries_created']}")
    print(f"  variants created: {result['variants_created']}")
    print(f"  bindings created: {result['bindings_created']}")
    print(f"  elapsed:          {result['elapsed_ms']}ms")


if __name__ == "__main__":
    main()
