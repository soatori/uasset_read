# Cooked vs Uncooked 格式对比

## 概述

**Cooked 格式定义：** 用于游戏发布的打包数据格式，经过 Cooking 处理，去除编辑器专用数据，优化加载性能。

**Uncooked 格式定义：** 编辑器中的原始资产格式，保留完整的编辑器数据和元信息。

**核心区别：** Cooked 格式去除编辑器专用数据、优化数据组织、使用更高效的序列化方式，以提高加载性能和减少包大小。

---

## 包标志定义

| 标志 | 值 | 说明 |
|------|-----|------|
| PKG_None | 0x00000000 | 无标志 |
| PKG_NewlyCreated | 0x00000001 | 新创建的包，尚未保存。仅在编辑器中。 |
| PKG_ClientOptional | 0x00000002 | 对客户端来说纯粹是可选的。 |
| PKG_ServerSideOnly | 0x00000004 | 仅在服务器端需要。 |
| PKG_CompiledIn | 0x00000010 | 此包来自"编译入"的类。 |
| PKG_ForDiffing | 0x00000020 | 此包仅用于比较目的加载。 |
| PKG_EditorOnly | 0x00000040 | 这是仅编辑器使用的包（如编辑器模块脚本包）。 |
| PKG_Developer | 0x00000080 | 开发者模块。 |
| PKG_UncookedOnly | 0x00000100 | 仅在未烘焙构建中加载。这类包在烘焙构建中不可用。 |
| PKG_Cooked | 0x00000200 | 包已 Cooked。加载时设置 IsLoadingFromCookedPackage 状态。 |
| PKG_ContainsNoAsset | 0x00000400 | 包不包含任何资产对象（尽管资产标签可能存在）。 |
| PKG_NotExternallyReferenceable | 0x00000800 | 此包中的对象不能在不同插件或挂载点中被引用（如 /Game -> /Engine）。 |
| PKG_AccessSpecifierEpicInternal | 0x00001000 | 此包中的对象只能被 Epic 引用。 |
| PKG_UnversionedProperties | 0x00002000 | 使用无版本属性序列化。跳过属性标签（FPropertyTag），直接序列化属性值。 |
| PKG_ContainsMapData | 0x00004000 | 包含地图数据（仅被单个 ULevel 引用的 UObject），但存储在不同包中。 |
| PKG_IsSaving | 0x00008000 | 在包保存期间临时设置。 |
| PKG_Compiling | 0x00010000 | 包当前正在编译。 |
| PKG_ContainsMap | 0x00020000 | 如果包包含 ULevel/UWorld 对象则设置。 |
| PKG_RequiresLocalizationGather | 0x00040000 | 如果包包含需要本地化收集的数据则设置。 |
| PKG_LoadUncooked | 0x00080000 | 此包必须从 IoStore/ZenStore 以未烘焙状态加载（仅在烹饪时设置）。 |
| PKG_PlayInEditor | 0x00100000 | 如果包是为 PIE 创建则设置。 |
| PKG_ContainsScript | 0x00200000 | 包允许包含 UClass 对象。 |
| PKG_DisallowExport | 0x00400000 | 编辑器不应导出此包中的资产。 |
| PKG_CookGenerated | 0x08000000 | 此包由烹饪器生成，不存在于 WorkspaceDomain 中。 |
| PKG_DynamicImports | 0x10000000 | 此包应在运行时从其导出中解析动态导入。 |
| PKG_RuntimeGenerated | 0x20000000 | 此包包含运行时生成的元素，可能不遵循标准加载顺序规则。 |
| PKG_ReloadingForCooker | 0x40000000 | 此包正在烹饪器中重新加载，尝试避免获取我们永远不需要的数据。不会保存此包。 |
| PKG_FilterEditorOnly | 0x80000000 | 已过滤编辑器数据。Cooking 过程中过滤了编辑器专用内容。 |

**与 Cooked 相关的核心标志说明：**
- PKG_Cooked（0x00000200）：标识包已完成 Cooking，加载路径使用 Cooked 专用逻辑
- PKG_FilterEditorOnly（0x80000000）：标识编辑器数据已过滤，Cooked 构建中跳过这些内容
- PKG_UnversionedProperties（0x00002000）：启用无版本属性序列化，大幅提升加载性能
- PKG_UncookedOnly（0x00000100）：用于仅编辑器使用的包，在 Cooked 构建中不加载

**瞬态标志（序列化到 PackageFileSummary 时会被清除）：**
`PKG_TransientFlags = PKG_NewlyCreated | PKG_IsSaving | PKG_ReloadingForCooker`

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

**Cooked 加载特殊处理：**
- BulkData PackageSegment：Cooked 包使用 `EPackageSegment::Exports`，Uncooked 使用 `EPackageSegment::Header`
- 偏移调整：Cooked 包的 BulkData 偏移需要减去 Header 大小
- 异步加载优化：Cooked 数据可使用 FAsyncArchive 加载器

---

## Cooked 数据拆分

Cooked 包将数据拆分为多个 FIoChunkId：

| ChunkType | 值 | 内容 |
|-----------|-----|------|
| Invalid | 0 | 无效类型 |
| ExportBundleData | 1 | 导出数据（主 .uasset 数据） |
| BulkData | 2 | BulkData 数据块 |
| OptionalBulkData | 3 | 可选 BulkData（如高清纹理） |
| MemoryMappedBulkData | 4 | 内存映射 BulkData |
| ScriptObjects | 5 | 脚本对象数据 |
| ContainerHeader | 6 | 容器头部 |
| ExternalFile | 7 | 外部文件 |
| ShaderCodeLibrary | 8 | Shader 代码库 |
| ShaderCode | 9 | Shader 代码 |
| PackageStoreEntry | 10 | Package Store 条目 |
| DerivedData | 11 | 派生数据 |
| EditorDerivedData | 12 | 编辑器派生数据 |
| PackageResource | 13 | Package 资源 |

**源码定义：** `enum class EIoChunkType : uint8`，位于 `Runtime/Core/Public/IO/IoChunkId.h`

---

## 源码引用

| 结构/逻辑 | 文件路径 |
|----------|----------|
| PKG 标志定义 | Runtime/CoreUObject/Public/UObject/ObjectMacros.h |
| Cooked 检测逻辑 | Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp |
| EIoChunkType 枚举 | Runtime/Core/Public/IO/IoChunkId.h |
| FIoChunkId 结构 | Runtime/Core/Public/IO/IoChunkId.h |
| CreateIoChunkId / CreateBulkDataIoChunkId | Runtime/Core/Public/IO/IoChunkId.h |
| FPackageStoreEntry | Runtime/CoreUObject/Public/Serialization/PackageStore.h |
| BulkData PackageSegment | Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp |

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
