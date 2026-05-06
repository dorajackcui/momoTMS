#!/usr/bin/env python
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.db import get_conn, init_db


def main() -> int:
    parser = argparse.ArgumentParser(description="Check query plans used by bulk content mutation.")
    parser.add_argument("--db-path", type=Path, help="Optional MOMO_TMS_DB_PATH override.")
    args = parser.parse_args()
    if args.db_path is not None:
        os.environ["MOMO_TMS_DB_PATH"] = str(args.db_path)
    init_db()
    with get_conn() as conn:
        plans = {
            "scope_bindings_entry_in": conn.execute(
                "EXPLAIN QUERY PLAN SELECT * FROM scope_bindings WHERE entry_id IN (1, 2, 3)"
            ).fetchall(),
            "scope_bindings_entry_variant": conn.execute(
                "EXPLAIN QUERY PLAN SELECT * FROM scope_bindings WHERE entry_id IN (1, 2, 3) AND variant_id IN (1, 2, 3)"
            ).fetchall(),
        }
    failed = False
    for name, rows in plans.items():
        print(f"[{name}]")
        text = "\n".join(str(tuple(row.values())) for row in rows)
        print(text)
        if "scope_bindings" in name and "idx_scope_bindings_entry_variant" not in text:
            failed = True
            print(f"ERROR: expected idx_scope_bindings_entry_variant in {name}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
