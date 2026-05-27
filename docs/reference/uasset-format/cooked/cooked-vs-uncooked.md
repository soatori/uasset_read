# Cooked vs Uncooked 格式对比

## 概述

**Cooked 格式定义：** 用于游戏发布的打包数据格式，经过 Cooking 处理，去除编辑器专用数据，优化加载性能。

**Uncooked 格式定义：** 编辑器中的原始资产格式，保留完整的编辑器数据和元信息。

**核心区别：** Cooked 格式去除编辑器专用数据、优化数据组织、使用更高效的序列化方式，以提高加载性能和减少包大小。

---

## 包标志定义

| 标志 | 值 | 说明 |
|------|-----|------|
| PKG_Cooked | 0x00000200 | 包已 Cooked。加载时设置 IsLoadingFromCookedPackage 状态。 |
| PKG_FilterEditorOnly | 0x80000000 | 已过滤编辑器数据。Cooking 过程中过滤了编辑器专用内容。 |
| PKG_UnversionedProperties | 0x00002000 | 使用无版本属性序列化。跳过属性标签（FPropertyTag），直接序列化属性值。 |
| PKG_UncookedOnly | 0x00000100 | 仅在 Uncooked 构建中加载。这类包在 Cooked 构建中不可用。 |

**用途说明：**
- PKG_Cooked：标识包已完成 Cooking，加载路径使用 Cooked 专用逻辑
- PKG_FilterEditorOnly：标识编辑器数据已过滤，Cooked 构建中跳过这些内容
- PKG_UnversionedProperties：启用无版本属性序列化，大幅提升加载性能
- PKG_UncookedOnly：用于仅编辑器使用的包，如某些调试工具

---

## 主要差异对比表

| # | 差异项 | Uncooked | Cooked | 影响 |
|---|--------|----------|--------|------|
| 1 | 编辑器专用数据 | 包含完整编辑器数据（MetaData、编辑器属性等） | 过滤编辑器专用数据 | 包大小减少 |
| 2 | 属性序列化格式 | 带标签属性序列化（FPropertyTag） | 无版本属性序列化（PKG_UnversionedProperties） | 加载性能提升 |
| 3 | BulkData 存储 | 可内嵌或外置（BULKDATA_PayloadAtEndOfFile） | 通常分离到独立数据块（ExportBundleData、BulkData Chunk） | 数据组织变化 |
| 4 | Import 表 | 包含完整 Import 信息（ObjectName、ClassPackage、ClassName） | 可能简化或预解析 | 引用解析变化 |
| 5 | Export 表 | 标准导出结构（SerialSize、SerialOffset） | 可能包含额外 Cooked 信息 | 导出加载变化 |
| 6 | 数据块组织 | 单一 .uasset 文件 | 拆分为多个 FIoChunkId（ExportBundleData、BulkData、OptionalBulkData 等） | 数据访问变化 |
| 7 | 容器格式 | 独立 .uasset 文件 | 打包到 IoStore (.ucas/.utoc) 或 Pak (.pak) | 存储方式变化 |
| 8 | 名称表 | 标准 FName 序列化（NameIndex + Number） | 可能使用更紧凑编码 | 内存占用变化 |
| 9 | 压缩 | 可选压缩 | 通常强制压缩（Oodle/Zlib） | 加载需解压 |
| 10 | 加密 | 无加密 | 可选 AES 加密（EIoContainerFlags::Encrypted） | 需密钥解密 |
| 11 | PackageTrailer | UE5 可选 | UE5 Cooked 包含（用于验证和定位） | 验证/定位变化 |
| 12 | ShaderMap 数据 | 内嵌材质 ShaderMap | 分离到 ShaderCodeLibrary Chunk | Shader 加载变化 |
| 13 | MetaData | 包含完整 MetaData（UPackage::MetaData） | 过滤或简化 MetaData | 元数据查询变化 |
| 14 | 资产引用 | 标准 Soft/Hard 引用（SoftObjectPath、ObjectPath） | Package Store Entry 索引引用 | 引用查找变化 |
| 15 | 加载流程 | LinkerLoad 直接加载 .uasset | 通过 IoDispatcher/PakPlatformFile 加载容器数据 | 加载路径变化 |

---

## Cooked 检测逻辑

LinkerLoad 在加载包时检测 Cooked 状态：

**检测流程：**
1. 从 FPackageFileSummary 获取 PackageFlags
2. 检测 PKG_Cooked 标志 → 设置 IsLoadingFromCookedPackage 状态
3. 检测 PKG_UnversionedProperties 标志 → 设置无版本属性序列化模式
4. 检测 PKG_FilterEditorOnly 标志 → 设置 bIsCookedForEditor 标志

源码位置：Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp — 行 1574-1580

**Cooked 加载特殊处理：**
- BulkData PackageSegment：Cooked 包使用 `EPackageSegment::Exports`，Uncooked 使用 `EPackageSegment::Header`
- 偏移调整：Cooked 包的 BulkData 偏移需要减去 Header 大小
- 异步加载优化：Cooked 数据可使用 FAsyncArchive 加载器

---

## Cooked 数据拆分

Cooked 包将数据拆分为多个 FIoChunkId：

| ChunkType | 值 | 内容 |
|-----------|-----|------|
| ExportBundleData | 1 | 导出数据（主 .uasset 数据） |
| BulkData | 2 | BulkData 数据块 |
| OptionalBulkData | 3 | 可选 BulkData（如高清纹理） |
| MemoryMappedBulkData | 4 | 内存映射 BulkData |
| ShaderCodeLibrary | 8 | Shader 代码库 |
| ShaderCode | 9 | Shader 代码 |
| PackageStoreEntry | 10 | Package Store 条目 |

---

## 源码引用

| 结构/逻辑 | 文件路径 |
|----------|----------|
| PKG 标志定义 | Runtime/CoreUObject/Public/UObject/ObjectMacros.h |
| Cooked 检测逻辑 | Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp (行 1574-1580) |
| Cooked MetaData | Runtime/CoreUObject/Private/UObject/CookedMetaData.cpp |
| FPackageStoreEntry | Runtime/CoreUObject/Public/Serialization/PackageStore.h |
| BulkData PackageSegment | Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp (行 7325) |

---

## 版本差异

**UE4 Cooked vs UE5 Cooked：**
- UE4：主要使用 Pak 容器格式
- UE5：引入 IoStore 容器格式，Pak 作为兼容支持

**无版本属性序列化引入时机：**
- UE4.7+ 开始支持 PKG_UnversionedProperties
- UE5 默认 Cooked 包使用无版本属性序列化

**IoStore 格式引入（UE5）：**
- UE5.0 引入 IoStore 作为主要容器格式
- 提供更高效的数据访问和分区支持
- 使用 Perfect Hash 优化目录索引查询

---

## 交叉引用

- 文件头结构见 [package-summary.md](../package-summary.md)
- 加载流程见 [serialization/linker-load.md](../serialization/linker-load.md)
- IoStore 格式见 [cooked/iostore.md](iostore.md)
- Pak 格式见 [cooked/pak.md](pak.md)