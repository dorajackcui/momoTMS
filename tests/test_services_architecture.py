from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _service_files(relative_dir: str) -> list[Path]:
    return sorted((ROOT / relative_dir).glob("*.py"))


def _read_doc(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_legacy_service_modules_are_removed() -> None:
    removed_paths = [
        ROOT / "app/services/branch/service.py",
        ROOT / "app/services/branch/details.py",
        ROOT / "app/services/branch/sync.py",
        ROOT / "app/services/branch/queries.py",
        ROOT / "app/services/project/state.py",
        ROOT / "app/services/read_models/_support.py",
        ROOT / "app/services/read_models/compare.py",
        ROOT / "app/services/read_models/history.py",
        ROOT / "app/services/read_models/hydration.py",
        ROOT / "app/services/read_models/inspection.py",
        ROOT / "app/services/read_models/master.py",
        ROOT / "app/services/read_models/queries.py",
        ROOT / "app/services/read_models/queue.py",
        ROOT / "app/services/read_models/service.py",
        ROOT / "app/services/read_models/scope_catalog.py",
        ROOT / "app/services/read_models/scope_refs.py",
        ROOT / "app/services/read_models/summary.py",
        ROOT / "app/services/read_models/variants.py",
        ROOT / "app/services/variant/assemblers.py",
        ROOT / "app/services/variant/inspection.py",
        ROOT / "app/services/variant/variants.py",
        ROOT / "app/services/variant/workflows.py",
        ROOT / "app/services/workflows/fill_queries.py",
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


def test_variant_records_do_not_hold_read_model_types() -> None:
    source = (ROOT / "app/services/variant/records.py").read_text(encoding="utf-8")
    for token in ("FillCandidateRecord", "BindingSummary", "ScopeEntryRecord", "EntryVariantView"):
        assert token not in source


def test_fill_workflow_uses_project_history_dataset_instead_of_variant_catalog() -> None:
    source = (ROOT / "app/services/workflows/fill.py").read_text(encoding="utf-8")
    assert "ProjectHistoryDataset" in source
    assert "VariantCatalogService" not in source


def test_branch_catalog_view_owns_branch_reads() -> None:
    source = (ROOT / "app/services/read_models/derived/branch_catalog.py").read_text(encoding="utf-8")
    assert "ScopeMembershipDataset" in source
    assert "list_entry_views" in source
    assert "BranchDetailService" not in source
    assert "BranchRegistryService" not in source


def test_bootstrap_and_workflow_routes_use_branch_catalog_read_model() -> None:
    bootstrap_source = (ROOT / "app/services/project/bootstrap.py").read_text(encoding="utf-8")
    workflows_source = (ROOT / "app/routers/workflows.py").read_text(encoding="utf-8")
    registry_source = (ROOT / "app/services/branch/registry.py").read_text(encoding="utf-8")

    assert "BranchCatalogView" in bootstrap_source
    assert "BranchDetailService" not in bootstrap_source
    assert "BranchRegistryService" not in bootstrap_source
    assert "BranchCatalogView" in workflows_source
    assert "BranchDetailService" not in workflows_source
    assert "BranchRegistryService" not in workflows_source
    registry_lower = registry_source.lower()
    assert "scope_bindings" not in registry_lower
    assert "group_concat" not in registry_lower
    assert "join entries" not in registry_lower
    assert "join variants" not in registry_lower
    assert "entry_count" not in registry_lower
    assert "count(" not in registry_lower


def test_active_docs_cover_branch_first_routes_and_replace_rules() -> None:
    contracts_doc = _read_doc("docs/contracts.md")
    workflows_doc = _read_doc("docs/workflows.md")

    assert "GET /api/projects/{project_id}/branches/{branch_ref:path}/rows" in contracts_doc
    assert "GET /api/projects/{project_id}/branches/{branch_ref:path}/lookup" in contracts_doc
    assert "GET /api/projects/{project_id}/scopes/{scope_ref:path}/rows" in contracts_doc
    assert "GET /api/projects/{project_id}/scopes/{scope_ref:path}/lookup" in contracts_doc
    assert "compatibility alias" in contracts_doc
    assert "scope-aware" in contracts_doc
    assert "REBIND_TARGET" in contracts_doc
    assert "kept_in_target_count" in contracts_doc
    assert "rebind_target_count" in contracts_doc

    assert "FORBIDDEN_BY_AUTHORITY" in workflows_doc
    assert "REBIND_TARGET" in workflows_doc
