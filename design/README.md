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

- [frontend-current-api-redesign.md](frontend-current-api-redesign.md): new `/app` IA and page redesign based on current project-scoped APIs, without frontend compatibility constraints
- [overview-variant-workspace-redesign.md](overview-variant-workspace-redesign.md): proposed merge of `Variants` into `Overview`, with a project-wide variant grid, API gap analysis, and phased delivery plan
- [pivot-language-design.md](pivot-language-design.md): pivot topology, async drift model, and Fill-facing design for dependent translation languages

## Suggested Workflow


1. When a decision becomes long-lived and cross-cutting, capture it as a dedicated design note or ADR under `design/`.
