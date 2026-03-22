from app.services.branch.models import BranchKind, BranchRef

__all__ = [
    "BranchMutationService",
    "BranchService",
    "BranchReplaceService",
    "BranchRef",
    "BranchKind",
]


def __getattr__(name: str):
    if name == "BranchMutationService":
        from app.services.branch.mutations import BranchMutationService

        return BranchMutationService
    if name == "BranchService":
        from app.services.branch.service import BranchService

        return BranchService
    if name == "BranchReplaceService":
        from app.services.branch.sync import BranchReplaceService

        return BranchReplaceService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
