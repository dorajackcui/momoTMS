# Design Workspace

## Purpose

- provide a working area for design methods, design reviews, and design coverage tracking
- help the team move from runtime facts in `docs/` to change-level design decisions and follow-up

## How To Use This Folder

- treat `docs/` as the source of truth for current runtime behavior
- treat `design/` as the place to explain why we design a change, what we evaluated, and what is still missing
- if a design note becomes a stable runtime fact, update the matching owner doc under `docs/`
- if a design note only records historical reasoning after a change is complete, move it to `archive/`

## File Map

- [design-process.md](design-process.md): recommended design steps and the content to produce at each step
- [current-state-review.md](current-state-review.md): review of the current repo's design strengths, risks, and suggested priorities
- [design-inventory.md](design-inventory.md): checklist and matrix of what is already designed and what still needs to be filled in

## Suggested Workflow

1. Read [current-state-review.md](current-state-review.md) to understand the current design baseline.
2. Use [design-process.md](design-process.md) to frame the next change before coding.
3. Update [design-inventory.md](design-inventory.md) when a design area becomes clearer or a new gap appears.
4. When a decision becomes long-lived and cross-cutting, capture it as a dedicated design note or ADR under `design/`.
