---
name: uasset-format
description: Use when working with Unreal Engine .uasset files, parsing UE asset formats, understanding PackageFileSummary/ImportExport structures, debugging asset serialization issues, or implementing UE asset readers. Triggers for .uasset file analysis, UE version compatibility questions, and asset type structure inquiries.
---

# UE .uasset 文件格式参考

> **版本**: 0.5.0 | **最后更新**: 2026-06-12

## Overview

Unreal Engine .uasset 文件格式知识库。核心原则：**解析 .uasset 必须先查 UE 源码理解结构，不能直接猜测二进制**。所有字段定义必须能追溯到 UE C++ 源码。

## Core Principle (铁律)

```
禁止直接读取/猜测二进制格式
├── ❌ 错误：读二进制 → 猜字段含义 → 实现
└── ✅ 正确：查 UE 源码 → 理解结构定义 → 实现

输出必须可追溯到 C++ 定义
├── 每个解析字段必须对应 UE 源码字段
└── 文档必须标注源码位置
```

## Quick Reference - 文档导航

### 文件结构基础
| 文档 | 内容 | 关键结构 |
|------|------|----------|
| [file-structure.md](file-structure.md) | 文件整体布局 | Header → Tables → Data → Trailer |
| [package-summary.md](package-summary.md) | FPackageFileSummary | Tag, Version, 各表 Offset/Count |
| [name-table.md](name-table.md) | 名称表 | FName 序列化机制 |
| [import-export-tables.md](import-export-tables.md) | Import/Export 表 | FPackageIndex 引用机制 |
| [bulkdata-region.md](bulkdata-region.md) | 数据区 | BulkData/PayloadTOC/DataResource |
| [package-trailer.md](package-trailer.md) | 文件尾 (UE5) | PackageTrailer 结构 |

### 序列化机制 (serialization/)
| 文档 | 内容 | 关键流程 |
|------|------|----------|
| [linker-load.md](serialization/linker-load.md) | 加载流程 | 4 阶段：Header → Tables → Objects → PostProcess |
| [linker-save.md](serialization/linker-save.md) | 保存流程 | 序列化写入机制 |
| [property-tag.md](serialization/property-tag.md) | FPropertyTag | 完整字段表、BoolProperty 特殊处理、EPropertyTagFlags |
| [uproperty-specifiers.md](serialization/uproperty-specifiers.md) | UPROPERTY 说明符 | CPF_* 标志、元数据说明符、序列化行为 |
| [class-default-object.md](serialization/class-default-object.md) | CDO 机制 | Class Default Object 序列化、Delta 差异、蓝图 CDO |
| [bulkdata.md](serialization/bulkdata.md) | BulkData 机制 | 运行时加载、流式传输 |
| [version-compatibility.md](serialization/version-compatibility.md) | 版本判断 | UE4/UE5 双版本机制 |

### Cooked 格式 (cooked/)
| 文档 | 内容 | 适用场景 |
|------|------|----------|
| [cooked-vs-uncooked.md](cooked/cooked-vs-uncooked.md) | 格式对比 | 15 项差异、PKG 标志 |
| [pak.md](cooked/pak.md) | Pak 容器 | UE4 Pak 文件格式 |
| [iostore.md](cooked/iostore.md) | IoStore 容器 | UE5 IoStore 格式 |

### 版本演进 (version/)
| 文档 | 内容 | 版本范围 |
|------|------|----------|
| [ue4-evolution.md](version/ue4-evolution.md) | UE4 版本历史 | 214-522 关键版本 |
| [ue5-evolution.md](version/ue5-evolution.md) | UE5 版本历史 | UE5 新增版本号 |
| [migration-guide.md](version/migration-guide.md) | 迁移指南 | 跨版本资产处理 |

### 资产类型 (assets/)
| 资产类型 | 导航文档 | 核心源码路径 |
|----------|----------|--------------|
| 静态网格 | [static-mesh.md](assets/static-mesh.md) | Engine/StaticMesh.h |
| 骨骼网格 | [skeletal-mesh.md](assets/skeletal-mesh.md) | Engine/SkeletalMesh.h |
| 动画序列 | [animation.md](assets/animation.md) | Animation/AnimSequence.h |
| 蓝图 | [blueprint.md](assets/blueprint.md) | Engine/Blueprint.h |
| 材质 | [material.md](assets/material.md) | Engine/Material.h |
| 纹理 | [texture.md](assets/texture.md) | Engine/Texture.h |
| 音频 | [audio.md](assets/audio.md) | Engine/SoundWave.h |
| 关卡 | [level.md](assets/level.md) | Engine/World.h |
| 粒子 | [particle-system.md](assets/particle-system.md) | Engine/ParticleSystem.h |
| UMG Widget | [widget-blueprint.md](assets/widget-blueprint.md) | UMG/WidgetBlueprint.h |

## Key Constants

```cpp
// 文件魔数
PACKAGE_FILE_TAG = 0x9E2A83C1
PACKAGE_FILE_TAG_SWAPPED = 0xC1832A9E  // 字节序交换

// 版本号
VER_UE4_OLDEST_LOADABLE_PACKAGE = 214  // 最低可加载版本

// 引用机制
FPackageIndex: 正数 = Export, 负数 = Import, 0 = Null
```

## UE 源码关键路径

| 文件 | 路径 | 说明 |
|------|------|------|
| PackageFileSummary.h | Runtime/CoreUObject/Public/UObject/ | 文件头结构 |
| ObjectVersion.h | Runtime/Core/Public/UObject/ | 版本号定义 |
| ObjectResource.h | Runtime/CoreUObject/Public/UObject/ | Import/Export 表 |
| LinkerLoad.h | Runtime/CoreUObject/Public/UObject/ | 加载逻辑 |
| PropertyTag.h | Runtime/CoreUObject/Public/UObject/ | 属性标签 |
| BulkData.h | Runtime/CoreUObject/Public/Serialization/ | BulkData 结构 |

## Common Mistakes

| 错误做法 | 正确做法 |
|----------|----------|
| 直接读二进制猜测字段含义 | 先查 UE 源码结构定义 |
| 忽略版本差异 | 检查 FileVersionUE4/UE5 和 CustomVersion |
| 假设字段固定位置 | 根据版本号动态判断字段存在性 |
| 混用 UE4/UE5 版本判断 | 使用 FPackageFileVersion.operator>=() |
| 忽略 Cooked vs Uncooked 差异 | 检查 PKG_Cooked 和 PKG_UnversionedProperties |
| 跳过 PackageTrailer (UE5) | UE5 文件必须解析 PayloadTOC |

## Red Flags - 停止并查阅源码

- "这个二进制值看起来像是..."
- "不确定这个字段的含义..."
- "版本号不匹配..."
- "资产加载失败..."

**所有这些意味着: 停止猜测，查阅 UE 源码。**

## Loading Process Summary

```
1. 验证 PACKAGE_FILE_TAG
2. 读取 FPackageFileSummary
3. 判断 UE4/UE5 版本
4. 加载 Name Table → Import Map → Export Map
5. 按依赖顺序创建 UObject
6. 序列化属性 (通过 FPropertyTag)
7. 加载 BulkData (纹理、网格等)
8. UE5: 解析 PackageTrailer 和 PayloadTOC
```

详见 [linker-load.md](serialization/linker-load.md)

## Asset Structure Pattern

每个资产文档遵循统一结构:
1. **概述**: 资产用途和核心组件
2. **字段表**: 字段名、类型、用途、源码位置、版本差异
3. **源码引用**: UE C++ 定义文件路径
4. **版本差异**: UE4/UE5 变更历史

## v0.4.5 关键变更

### 1. 状态模型统一

**之前**: `success | fail | error`
**之后**: `success | partial | failed`

- `success`: 无错误，所有 export 解析成功
- `partial`: 部分错误或某些 export 为 opaque/skipped，但核心数据可用
- `failed`: 严重错误，无可用数据

### 2. UE 风格加载生命周期

执行顺序: `link() → preload(idx) × N → post_load()`

- `post_load()` 在所有 export 预加载之后调用
- 确保 ObjectProperty 引用能正确解析为 UObjectInstance

### 3. 类序列化策略表

4 种策略:
- `FULL_SERIALIZER`: 完整序列化（默认）
- `TAGGED_PROPERTIES_ONLY`: 仅解析属性标签
- `OPAQUE_CLASS_PAYLOAD`: 标记为 opaque（如 StaticMesh、Texture2D）
- `SKIP_UNSUPPORTED`: 跳过不支持的类

### 4. Payload 偏移策略

默认使用 `SerialOffset/SerialSize`（与 UE LinkerLoad.cpp:4793 对齐）

- ScriptSerialization 偏移保留为诊断字段
- 对于包含 class-specific payload 的资产，现在会解析更多数据

### 5. SoftObjectPath 索引化解析

UE5.7+ 支持索引模式:
- 当存在 `SoftObjectPathList` 时，`SoftObjectProperty` 读取 int32 索引
- 越界索引产生诊断信息，不崩溃

### 6. DependsMap FPackageIndex 语义

DependsMap 值现在使用 FPackageIndex 语义:
- 正值 = export (1-based)
- 负值 = import (-1-based)
- 零 = null