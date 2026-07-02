# 输出格式重构设计

## 目标

重构 JSON 输出结构，补齐缺失字段，保持 agent 友好性，避免过度输出。

## 设计原则

1. **完整性** — 输出所有结构化重要字段（参考 uasset 文件格式规范）
2. **可读性** — 索引值同时输出 resolved 名称和原始索引
3. **分层** — 区分核心数据和调试/诊断数据
4. **Agent 友好** — snake_case 命名、扁平结构、避免冗余嵌套
5. **条件输出** — 仅在有数据时输出，避免空字段噪音

## 新输出结构

```json
{
  "status": { "status": "success", "message": "...", "code": 0 },
  "output_version": "6.0",

  "header": {
    "package_name": "...",
    "package_class": "...",
    "package_flags": 0,
    "total_export_count": 0,
    "total_import_count": 0,
    "ue_version": "5.4",

    "file_version_ue4": 522,
    "file_version_ue5": 1018,
    "file_version_licensee": 0,
    "total_header_size": 0,
    "custom_versions": [{"key": 0, "version": 0}],
    "folder_name": "",
    "name_count": 0,
    "name_offset": 0,
    "soft_object_paths_count": 0,
    "soft_object_paths_offset": 0,
    "localization_id": "",
    "gatherable_text_data_count": 0,
    "gatherable_text_data_offset": 0,
    "export_count": 0,
    "export_offset": 0,
    "import_count": 0,
    "import_offset": 0,
    "metadata_offset": 0,
    "depends_offset": 0,
    "soft_package_references_count": 0,
    "soft_package_references_offset": 0,
    "searchable_names_offset": 0,
    "thumbnail_table_offset": 0,
    "import_type_hierarchies_count": 0,
    "import_type_hierarchies_offset": 0,
    "persistent_guid": "00000000000000000000000000000000",
    "generations": [],
    "saved_by_engine_version": "",
    "compatible_with_engine_version": "",
    "compression_flags": 0,
    "package_source": 0,
    "bulk_data_start_offset": 0,
    "world_tile_info_data_offset": 0,
    "chunk_ids": [],
    "preload_dependency_count": 0,
    "preload_dependency_offset": 0,
    "names_referenced_from_export_data_count": 0,
    "payload_toc_offset": 0,
    "data_resource_offset": 0,
    "saved_hash": "..."
  },

  "names": [
    {"index": 0, "name": "...", "non_case_preserving_hash": 0, "case_preserving_hash": 0}
  ],

  "imports": [
    {
      "index": 0,
      "class_package": "...",
      "class_name": "...",
      "object_name": "...",
      "outer_index": 0,
      "outer_index_resolved": "",
      "package_name": "",
      "b_import_optional": false
    }
  ],

  "exports": [
    {
      "index": 0,
      "object_name": "...",
      "object_class": "...",
      "serial_size": 0,
      "serial_offset": 0,
      "parent_class": "...",
      "outer_index_resolved": "",
      "super_index_resolved": "",
      "template_index": 0,
      "object_flags": 0,
      "package_flags": 0,
      "b_forced_export": false,
      "b_not_for_client": false,
      "b_not_for_server": false,
      "b_is_asset": true,
      "b_generate_public_hash": false,
      "b_not_always_loaded_for_editor_game": false,
      "guid": "00000000000000000000000000000000",

      "properties": [{"name": "...", "type": "...", "value": "...", "array_index": 0, "guid": null}],
      "graphs": [{"graph_name": "...", "graph_guid": "...", "nodes": [...], "execution_chains": [...]}],

      "parse_status": "success",
      "fallback_reason": null,
      "error_message": null
    }
  ],

  "depends": [
    {"export_index": 0, "dependencies": [0]}
  ],

  "soft_package_references": ["..."],

  "searchable_names": [],

  "thumbnails": [],

  "asset_registry_data": {},

  "preload_dependency": {
    "count": 0,
    "offset": 0
  },

  "bulk_data_start": {
    "offset": 0
  },

  "blueprint": {
    "parent_class": "...",
    "description": "",
    "interfaces": [],
    "functions": [],
    "events": [],
    "components": []
  },

  "variables": [...],

  "decompiled_functions": [...],

  "execution_chains": [...],

  "function_graphs": [...],

  "anim_blueprint": {
    "class_name": "...",
    "state_machines": [...],
    "anim_notifies": [...]
  },

  "anim_sequence": {
    "target_skeleton": "...",
    "additive_anim_type": "...",
    "ref_pose_type": "...",
    "ref_frame_index": 0,
    "sequence_length": 0.0,
    "notifies": [...],
    "float_curve_names": [...],
    "has_compressed_data": false
  },

  "anim_montage": {
    "blend_mode_in": 0,
    "blend_mode_out": 0,
    "blend_in_option": {},
    "blend_out_option": {},
    "sync_group": "",
    "rate_scale": 1.0,
    "composite_sections": [...],
    "slot_anim_tracks": [...],
    "branching_point_markers": [...],
    "notifies": [...]
  },

  "resolved_parent_assets": [...],
  "inherited_blueprint_graphs": [...],
  "logic_sources": [...],

  "diagnostics": [],
  "errors": []
}
```

## 分层策略

| 层级 | 内容 | 输出条件 |
|------|------|---------|
| **Header** | 文件格式元数据 | 始终输出 |
| **Names** | Name 表 | 始终输出（轻量） |
| **Imports** | 导入表 | 始终输出 |
| **Exports** | 导出表 + 属性/图 | 始终输出 |
| **Depends** | 依赖关系 | 始终输出（轻量） |
| **SoftRefs** | 软包引用 | 有数据时输出 |
| **Blueprint** | 蓝图元数据 | 仅蓝图类 export |
| **Anim** | 动画数据 | 仅动画类 export |
| **Diagnostics** | 诊断信息 | 有数据时输出 |

## 参考库字段映射

| 参考库字段 | 新输出字段 | 来源 |
|-----------|-----------|------|
| `header.*` | `header.*` | PackageFileSummary 全量 |
| `names[]` | `names[]` | NameMap 全量 |
| `imports.Imports[]` | `imports[]` | ImportMap 全量 |
| `exports[].classIndex` | `exports[].index` (int) | ExportMap |
| `exports[].objectFlags` | `exports[].object_flags` | ExportRawIR |
| `exports[].serialOffset` | `exports[].serial_offset` | ExportRawIR |
| `depends.Depends[]` | `depends[]` | DependsMap |
| `softPackageReferences` | `soft_package_references` | PackageIR |
| `thumbnails` | `thumbnails` | ThumbnailTable |
| `hexView` | 不输出（通过 --hex-view 控制） | 调试数据 |

## 实施计划

### Phase 1: IR 层扩展
- PackageHeaderIR: 添加 ~30 个字段
- ExportIR: 添加 object_flags, serial_offset, template_index 等
- ImportIR: 添加 outer_index, package_name, b_import_optional
- 添加 DependsIR, ThumbnailIR 等新结构

### Phase 2: IR Builder 更新
- `_build_header`: 从 PackageFileSummary 提取全量字段
- `_build_exports`: 从 ExportRawIR 提取全量字段
- `_build_imports`: 从 ObjectImport 提取全量字段

### Phase 3: JSON Renderer 重构
- 添加 header 全量输出
- 添加 names/imports 输出
- 添加 depends/softRefs 输出
- 补齐动画子结构字段

### Phase 4: 测试与验证
- 运行 smoke test 验证不破坏现有功能
- 对比新旧输出，确认无信息丢失
