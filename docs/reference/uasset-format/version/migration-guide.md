# 版本迁移指南

## 概述

版本迁移指南帮助开发者理解 UE4/UE5 资产版本变更，处理跨版本资产加载问题。本文档覆盖常见迁移问题、各资产类型迁移注意事项和版本检测逻辑。

版本判断机制详见 [version-compatibility.md](../serialization/version-compatibility.md)。

## 常见迁移问题

### 1. 版本检测失败

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| 包无法加载 | 版本号低于 VER_UE4_OLDEST_LOADABLE_PACKAGE (214) | 在原始引擎版本中重新保存资产 |
| 版本号异常 | Licensee 标志损坏 (4.26) | 使用 VER_UE4_CORRECT_LICENSEE_FLAG 修复版本 |
| 版本判断错误 | 混用 UE4/UE5 版本判断 | 使用 FPackageFileVersion.operator>=() 正确判断 |

### 2. 数据丢失风险

| 问题 | 原因 | 解决方法 |
|------|------|----------|
| BulkData 丢失 | 旧版本 BulkData 存储路径失效 | 使用 VER_UE4_SUPPORT_32BIT_STATIC_MESH_INDICES 后重新保存 |
| 名称表损坏 | 旧版本哈希计算错误 | VER_UE4_FIX_WIDE_STRING_CRC 后重新保存 |
| 属性丢失 | PropertyTag 版本不匹配 | 检查 VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG 支持 |

### 3. 重新保存需求

| 版本变更 | 需重新保存资产 | 说明 |
|----------|----------------|------|
| VER_UE4_CASE_PRESERVING_FNAME | 所有资产 | FName 大小写保留变更 |
| VER_UE4_ADDED_SOFT_OBJECT_PATH | 引用资产 | FStringAssetReference → FSoftObjectPath |
| VER_UE4_64BIT_EXPORTMAP_SERIALSIZES | 大型资产 | Export 表 SerialSize 升级 |
| VER_UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS | Cooked 资产 | 依赖图预加载 |

### 4. 向后兼容处理

| 处理方式 | 说明 |
|----------|------|
| IsCompatible() 检查 | 加载前检查版本兼容性 |
| CustomVersion 模块版本 | 模块级版本控制，独立于全局版本 |
| 版本降级警告 | 保存时警告降级版本可能丢失数据 |

## 全资产类型迁移注意事项

### 材质资产迁移

关键变更：材质属性重排序、材质实例覆盖、混合模式处理。

- 版本 < 220：材质属性顺序可能不正确，需重新保存
- 版本 < 297：材质实例基础属性覆盖不支持
- 版本 < 633：bUsedWithUI 标志需迁移为 MaterialDomain

详见 [材质资产版本差异](asset-material.md)

### 纹理资产迁移

关键变更：纹理坐标数量增加、BulkData 存储变更、Gamma 处理。

- 版本 < 226：最大纹理坐标为 4，需检查纹理采样
- 版本 < 447：纹理 Mip 数据 BulkData 存储方式不同
- 版本 < 536：Gamma 处理方式可能不同

详见 [纹理资产版本差异](asset-texture.md)

### 静态网格迁移

关键变更：LOD 格式变更、32 位索引支持、边界数据扩展。

- 版本 < 236：不支持 32 位索引缓冲，大型网格可能失败
- 版本 < 347：LOD ScreenSize 格式不同
- 版本 < 492：ExtendedBounds 字段不存在

详见 [静态网格版本差异](asset-static-mesh.md)

### 骨骼网格迁移

关键变更：骨骼层级重构、骨骼权重扩展、服装数据变更。

- 版本 < 258：骨骼层级结构不同 (FReferenceSkeleton)
- 版本 < 264：仅支持 4 骨骼影响，需重新导入
- 版本 < 228：不支持 APEX 服装

详见 [骨骼网格版本差异](asset-skeletal-mesh.md)

### 蓝图资产迁移

关键变更：Skeleton 类处理、节点引用机制、输入绑定变更。

- 版本 < 430：K2Node 缺少 ReferenceGuid，重命名可能失败
- 版本 < 466：组件模板公开标志缺失
- 版本 < 521：事件节点缺少 MemberReference

详见 [蓝图资产版本差异](asset-blueprint.md)

### 动画序列迁移

关键变更：曲线数据添加、骨骼 SmartNames、NaN 处理。

- 版本 < 380：动画曲线数据格式不同
- 版本 < 395：骨骼缺少 SmartNames
- 版本 < 272：动画数据可能包含 NaN

详见 [动画序列版本差异](asset-animation.md)

### 音频资产迁移

关键变更：压缩格式变更、并发设置、BulkData 存储。

- 版本 < 318：压缩类型字段不存在
- 版本 < 409：并发设置结构不同
- 版本 < 518：音频 BulkData 存储方式不同

详见 [音频资产版本差异](asset-audio.md)

## 源码引用

| 文件 | 路径 | 说明 |
|------|------|------|
| ObjectVersion.h | Runtime/Core/Public/UObject/ | 版本枚举定义 |
| LinkerLoad.cpp | Runtime/CoreUObject/Private/UObject/ | 版本检测逻辑 |
| PackageFileSummary.h | Runtime/CoreUObject/Public/UObject/ | 文件头版本字段 |

---

*Phase: 07-版本演进历史*
*Created: 2026-04-29*