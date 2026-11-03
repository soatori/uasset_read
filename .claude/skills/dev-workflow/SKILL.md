---
name: dev-workflow
description: Repository workflow reference when implementing an explicitly requested change or executing an exact user-selected plan.
---

# Development Workflow

Repository rules live in root `AGENTS.md`. When present, read `docs/reference/agent-dev-reference.md` for task flow and `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md` for target direction. Source/tests/real samples establish implemented behavior.

## Choose the task mode

- Explanation, diagnosis, audit, or status check: inspect evidence and report it.
- Documentation: update the relevant authority and routes, check diffs/links/assertions, and report current versus target clearly.
- Implementation: identify the concrete gap, affected callers/models/schema/tests, then use the smallest approved change and meaningful verification.
- Plan execution: enter only for an exact plan supplied by the user or an explicit request to execute a named plan.

Historical/completed/superseded records are evidence. Do not scan plan directories to infer an active task or replay old phases. After one narrower retry without new evidence, report the missing state instead of repeating a search.

## Current direction

Keep the parser pure Python and read-only. Improve existing Blueprint analysis and the existing package output with evidence-backed identity, parameter, execution, and data relationships. Preserve node/Pin/link facts and unknown states. Follow the canonical contract decision process if a field truly needs to change.

The rejected standalone logic-report proposal is historical. It does not authorize a new output format, framework, AI dependency, or transport.

## Implement and verify

1. If `.codegraph/` exists, use CodeGraph before understanding/editing indexed code. Use rg for precise text and docs.
2. Trace binary/node rules to the relevant UE source version. Start with a strict reproduction and a real sample where support is claimed.
3. Reuse existing shared code; preserve validation, caller behavior, evidence, and unrelated work.
4. Run the relevant regressions and required gates. Documentation-only work does not trigger a full suite, branch finishing, or implementation review.
5. Read actual test/size budgets from configuration. Record current results instead of repeating historical counts or machine requirements.
6. Report changes, evidence, limitations, and integration choices. Commit, push, merge, or clean a worktree only with the applicable user authorization.

Use other skills when the requested workflow needs them. Delegation is a task-specific choice or explicit skill requirement, not the default consequence of opening this page.
