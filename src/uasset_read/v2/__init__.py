"""uasset_read v2 — Package-First architecture.

This package implements the new PackageDocument-based architecture
defined in docs/designs/2026-08-26-package-first-uasset-parser-refactor.md.

The v1 pipeline it was migrated from has been removed; v2 is the only parse
path. Legacy Semantic 1.x JSON and the renderer system are gone with it.
"""
