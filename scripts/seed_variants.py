#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import init_db
from app.services.branch.models import BranchRef
from app.services.bulk.writer import BulkVariantWriter


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk-seed variants into an empty project")
    parser.add_argument("--project-id", type=int, required=True, help="Target project ID (must exist, zero variants)")
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
    writer = BulkVariantWriter()
    try:
        result = writer.seed(
            project_id=args.project_id,
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
