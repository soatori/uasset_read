---
title: 蓝图解析
section: blueprint
---

# 蓝图解析

> **模块路径**: `blueprint/`
> **职责**: 提取蓝图变量、变换、组件和元数据。

## 核心 API

### extract_blueprint_variables

<!-- data-api="extract_blueprint_variables" -->
```python
extract_blueprint_variables(properties: List[PropertyValue]) → List[BlueprintVariable]
```

从属性列表中提取蓝图变量。

### extract_blueprint_metadata

<!-- data-api="extract_blueprint_metadata" -->
```python
extract_blueprint_metadata(export, archive, import_map, export_map, name_map, summary, linker, graphs) → Tuple[BlueprintMetadata, str]
```

提取蓝图完整元数据，包括变量、函数、事件等信息。

### parse_component_transform

<!-- data-api="parse_component_transform" -->
```python
parse_component_transform(properties: List[PropertyValue]) → Dict[str, Any]
```

解析组件变换数据。

## 变量提取路径

- **主要路径**：从 `UBlueprint.NewVariables` 解析 FBPVariableDescription 结构
- **回退路径**：从属性迭代推断类型和标志

## 组件相关

### extract_components

<!-- data-api="extract_components" -->
```python
extract_components(export_map, import_map) → List[Dict]
```

从 ExportMap 中发现 SCS（SimpleConstructionScript）组件。

### extract_component_transforms

<!-- data-api="extract_component_transforms" -->
```python
extract_component_transforms(export_properties, component_name) → Dict
```

提取组件的变换信息：
- `RelativeLocation` - 相对位置
- `RelativeRotation` - 相对旋转
- `RelativeScale3D` - 相对缩放

## 相关章节

- [[Graph]] - 图分析
- [[Kismet]] - Kismet 反编译
