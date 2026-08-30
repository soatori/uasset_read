# Unreal Engine UAsset 文件格式深度分析报告

> 基于 Unreal Engine 源码分析  
> 分析日期: 2026-08-26  
> 源码路径: `<UnrealEngine source root>`（分析者本地 checkout，非仓库内容）

---

## 目录

1. [UAsset 文件概述](#1-uasset-文件概述)
2. [两种主要格式](#2-两种主要格式)
3. [经典格式文件布局 (FPackageFileSummary)](#3-经典格式文件布局)
4. [Zen/Cooked 格式文件布局 (FZenPackageSummary)](#4-zencooked-格式文件布局)
5. [核心数据结构详解](#5-核心数据结构详解)
6. [缩略图存储格式](#6-缩略图-thumbnail-存储格式)
7. [Blueprint 缩略图预览代码](#7-blueprint-缩略图预览代码)
8. [IoStore 格式 (UE5 新格式)](#8-iostore-格式)
9. [Bulk Data 格式](#9-bulk-data-格式)
10. [创建 UAsset 解析器的输出建议](#10-创建-uasset-解析器的输出建议)
11. [关键源文件参考](#11-关键源文件参考)

---

## 1. UAsset 文件概述

UAsset 是 Unreal Engine 的核心资产文件格式，本质上是一个序列化的 UObject 包（`UPackage`）。它采用**二进制格式**存储，包含对象的序列化数据、依赖关系、名称表、缩略图等多种信息。

### 文件魔数 (Magic Number)

```cpp
#define PACKAGE_FILE_TAG 0x9E2A83C1
```

- 位于文件头部第一个字段
- 用于验证是否为有效的 UE 包文件
- 在 `PackageTrailer` 页脚中也包含此标记用于验证

---

## 2. 两种主要格式

Unreal Engine 有两种主要的 UAsset 格式：

| 格式 | 头部结构 | 用途 |
|------|---------|------|
| **经典格式 (Classic)** | `FPackageFileSummary` | Editor/未Cook包 |
| **Zen/Cooked 格式** | `FZenPackageSummary` | Cooked包（运行时） |

此外，UE5 引入了 **IoStore** 格式作为替代的容器格式。

---

## 3. 经典格式文件布局

> 源文件: `Engine/Source/Runtime/CoreUObject/Public/UObject/PackageFileSummary.h`

### 3.1 文件结构概览

```
┌─────────────────────────────────────────────────────────┐
│                    FPackageFileSummary                    │
│                    (文件头/目录)                          │
├─────────────────────────────────────────────────────────┤
│                    CustomVersionContainer                 │
│                    (自定义版本信息)                        │
├─────────────────────────────────────────────────────────┤
│                    Name Table                             │
│                    (名称表)                               │
├─────────────────────────────────────────────────────────┤
│                    Import Table                           │
│                    (导入表)                               │
├─────────────────────────────────────────────────────────┤
│                    Export Table                           │
│                    (导出表)                               │
├─────────────────────────────────────────────────────────┤
│                    Export Data                            │
│                    (导出数据 - UObject序列化数据)          │
├─────────────────────────────────────────────────────────┤
│                    Asset Registry                         │
│                    (资产注册表标签)                        │
├─────────────────────────────────────────────────────────┤
│                    Thumbnail Table                        │
│                    (缩略图表)                             │
├─────────────────────────────────────────────────────────┤
│                    Bulk Data                              │
│                    (批量数据)                             │
└─────────────────────────────────────────────────────────┘
```

### 3.2 FPackageFileSummary 字段详解

```cpp
struct FPackageFileSummary
{
    // === 基础信息 ===
    int32       Tag;                    // 魔数 0x9E2A83C1
    FPackageFileVersion FileVersionUE;  // UE文件版本
    int32       FileVersionLicenseeUE;  // Licensee版本
    FCustomVersionContainer CustomVersionContainer; // 自定义版本容器
    uint32      PackageFlags;           // 包标志

    // === 头部大小 ===
    int32       TotalHeaderSize;        // 需要读取的总头部大小

    // === 包名 ===
    FString     PackageName;            // 包名称

    // === 名称表 ===
    int32       NameCount;              // 名称数量
    int32       NameOffset;             // 名称表文件偏移

    // === Soft Object Paths ===
    int32       SoftObjectPathsCount;   // SoftObjectPath引用数量
    int32       SoftObjectPathsOffset;  // SoftObjectPath列表偏移

    // === 本地化 ===
    FString     LocalizationId;         // 本地化ID

    // === 可收集文本数据 ===
    int32       GatherableTextDataCount;
    int32       GatherableTextDataOffset;

    // === 元数据 ===
    int32       MetaDataOffset;         // 元数据偏移

    // === 导出表 ===
    int32       ExportCount;            // 导出对象数量
    int32       ExportOffset;           // 导出表偏移

    // === 导入表 ===
    int32       ImportCount;            // 导入对象数量
    int32       ImportOffset;           // 导入表偏移

    // === Cell导入导出表 (UE5) ===
    int32       CellExportCount;
    int32       CellExportOffset;
    int32       CellImportCount;
    int32       CellImportOffset;

    // === 依赖关系 ===
    int32       DependsOffset;          // 依赖映射偏移

    // === 软包引用 ===
    int32       SoftPackageReferencesCount;
    int32       SoftPackageReferencesOffset;

    // === 可搜索名称 ===
    int32       SearchableNamesOffset;

    // === 缩略图表 ===
    int32       ThumbnailTableOffset;   // 缩略图表偏移

    // === 导入类型层次结构 ===
    int32       ImportTypeHierarchiesCount;
    int32       ImportTypeHierarchiesOffset;

    // === 哈希 ===
    FIoHash     SavedHash;              // 文件保存时的哈希

    // === 持久化GUID (EditorOnly) ===
    FGuid       PersistentGuid;

    // === 版本历史 ===
    TArray<FGenerationInfo> Generations;

    // === 引擎版本 ===
    FEngineVersion SavedByEngineVersion;
    FEngineVersion CompatibleWithEngineVersion;

    // === 压缩 ===
    uint32      CompressionFlags;

    // === 来源 ===
    uint32      PackageSource;

    // === 无版本标志 ===
    bool        bUnversioned;

    // === 资产注册表 ===
    int32       AssetRegistryDataOffset;

    // === Bulk Data ===
    int64       BulkDataStartOffset;

    // === 世界瓦片信息 ===
    int32       WorldTileInfoDataOffset;

    // === 流式安装ChunkID ===
    TArray<int32> ChunkIDs;

    // === 预加载依赖 ===
    int32       PreloadDependencyCount;
    int32       PreloadDependencyOffset;

    // === 名称引用 ===
    int32       NamesReferencedFromExportDataCount;

    // === Payload TOC ===
    int64       PayloadTocOffset;

    // === 数据资源 ===
    int32       DataResourceOffset;
};
```

---

## 4. Zen/Cooked 格式文件布局

> 源文件: `Engine/Source/Runtime/CoreUObject/Public/Serialization/AsyncLoading2.h`

### 4.1 文件结构概览

```
┌─────────────────────────────────────────────────────────┐
│                    FZenPackageSummary                     │
│                    (Zen格式头部)                          │
├─────────────────────────────────────────────────────────┤
│                    VersioningInfo (可选)                  │
├─────────────────────────────────────────────────────────┤
│                    NameMap                                │
│                    (FMappedName 映射表)                   │
├─────────────────────────────────────────────────────────┤
│                    ImportedPublicExportHashes             │
│                    (跨包导入公共导出哈希)                  │
├─────────────────────────────────────────────────────────┤
│                    ImportMap                              │
│                    (FPackageObjectIndex 数组)             │
├─────────────────────────────────────────────────────────┤
│                    ExportMap                              │
│                    (FExportMapEntry 数组)                 │
├─────────────────────────────────────────────────────────┤
│                    ExportBundleEntries                    │
│                    (FExportBundleEntry - 序列化顺序)      │
├─────────────────────────────────────────────────────────┤
│                    DependencyBundleHeaders/Entries        │
│                    (依赖信息)                             │
├─────────────────────────────────────────────────────────┤
│                    Export Data                            │
│                    (序列化的 UObject 数据)                │
└─────────────────────────────────────────────────────────┘
```

### 4.2 FZenPackageSummary

```cpp
struct FZenPackageSummary
{
    uint32 bHasVersioningInfo;          // 是否有版本信息
    uint32 HeaderSize;                  // 头部大小
    FMappedName Name;                   // 包名
    uint32 PackageFlags;                // 包标志
    uint32 _Unused;                     // 未使用 (原 CookedHeaderSize)
    int32 ImportedPublicExportHashesOffset; // 导入公共导出哈希偏移
    int32 ImportMapOffset;              // 导入映射偏移
    int32 ExportMapOffset;              // 导出映射偏移
    int32 ExportBundleEntriesOffset;    // 导出包条目偏移
    int32 DependencyBundleHeadersOffset;// 依赖包头偏移
    int32 DependencyBundleEntriesOffset;// 依赖包条目偏移
    int32 ImportedPackageNamesOffset;   // 导入包名偏移
};
```

### 4.3 FZenPackageHeader (运行时头部视图)

> 源文件: `Engine/Source/Runtime/CoreUObject/Internal/Serialization/ZenPackageHeader.h`

```cpp
struct FZenPackageHeader
{
    uint32 ExportCount = 0;
    TOptional<FZenPackageVersioningInfo> VersioningInfo;
    FNameMap NameMap;
    FName PackageName;

    const FZenPackageSummary* PackageSummary = nullptr;
    TArrayView<const uint64> ImportedPublicExportHashes;
    TArrayView<const FPackageObjectIndex> ImportMap;
    TArrayView<const FExportMapEntry> ExportMap;
    TArrayView<const FPackageObjectIndex> CellImportMap;      // UE5 Cell导入映射
    TArrayView<const FCellExportMapEntry> CellExportMap;      // UE5 Cell导出映射
    TArrayView<const FBulkDataMapEntry> BulkDataMap;          // Bulk Data映射
    TArrayView<const FExportBundleEntry> ExportBundleEntries;
    TArrayView<const FDependencyBundleHeader> DependencyBundleHeaders;
    TArrayView<const FDependencyBundleEntry> DependencyBundleEntries;
    TArray<FName> ImportedPackageNames;
};
```

### 4.4 Zen 版本枚举

```cpp
enum class EZenPackageVersion : uint32
{
    Initial,                    // 初始版本
    DataResourceTable,          // 数据资源表
    ImportedPackageNames,       // 导入包名
    ExportDependencies,         // 导出依赖 (最新)
};
```

---

## 5. 核心数据结构详解

### 5.1 FObjectExport (导出对象结构)

> 源文件: `Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectResource.h`

```cpp
struct FObjectExport : public FObjectResource
{
    // === 序列化字段 ===
    FPackageIndex   ClassIndex;              // 类索引
    FPackageIndex   ThisIndex;              // 导出映射中的位置 (非序列化)
    FPackageIndex   SuperIndex;             // 父类索引
    FPackageIndex   TemplateIndex;          // 模板/原型索引
    EObjectFlags    ObjectFlags;            // 对象标志
    int64           SerialSize;             // 序列化大小 (字节)
    int64           SerialOffset;           // 序列化偏移 (文件位置)
    int64           ScriptSerializationStartOffset;  // 脚本序列化起始偏移
    int64           ScriptSerializationEndOffset;    // 脚本序列化结束偏移

    // === 运行时字段 (非序列化) ===
    UObject*        Object;                 // 指向实际对象
    int32           HashNext;               // 哈希表下一项

    // === 标志 ===
    bool            bForcedExport:1;        // 强制导出
    bool            bNotForClient:1;        // 客户端不加载
    bool            bNotForServer:1;        // 服务器不加载
    bool            bNotAlwaysLoadedForEditorGame:1; // 编辑器游戏不总是加载
    bool            bIsAsset:1;             // 是否为资产对象
    bool            bIsInheritedInstance:1; // 是否为继承实例
    bool            bGeneratePublicHash:1;  // 是否生成公共哈希
    bool            bExportLoadFailed:1;    // 导出加载失败
    bool            bWasFiltered:1;         // 已被过滤

    // === 包信息 ===
    uint32          PackageFlags;           // 包标志 (顶层包时有效)

    // === 依赖索引 ===
    int32 FirstExportDependency;            // 第一个导出依赖
    int32 SerializationBeforeSerializationDependencies;
    int32 CreateBeforeSerializationDependencies;
    int32 SerializationBeforeCreateDependencies;
    int32 CreateBeforeCreateDependencies;
};
```

### 5.2 FObjectImport (导入对象结构)

> 源文件: `Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectResource.h`

```cpp
struct FObjectImport : public FObjectResource
{
    // === 序列化字段 ===
    FName           ClassPackage;   // 包含类的包名
    FName           ClassName;      // 类名
    FName           PackageName;    // 此导入所属的包名
    int32           SourceIndex;    // 源链接器导出映射表中的索引 (运行时)
    bool            bImportOptional;// 是否可选导入

    // === 运行时字段 (非序列化) ===
    UObject*        XObject;        // 指向实际对象
    FLinkerLoad*    SourceLinker;   // 源链接器

    // === 辅助方法 ===
    bool HasPackageName() const;
    FName GetPackageName() const;
    void SetPackageName(FName InPackageName);
};
```

### 5.3 FExportMapEntry (Zen格式导出表条目)

> 源文件: `Engine/Source/Runtime/CoreUObject/Public/Serialization/AsyncLoading2.h`

```cpp
struct FExportMapEntry
{
    uint64 CookedSerialOffset = 0;      // 从导出数据开始的偏移
                                         // (HeaderSize + CookedSerialOffset = 实际偏移)
    uint64 CookedSerialSize = 0;        // 序列化数据大小
    FMappedName ObjectName;             // 对象名称
    FPackageObjectIndex OuterIndex;     // 外部对象索引
    FPackageObjectIndex ClassIndex;     // 类索引
    FPackageObjectIndex SuperIndex;     // 父类索引
    FPackageObjectIndex TemplateIndex;  // 模板对象索引
    uint64 PublicExportHash = 0;        // 公共导出哈希 (跨包引用)
    EObjectFlags ObjectFlags = EObjectFlags::RF_NoFlags;
    EExportFilterFlags FilterFlags = EExportFilterFlags::None;
    uint8 Pad[3] = {};                  // 填充字节
};
```

### 5.4 FPackageObjectIndex (包对象索引)

> 源文件: `Engine/Source/Runtime/CoreUObject/Public/Serialization/AsyncLoading2.h`

```cpp
class FPackageObjectIndex
{
    enum EType
    {
        Export,         // 导出对象
        ScriptImport,   // 脚本导入
        PackageImport,  // 包导入
        Null,           // 空
        TypeCount = Null,
    };

    uint64 TypeAndId;   // 2位类型 + 62位索引/哈希

    static uint64 GenerateImportHashFromObjectPath(const FStringView& ObjectPath);
    // ...
};
```

### 5.5 FExportBundleEntry (导出包条目 - 控制序列化顺序)

> 源文件: `Engine/Source/Runtime/CoreUObject/Public/Serialization/AsyncLoading2.h`

```cpp
struct FExportBundleEntry
{
    enum EExportCommandType
    {
        ExportCommandType_Create,        // 创建对象
        ExportCommandType_Serialize,     // 序列化对象
        ExportCommandType_Count          // 计数 (值为2)
    };

    uint32 LocalExportIndex;    // 本地导出索引
    uint32 CommandType;         // 命令类型
};
```

### 5.6 FDependencyBundleHeader (依赖包头)

> 源文件: `Engine/Source/Runtime/CoreUObject/Public/Serialization/AsyncLoading2.h`

```cpp
struct FDependencyBundleHeader
{
    int32 FirstEntryIndex;      // 第一个条目索引
    uint32 EntryCount[FExportBundleEntry::ExportCommandType_Count]
                     [FExportBundleEntry::ExportCommandType_Count];
    // EntryCount[Create][Serialize] = 创建/序列化依赖计数
};
```

### 5.7 FDependencyBundleEntry (依赖包条目)

```cpp
struct FDependencyBundleEntry
{
    FPackageIndex LocalImportOrExportIndex;  // 本地导入或导出索引
};
```

### 5.8 FScriptObjectEntry (脚本对象条目)

> 源文件: `Engine/Source/Runtime/CoreUObject/Public/Serialization/AsyncLoading2.h`

```cpp
struct FScriptObjectEntry
{
    union
    {
        FMappedName Mapped;
        FMinimalName ObjectName;
    };
    FPackageObjectIndex GlobalIndex;
    FPackageObjectIndex OuterIndex;
    FPackageObjectIndex CDOClassIndex;
};
```

### 5.9 FCellExportMapEntry (UE5 Cell导出映射)

```cpp
struct FCellExportMapEntry
{
    uint64 CookedSerialOffset = 0;
    uint64 CookedSerialLayoutSize = 0;
    uint64 CookedSerialSize = 0;
    FMappedName CppClassInfo;
    uint64 PublicExportHash = 0;
};
```

### 5.10 FBulkDataMapEntry (Bulk Data映射)

```cpp
struct FBulkDataMapEntry
{
    int64 SerialOffset = 0;
    int64 DuplicateSerialOffset = 0;
    int64 SerialSize = 0;
    uint32 Flags = 0;
    FBulkDataCookedIndex CookedIndex;
    uint8 Pad[3] = { 0, 0, 0 };
};
```

### 5.11 FObjectDataResource (对象数据资源)

> 源文件: `Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectResource.h`

```cpp
struct FObjectDataResource
{
    enum class EVersion : uint32
    {
        Invalid,
        Initial,
        AddedCookedIndex,
        LatestPlusOne,
    };

    // 数据资源标志
    enum class EObjectDataResourceFlags : uint32
    {
        None                    = 0,
        Inline                  = (1 << 0),  // 内联
        Streaming               = (1 << 1),  // 流式加载
        Optional                = (1 << 2),  // 可选
        Duplicate               = (1 << 3),  // 重复
        MemoryMapped            = (1 << 4),  // 内存映射
        DerivedDataReference    = (1 << 5),  // 派生数据引用
    };
};
```

---

## 6. 缩略图 (Thumbnail) 存储格式

> 源文件: `Engine/Source/Runtime/Core/Public/Misc/ObjectThumbnail.h`

### 6.1 FObjectThumbnail (缩略图数据)

```cpp
class FObjectThumbnail
{
public:
    // === 序列化字段 ===
    int32 ImageWidth;                  // 图像宽度
    int32 ImageHeight;                 // 图像高度
    TArray<uint8> CompressedImageData; // 压缩后的图像数据 (PNG/JPEG)

    // === 运行时字段 ===
    TArray<uint8> ImageData;           // 原始图像数据 (BGRA8-sRGB)
    bool bIsDirty;                     // 是否需要重新生成
    bool bLoadedFromDisk;              // 是否从磁盘加载
    bool bIsJPEG;                      // 压缩格式是否为JPEG
    bool bCreatedAfterCustomThumbForSharedTypesEnabled;

    // === 方法 ===
    int32 GetImageWidth() const;
    int32 GetImageHeight() const;
    int32 GetCompressedDataSize() const;
    void SetImageSize(int32 InWidth, int32 InHeight);
    bool IsEmpty() const;              // 宽度或高度为0
    bool HasValidImageData() const;    // 有压缩或未压缩数据
    const TArray<uint8>& GetUncompressedImageData() const;
    FThumbnailCompressionInterface* GetCompressor() const;
    void CompressImageData();
    void DecompressImageData();
    void Serialize(FArchive& Ar);
    void Serialize(FStructuredArchive::FSlot Slot);
};
```

### 6.2 FObjectFullNameAndThumbnail (缩略图表条目)

```cpp
struct FObjectFullNameAndThumbnail
{
    FName ObjectFullName;              // 对象完整名称
    const FObjectThumbnail* ObjectThumbnail; // 缩略图数据指针
    int32 FileOffset;                  // 文件中的偏移

    // 序列化: Ar << ObjectFullName << FileOffset
};
```

### 6.3 FThumbnailMap (缩略图映射)

```cpp
typedef TMap<FName, FObjectThumbnail> FThumbnailMap;
```

### 6.4 缩略图表在文件中的存储位置

- `ThumbnailTableOffset` 字段指向缩略图表在文件中的位置
- 表结构:
  1. **索引数组**: 对象类名 + 对象路径（不含包名） + 文件偏移
  2. **图像数据**: `FObjectThumbnail` 序列化数据

### 6.5 压缩接口

```cpp
class FThumbnailCompressionInterface
{
public:
    virtual bool CompressImage(const TArray<uint8>& InUncompressedData,
                               const int32 InWidth, const int32 InHeight,
                               TArray<uint8>& OutCompressedData) = 0;
    virtual bool DecompressImage(const TArray<uint8>& InCompressedData,
                                 const int32 InWidth, const int32 InHeight,
                                 TArray<uint8>& OutUncompressedData) = 0;
    virtual FName GetThumbnailCompressorName() const = 0;
    virtual bool IsLosslessCompression() const = 0;
    virtual FStringView GetMimeType() const = 0;
};
```

---

## 7. Blueprint 缩略图预览代码

### 7.1 UThumbnailRenderer (缩略图渲染器基类)

> 源文件: `Engine/Source/Editor/UnrealEd/Classes/ThumbnailRendering/ThumbnailRenderer.h`

```cpp
UCLASS(abstract, MinimalAPI)
class UThumbnailRenderer : public UObject
{
    // 检查是否可以可视化资产
    virtual bool CanVisualizeAsset(UObject* Object) { return true; }

    // 获取缩略图大小
    virtual void GetThumbnailSize(UObject* Object, float Zoom,
                                   uint32& OutWidth, uint32& OutHeight) const;

    // 绘制缩略图
    virtual void Draw(UObject* Object, int32 X, int32 Y,
                      uint32 Width, uint32 Height,
                      FRenderTarget* Viewport, FCanvas* Canvas,
                      bool bAdditionalViewFamily);

    // 获取渲染频率
    virtual EThumbnailRenderFrequency GetThumbnailRenderFrequency(UObject* Object) const;

protected:
    static void RenderViewFamily(FCanvas* Canvas, FSceneViewFamily* ViewFamily, FSceneView* View);
    static FGameTime GetTime();
};
```

### 7.2 UBlueprintThumbnailRenderer (蓝图缩略图渲染器)

> 源文件: `Engine/Source/Editor/UnrealEd/Classes/ThumbnailRendering/BlueprintThumbnailRenderer.h`

```cpp
UCLASS(config=Editor, MinimalAPI)
class UBlueprintThumbnailRenderer : public UDefaultSizedThumbnailRenderer
{
    // 检查是否可以可视化
    virtual bool CanVisualizeAsset(UObject* Object) override;
    // 条件: 必须是 Actor 类型的蓝图，且有可渲染组件

    // 绘制缩略图
    virtual void Draw(UObject* Object, int32 X, int32 Y,
                      uint32 Width, uint32 Height,
                      FRenderTarget* RenderTarget, FCanvas* Canvas,
                      bool bAdditionalViewFamily) override;

    // 通知蓝图已更改
    void BlueprintChanged(UBlueprint* Blueprint);

private:
    TOptional<FBlueprintThumbnailScene> ThumbnailScene;
};
```

### 7.3 Blueprint 缩略图渲染流程

```
1. CanVisualizeAsset()
   ├── 检查是否为 UBlueprint
   ├── 检查 GeneratedClass 是否存在
   ├── 检查 GeneratedClass 是否为 AActor 子类
   └── 遍历组件，检查是否有可渲染组件

2. Draw()
   ├── 验证蓝图状态 (已生成、未编译、非瞬态)
   ├── 创建 FBlueprintThumbnailScene (如不存在)
   ├── ThumbnailScene->SetBlueprint(Blueprint)
   ├── 创建 FSceneViewFamilyContext
   ├── 配置渲染标志 (禁用高级特性、运动模糊)
   └── RenderViewFamily(Canvas, &ViewFamily, View)
```

### 7.4 FThumbnailPreviewScene (缩略图预览场景)

> 源文件: `Engine/Source/Editor/UnrealEd/Public/ThumbnailHelpers.h`

```cpp
class FThumbnailPreviewScene : public FPreviewScene, public FTickableEditorObject
{
    struct FConstructionValues
    {
        uint32 bCreateSkySphere : 1;           // 创建天空球
        uint32 bDefaultLightingThumbnailScene : 1; // 默认灯光
        FRotator LightRotation2;                // 灯光2旋转
        float LightBrightness2;                 // 灯光2亮度
        FRotator LightRotation3;                // 灯光3旋转
        float LightBrightness3;                 // 灯光3亮度
        uint32 bSetSkyCubeMap : 1;             // 设置天空立方体贴图
        uint32 bCreateFloorPlane : 1;          // 创建地面平面
    };

    // 创建视图
    FSceneView* CreateView(FSceneViewFamily* ViewFamily,
                           int32 X, int32 Y, uint32 SizeX, uint32 SizeY) const;

    // 获取视图矩阵参数 (子类实现)
    virtual void GetViewMatrixParameters(const float InFOVDegrees,
                                         FVector& OutOrigin,
                                         float& OutOrbitPitch,
                                         float& OutOrbitYaw,
                                         float& OutOrbitZoom) const = 0;
};
```

### 7.5 FBlueprintThumbnailScene

> 源文件: `Engine/Source/Editor/UnrealEd/Public/ThumbnailHelpers.h`

```cpp
class FBlueprintThumbnailScene : public FClassActorThumbnailScene
{
public:
    FBlueprintThumbnailScene();

    // 设置要渲染的蓝图
    void SetBlueprint(class UBlueprint* Blueprint);

    // 刷新蓝图组件
    void BlueprintChanged(class UBlueprint* Blueprint);

    // 获取当前蓝图
    TWeakObjectPtr<class UBlueprint> GetCurrentBlueprint() const;

protected:
    // 获取场景缩略图信息
    virtual USceneThumbnailInfo* GetSceneThumbnailInfo(const float TargetDistance) const override;

private:
    TWeakObjectPtr<class UBlueprint> CurrentBlueprint;
};
```

### 7.6 缩略图管理器

> 源文件: `Engine/Source/Editor/UnrealEd/Classes/ThumbnailRendering/ThumbnailManager.h`

```cpp
UCLASS(config=Editor)
class UThumbnailRenderer : public UObject
{
    // 注册自定义渲染器
    virtual void RegisterCustomRenderer(UClass* Class,
                                        TSubclassOf<UThumbnailRenderer> RendererClass);

    // 获取渲染信息
    FThumbnailRenderingInfo* GetRenderingInfo(UObject* Object);

    // 获取共享缩略图池
    TSharedPtr<FAssetThumbnailPool> GetSharedThumbnailPool() const;

    // 静态获取实例
    static UThumbnailManager& Get();
    static UThumbnailManager* TryGet();
};
```

### 7.7 FThumbnailRenderingInfo (缩略图渲染信息)

```cpp
USTRUCT()
struct FThumbnailRenderingInfo
{
    FString ClassNeedingThumbnailName;    // 需要缩略图的类名
    TSubclassOf<UObject> ClassNeedingThumbnail; // 需要缩略图的类
    FString RendererClassName;            // 渲染器类名
    TObjectPtr<UThumbnailRenderer> Renderer; // 渲染器实例
    bool bUseClassDefaultObject = false;  // 是否使用CDO (仅蓝图)
};
```

### 7.8 相关缩略图渲染器类

| 类名 | 用途 |
|------|------|
| `UBlueprintThumbnailRenderer` | 蓝图缩略图 |
| `UClassThumbnailRenderer` | 类缩略图 |
| `UAnimBlueprintThumbnailRenderer` | 动画蓝图缩略图 |
| `UStaticMeshThumbnailRenderer` | 静态网格缩略图 |
| `USkeletalMeshThumbnailRenderer` | 骨骼网格缩略图 |
| `UTextureThumbnailRenderer` | 纹理缩略图 |
| `UMaterialInstanceThumbnailRenderer` | 材质实例缩略图 |
| `USoundWaveThumbnailRenderer` | 音频波形缩略图 |
| `UParticleSystemThumbnailRenderer` | 粒子系统缩略图 |
| `UWorldThumbnailRenderer` | 世界缩略图 |
| `UFontThumbnailRenderer` | 字体缩略图 |
| `USkeletonThumbnailRenderer` | 骨架缩略图 |
| `UPhysicsAssetThumbnailRenderer` | 物理资产缩略图 |
| `USlateBrushThumbnailRenderer` | Slate画刷缩略图 |
| `UAnimSequenceThumbnailRenderer` | 动画序列缩略图 |
| `UBlendSpaceThumbnailRenderer` | 混合空间缩略图 |
| `UMaterialFunctionThumbnailRenderer` | 材质函数缩略图 |
| `UVolumeTextureThumbnailRenderer` | 体积纹理缩略图 |
| `USubsurfaceProfileRenderer` | 次表面配置缩略图 |
| `USpecularProfileRenderer` | 镜面配置缩略图 |

---

## 8. IoStore 格式 (UE5 新格式)

> 源文件: `Engine/Source/Runtime/Core/Internal/IO/IoStore.h`

### 8.1 FIoStoreTocHeader

```cpp
struct FIoStoreTocHeader
{
    uint8 TocMagic[16];                    // "-==--==--==--==-"
    uint8 Version;                         // TOC版本
    uint32 TocEntryCount;                  // TOC条目数
    uint32 TocCompressedBlockEntryCount;   // 压缩块条目数
    uint32 CompressionMethodNameCount;     // 压缩方法名数量
    uint32 CompressionBlockSize;           // 压缩块大小
    uint32 DirectoryIndexSize;             // 目录索引大小
    uint32 PartitionCount;                 // 分区数量
    FIoContainerId ContainerId;            // 容器ID
    FGuid EncryptionKeyGuid;               // 加密密钥GUID
    EIoContainerFlags ContainerFlags;      // 容器标志
};
```

### 8.2 FIoStoreTocResource

```cpp
struct FIoStoreTocResource
{
    FIoStoreTocHeader Header;
    TArray<FIoChunkId> ChunkIds;                           // Chunk ID列表
    TArray<FIoOffsetAndLength> ChunkOffsetLengths;         // 偏移和长度
    TArray<FIoStoreTocCompressedBlockEntry> CompressionBlocks; // 压缩块
    TArray<FName> CompressionMethods;                      // 压缩方法
    TArray<uint8> DirectoryIndexBuffer;                    // 目录索引缓冲
    TArray<FIoStoreTocEntryMeta> ChunkMetas;               // Chunk元数据
};
```

---

## 9. Bulk Data 格式

> 源文件: `Engine/Source/Runtime/CoreUObject/Public/UObject/PackageTrailer.h`

### 9.1 FPackageTrailer 结构

```
┌─────────────────────────────────────────────────────────┐
│                       [Header]                           │
│  Tag              │ uint64    │ 与 FHeader::HeaderTag 匹配 │
│  Version          │ uint32    │ 版本号                     │
│  HeaderLength     │ uint32    │ 头部总大小 (字节)           │
│  PayloadsDataLength│ uint64   │ 负载数据总大小 (字节)       │
│  NumPayloads      │ int32     │ 负载数量                   │
│  LookupTableArray │ FLookupTableEntry[] │ 查找表数组        │
├─────────────────────────────────────────────────────────┤
│                    [Payload Data]                         │
│  Array            │ FCompressedBuffer │ 所有负载的二进制数据  │
├─────────────────────────────────────────────────────────┤
│                      [Footer]                            │
│  Tag              │ uint64    │ 与 FFooter::FooterTag 匹配 │
│  TrailerLength    │ uint64    │ 尾部总大小 (字节)           │
│  PackageTag       │ uint32    │ PACKAGE_FILE_TAG           │
└─────────────────────────────────────────────────────────┘
```

### 9.2 FLookupTableEntry (查找表条目)

每个条目约49字节:
- `FIoHash Identifier` - 负载哈希
- `int64 OffsetInFile` - 文件偏移
- `uint64 CompressedSize` - 压缩大小
- `uint64 RawSize` - 原始大小
- `EPayloadAccessMode AccessMode` - 访问模式 (Local/Referenced/Virtualized)

### 9.3 EPayloadStorageType

```cpp
enum class EPayloadStorageType : uint8
{
    Any,            // 所有负载
    Local,          // 本地存储在包尾部
    Referenced,     // 引用工作区域尾部的负载
    Virtualized     // 虚拟化后端存储
};
```

---

## 10. 创建 UAsset 解析器的输出建议

### 10.1 应输出的内容

| 内容类别 | 输出内容 | 格式建议 |
|---------|---------|---------|
| **文件头信息** | Magic Number, 版本号, 包标志, 总头大小 | 结构化 JSON/YAML |
| **包元数据** | 包名, LocalizationId, 引擎版本, PersistentGuid | 键值对 |
| **名称表** | 所有 FName 字符串 | 字符串数组 |
| **导入表** | 类包名, 类名, 包名, 源索引, 可选标志 | 对象数组 |
| **导出表** | 对象名, 类, 父类, 模板, 偏移, 大小, 标志 | 对象数组 |
| **导出数据** | 序列化的 UObject 数据 | Hex dump + 解析 |
| **依赖关系** | 包间依赖, 对象依赖图 | 图结构/邻接表 |
| **缩略图** | 图像数据 (PNG/JPEG) | 图像文件 (base64) |
| **Asset Registry** | 标签数据 | 嵌套键值对 |
| **Bulk Data** | 批量数据负载 | 二进制文件 |
| **Cell映射** (UE5) | Cell导入/导出映射 | 对象数组 |
| **数据资源** | 数据资源信息 | 对象数组 |

### 10.2 推荐输出格式 (JSON)

```json
{
  "format": "classic|zen",
  "header": {
    "magic": "0x9E2A83C1",
    "version": {
      "ue4": 522,
      "ue5": 1009,
      "licensee": 0
    },
    "packageName": "/Game/Path/To/Asset",
    "packageFlags": 0,
    "totalHeaderSize": 1234,
    "engineVersion": {
      "savedBy": "5.4.0",
      "compatibleWith": "5.4.0"
    },
    "compressionFlags": 0,
    "packageSource": 0,
    "bUnversioned": false,
    "persistentGuid": "00000000-0000-0000-0000-000000000000",
    "bulkDataStartOffset": 123456
  },
  "customVersions": [
    {
      "key": "0x00000000",
      "version": 1
    }
  ],
  "nameTable": [
    "ClassName",
    "PropertyName",
    "MyObject",
    "..."
  ],
  "imports": [
    {
      "index": 0,
      "classPackage": "/Script/Engine",
      "className": "StaticMesh",
      "packageName": "/Game/Meshes/MyMesh",
      "sourceIndex": 0,
      "bImportOptional": false
    }
  ],
  "exports": [
    {
      "index": 0,
      "name": "MyObject",
      "className": "Blueprint",
      "superClass": "Actor",
      "outerIndex": 0,
      "templateIndex": 0,
      "serialOffset": 5678,
      "serialSize": 456,
      "objectFlags": 0,
      "scriptSerializationStartOffset": 100,
      "scriptSerializationEndOffset": 400,
      "bForcedExport": false,
      "bNotForClient": false,
      "bNotForServer": false,
      "bIsAsset": true
    }
  ],
  "exportData": {
    "rawHex": "4E 89 A1 2C ...",
    "parsedProperties": [
      {
        "name": "StaticMeshComponent",
        "type": "ObjectProperty",
        "value": "/Game/Meshes/MyMesh.MyMesh"
      }
    ]
  },
  "dependencies": {
    "preloadDependencies": [0, 1, 2],
    "externalReadDependencies": []
  },
  "thumbnails": [
    {
      "objectFullName": "Blueprint /Game/Path/To/Asset.Asset",
      "width": 256,
      "height": 256,
      "imageFormat": "png",
      "imageData": "base64...",
      "fileOffset": 12345
    }
  ],
  "assetRegistry": {
    "tags": {
      "AssetImportData": "...",
      "ThumbnailInfo": "..."
    }
  },
  "bulkData": [
    {
      "identifier": "hash123...",
      "offset": 0,
      "compressedSize": 1024,
      "rawSize": 2048,
      "accessMode": "Local"
    }
  ],
  "cellExportMap": [],
  "cellImportMap": [],
  "dataResources": []
}
```

### 10.3 二进制解析伪代码

```python
class UAssetParser:
    def parse(self, filepath):
        with open(filepath, 'rb') as f:
            # 1. 读取魔数
            magic = read_uint32(f)
            if magic != 0x9E2A83C1:
                raise ValueError("Invalid UAsset file")

            # 2. 读取头部
            header = self.parse_header(f)

            # 3. 根据版本选择解析方式
            if header.version.ue5 >= SOME_ZEN_VERSION:
                return self.parse_zen(f, header)
            else:
                return self.parse_classic(f, header)

    def parse_classic(self, f, header):
        # 1. 名称表
        name_table = self.read_name_table(f, header.name_offset, header.name_count)

        # 2. 导入表
        imports = self.read_import_table(f, header.import_offset, header.import_count)

        # 3. 导出表
        exports = self.read_export_table(f, header.export_offset, header.export_count)

        # 4. 导出数据
        for export in exports:
            export.data = self.read_export_data(f, export.serial_offset, export.serial_size)

        # 5. 缩略图
        if header.thumbnail_table_offset > 0:
            thumbnails = self.read_thumbnails(f, header.thumbnail_table_offset)

        # 6. Asset Registry
        if header.asset_registry_data_offset > 0:
            registry = self.read_asset_registry(f, header.asset_registry_data_offset)

        # 7. Bulk Data
        if header.bulk_data_start_offset > 0:
            bulk_data = self.read_bulk_data(f, header.bulk_data_start_offset)

        return Package(header, name_table, imports, exports, thumbnails, registry, bulk_data)

    def parse_zen(self, f, header):
        # Zen格式使用偏移表直接定位各部分
        # 1. NameMap
        name_map = self.read_name_map(f, header.name_offset)

        # 2. ImportMap
        import_map = self.read_import_map(f, header.import_map_offset)

        # 3. ExportMap
        export_map = self.read_export_map(f, header.export_map_offset)

        # 4. ExportBundleEntries
        bundle_entries = self.read_export_bundle(f, header.export_bundle_offset)

        # 5. 依赖信息
        dependencies = self.read_dependencies(f, header.dependency_offset)

        # 6. 导出数据
        for entry in export_map:
            entry.data = self.read_export_data(f, entry.cooked_serial_offset, entry.cooked_serial_size)

        return ZenPackage(header, name_map, import_map, export_map, bundle_entries, dependencies)
```

---

## 11. 关键源文件参考

### 11.1 头部结构

| 文件路径 | 作用 |
|---------|------|
| `CoreUObject/Public/UObject/PackageFileSummary.h` | 经典格式头部结构 `FPackageFileSummary` |
| `CoreUObject/Public/Serialization/AsyncLoading2.h` | Zen格式结构 `FZenPackageSummary`, `FExportMapEntry` 等 |
| `CoreUObject/Internal/Serialization/ZenPackageHeader.h` | Zen头部视图 `FZenPackageHeader` |
| `CoreUObject/Public/UObject/ObjectResource.h` | 导入/导出表结构 `FObjectExport`, `FObjectImport` |

### 11.2 序列化/反序列化

| 文件路径 | 作用 |
|---------|------|
| `CoreUObject/Private/Serialization/AsyncLoading2.cpp` | Zen格式加载实现 |
| `CoreUObject/Private/Serialization/ZenPackageHeader.cpp` | Zen头部解析 |
| `CoreUObject/Private/UObject/LinkerLoad.cpp` | 经典格式加载 |
| `CoreUObject/Private/UObject/SavePackage2.cpp` | 保存实现 |
| `CoreUObject/Private/UObject/PackageFileSummary.cpp` | Summary序列化 |

### 11.3 缩略图

| 文件路径 | 作用 |
|---------|------|
| `Core/Public/Misc/ObjectThumbnail.h` | 缩略图数据结构 `FObjectThumbnail` |
| `CoreUObject/Public/UObject/Package.h` | `FThumbnailMap` 定义 |
| `Editor/UnrealEd/Classes/ThumbnailRendering/ThumbnailRenderer.h` | 缩略图渲染器基类 |
| `Editor/UnrealEd/Classes/ThumbnailRendering/ThumbnailManager.h` | 缩略图管理器 |
| `Editor/UnrealEd/Classes/ThumbnailRendering/BlueprintThumbnailRenderer.h` | 蓝图缩略图渲染器 |
| `Editor/UnrealEd/Public/ThumbnailHelpers.h` | 缩略图场景辅助类 |
| `Editor/UnrealEd/Private/ThumbnailRendering/BlueprintThumbnailRenderer.cpp` | 蓝图缩略图渲染实现 |

### 11.4 Bulk Data / IoStore

| 文件路径 | 作用 |
|---------|------|
| `CoreUObject/Public/UObject/PackageTrailer.h` | Bulk Data尾部 `FPackageTrailer` |
| `CoreUObject/Private/UObject/PackageTrailer.cpp` | 尾部实现 |
| `Core/Internal/IO/IoStore.h` | IoStore容器格式 |
| `Core/Private/IO/IoStore.cpp` | IoStore实现 |

### 11.5 资产注册表

| 文件路径 | 作用 |
|---------|------|
| `AssetRegistry/Public/AssetRegistry/AssetData.h` | 资产数据 |
| `CoreUObject/Private/UObject/SavePackage/SavePackageUtilities.cpp` | 保存工具 (缩略图、注册表) |

---

## 附录 A: 文件偏移计算

### 经典格式偏移计算

```
实际文件偏移 = 各表的 Offset 字段值
导出数据起始 = TotalHeaderSize
Bulk Data起始 = BulkDataStartOffset
```

### Zen格式偏移计算

```
导出数据实际偏移 = HeaderSize + ExportMapEntry.CookedSerialOffset
NameMap位置 = FZenPackageSummary.Name 字段 (FMappedName)
各表位置 = FZenPackageSummary 中对应的 Offset 字段
```

---

## 附录 B: 版本兼容性

### 最低可加载版本

```cpp
#define VER_UE4_OLDEST_LOADABLE_PACKAGE  // UE4最早可加载版本
```

### 版本检查

```cpp
bool IsFileVersionTooOld() const;  // 版本过旧
bool IsFileVersionTooNew() const;  // 版本过新
bool IsFileVersionValid() const;   // 版本有效
```

---

## 附录 C: 常用标志

### PackageFlags

```cpp
PKG_FilterEditorOnly  // 过辑器专用数据
PKG_NewlyCreated     // 新创建
PKG_IsSaving         // 正在保存
```

### EObjectFlags (部分)

```cpp
RF_NoFlags           // 无标志
RF_Public            // 公共对象
RF_Transient         // 瞬态对象
RF_MarkAsNative      // 原生对象
RF_MarkAsReachable   // 可达对象
```

### EExportFilterFlags

```cpp
ExportFilter_None           // 无过滤
ExportFilter_NotForClient   // 客户端不加载
ExportFilter_NotForServer   // 服务器不加载
```

---

> **报告完成**  
> 如有疑问，请参考源码中的具体实现。
