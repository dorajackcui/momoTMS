from __future__ import annotations

from types import SimpleNamespace

from app.services.branch.details import BranchDetailService
from app.services.branch.registry import BranchRegistryService
from app.services.variant.catalog import VariantCatalogService
from app.services.variant.entries import EntryService
from app.services.variant.state_coordinator import VariantStateCoordinator


def branch_services() -> SimpleNamespace:
    details = BranchDetailService()
    registry = BranchRegistryService()
    return SimpleNamespace(
        details=details,
        registry=registry,
        entries=EntryService(),
        bindings=VariantStateCoordinator(),
        catalog=VariantCatalogService(),
        list_branch_entries=details.list_branch_entries,
        list_dev_branches=registry.list_dev_branches,
        get_dev_branch=details.get_dev_branch,
    )
