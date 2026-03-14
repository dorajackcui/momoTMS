# Momo TMS Review Checklist

Use this checklist for self-review or Codex `/review`.

## Behavior And Regressions

- Does the diff change runtime behavior intentionally, and is that behavior covered by tests or explicit manual verification?
- Are negative paths still correct for missing projects, removed routes, and cross-project access?

## Route And Docs Drift

- If a route, payload, or SPA flow changed, were the matching docs under `docs/reference/`, `docs/development/`, or `docs/architecture/` updated?
- Does `README.md` still match the current public runtime surfaces and commands?
- Are all referenced links, file paths, and commands still valid?

## Branch And Scope Invariants

- Does the change preserve project-scoped API behavior?
- Does it preserve canonical same-source variant behavior, scope binding rules, and orphan or trashed lifecycle semantics?
- Does it avoid reintroducing `retained` or old route families such as `/api/state`, `/api/strings`, or `/api/scopes/...`?

## Compatibility Boundaries

- Did the diff accidentally add or extend legacy compatibility routes or old-data semantic fallback?
- If migration or compatibility work is intentional, is that called out explicitly in the plan and active docs?

## Verification Evidence

- Were the right commands run for this change type?
- If not, does the final summary say exactly what was not run and why?
- Is there enough evidence that the change works beyond “the code looks right”?

## Documentation Follow-Through

- Did the diff update the narrowest source-of-truth doc rather than copy the same fact into multiple files?
- Are historical notes preserved under `archive/` instead of mixed into active guidance?
