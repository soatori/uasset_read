# 静态网格版本差异

## 概述

静态网格结构随 UE 版本演进，UE5 引入 Nanite、TObjectPtr、平台相关 LOD 等新特性。解析静态网格时需检查版本号以选择正确的字段读取方式。

## 关键版本变更

### UE5 新增特性

| 特性 | 版本 | 说明 | 源码位置 |
|------|------|------|----------|
| Nanite 数据 | UE5.0 | NaniteResourcesPtr 字段新增 | StaticMeshResources.h 第 791 行 |
| TObjectPtr | UE5.0 | 智能指针替代原始指针 | StaticMesh.h 第 506 行 |
| PerPlatform LOD | UE5.0 | FPerPlatformInt/FPerPlatformFloat | StaticMesh.h |
| ImportedMaterialSlotName | UE5.0 | 材质重映射支持 | StaticMesh.h 第 514-515 行 |
| OverlayMaterialInterface | UE5.0 | 覆盖材质支持 | StaticMesh.h 第 521-522 行 |
| RayTracingGeometry | UE5.0 | 光线追踪几何 | StaticMeshResources.h 第 439 行 |

### UE4 关键变更

| 特性 | 版本 | 说明 | 源码位置 |
|------|------|------|----------|
| LODGroup | UE4.22 | LOD 组设置新增 | StaticMesh.h 第 687-690 行 |
| ReducedLODs | UE4.24 | LOD 级别限制优化 | StaticMeshResources.h |
| MaterialIndexToImportIndex | UE4.23 | 材质索引映射 | StaticMeshResources.h |
| bAutoComputeLODScreenSize | UE4.25 | 自动计算 LOD 阈值 | StaticMesh.h 第 712 行 |

## 废弃字段

| 字段名 | 废弃版本 | 替代字段 | 源码位置 |
|--------|----------|----------|----------|
| Materials_DEPRECATED | UE5.0 | StaticMaterials (FStaticMaterial 数组) | StaticMesh.h 第 729-731 行 |
| bStripComplexCollisionForConsole_DEPRECATED | UE5.0 | 平台 LOD 设置 | StaticMesh.h |
| SourceModels (直接访问) | UE5.0 | 使用 GetSourceModels() | StaticMesh.h 第 644-647 行 |

## 版本判断机制

解析静态网格时应遵循以下流程：

1. **检查 FileVersionUE**: 确定引擎版本范围
2. **检查 CustomVersion**: 确定静态网格特定版本
3. **根据版本选择字段读取方式**:
   - TObjectPtr vs 原始指针
   - FPerPlatformFloat vs float
   - Nanite 数据是否存在
4. **忽略废弃字段**: 使用替代字段或默认值

### 版本判断代码位置

StaticMesh.cpp 中使用 `Ar.CustomVer()` 检查版本号：
- FStaticMeshVersion 枚举定义静态网格特定版本
- ObjectVersion.h 定义引擎全局版本

详见 [版本兼容机制](../serialization/version-compatibility.md)。

## FStaticMeshVersion 静态网格版本枚举

关键版本值（具体值见 ObjectVersion.h）：
- 增加 Nanite 数据版本
- TObjectPtr 迁移版本
- 材质重映射版本

## 源码引用

- Runtime/Core/Public/UObject/ObjectVersion.h — 版本号定义
- Runtime/Core/Public/UObject/UE5MainStreamObjectVersions.inl — UE5 版本定义
- Runtime/Engine/Private/Engine/StaticMesh.cpp — 版本判断代码
- Runtime/Engine/Classes/Engine/StaticMesh.h — 废弃字段标记

## 版本兼容处理建议

解析静态网格时：
1. 优先使用现代字段（TObjectPtr、FPerPlatform）
2. 检查 NaniteSettings.IsValid() 判断 Nanite 数据存在
3. Materials_DEPRECATED 需转换为 FStaticMaterial 数组
4. 旧版 LOD 阈值需转换为 FPerPlatformFloat
5. ImportedMaterialSlotName 缺失时使用 MaterialSlotName