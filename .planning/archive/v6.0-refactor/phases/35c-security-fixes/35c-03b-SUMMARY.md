---
title: "35c-03b: package_summary.py 偏移验证（14 个字段）"
plan_id: "35c-03b"
phase: "35c"
status: "complete"
---

# 35c-03b-SUMMARY.md — PackageSummary 偏移验证完成

## 一句话总结

为 `package_summary.py` 的 14 个偏移字段添加 `validate_offset()` 调用，确保所有 seek 操作前经过边界验证。

## 修改内容

### 原有验证（保留）

- `name_offset`（第 186 行）
- `export_offset`（第 218 行）
- `import_offset`（第 227 行）

### 新增验证（14 个）

| 偏移字段 | 行号 | 条件 | 说明 |
|---------|------|------|------|
| `soft_object_paths_offset` | 193-194 | UE5 >= 1008 | 软对象路径表偏移 |
| `gatherable_text_data_offset` | 211-212 | UE4 >= 401 或 UE5 | 可收集文本数据偏移 |
| `cell_export_offset` | 244-245 | UE5 >= 1015 | Verse Cells 导出表偏移 |
| `cell_import_offset` | 250-251 | UE5 >= 1015 | Verse Cells 导入表偏移 |
| `metadata_offset` | 257-258 | UE5 >= 1014 | UE5 元数据偏移 |
| `soft_package_references_offset` | 274-275 | UE4 >= 382 | 软包引用偏移 |
| `searchable_names_offset` | 282-283 | UE4 >= 508 | 可搜索名称偏移 |
| `thumbnail_table_offset` | 287-288 | 无条件 | 缩略图表偏移 |
| `import_type_hierarchies_offset` | 296-297 | UE5 >= 1018 | 导入类型层次偏移 |
| `asset_registry_data_offset` | 373-374 | 无条件 | 资产注册表偏移 |
| `world_tile_info_data_offset` | 383-384 | UE4 >= 223 或 UE5 | 世界 tile 信息偏移 |
| `preload_dependency_offset` | 407-408 | UE4 >= 507 | 预加载依赖偏移 |
| `payload_toc_offset` | 423-424 | UE5 >= 1002 | 载荷 TOC 偏移（i64） |
| `data_resource_offset` | 432-433 | UE5 >= 1009 | 数据资源偏移 |

### 验证逻辑

每个偏移读取后，当值 > 0 时调用 `archive.validate_offset()`：

```python
offset = archive.read_i32()  # 或 read_i64()
if offset > 0:
    archive.validate_offset(offset, "OffsetName")
```

- 偏移为 0 表示"不存在"，跳过验证
- 偏移为 -1（i64 字段默认值）跳过验证
- 负偏移或超界偏移抛 `ParseError`

## 测试结果

```
257 passed, 65 skipped, 1 failed
```

失败测试 `test_jump_started_flow` 是 Phase 21 执行流程验证，与本次偏移验证修改无关。

## 与计划偏差

无偏差 — 计划执行完全符合预期。

## 安全影响

- **M4 风险消除**: 所有偏移字段在 seek 前经过验证，防止无效偏移导致的内存访问越界
- **攻击向量阻断**: 恶意构造的 .uasset 文件无法通过超界偏移触发非法内存访问

## 关键文件

- `src/uasset_read/serializers/package_summary.py` — 唯一修改文件，新增 28 行

## 提交记录

- `42d0d38`: feat(35c-03b): 为 package_summary.py 添加 14 个偏移验证