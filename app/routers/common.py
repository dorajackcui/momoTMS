from __future__ import annotations

import json

from fastapi import HTTPException, UploadFile

from app.services.branch.models import BranchRef


def handle_errors(fn):
    try:
        return fn()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (KeyError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def parse_branch_ref(branch_ref: str) -> BranchRef:
    return BranchRef.parse(branch_ref)


def read_folder_upload(
    files: list[UploadFile],
    relative_paths: list[str],
) -> list[tuple[str, bytes]]:
    if len(files) != len(relative_paths):
        raise ValueError("files and relative_paths must have the same length")
    payloads: list[tuple[str, bytes]] = []
    for upload, relative_path in zip(files, relative_paths, strict=True):
        payloads.append((relative_path, upload.file.read()))
    return payloads


def parse_column_mapping_json(payload: str | None) -> dict[str, dict[str, object]] | None:
    if payload is None or not payload.strip():
        return None
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("column_mapping_json must be a JSON object")
    for sheet_key, mapping in value.items():
        if not isinstance(sheet_key, str) or not isinstance(mapping, dict):
            raise ValueError("column_mapping_json must map sheet keys to mapping objects")
    return value
