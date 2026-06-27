---
title: Object Linker
section: linker
---

# Object Linker

`link/` implements FLinkerLoad-style two-phase object graph reconstruction.

<!-- data-api="PackageLinker" -->
```python
PackageLinker(archive, summary, name_map, import_map, export_map, version_container)
```

## Two-Phase Loading

```
link() -- Phase 1
├── _create_import_instances() → _import_objects[]
├── _create_export_instances() → _export_objects[]
├── build_outer_tree() → resolve outer_index
└── _collect_root_objects()

preload(index) -- Phase 2 (deferred)
└── parse_properties_from_export() → serialized_properties

post_load() -- Stage 4
├── _resolve_property_references() + _resolve_weak_references()
├── _verify_imports() + _resolve_template_objects()
└── _build_dependency_graph()
```

## UObjectInstance Fields

| Field | Type | Description |
|-------|------|-------------|
| `package_index` | int | +export, -import, 0=null |
| `object_name / object_class` | str | Object name/class |
| `outer_index / super_object` | PackageIndex / UObjectInstance | Outer object/parent class |
| `template_object` | UObjectInstance | CDO reference |
| `serialized_properties` | List[Any] | Serialized properties |
| `property_references` | Dict[str, UObjectInstance] | Property references |
| `dependencies` | List[UObjectInstance] | Dependency list |

## PackageRegistry

<!-- data-api="get_or_load" -->
```python
get_or_load(package_path, provider, tolerant) → PackageLinker
resolve_import_across_packages(path, name, provider) → UObjectInstance
```

> [!TIP]
> **Related Sections**: [[Parse Pipeline]] · [[Serializers]]
