"""Isolate and time the bulk_bind SQL steps directly."""
from __future__ import annotations

import argparse
import sys
from time import perf_counter

sys.path.insert(0, ".")

from app.db import init_db, get_conn


def main() -> int:
    parser = argparse.ArgumentParser(description="Isolate and time the bulk_bind SQL steps directly.")
    parser.add_argument("--project-id", type=int, default=4)
    args = parser.parse_args()

    init_db()
    project_id = args.project_id

    with get_conn() as conn:
        row = conn.execute(
            "SELECT MAX(import_batch_id) AS b FROM imports WHERE project_id=?",
            (project_id,),
        ).fetchone()
        if row is None or row["b"] is None:
            print(f"No import batch found for project_id={project_id}", file=sys.stderr)
            return 1
        batch_id = int(row["b"])
        print(f"using batch_id={batch_id}", flush=True)

    t0 = perf_counter()
    with get_conn() as conn:
        print("got connection", flush=True)

        t1 = perf_counter()
        conn.execute(
            """
            CREATE TEMP TABLE _bulk_first AS
            SELECT MIN(ir.import_row_id) AS import_row_id, ir.business_key, ir.source
            FROM import_rows ir
            WHERE ir.import_batch_id = ? AND ir.status = 'ok'
              AND ir.business_key != '' AND ir.business_key IS NOT NULL
              AND ir.source != '' AND ir.source IS NOT NULL
            GROUP BY ir.business_key
        """,
            (batch_id,),
        )
        cnt = conn.execute("SELECT COUNT(*) AS c FROM _bulk_first").fetchone()["c"]
        print(f"_bulk_first created: {cnt} rows  ({perf_counter()-t1:.2f}s)", flush=True)

        t2 = perf_counter()
        conn.execute(
            """
            CREATE TEMP TABLE _bulk_matched AS
            SELECT bf.import_row_id, ir.file_path, ir.sheet_name, ir.row_index,
                   bf.business_key, bf.source, e.entry_id, v.variant_id
            FROM _bulk_first bf
            JOIN import_rows ir ON ir.import_row_id = bf.import_row_id
            JOIN entries e ON e.project_id = ? AND e.business_key = bf.business_key
            JOIN variants v ON v.entry_id = e.entry_id AND v.source = bf.source AND v.trashed_at IS NULL
        """,
            (project_id,),
        )
        print(f"_bulk_matched join done  ({perf_counter()-t2:.2f}s)", flush=True)

        t3 = perf_counter()
        cnt2 = conn.execute("SELECT COUNT(*) AS c FROM _bulk_matched").fetchone()["c"]
        print(f"matched count: {cnt2}  ({perf_counter()-t3:.2f}s)", flush=True)

        conn.execute("DROP TABLE IF EXISTS _bulk_matched")
        conn.execute("DROP TABLE IF EXISTS _bulk_first")

    print(f"total: {perf_counter()-t0:.2f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
