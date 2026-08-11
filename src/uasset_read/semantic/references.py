"""Reference table -- collect, deduplicate, and close references.

Collects import/export entries from PackageIR and produces
a deterministic, deduplicated tuple of ReferenceEntry.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.semantic.ir import ReferenceEntry

if TYPE_CHECKING:
    from uasset_read.models.ir import ImportIR, ExportIR


class ReferenceTable:
    """Collects and deduplicates references from imports and exports."""

    def __init__(self) -> None:
        self._seen: set[tuple[str, int]] = set()
        self._entries: list[ReferenceEntry] = []

    def collect(
        self,
        imports: list[ImportIR],
        exports: list[ExportIR],
    ) -> tuple[ReferenceEntry, ...]:
        """Collect references from imports and exports.

        Args:
            imports: ImportIR list from PackageIR
            exports: ExportIR list from PackageIR

        Returns:
            Deduplicated tuple of ReferenceEntry, sorted by (kind, index)
        """
        for i, imp in enumerate(imports):
            key = ("import", i)
            if key not in self._seen:
                self._seen.add(key)
                self._entries.append(ReferenceEntry(
                    index=i,
                    kind="import",
                    class_name=imp.class_name or "",
                    object_name=imp.object_name or "",
                    package_path=imp.class_package or "",
                ))

        for i, exp in enumerate(exports):
            key = ("export", i)
            if key not in self._seen:
                self._seen.add(key)
                self._entries.append(ReferenceEntry(
                    index=i,
                    kind="export",
                    class_name=exp.object_class or "",
                    object_name=exp.object_name or "",
                    package_path="",
                ))

        # Sort by (kind, index) for deterministic output
        return tuple(sorted(self._entries, key=lambda r: (r.kind, r.index)))
