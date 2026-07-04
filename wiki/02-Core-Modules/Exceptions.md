---
title: Exception Hierarchy
section: exceptions
---

# Exception Hierarchy

## Exception Class Hierarchy

```
UAssetError (Exception)
├── VersionError
├── ParseError (partial_result, context: ErrorContext)
├── InvalidFormatError (format_type)
├── CorruptedDataError
├── UnsupportedFeatureError (feature)
├── MissingDependencyError (dependency)
└── ContainerError
    ├── PakError
    └── IoStoreError
```

## ErrorContext

| Field | Type | Description |
|------|------|-------------|
| `offset` | int | File offset |
| `phase` | str | Parse phase |
| `operation` | str | Operation type |
| `export_index` | Optional[int] | Export index |
| `expected_offset` | Optional[int] | Expected offset |
