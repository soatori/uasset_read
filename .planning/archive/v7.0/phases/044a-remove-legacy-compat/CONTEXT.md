# Phase 44a: 移除旧版本/UE4 兼容代码

## Status
⏳ 待执行

## Goal
删除所有 UE4/旧版本兼容路径，仅保留 UE5 当前版本支持。消除版本条件分支带来的代码复杂度和 AI 分析误导。

## Scope

### 涉及文件
| 文件 | 操作 |
|------|------|
| `src/uasset_read/constants.py` | 删除 UE4 版本常量（UE4_* 前缀） |
| `src/uasset_read/serializers/package_summary.py` | 删除 `is_ue4_file` 分支和 UE4 条件读取 |
| `src/uasset_read/serializers/object_resources.py` | 删除 UE4 >= 508/511/520 等条件分支 |
| `src/uasset_read/serializers/property_tags.py` | 删除 UE4 格式路径 |
| `src/uasset_read/serializers/graph.py` | 删除 UE4 FEdGraphPinType 序列化路径 |
| `src/uasset_read/parsers/property_parser.py` | 删除 UE4 版本条件 |
| `src/uasset_read/archive.py` | 删除 `read_bool()` UE4 路径（保留 `read_bool_ue5()`） |
| `src/uasset_read/formatters/json_formatter.py` | 删除 legacy_version 输出 |
| 相关测试 fixtures | 更新 `ue4_summary` 等 fixture |

### 不变
- `legacy_file_version` 字段保留（仍需从文件头读取，但不再作为分支条件）
- FArchive 核心字节序处理逻辑保留

## Success Criteria
- `grep -rn 'is_ue4_file\|UE4_\|legacy_file_version >' src/` 返回 0 结果
- 所有测试通过，无回归
- `uasset-read` 对 UE5 资产解析行为不变

## Dependencies
- Phase 44（模型增强）已完成

## Notes
执行前先检索当前代码状态，部分兼容代码可能已被移除。

*Created: 2026-05-14*
