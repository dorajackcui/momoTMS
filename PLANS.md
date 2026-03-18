# Plan Template

Use this template for long, ambiguous, or risky work before implementation starts.

## Goal

- What needs to change or be delivered?

## Context

- Which files, docs, routes, tests, errors, or user flows matter?
- What current behavior did you confirm from the codebase?

## Constraints

- Which architecture rules, product boundaries, safety limits, or compatibility rules must hold?
- Which files or surfaces are out of scope?

## Documentation

- Which owner doc from `AGENTS.md` and `docs/README.md` owns the change?
- Which secondary docs or indexes need a link-only update?

## Done When

- What must be true when the work is complete?
- Which behavior, route, or UI state should change?

## Validation

- Which commands should run?
- Which manual checks are required?
- Should `.venv/bin/python scripts/validate_docs.py` run, and which doc claims still need manual verification after it?
- Which existing tests or docs need to stay aligned?

## Risks / Open Questions

- What could regress?
- Which assumption is being made?
- What still needs explicit confirmation before implementation?
