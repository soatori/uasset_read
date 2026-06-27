---
title: 版本管理
section: versioning
---

# 版本管理

<!-- data-api="build_version_container" -->
```python
build_version_container(summary) → VersionContainer
```

## CustomVersion GUIDs

| GUID | 名称 | 说明 |
|------|------|------|
| `FFrameworkObjectVersion` | 框架对象版本 | 蓝图图结构版本 |
| `FUE5MainStreamObjectVersion` | UE5 主流版本 | UE5 核心版本 |
| `FReleaseObjectVersion` | 发行版本 | UE 发行版本 |

> [!TIP]
> 版本管理负责从 PackageFileSummary 中读取并统一化各 CustomVersion GUID 的版本号。
>
> **相关章节**: [[Serializers]] · [[Parsers]]
