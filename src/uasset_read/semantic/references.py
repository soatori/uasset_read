"""Reference table — collect, deduplicate, and sort references."""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.semantic.models import ReferenceEntry

if TYPE_CHECKING:
    from uasset_read.models.ir import ImportIR, ExportIR


def collect_references(
    imports: list[ImportIR],
    exports: list[ExportIR],
) -> tuple[ReferenceEntry, ...]:
    """Collect references from imports and exports, sorted by (kind, index).

    NOTE: At #551 scope, this collects ALL references. Reachable-reference
    closure filtering for standard mode will be added when domain extensions
    (#554-#557) define which references are semantically reachable from the
    primary asset. The current output is complete but not yet filtered.
    """
    entries: list[ReferenceEntry] = []
    seen: set[tuple[str, int]] = set()

    for i, imp in enumerate(imports):
        key = ("import", i)
        if key not in seen:
            seen.add(key)
            entries.append(ReferenceEntry(
                index=i, kind="import",
                class_name=imp.class_name or "",
                object_name=imp.object_name or "",
                package_path=imp.class_package or "",
            ))

    for i, exp in enumerate(exports):
        key = ("export", i)
        if key not in seen:
            seen.add(key)
            entries.append(ReferenceEntry(
                index=i, kind="export",
                class_name=exp.object_class or "",
                object_name=exp.object_name or "",
                package_path="",
            ))

    return tuple(sorted(entries, key=lambda r: (r.kind, r.index)))
