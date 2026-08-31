# Issue #541: CurveMetaData Tagged Fallback Resolution

status: historical

## Summary

Resolve `UnknownStruct` (CurveMetaData) map-value struct types in `CiciToon_SK_Mannequin.uasset` by registering `CurveMetaData` (without F prefix) in the tagged fallback struct set.

## Problem

The `AnimCurveMetaData` export contains a `CurveMetaData` MapProperty where:

- Map keys: `NameProperty` (bone/curve names)
- Map values: `StructProperty` with `struct_type="CurveMetaData"`

The binary stream provides the struct name as `CurveMetaData` (no F prefix), but only `FCurveMetaData` was registered in `_TAGGED_FALLBACK_STRUCTS`. This caused the struct to return `parse_status=opaque` with empty fields.

## UE Source Evidence

- **File**: `Engine/Source/Runtime/Engine/Public/AnimCurveMetaData.h`
- **Struct**: `FAnimCurveMetaData` contains `TMap<FName, FCurveMetaData> CurveMetaData`
- **Value struct**: `FCurveMetaData` has fields:
  - `LinkedBones`: `TArray<FBoneReference>` (array of bone references)
  - `MaxLOD`: `uint8` (maximum LOD level)
  - `Type`: `FAnimCurveType` (curve type descriptor)

## Solution

Add `"CurveMetaData"` (without F prefix) to `_TAGGED_FALLBACK_STRUCTS` in `property_types.py`. The tagged fallback parsing loop reads property tags from the stream and reconstructs the struct fields without requiring a predefined schema.

## Verification

- **Fixture**: `tests/samples/CiciToon_SK_Mannequin.uasset` (SHA-256: `c13cff72879be5e6c07a65a12201a475fd629a6330149871424abac071d83639`)
- **Result**: `CurveMetaData` struct values now decode with fields `LinkedBones`, `MaxLOD`, `Type`
- **Status**: `parse_status=success` (was `opaque`)

## Scope

- **In scope**: Map-value struct type resolution for `CurveMetaData`
- **Out of scope**: `key_type_struct` extraction for MapProperty keys (latent asymmetry, not hit by current fixtures)

## Files Modified

- `src/uasset_read/parsers/property_types.py`: Added `"CurveMetaData"` to `_TAGGED_FALLBACK_STRUCTS`
