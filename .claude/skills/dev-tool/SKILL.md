---
name: dev-tool
description: Unified dev knowledge base: commands, test rules, architecture, log analysis, batch parsing, issue review. Load sub-docs on demand.
---

# Dev Tool — Unified Knowledge Base

On-demand project knowledge base covering commands, test rules, core architecture, and maintenance workflows.

## Trigger

Auto-load the matching sub-document based on user keywords:

| Keywords | File |
|----------|------|
| "commands", "run.py", "pytest", "common commands" | `references/commands.md` |
| "test rules", "test limits", "test files" | `references/test-rules.md` |
| "architecture", "modules", "pipeline", "structure" | `references/architecture.md` |
| "analyze logs", "review log", "log report" | `references/log-analysis.md` |
| "batch parse", "test samples", "error report" | `references/batch-parse.md` |
| "issue status", "review issue", "check fix" | `references/issue-review.md` |
| First question about project structure / no specific keyword | Load this file only (routing table) |

## Quick Reference

**commands.md** — `run.py` usage, pytest commands
**test-rules.md** — File placement, quantity limits, naming conventions
**architecture.md** — Pipeline, key modules, status model
**log-analysis.md** — 6-step log triage workflow
**batch-parse.md** — Batch parsing and error reporting
**issue-review.md** — GitHub issue status review workflow
