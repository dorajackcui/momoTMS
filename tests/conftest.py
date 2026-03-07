from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_runtime_paths(tmp_path, monkeypatch):
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("MOMO_TMS_DB_PATH", str(runtime_root / "data" / "tms.db"))
    monkeypatch.setenv("MOMO_TMS_JOBS_DIR", str(runtime_root / "jobs"))
    monkeypatch.setenv("MOMO_TMS_DEMO_ROOT", str(runtime_root / "demo_samples"))
    yield
