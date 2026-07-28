# Issue 508 Final Gaps Design

## Scope

Close two acceptance gaps in the UE5 property-first metadata path without adding native payload decoders:

1. Versioned and unversioned property parsing must converge on one asset-handler dispatch after the complete property list is available.
2. Texture2D `ImportedSize` must accept the runtime `StructValue(fields={"X": ..., "Y": ...})` representation and count as business metadata.

## Design

`parse_properties_from_export` will retain the existing versioned and unversioned property readers, but both results will flow through one common handler-dispatch block. This guarantees exactly one handler invocation for either path and keeps the handler contract unchanged.

`property_metadata._size` will unwrap a `fields` mapping before reading `X` and `Y`. Texture2D will pass a successfully normalized size through the existing `project` helper so sanitization, meaningful-value checks, and `business_field_count` stay consistent.

## Verification

- A regression test will exercise an unversioned export through `parse_properties_from_export` and assert one handler call with the completed properties.
- A public-output regression will feed a real `StructValue` through the registered handler, IR builder, and JSON renderer, then assert `imported_size` and `partial_metadata` in JSON.
- Run the focused Issue 508 tests first, then the full suite with `PYTHONPATH=src`.
