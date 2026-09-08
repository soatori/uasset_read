# Unversioned Test Fixture Provenance

## Overview

This document describes the provenance of the unversioned test fixtures used for testing UE5 unversioned package parsing.

## Fixtures

### BP_UnversionedTest.uasset

- **Type:** Blueprint Generated Class
- **Engine:** UE5.4
- **Properties:** 112 unversioned properties
- **Exports:** 5 objects (BlueprintGeneratedClass, default objects, scene components)
- **Imports:** 18 dependencies

### DA_UnversionedTest.uasset

- **Type:** Data Asset
- **Engine:** UE5.4
- **Properties:** 4 unversioned properties
- **Exports:** 1 object
- **Imports:** 3 dependencies

### UnversionedTest.usmap

- **Type:** Schema mapping file
- **Structs:** 9 definitions
- **Enums:** 10 definitions
- **Purpose:** Provides type information for unversioned property deserialization

## Creation Process

1. Created a minimal UE5.4 project with unversioned packages
2. Configured packages to use `PKG_UnversionedProperties` flag
3. Exported with version fields set to 0 (FileVersionUE4=0, FileVersionUE5=0)
4. Generated USMAP mapping file from project schema

## Key Format Characteristics

- `FileVersionUE4 == 0 && FileVersionUE5 == 0` signals unversioned properties
- `PKG_UnversionedProperties` (0x2000) flag confirms unversioned format
- Binary header follows full UE5 layout despite version=0
- Parser must override versions to AUTOMATIC_VERSION for correct field reading

## References

- UE Source: `UnversionedPropertySerialization.cpp`
- CUE4Parse: `FPackageFileSummary` constructor
- Design Doc: `docs/designs/2026-08-26-package-first-uasset-parser-refactor.md`
