"""Kismet bytecode expression system -- EExprToken + KismetExpression class hierarchy + FKismetArchive.

Import from the submodules directly (e.g. ``uasset_read.kismet.tokens``,
``uasset_read.kismet.expressions``).

INTERNAL since v0.6.0 (issue #642): this package is a v2 implementation detail, not a
deprecated one. The v1 pipeline that consumed it was removed in Phase 6; v2 now reaches
it only through ``decompile_bridge`` for the decode-depth view, degrading to a
``KISMET_DECOMPILE_FAILED`` diagnostic when a script cannot be read. The custom-version
GUIDs and lookup that ``parsers/`` and ``serializers/`` needed moved to
``uasset_read.versioning``, so nothing outside this package imports into it anymore.

No public API is promised here: the only supported contract is ``PackageDocument`` via
``parse_package_document()``. Deleting this package would first require a v2-native
decompilation projection, which is a separate approved design, not a cleanup.
"""
