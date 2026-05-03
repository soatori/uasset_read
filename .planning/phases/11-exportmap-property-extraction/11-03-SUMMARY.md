---
phase: 11
plan: 03
subsystem: ExportMap属性值提取
tags: [property-parsing, SoftObjectProperty, FSoftObjectPath]
requires:
  - 11-01
provides:
  - SoftObjectProperty解析器
affects:
  - parse_property_value分派表
tech-stack:
  added:
    - parse_soft_object_property函数
    - FSoftObjectPath序列化支持
  patterns:
    - 字典分派模式
key-files:
  created: []
  modified:
    - uasset_read.py (新增parse_soft_object_property函数，分派表注册)
    - tests/test_property_parsing.py (新增5个测试)
decisions:
  - D-01: SoftObjectProperty返回{"asset_path": str, "sub_path": str}格式
  - D-02: 使用字典分派而非match/case，保持现有模式一致性
metrics:
  duration: 4min
  tasks_completed: 3
  files_modified: 2
  tests_added: 5
  tests_passed: 190
  completed_date: "2026-05-02T17:47:04Z"
---

# Phase 11 Plan 03: 新增SoftObjectProperty解析器 Summary

**一句话:** 新增SoftObjectProperty解析器，支持FSoftObjectPath序列化格式，返回asset_path和sub_path结构化数据。

## 任务完成情况

| 任务 | 名称 | 状态 | Commit | 文件 |
|------|------|------|--------|------|
| 1 | 新增parse_soft_object_property函数 | ✓ 完成 | cd07a63 | uasset_read.py |
| 2 | 注册SoftObjectProperty到类型分派表 | ✓ 完成 | cd07a63 | uasset_read.py |
| 3 | 新增SoftObjectProperty测试 | ✓ 完成 | 9abedae | tests/test_property_parsing.py |

## 实现细节

### parse_soft_object_property函数

新增于uasset_read.py约line 3230，解析SoftObjectProperty类型：

```python
def parse_soft_object_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str]
) -> Dict[str, str]:
    """
    解析 SoftObjectProperty（FSoftObjectPath）。

    UE5格式：
    - AssetPath: FString（如 "/Game/Characters/Animations/Walk")
    - SubPath: FString（如 "" 或 "SubObject.Path")

    Returns:
        {"asset_path": str, "sub_path": str}
    """
    asset_path = archive.read_fstring()
    sub_path = archive.read_fstring()

    return {
        "asset_path": asset_path,
        "sub_path": sub_path
    }
```

### 类型分派表注册

在parse_property_value函数的type_dispatch字典中新增：

```python
"SoftObjectProperty": lambda t, a, n, e, s, d: parse_soft_object_property(t, a, n),
```

### 测试覆盖

新增5个测试函数：
- test_soft_object_property_basic: 基本解析（无子路径）
- test_soft_object_property_with_subpath: 带子路径解析
- test_soft_object_property_in_parse_property_value: 分派验证
- test_soft_object_property_empty_asset_path: 空资产路径边界测试
- test_soft_object_property_unicode_path: Unicode路径支持

## 验证结果

### 单元测试

```
tests/test_property_parsing.py::test_soft_object_property_basic PASSED
tests/test_property_parsing.py::test_soft_object_property_with_subpath PASSED
tests/test_property_parsing.py::test_soft_object_property_in_parse_property_value PASSED
tests/test_property_parsing.py::test_soft_object_property_empty_asset_path PASSED
tests/test_property_parsing.py::test_soft_object_property_unicode_path PASSED
```

全部测试套件：190 passed, 47 skipped

### 实际资产验证

由于依赖Phase 11-01（ExportMap属性填充），当前BP_FirstPersonCharacter.uasset资产的ExportMap解析存在错误（Phase 11-01的问题），无法验证实际SoftObjectProperty数据。但解析器本身功能已通过单元测试验证。

## Deviations from Plan

None - 计划执行完全按预期完成。

## Key Decisions

| 决策 | 理由 |
|------|------|
| D-01: 返回Dict而非dataclass | 保持与其他简单属性类型一致性（StrProperty返回str，ObjectProperty返回int） |
| D-02: 保持字典分派模式 | 现有parse_property_value使用字典分派，新增类型遵循相同模式 |

## Threat Flags

None - 本计划仅新增解析器，不引入新的安全表面。

## Self-Check: PASSED

- [x] parse_soft_object_property函数存在 (uasset_read.py:~line 3230)
- [x] SoftObjectProperty在type_dispatch中注册 (uasset_read.py:~line 3955)
- [x] 测试文件包含5个SoftObjectProperty测试
- [x] Commit cd07a63存在
- [x] Commit 9abedae存在

---

*完成时间: 2026-05-02T17:47:04Z*
*总耗时: ~4分钟*