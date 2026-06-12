---
title: 对象链接器
section: linker
---

# 对象链接器

`link/` 实现 FLinkerLoad 风格的两阶段对象图重建。

<!-- data-api="PackageLinker" -->
```python
PackageLinker(archive, summary, name_map, import_map, export_map, version_container)
```

## 两阶段加载

```
link() -- Phase 1: 创建对象实例
├── _create_import_instances() → _import_objects[]
├── _create_export_instances() → _export_objects[]
├── build_outer_tree() → 解析 outer_index
└── _collect_root_objects()

preload(index) × N -- Phase 2: 序列化属性
├── 检查类序列化策略（ClassSerializationStrategy）
├── parse_properties_from_export() → serialized_properties
└── 标记 opaque/skipped 类

post_load() -- Phase 3: 解析引用
├── _resolve_property_references() + _resolve_weak_references()
├── _verify_imports() + _resolve_template_objects()
└── _build_dependency_graph()
```

> **v0.4.5 变更**: 执行顺序为 `link() → preload(idx) × N → post_load()`。
> `post_load()` 在所有 export 预加载之后调用，确保 ObjectProperty 引用能正确解析。

## UObjectInstance 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `package_index` | int | +导出, -导入, 0=null |
| `object_name / object_class` | str | 对象名/类 |
| `outer_index / super_object` | PackageIndex / UObjectInstance | 外部对象/父类 |
| `template_object` | UObjectInstance | CDO 引用 |
| `serialized_properties` | List[Any] | 序列化属性 |
| `property_references` | Dict[str, UObjectInstance] | 属性引用 |
| `dependencies` | List[UObjectInstance] | 依赖列表 |

## PackageRegistry

<!-- data-api="get_or_load" -->
```python
get_or_load(package_path, provider, tolerant) → PackageLinker
resolve_import_across_packages(path, name, provider) → UObjectInstance
```

> [!TIP]
> **相关章节**: [[解析管线]] · [[序列化模块]]
