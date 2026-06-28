---
title: Formatters
section: formatters
---

# Formatters

> [!WARNING] Deprecated
>
> The `formatters/` directory has been emptied since v0.5.0. All formatting functionality has been migrated to the `renderers/` system. This document is retained for historical reference.

## Deprecation Notice

In the 0.4.1 IR architecture, formatters were called internally by renderers. In the current version, the `formatters/` directory contains no Python files. All output formatting logic has been fully migrated to the renderer system.

**Recommended usage**:
- `parse_single(format="json")` — JSON output
- `parse_single(format="markdown")` — Markdown output
- `get_renderer("json")` / `get_renderer("markdown")` — Use renderers directly

**Related sections**: [[Renderer System]] · [[CLI Interface]]
