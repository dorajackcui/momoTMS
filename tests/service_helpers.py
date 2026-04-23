from __future__ import annotations

from types import SimpleNamespace

from app.services.variant.catalog import VariantCatalogService
from app.services.variant.entries import EntryService
from app.services.variant.state_coordinator import VariantStateCoordinator
from app.services.read_models.derived.branch_catalog import BranchCatalogView


def branch_services() -> SimpleNamespace:
    catalog = BranchCatalogView()
    return SimpleNamespace(
        details=catalog,
        registry=catalog,
        entries=EntryService(),
        bindings=VariantStateCoordinator(),
        catalog=VariantCatalogService(),
        list_branch_entries=catalog.list_branch_entries,
        list_dev_branches=catalog.list_dev_branches,
        get_dev_branch=catalog.get_dev_branch,
        release_summary=catalog.release_summary,
    )
