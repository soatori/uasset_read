"""Reference table — collect, deduplicate, and sort references.

Import ``package_path`` is the package containing the referenced object,
resolved through the outer chain. It is deliberately NOT ``class_package``,
which identifies where the object's *class* is defined.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.semantic.models import ReferenceEntry

if TYPE_CHECKING:
    from uasset_read.models.ir import ImportIR, ExportIR


def _outer_import_position(outer_index: object) -> int | None:
    """Return the import-list position referenced by a PackageIndex, or None.

    Negative PackageIndex values reference imports (position = -index - 1).
    Zero (null) and positive (export) values never point at a Package import.
    Accepts both PackageIndex instances (runtime) and plain ints (tests).
    """
    idx = getattr(outer_index, "index", outer_index)
    if not isinstance(idx, int) or idx >= 0:
        return None
    return -idx - 1


def _resolve_object_package(imp: "ImportIR", imports: "list[ImportIR]") -> str:
    """Resolve the package that contains the referenced object.

    Imports of class ``Package`` name the package itself in ``object_name``;
    other imports are resolved by walking the outer chain until a ``Package``
    import is found. Returns "" when unresolvable (null/export/out-of-range
    outer, or a cycle in corrupted data).
    """
    if imp.class_name == "Package":
        return imp.object_name or ""
    position = _outer_import_position(imp.outer_index)
    seen: set[int] = set()
    while position is not None and 0 <= position < len(imports):
        if position in seen:
            return ""
        seen.add(position)
        outer = imports[position]
        if outer.class_name == "Package":
            return outer.object_name or ""
        position = _outer_import_position(outer.outer_index)
    return ""


def collect_references(
    imports: list[ImportIR],
    exports: list[ExportIR],
) -> tuple[ReferenceEntry, ...]:
    """Collect references from imports and exports, sorted by (kind, index).

    NOTE: At #551 scope, this collects ALL references. Reachable-reference
    closure filtering is deferred to the domain extractor issues (#554-#557);
    see docs/formats/uasset/semantic-json.md ("Reference Scope").
    """
    entries: list[ReferenceEntry] = []
    seen: set[tuple[str, int]] = set()

    for i, imp in enumerate(imports):
        key = ("import", i)
        if key not in seen:
            seen.add(key)
            entries.append(
                ReferenceEntry(
                    index=i,
                    kind="import",
                    class_name=imp.class_name or "",
                    object_name=imp.object_name or "",
                    package_path=_resolve_object_package(imp, imports),
                )
            )

    for i, exp in enumerate(exports):
        key = ("export", i)
        if key not in seen:
            seen.add(key)
            entries.append(
                ReferenceEntry(
                    index=i,
                    kind="export",
                    class_name=exp.object_class or "",
                    object_name=exp.object_name or "",
                    package_path="",
                )
            )

    return tuple(sorted(entries, key=lambda r: (r.kind, r.index)))
