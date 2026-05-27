# FArchive COR Fixes — VersionContainer 集成 + StructProperty 边界

## 背景

Phase 76 不是"未开始"而是"部分实现、未收口"。`VersionContainer`、`build_version_container()`、`EUEVersion` 已实现，`parse_uasset()` 已挂接 `version_container`，但关键读取路径仍使用硬编码的 `summary.file_version_ue5` 和 `summary.get_custom_version()`。

## 目标

1. VersionContainer 从结果对象升级为序列化决策基础设施
2. 4 个关键路径的版本判断统一收敛
3. StructProperty fast-path 增加 `tag.size` 校验
4. 修复 Phase 75 回归测试红灯

## 架构

给 `PackageFileSummary` 添加可选 `version_container: Optional[VersionContainer]` 字段。关键路径优先使用 `summary.version_container`，若无则回退到旧的 `summary.file_version_ue5` 检查。

StructProperty fast-path 在读取前校验 `tag.size` 是否匹配预期布局大小，不匹配时回退到 PropertyTag loop。

## 关键路径版本判断审计

| File | Line | 当前用法 | 迁移策略 |
|------|------|---------|---------|
| `parsers/property_parser.py` | 133,140,148 | `summary.file_version_ue5 >= threshold` | `version_container.is_at_least(threshold)` |
| `serializers/graph.py` | 165-166 | `summary.get_custom_version(GUID, 0)` | `version_container.get_version(GUID)` |
| `serializers/graph.py` | 1688 | `summary.file_version_ue5 >= 1011` (硬编码) | `version_container.is_at_least(1011)` |
| `kismet/bytecode_extractor.py` | 96,104 | `summary.file_version_ue5 >= threshold` | 同上 |
| `kismet/bpgc_bytecode.py` | 132,140 | `summary.file_version_ue5 >= threshold` | 同上 |

**不需要迁移的点：**
- `serializers/package_summary.py` — 这里是值被 SET 的地方
- `formatters/` — 仅用于输出展示

## StructProperty Fast-Path 增强

为所有 fast-path struct 增加 `tag.size` 预期值校验：

```python
_EXPECTED_STRUCT_SIZES = {
    "Vector": 12, "Rotator": 12, "Vector2D": 8, "Vector4": 16,
    "LinearColor": 16, "Color": 4, "Quat": 16, "Plane": 16,
    "Guid": 16, "IntPoint": 8, "IntVector": 12,
    "Box2D": 20, "Box": 28, "Sphere": 16, "BoxSphereBounds": 40,
    "Matrix": 64, "TwoVectors": 24, "OrientedBox": 60,
    "Transform": 48,
}
```

当 `tag.size != expected` 时，不走快径，回退到 PropertyTag loop。

## BodyInstance 策略

**不添加 BodyInstance fast-path。** CUE4Parse 本身只有游戏特定的 BodyInstance 处理（ConanExilesEnhanced），对通用情况使用 `FStructFallback`。BodyInstance 是 30+ 字段的复杂结构体，版本依赖性强，无稳定测试样本。

## 关键文件

- `src/uasset_read/versioning.py` — 版本查询 API
- `src/uasset_read/serializers/package_summary.py` — 添加 version_container 字段
- `src/uasset_read/parsers/property_parser.py` — 版本判断收敛
- `src/uasset_read/serializers/graph.py` — CustomVersion 查询收敛
- `src/uasset_read/parsers/property_types.py` — StructProperty tag.size 校验
- `src/uasset_read/kismet/bytecode_extractor.py` — 版本判断收敛
- `src/uasset_read/kismet/bpgc_bytecode.py` — 版本判断收敛

## 测试

- `tests/test_versioning.py` — 版本查询行为测试
- `tests/test_struct_property.py` — tag.size mismatch / fallback / recovery 测试
- `tests/test_phase75_event_node_field_alignment.py` — 回归修复

## 验收标准

- 至少 2 个关键读取函数使用 VersionContainer 或统一封装
- `tests/test_struct_property.py` 通过 + 至少 3 个新边界测试
- 全量测试绿灯（或无关失败已记录）
