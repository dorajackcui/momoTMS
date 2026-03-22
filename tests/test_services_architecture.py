from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _service_files(relative_dir: str) -> list[Path]:
    return sorted((ROOT / relative_dir).glob("*.py"))


def test_legacy_service_modules_are_removed() -> None:
    removed_paths = [
        ROOT / "app/services/branch/service.py",
        ROOT / "app/services/branch/sync.py",
        ROOT / "app/services/project/state.py",
        ROOT / "app/services/read_models/service.py",
        ROOT / "app/services/variant/assemblers.py",
        ROOT / "app/services/variant/inspection.py",
        ROOT / "app/services/variant/variants.py",
        ROOT / "app/services/variant/workflows.py",
        ROOT / "app/services/workflows/workbench.py",
    ]
    assert all(not path.exists() for path in removed_paths)


def test_variant_package_stays_independent_from_branch_read_models_and_workflows() -> None:
    disallowed = (
        "app.services.branch",
        "app.services.read_models",
        "app.services.workflows",
    )
    offenders: list[str] = []
    for path in _service_files("app/services/variant"):
        source = path.read_text(encoding="utf-8")
        for token in disallowed:
            if token in source:
                offenders.append(f"{path.relative_to(ROOT)} -> {token}")
    assert offenders == []


def test_shared_package_does_not_import_higher_level_services() -> None:
    offenders: list[str] = []
    for path in _service_files("app/services/shared"):
        source = path.read_text(encoding="utf-8")
        if "app.services." in source and "app.services.shared" not in source:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_fill_workflow_uses_workflow_query_service_instead_of_variant_catalog() -> None:
    source = (ROOT / "app/services/workflows/fill.py").read_text(encoding="utf-8")
    assert "FillQueryService" in source
    assert "VariantCatalogService" not in source
