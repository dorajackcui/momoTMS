from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from typing import TypeVar

SQLITE_QUERY_CHUNK_SIZE = 900

T = TypeVar("T")


def sql_variable_chunk_size(
    conn: sqlite3.Connection,
    *,
    reserved_params: int = 0,
) -> int:
    limit = SQLITE_QUERY_CHUNK_SIZE
    if hasattr(conn, "getlimit") and hasattr(sqlite3, "SQLITE_LIMIT_VARIABLE_NUMBER"):
        limit = min(limit, int(conn.getlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER)))
    return max(1, limit - reserved_params)


def iter_sql_chunks(
    values: Sequence[T],
    conn: sqlite3.Connection,
    *,
    reserved_params: int = 0,
) -> Iterator[list[T]]:
    size = sql_variable_chunk_size(conn, reserved_params=reserved_params)
    for start in range(0, len(values), size):
        yield list(values[start : start + size])
