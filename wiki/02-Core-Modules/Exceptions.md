---
title: 异常体系
section: exceptions
---

# 异常体系

## 异常类层次

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

| 字段 | 类型 | 说明 |
|------|------|------|
| `offset` | int | 文件偏移 |
| `phase` | str | 解析阶段 |
| `operation` | str | 操作类型 |
| `export_index` | Optional[int] | 导出索引 |
| `expected_offset` | Optional[int] | 预期偏移 |
