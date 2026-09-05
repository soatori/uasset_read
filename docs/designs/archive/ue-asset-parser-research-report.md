# Unreal Engine UAsset 通用解析器技术研究与系统设计报告

**文档性质：** 技术研究 / 架构设计 / 开发规范  
**目标范围：** Unreal Engine 4 / Unreal Engine 5 资产解析  
**建议首期支持：** UE4.27、UE5.0–UE5.8 架构兼容  
**核心目标：** Package 解析、UObject 反射解析、Typed Asset 深度解析、依赖分析、统一中间表示、资源转换  
**不纳入本报告参考：** `uasset_read`

---

# 1. 执行摘要

如果要开发一个真正通用的 Unreal `.uasset` 解析器，项目不应被定义为：

> “读取 `.uasset` 并转成 JSON 的程序”

而应该定义为：

> **Unreal Engine Package & Asset Analysis Framework**

其核心数据流建议为：

```text
Physical Storage
      ↓
Container Layer
Loose / Pak / IoStore
      ↓
Package Layer
Legacy Package / IoPackage
      ↓
Object Model
Name / Import / Export / ObjectRef
      ↓
Serialization
Tagged Property / Unversioned Property / Native Serialization
      ↓
UObject
      ↓
Typed Asset Handlers
Texture / Mesh / Animation / Blueprint / ...
      ↓
Canonical IR
      ↓
JSON / SQLite / Graph / GLTF / PNG / WAV / AI Context
```

整个系统最重要的设计原则有六条：

1. **以 Package 为核心，而不是以 `.uasset` 扩展名为核心。**
2. **以 UObject + Property 为通用基础，而不是逐资产类型硬编码。**
3. **以 VersionContext 管理版本差异，而不是遍布 `if UE5.x`。**
4. **以 IR 为内部标准，而不是直接把解析对象序列化为 JSON。**
5. **未知类型允许降级解析和 Raw Preservation，而不是整体失败。**
6. **解析、解码、转换、导出必须分层。**

Epic 当前仍将 `FPackageFileSummary` 定义为 Unreal Package 顶部的“table of contents”，其中保存 Name、Import、Export、依赖、BulkData、Asset Registry、Soft Reference 等区域的位置和数量。这意味着从官方模型本身看，正确抽象单位就应该是 **Package**。citeturn256387view0

---

# 2. 项目定位

## 2.1 建议项目定义

建议项目名称概念上定义为：

```text
Unreal Asset Parser
```

实际内部应覆盖：

```text
Unreal Package Parser
+
UObject Serialization Framework
+
Asset Type Framework
+
Asset Conversion Framework
```

即：

```text
Package
   ↓
Object
   ↓
Asset
```

三层模型。

---

# 3. 研究参考

## 3.1 Epic Unreal Engine 官方定义

这是最高优先级参考。

关键结构包括：

```text
FPackageFileSummary
FObjectImport
FObjectExport
FPackageIndex
FPropertyTag
FName
FBulkData
FPackageTrailer
FPackageStore
FPackageStoreEntry
FIoStoreReader
```

例如 `FPackageFileSummary` 当前包含：

- NameCount / NameOffset
- ImportCount / ImportOffset
- ExportCount / ExportOffset
- DependsOffset
- SoftObjectPaths
- SoftPackageReferences
- AssetRegistryDataOffset
- BulkDataStartOffset
- PayloadTocOffset
- PreloadDependencyOffset
- DataResourceOffset
- CustomVersionContainer
- UE File Version
- Licensee Version
- SavedByEngineVersion

等信息。citeturn256387view0

因此所有格式实现都应该遵守：

> **源码定义优先，实测样本验证其次，第三方实现用于交叉验证。**

---

# 4. 第三方成熟实现分析

## 4.1 UAssetAPI

UAssetAPI 的定位非常明确：

> low-level Unreal asset read/write library。

当前项目声明大致支持 UE4.13 到 UE5.7，支持超过 100 种 Property 类型，并支持：

- cooked / uncooked asset
- `.uasset`
- `.uexp`
- `.ubulk`
- JSON
- Kismet bytecode
- `.usmap`
- Unversioned Properties
- game-specific overrides
- Raw fallback
- binary equality-oriented serialization citeturn191704search1turn191704search2


### 值得借鉴

主要是：

```text
版本精确管理
Property 覆盖
USMAP
Raw fallback
Writer / Roundtrip
Game override
```

### 不建议完全照搬

UAssetAPI 很大程度围绕：

```text
Binary Asset
↕
Object Model
```

以及编辑和重新序列化设计。

如果我们的主要目标还有：

```text
搜索
分析
资源理解
AI
依赖关系
批量扫描
资源转换
```

就应该增加独立的 Semantic IR。

---

# 5. CUE4Parse

CUE4Parse 当前定位是 UE4 / UE5 archives & packages parsing library，并明确支持大量 native asset class，包括：

```text
UObject
UTexture2D
UAnimSequence
UStaticMesh
...
``` citeturn191704search0turn191704search5


它非常值得参考的一点是 Provider 设计。

当前实现会从输入文件找到：

```text
.uasset
.uexp
.ubulk
.uptnl
```

然后根据来源创建不同 Package：

```text
Pak / Loose
    ↓
Package

IoStore
    ↓
IoPackage
``` citeturn191704search4


这是非常合理的架构。

---

# 6. UE Viewer / UModel

UE Viewer 是较老但非常重要的资产解析案例。

其代码结构明确分离：

```text
Unreal
Exporters
Viewers
Tools
```

并长期处理不同 Unreal 游戏的兼容性。citeturn798551search0turn798551search3

它给我们的一个重要经验是：

> **资产支持数量与 Package 能否打开应该是两件不同的事情。**

即使一个资产类型没有 Viewer/Exporter：

```text
Package Parser
```

依然应该能够：

```text
识别
索引
列出
跳过
继续解析
```

---

# 7. FModel

FModel 本身将 CUE4Parse 作为核心解析层，然后在其上实现：

```text
Archive Explorer
Preview
Conversion
UI
``` citeturn798551search4turn798551search5


这是一个很好的工程验证：

```text
Parser Core
    ↓
Application
```

应该分离。

因此自己的项目同样不建议让：

```text
UI
CLI
JSON
GLTF
Texture Decoder
```

进入 Parser Core。

---

# 8. 对 UAsset 格式的正确理解

## 8.1 `.uasset` 不是完整资产的唯一载体

传统 Cooked Package 很可能由：

```text
Foo.uasset
Foo.uexp
Foo.ubulk
Foo.uptnl
```

共同组成。

其中大致可以理解为：

```text
.uasset
    metadata / tables / package header

.uexp
    export serialization

.ubulk
    bulk payload

.uptnl
    optional bulk payload
```

实际布局会因版本和保存方式改变。

因此：

```text
UAssetFile
```

不应该成为整个系统最高层对象。

应该是：

```text
PackageSource
```

---

# 9. UE5 IoStore

现代 UE5 游戏还大量使用：

```text
.utoc
.ucas
```

IoStore。

Epic 当前提供 `FIoStoreReader`，其接口包含：

- chunk enumeration
- compressed blocks
- compression method
- encryption key GUID
- container flags
- directory index
- partition
- ChunkId
- automatic decrypt/decompress read citeturn505954view3


因此：

```text
.uasset parser
```

和：

```text
IoStore reader
```

必须分层。

正确关系：

```text
              IPackageSource
                    │
       ┌────────────┴─────────────┐
       │                          │
 LoosePackageSource       IoStorePackageSource
       │                          │
       └────────────┬─────────────┘
                    ↓
               IPackage
```

---

# 10. Package Source Layer

建议定义：

```cpp
interface IPackageSource {
    PackageIdentity identity();

    Stream openHeader();
    optional<Stream> openExports();

    optional<BulkSource>
        locateBulk(BulkLocator locator);

    PackageCapabilities capabilities();
};
```

实现：

```text
LoosePackageSource
PakPackageSource
IoStorePackageSource
MemoryPackageSource
MappedFilePackageSource
```

以后还可以添加：

```text
RemotePackageSource
CustomGamePackageSource
```

---

# 11. Archive Layer

所有解析器都不应直接操作：

```text
ifstream
FileStream
byte[]
```

而应该建立统一的：

```text
IArchive
```

建议提供：

```cpp
read<T>()
readBytes()
readString()
readFString()

tell()
seek()
size()

slice(offset, size)

version()
context()
```

关键实现：

```text
FileArchive
MemoryArchive
MappedArchive
SliceArchive
CompositeArchive
IoStoreChunkArchive
DecompressionArchive
```

---

# 12. Bounded Archive

所有 Export Parser 必须运行在受限 Archive 内。

例如：

```cpp
auto exportAr = archive.slice(
    export.serialOffset,
    export.serialSize
);
```

禁止 Handler 自己无限读取主 Archive。

解析结束必须验证：

```text
Consumed == Expected
```

状态：

```text
Consumed == SerialSize
    OK

Consumed < SerialSize
    RemainingNativeData

Consumed > SerialSize
    Corrupted / ParserBug
```

这是防止一个资产解析错误破坏整个 Package 状态的核心设计。

---

# 13. VersionContext

Unreal 序列化最大的复杂度不是类型数量，而是：

> **版本。**

不能简单定义：

```cpp
EngineVersion version = UE5_3;
```

建议：

```cpp
struct VersionContext {

    EngineFamily family;

    FPackageFileVersion fileVersion;

    int32 licenseeVersion;

    EngineVersion savedBy;
    EngineVersion compatibleWith;

    CustomVersionMap customVersions;

    Platform platform;

    CookMode cookMode;

    GameProfile game;

    SchemaProvider* schemas;
};
```

CUE4Parse 当前 `VersionContainer` 本身就同时管理：

```text
Game
FPackageFileVersion
LicenseeVersion
Platform
CustomVersions
Options
```

以及大量资产级 feature switches。citeturn235691search1

因此版本上下文必须是一级系统对象，而不是散布的全局变量。

---

# 14. 版本判断规范

禁止：

```cpp
if (engine == UE5_3)
```

优先：

```cpp
if (version.fileVersion >= VER_XXX)
```

或：

```cpp
if (
    version.customVersions[
        SomeCustomVersionGUID
    ] >= SomeVersion
)
```

只有在游戏修改引擎 Serialization 时：

```cpp
if (profile.hasFeature(...))
```

---

# 15. Game Profile

建议建立：

```cpp
interface IGameProfile {

    GameId id();

    void configureVersion(
        VersionContext&
    );

    optional<AssetHandler>
        findCustomHandler(ClassPath);

    optional<SerializerOverride>
        findSerializer(TypeId);
};
```

例如：

```text
GenericUE427
GenericUE50
GenericUE51
...
GenericUE58

Game_X
Game_Y
Game_Z
```

这样游戏特殊判断不会污染核心代码。

---

# 16. Package Layer

建议：

```text
IPackage
├── LegacyPackage
└── IoPackage
```

而不是让同一个：

```text
PackageParser
```

用几十个条件处理所有格式。

---

# 17. FPackageFileSummary

Legacy Package 首先读取 Summary。

官方明确将其定义为：

> package file 顶部的 table of contents。 citeturn256387view0


第一阶段应至少支持：

```text
Tag
PackageName

Version
LicenseeVersion
CustomVersions

PackageFlags

NameCount
NameOffset

ImportCount
ImportOffset

ExportCount
ExportOffset

DependsOffset

SoftObjectPaths
SoftPackageReferences

AssetRegistryDataOffset

BulkDataStartOffset

PreloadDependencies

ThumbnailTableOffset

PayloadTocOffset

DataResourceOffset

SavedByEngineVersion
CompatibleWithEngineVersion
```

---

# 18. Name 系统

FName 不应该立即转成：

```text
std::string
```

建议：

```cpp
struct UnrealName {

    NameDomain domain;

    uint32 index;

    uint32 number;

    string resolved;
};
```

其中：

```text
NameDomain
├── Package
├── Container
├── Global
└── Script
```

这样才能兼容 Legacy Package 与 UE5 Name Map 体系。

---

# 19. Import Map

Import 表描述当前 Package 引用的外部对象。

建议内部：

```cpp
struct ImportEntry {

    UnrealName classPackage;
    UnrealName className;

    ObjectRef outer;

    UnrealName objectName;

    optional<string> resolvedPath;
};
```

随后由：

```text
ObjectResolver
```

建立：

```text
/Game/...
/Script/...
```

路径。

---

# 20. Export Map

Export 是 Package 中实际包含的对象。

Epic 当前 `FObjectExport` 中仍包含：

```text
ClassIndex
SuperIndex
TemplateIndex
ObjectFlags
SerialOffset
SerialSize
dependency information
ScriptSerializationStartOffset
ScriptSerializationEndOffset
```

等核心字段。citeturn505954view2

建议定义：

```cpp
struct ExportEntry {

    ExportId id;

    UnrealName name;

    ObjectRef classRef;
    ObjectRef superRef;
    ObjectRef outerRef;
    ObjectRef templateRef;

    uint64 objectFlags;

    int64 serialOffset;
    int64 serialSize;

    ExportDependencyInfo dependencies;

    RawSpan serializedData;
};
```

---

# 21. FPackageIndex

这是整个 Legacy Object Graph 的核心。

Epic 规则为：

```text
Index > 0
    ExportMap[Index - 1]

Index < 0
    ImportMap[-Index - 1]

Index == 0
    null
``` citeturn505954view0


因此不能让每个 Asset Handler 自己解析整数。

应该统一：

```cpp
struct ObjectRef {

    RefKind kind;

    int32 rawIndex;

    optional<ObjectId> resolved;
};
```

---

# 22. 两阶段 Object Resolution

建议：

## Phase A

只读取：

```text
PackageSummary
NameMap
ImportMap
ExportMap
Dependency Tables
```

建立：

```text
ObjectIndex
```

## Phase B

解析各 Export。

## Phase C

Resolve：

```text
Outer
Class
Super
Template
Properties
Hard Reference
Soft Reference
```

这可以天然处理：

```text
A → B
B → C
C → A
```

循环引用。

---

# 23. UObject Layer

Package Table 完成之后才进入 UObject。

建议：

```cpp
struct UObjectIR {

    ObjectId id;

    string name;

    ObjectRef classRef;
    ObjectRef outerRef;

    PropertyBag properties;

    optional<TypedAssetData> native;

    vector<ObjectRef> references;

    RawData trailingData;
};
```

---

# 24. Property System

这是项目最重要的通用模块之一。

不能在：

```text
TextureParser
StaticMeshParser
BlueprintParser
```

中分别实现属性读取。

应该统一建立：

```text
PropertySystem
```

---

# 25. Tagged Property

Epic 当前仍存在 `FPropertyTag`，其字段包括：

```text
Name
Type
Size
ArrayIndex
BoolVal
PropertyGuid
SerializeType
```

等。citeturn355719view1

因此建议：

```cpp
struct PropertyTag {

    UnrealName name;

    PropertyType type;

    uint32 arrayIndex;

    uint64 serializedSize;

    optional<Guid> propertyGuid;

    PropertyMetadata metadata;
};
```

---

# 26. Property 类型体系

核心支持：

```text
BoolProperty

ByteProperty

Int8Property
Int16Property
IntProperty
Int64Property

UInt16Property
UInt32Property
UInt64Property

FloatProperty
DoubleProperty

NameProperty
StrProperty
TextProperty

ObjectProperty
ClassProperty
InterfaceProperty

SoftObjectProperty
SoftClassProperty
WeakObjectProperty

EnumProperty
StructProperty

ArrayProperty
SetProperty
MapProperty

DelegateProperty
MulticastDelegateProperty

FieldPathProperty
OptionalProperty
```

当前 CUE4Parse USMAP 类型体系已经包含：

```text
OptionalProperty
Utf8StrProperty
AnsiStrProperty
VerseStringProperty
VerseDynamicProperty
VerseFunctionProperty
```

等较新类型。citeturn235691search0

因此建议内部 Property Type 不要使用固定的闭合 enum。

更推荐：

```cpp
struct PropertyType {

    TypeKind kind;

    optional<TypeRef> inner;
    optional<TypeRef> key;
    optional<TypeRef> value;

    optional<string> structName;
    optional<string> enumName;
};
```

---

# 27. Unversioned Properties

Cooked 游戏经常使用：

```text
Unversioned Properties
```

此时资产中并不存在完整 Property Tag。

因此需要：

```text
Schema
```

通常来源：

```text
.usmap
```

UAssetAPI 明确要求 Unversioned Properties 在缺少对应 mapping 时无法正确解析，并提供 USMAP 支持。citeturn191704search2turn191704search3

设计上必须将：

```text
TaggedPropertyReader
```

和：

```text
UnversionedPropertyReader
```

完全分离。

---

# 28. Schema 系统

建议：

```text
ISchemaProvider
│
├── UsmapSchemaProvider
├── ReflectionSchemaProvider
├── GeneratedSchemaProvider
├── GameSchemaProvider
└── CompositeSchemaProvider
```

统一输出：

```cpp
struct TypeSchema {

    string name;

    optional<string> super;

    vector<PropertySchema>
        properties;
};
```

Property：

```cpp
struct PropertySchema {

    string name;

    uint16 index;

    uint8 arrayDim;

    PropertyType type;
};
```

CUE4Parse 当前 USMAP parser 本身也会读取：

```text
schema name
super
property count
serializable property count
property index
array dim
recursive property type
``` citeturn235691search2


---

# 29. Property Value IR

Property 不建议直接用语言运行时类型。

例如不要：

```text
Dictionary<string, object>
```

作为唯一内部表示。

更推荐：

```text
PropertyValue

├── Null
├── Bool
├── Integer
├── Unsigned
├── Float
├── String
├── Name
├── Text
├── Enum
├── ObjectRef
├── SoftObjectRef
├── Struct
├── Array
├── Set
├── Map
└── Raw
```

这样可以：

```text
JSON
SQLite
Binary Writer
UI
AI
```

共享。

---

# 30. Native Serialization

这是通用 UObject Parser 和真正资产解析之间的界限。

一个 UObject 的数据可以概念上理解为：

```text
UObject Serialization

Properties
+
Native Serialization
```

很多高价值资产真正重要的信息并不全部存在于 Property。

例如：

```text
StaticMesh RenderData
SkeletalMesh LOD Data
Texture PlatformData
Animation Compressed Data
Sound Compressed Data
```

因此需要：

```text
Asset Type Handler
```

---

# 31. Asset Handler Registry

建议接口：

```cpp
interface IAssetHandler {

    HandlerId id();

    bool supports(
        ClassPath classPath,
        VersionContext context
    );

    TypedAsset parse(
        UObjectIR& object,
        Archive& nativeArchive,
        ParseContext& context
    );
};
```

Registry：

```text
HandlerRegistry

ClassPath
    ↓
Handler
```

例如：

```text
/Script/Engine.Texture2D
    ↓
Texture2DHandler
```

---

# 32. Handler 优先级

建议：

```text
Game Handler
        ↓
Exact Type Handler
        ↓
Base Type Handler
        ↓
Generic UObject Handler
```

即：

```text
GameSpecialTexture
Texture2D
Texture
UObject
```

---

# 33. Unknown Asset

绝不能：

```text
Unknown class
    ↓
throw
```

应该：

```text
Unknown class
    ↓
Generic UObject
    ↓
Known Properties
+
Raw Native Span
```

例如：

```json
{
  "class": "/Script/MyGame.SpecialAsset",

  "properties": {
    "Damage": 10,
    "DisplayName": "ABC"
  },

  "native": {
    "status": "unsupported",
    "blob": "blob:7"
  }
}
```

这对于实际游戏批量扫描极其重要。

---

# 34. BulkData

Bulk Data 必须作为独立 subsystem。

Epic 当前 `FBulkData` 已经包含：

```text
BulkChunkId
Bulk metadata
offset
size
size on disk
compression
inline/separate
optional
IoDispatcher
memory mapping
streaming request
```

等行为。citeturn505954view1

因此不要定义：

```cpp
vector<uint8> bulk;
```

而建议：

```cpp
struct BulkDataRef {

    BulkId id;

    BulkStorage storage;

    uint64 offset;

    uint64 size;

    uint64 sizeOnDisk;

    BulkFlags flags;

    Compression compression;

    optional<IoChunkId> chunkId;

    optional<Hash> payloadId;
};
```

---

# 35. BulkStorage

建议支持：

```text
Inline

UAsset
UExp
UBulk
UPtnl

IoStoreChunk

PackageTrailer

ExternalResource

Virtualized

Unknown
```

---

# 36. Lazy Bulk Loading

Package Parse：

```text
Texture
    ↓
Mip Metadata
    ↓
BulkDataRef
```

只有真正：

```text
decode texture
```

时才：

```text
BulkResolver.load(ref)
```

不要扫描 10 万资产时把全部 Mip、Mesh、Audio 载入内存。

---

# 37. Package Trailer

现代 UE Package 还可能包含 Package Trailer。

Epic 当前 `FPackageTrailer` 支持：

```text
payload enumeration
payload size
payload offset
payload status
local payload loading
virtualized payload state
``` citeturn355719view2


因此 Package 模型最好从第一版就预留：

```cpp
optional<PackageTrailerIR>
```

即使 v0.1 暂时不完整解析。

---

# 38. Derived Data

现代 UE 还在持续增强 Derived Data / Virtualized Payload 系统。

Epic UE5.8 的 `FDerivedData` 已明确设计为：

```text
editor
cooked package
cache
raw buffer
compressed buffer
Zen
```

统一引用 Derived Data，并可以替代传统 serialized bulk data。citeturn355719search6

因此从长期设计上：

```text
BulkData
```

不应等同于：

```text
文件中的 bytes
```

更合理的抽象是：

```text
PayloadReference
```

BulkData 只是其中一种来源。

---

# 39. Typed Asset 支持规划

以下是推荐支持范围。

---

# 40. DataAsset

优先级：

**最高。**

原因：

```text
Property 驱动
开发成本低
信息价值高
```

可输出：

```text
Class
Properties
References
```

---

# 41. DataTable

建议输出：

```text
RowStruct
Rows
```

例如：

```json
{
  "type": "DataTable",

  "rowStruct":
    "/Script/Game.ItemConfig",

  "rows": {
    "Sword01": {
      "Damage": 100,
      "Price": 500
    }
  }
}
```

特别适合：

```text
数据分析
数据库
AI
```

---

# 42. CurveTable / StringTable

同样应列为第一阶段资产。

输出：

```text
JSON
CSV
```

即可。

---

# 43. Texture2D

建议解析：

```text
Texture2D

sizeX
sizeY

pixelFormat

sRGB

compressionSettings

filter

addressing

platformData

mips[]
    width
    height
    depth
    bulk
```

Decoder 单独处理：

```text
BC1
BC3
BC4
BC5
BC6H
BC7

ASTC
ETC

BGRA
RGBA

G8
...
```

---

# 44. Texture Pipeline

严格分成：

```text
Texture Parser
      ↓
Texture IR
      ↓
Pixel Decoder
      ↓
Image
      ↓
PNG / DDS / KTX2 / EXR
```

禁止：

```text
Texture2DHandler
    ↓
直接 PNG
```

否则以后无法：

```text
预览
数据库
转 KTX
转 DDS
GPU decode
```

共享。

---

# 45. StaticMesh

建议解析：

```text
StaticMesh

bounds

materialSlots[]

LODs[]
    sections[]
    vertexCount
    indexCount

    positions
    normals
    tangents

    UV channels

    colors
    indices

sockets
collision
renderData
nanite metadata
```

注意：

第一阶段不建议立刻尝试：

```text
完整 Nanite cluster 解码
```

建议先做到：

```text
识别
Metadata
Raw Preservation
Fallback LOD
```

---

# 46. SkeletalMesh

建议：

```text
SkeletalMesh

skeletonRef

referenceSkeleton

bones[]
    name
    parent
    localTransform

materials[]

LODs[]
    sections
    vertices
    indices
    skinWeights
    boneMap

morphTargets[]

sockets
bounds
```

输出：

```text
Canonical Mesh IR
```

之后 GLTF Exporter 消费 Mesh IR。

---

# 47. Skeleton

建议独立 Handler：

```text
Skeleton

referenceSkeleton

virtualBones

sockets

retargetSources

blendProfiles

slotGroups
```

---

# 48. Animation

建议支持：

```text
AnimSequence
AnimMontage
AnimComposite
BlendSpace
```

其中 AnimSequence：

```text
duration
frameRate
frameCount

tracks[]
    bone
    translation keys
    rotation keys
    scale keys

curves
notifies
syncMarkers

rootMotion
```

最大困难：

```text
Compressed Animation Data
```

可能涉及：

```text
不同 UE Version
不同 Codec
ACL
Game-specific codec
```

因此 Animation 应作为独立 subsystem。

---

# 49. MaterialInstance

这是非常值得较早支持的类型。

建议：

```text
MaterialInstance

parent

scalarParameters
vectorParameters
textureParameters

staticSwitches

fontParameters

runtimeVirtualTexture
```

---

# 50. Material

Material 比 MaterialInstance 更复杂。

可以逐步解析：

```text
domain
blendMode
shadingModel
twoSided
masked

texture dependencies

cached expressions

shader map references
```

但必须明确：

> Cooked Material 不保证保留 Editor Material Graph。

因此 API 不应承诺：

```text
任何 cooked Material
→
100% 恢复 Material Editor Node Graph
```

---

# 51. SoundWave

建议：

```text
SoundWave

sampleRate
channels
duration

compression format

streaming chunks

bulk payload
```

Decoder：

```text
PCM
OGG
Opus
Bink Audio
ADPCM
platform-specific
```

与 SoundWave Parser 分离。

---

# 52. Blueprint

Blueprint 建议拆成三个不同概念。

## Reflection

```text
BlueprintGeneratedClass

parentClass

properties

functions

interfaces

components

CDO
```

## Kismet

```text
bytecode
    ↓
Instruction IR
    ↓
Control Flow
    ↓
AST
    ↓
Pseudo Code
```

UAssetAPI 已支持 raw Kismet bytecode 读取，可作为低层格式参考。citeturn191704search1

## Editor Graph

```text
UEdGraph
K2Node
Pins
Node Position
Comment
```

这部分只在数据存在时支持。

不能假定 Cooked Package 仍保存完整 Editor Graph。

---

# 53. World / Level

建议最终支持：

```text
World
    ↓
Level
    ↓
Actor[]
```

Actor：

```text
Class
Name
Transform
Properties
Components
References
```

组件：

```text
SceneComponent

StaticMeshComponent
SkeletalMeshComponent

CameraComponent

LightComponent

AudioComponent

SplineComponent
...
```

最终生成：

```text
Scene IR
```

---

# 54. UE5 World Partition

单独作为后期阶段。

需要考虑：

```text
World Partition
External Actors
Data Layers
Runtime Cells
Actor Desc
HLOD
```

不建议和普通 `ULevel` 第一阶段一起实现。

---

# 55. LevelSequence

建议解析：

```text
LevelSequence

MovieScene

bindings

tracks

sections

channels

keyframes
```

可以形成：

```text
Timeline IR
```

---

# 56. Niagara

建议中后期支持：

```text
NiagaraSystem
NiagaraEmitter
NiagaraScript
NiagaraParameterStore
```

其内部版本和 VM 数据相对复杂。

第一阶段：

```text
Properties
Dependencies
Raw Native Data
```

即可。

---

# 57. PhysicsAsset

可解析：

```text
Skeleton link

Bodies
Shapes

Constraints

PhysicalMaterial
```

方便模型分析和资源转换。

---

# 58. Landscape

属于高复杂度资产。

涉及：

```text
components
heightmap
weightmaps
layers
material
collision
streaming
```

建议在：

```text
Texture
Mesh
World
```

稳定以后开发。

---

# 59. 推荐资产优先级

## P0

```text
Generic UObject
DataAsset
DataTable
CurveTable
StringTable
```

## P1

```text
Texture2D
MaterialInstance
SoundWave
```

## P2

```text
StaticMesh
Skeleton
SkeletalMesh
```

## P3

```text
Animation
Material
BlueprintGeneratedClass
```

## P4

```text
World
LevelSequence
PhysicsAsset
```

## P5

```text
WorldPartition
Landscape
Niagara
Nanite deep decode
```

---

# 60. 核心 IR 设计

解析器内部最终不应该直接暴露 Parser Class。

建议统一输出：

```text
AssetDocument
```

结构：

```text
AssetDocument

metadata

source

package

names

imports

exports

objects

dependencies

payloads

diagnostics
```

---

# 61. Package IR

```cpp
struct PackageIR {

    PackageId id;

    string packageName;

    PackageFormat format;

    VersionInfo version;

    PackageFlags flags;

    vector<NameEntry> names;

    vector<ImportIR> imports;

    vector<ExportIR> exports;

    DependencyGraph dependencies;
};
```

---

# 62. Object IR

```cpp
struct ObjectIR {

    ObjectId id;

    string name;

    string path;

    string classPath;

    optional<ObjectId> outer;

    PropertyBag properties;

    optional<TypedAssetIR> asset;

    RawRegions raw;
};
```

---

# 63. Typed Asset IR

建议用：

```text
Variant
```

而不是基类层层继承。

例如：

```cpp
using TypedAssetIR =
    variant<
        DataTableIR,
        TextureIR,
        StaticMeshIR,
        SkeletalMeshIR,
        SkeletonIR,
        AnimationIR,
        MaterialIR,
        SoundIR,
        BlueprintIR,
        WorldIR
    >;
```

---

# 64. Dependency Graph

Dependency 不要只是：

```text
string[]
```

而应该：

```cpp
struct DependencyEdge {

    ObjectId from;

    ResourceId to;

    DependencyKind kind;
};
```

DependencyKind：

```text
Hard
Soft
Class
Package
Outer
Material
Texture
Skeleton
Animation
Blueprint
Runtime
EditorOnly
Unknown
```

---

# 65. 输出格式总体设计

建议提供四层输出。

---

# 66. Raw JSON

用于：

```text
逆向
调试
Parser 开发
格式研究
```

保留：

```text
offset
size
raw index
raw flags
unknown bytes
```

例如：

```json
{
  "classIndex": -7,
  "serialOffset": 18320,
  "serialSize": 1422
}
```

---

# 67. Semantic JSON

作为默认格式。

例如：

```json
{
  "name": "Hero",

  "path":
    "/Game/Characters/Hero.Hero",

  "class":
    "/Script/Engine.SkeletalMesh",

  "asset": {
    "kind": "skeletalMesh",
    "lodCount": 4,
    "boneCount": 126
  }
}
```

---

# 68. Raw + Semantic 双视图

推荐默认 Semantic，但允许：

```json
{
  "name": "Hero",

  "_raw": {
    "objectNameIndex": 193,
    "classIndex": -7
  }
}
```

这样同时满足：

```text
人
AI
调试
逆向
```

需求。

---

# 69. Blob 输出

禁止把大型：

```text
Texture
Mesh Buffer
Audio
Unknown Native Data
```

全部 Base64 塞进 JSON。

推荐：

```text
Hero.asset.json

Hero.blobs/
    payload_000.bin
    texture_mip_00.bin
    index_buffer.bin
```

JSON：

```json
{
  "payload": {
    "$blob": "blob:000",

    "size": 8388608,

    "sha256":
      "..."
  }
}
```

---

# 70. Blob Manifest

建议：

```json
{
  "blobs": {
    "blob:000": {
      "file":
        "Hero.blobs/payload_000.bin",

      "size": 8388608,

      "sha256":
        "..."
    }
  }
}
```

---

# 71. Binary / Database IR

如果需要扫描几十万资产，不建议只依赖 JSON。

建议内部再提供：

```text
MessagePack
CBOR
SQLite
Parquet
```

其中：

```text
SQLite
```

尤其适合：

```text
asset index
dependency search
property query
```

---

# 72. 推荐 JSON 顶层 Schema

```json
{
  "schema": {
    "name":
      "unreal-asset-ir",

    "version":
      "1.0"
  },

  "source": {},

  "package": {},

  "imports": [],

  "exports": [],

  "objects": [],

  "dependencies": [],

  "payloads": [],

  "diagnostics": []
}
```

---

# 73. Source 信息

```json
{
  "source": {

    "container":
      "loose",

    "files": [
      "Hero.uasset",
      "Hero.uexp",
      "Hero.ubulk"
    ],

    "engineFamily":
      "UE5",

    "cooked":
      true
  }
}
```

---

# 74. Version 信息

```json
{
  "version": {

    "fileVersionUE4":
      522,

    "fileVersionUE5":
      1012,

    "licenseeVersion":
      0,

    "savedBy":
      "5.x",

    "customVersions": []
  }
}
```

---

# 75. Export 示例

```json
{
  "id":
    "export:0",

  "name":
    "Hero",

  "path":
    "/Game/Hero.Hero",

  "class":
    "/Script/Engine.SkeletalMesh",

  "serialization": {
    "offset": 18420,
    "size": 950124
  },

  "properties": {},

  "asset": {
    "kind":
      "skeletalMesh"
  }
}
```

---

# 76. Parser Level

建议正式支持不同解析深度。

```text
Level 0
Package

Level 1
Object

Level 2
Typed Asset

Level 3
Decoded Resource
```

对应：

```cpp
enum class ParseDepth {
    Package,
    Object,
    Asset,
    Decode
};
```

---

# 77. Level 0

只读取：

```text
Summary

Name
Import
Export

Dependency
```

适用于：

```text
几十万资产索引
```

---

# 78. Level 1

增加：

```text
Properties
References
```

适用于：

```text
搜索
数据分析
AI
```

---

# 79. Level 2

增加：

```text
Native Asset Data
```

例如：

```text
Mesh
Texture metadata
Animation metadata
```

---

# 80. Level 3

真正解码：

```text
Pixels
Vertices
Audio PCM
Animation Tracks
```

这是最昂贵级别。

---

# 81. Strict / Tolerant Mode

必须同时存在。

## Tolerant

默认。

遇到：

```text
未知 Property
未知资产
未知尾部
```

执行：

```text
Warning
+
Raw Preservation
+
Continue
```

---

# 82. Strict

用于 Parser 开发：

```text
Unexpected bytes
Unknown serialization
Invalid offset
Mismatch size
```

直接：

```text
Error
```

这样逆向时更容易发现错误。

---

# 83. Diagnostics

不要只：

```cpp
throw runtime_error("bad asset");
```

建议：

```cpp
struct Diagnostic {

    Severity severity;

    DiagnosticCode code;

    uint64 offset;

    optional<uint64> size;

    string package;

    optional<string> object;

    optional<string> property;

    string message;
};
```

---

# 84. Diagnostic Code

例如：

```text
INVALID_MAGIC

INVALID_OFFSET

OUT_OF_BOUNDS

VERSION_UNSUPPORTED

SCHEMA_REQUIRED

SCHEMA_MISMATCH

UNKNOWN_PROPERTY

PROPERTY_SIZE_MISMATCH

UNKNOWN_NATIVE_DATA

UNKNOWN_COMPRESSION

DECRYPTION_FAILED

BULK_DATA_MISSING

OBJECT_REFERENCE_INVALID

EXPORT_SIZE_MISMATCH
```

---

# 85. Error 与 Warning 分级

```text
Info

Warning

RecoverableError

Fatal
```

例如：

```text
Unknown Native Data
    Warning

Invalid Export Offset
    Fatal
```

---

# 86. Parser 安全规范

所有 Binary Parser 都必须假定输入可能损坏。

设置：

```text
ParseLimits
```

例如：

```cpp
struct ParseLimits {

    uint32 maxNames;

    uint32 maxImports;

    uint32 maxExports;

    uint64 maxStringBytes;

    uint64 maxArrayElements;

    uint64 maxBulkBytes;

    uint32 maxObjectDepth;

    uint32 maxStructDepth;
};
```

---

# 87. Checked Arithmetic

所有：

```text
offset + size

count * elementSize
```

必须进行 overflow 检测。

禁止：

```cpp
seek(offset + size);
```

直接计算。

---

# 88. 内存策略

大型数据必须：

```text
Lazy
```

不要：

```text
Load Entire Game
```

建议：

```text
mmap
slice
shared buffer
lazy payload
```

---

# 89. Streaming

解析器尽量保证：

```text
Metadata
```

可以 streaming。

例如：

```text
1GB Texture Asset

Package Parse
    < 几 MB RAM

Decode
    才读取 Bulk
```

---

# 90. Cache

建议：

```text
Name cache

Schema cache

Package cache

Resolved object cache

Decompression block cache
```

注意避免把：

```text
decoded texture
mesh vertex
```

默认放全局 Cache。

---

# 91. 并发

Package 之间天然可以：

```text
parallel
```

Package 内：

```text
Metadata
```

建议单线程完成。

随后 Export：

```text
parallel
```

需要确保：

```text
ObjectResolver
SchemaProvider
NameTable
```

是只读安全的。

---

# 92. Parser 与 Converter 分离

建议模块：

```text
parser-core

asset-types

codecs

exporters
```

例如：

```text
Texture2DHandler
```

只输出：

```text
TextureIR
```

然后：

```text
TextureDecoder
```

输出：

```text
ImageIR
```

最后：

```text
PngExporter
```

才写 PNG。

---

# 93. 推荐模块架构

```text
src/

core/
    archive/
    buffer/
    compression/
    crypto/
    diagnostics/

version/
    package_version/
    custom_version/
    game_profile/
    platform/

container/
    loose/
    pak/
    iostore/

package/
    common/
    legacy/
    io_package/

reflection/
    name/
    object_ref/
    import/
    export/
    schema/

property/
    common/
    tagged/
    unversioned/
    primitive/
    container/
    struct/

object/
    uobject/
    resolver/

bulk/
    metadata/
    locator/
    resolver/
    payload/

assets/
    generic/
    data/
    texture/
    mesh/
    skeleton/
    animation/
    material/
    audio/
    blueprint/
    world/
    sequence/

ir/
    package/
    object/
    property/
    asset/
    dependency/

codecs/
    texture/
    animation/
    audio/
    compression/

exporters/
    json/
    sqlite/
    gltf/
    image/
    audio/
    graph/

profiles/
    games/

cli/

tests/
```

---

# 94. API 设计

建议顶层：

```cpp
Parser parser(config);

ParseResult result =
    parser.parse(
        source,
        options
    );
```

Options：

```cpp
struct ParseOptions {

    ParseDepth depth;

    Strictness strictness;

    bool resolveReferences;

    bool preserveRaw;

    bool parseDependencies;

    bool lazyBulk;

    ResourceLimits limits;
};
```

---

# 95. Package API

```cpp
auto pkg =
    parser.openPackage(path);

auto summary =
    pkg.summary();

auto exports =
    pkg.exports();
```

---

# 96. Object API

```cpp
auto object =
    pkg.loadObject(
        "/Game/Hero.Hero"
    );

object.classPath();

object.properties();
```

---

# 97. Typed API

```cpp
if (
    auto mesh =
        object.as<SkeletalMeshIR>()
) {
    mesh->lods();
}
```

---

# 98. CLI

建议一开始就把 CLI 当稳定 API 设计。

```bash
ueasset inspect Hero.uasset
```

输出 Summary。

---

```bash
ueasset list Hero.uasset
```

列出 Imports / Exports。

---

```bash
ueasset parse Hero.uasset
```

输出 Semantic IR。

---

```bash
ueasset parse Hero.uasset --raw
```

输出 Raw IR。

---

```bash
ueasset deps Hero.uasset
```

输出依赖。

---

```bash
ueasset extract Hero.uasset
```

导出媒体资产。

---

```bash
ueasset verify Hero.uasset
```

执行结构校验。

---

```bash
ueasset scan Content/
```

批量索引。

---

# 99. 批量扫描模式

大型项目真正有价值的能力是：

```text
Game
 ↓
100,000 packages
 ↓
Index
```

建议建立：

```text
AssetDatabase
```

包含：

```text
Package
Object
Class
Property
Dependency
Payload
```

---

# 100. SQLite Schema

例如：

```text
packages

objects

properties

dependencies

payloads

diagnostics
```

查询：

```sql
SELECT *
FROM objects
WHERE class_path =
'/Script/Engine.SkeletalMesh';
```

---

# 101. AI 输出层

如果以后要把解析结果交给 AI，不应把 Raw IR 直接塞给模型。

建议：

```text
Binary IR
    ↓
Semantic IR
    ↓
AI View
```

例如：

```json
{
  "asset":
    "/Game/Character/Hero",

  "type":
    "SkeletalMesh",

  "lods":
    4,

  "bones":
    126,

  "skeleton":
    "/Game/Character/HeroSkeleton",

  "materials": [
    "/Game/Character/M_Hero"
  ]
}
```

这比：

```text
FPackageIndex
NameIndex
SerialOffset
```

更适合语义分析。

---

# 102. Writer 是否第一阶段实现

建议：

> **不实现。**

第一阶段只：

```text
Read
Analyze
Export
```

原因是 Writer 会立刻引入：

```text
offset recalculation

name table rewrite

export relocation

bulk relocation

binary preservation

padding

version serialization

unknown field preservation
```

复杂度会显著提升。

---

# 103. Writer 第二阶段

以后如果实现：

```text
read
modify
write
```

需要增加：

```text
Raw Preservation
```

即未理解的数据也必须能够原样重新写入。

UAssetAPI 对 binary equality 的强调非常值得借鉴，其 JSON/serialization 设计就是围绕尽量保留原始二进制结构。citeturn191704search1

---

# 104. Roundtrip Test

Writer 阶段要求：

```text
Original
    ↓
Parse
    ↓
Write
    ↓
Output
```

对于没有修改的数据尽量达到：

```text
binary equivalent
```

或者至少：

```text
semantic equivalent
```

这两个测试要分开定义。

---

# 105. 测试体系

Parser 项目的质量主要不是由：

```text
代码量
```

决定，而是由：

```text
测试 Corpus
```

决定。

建议：

```text
tests/corpus/
```

---

# 106. Version Corpus

至少覆盖：

```text
UE4.20
UE4.21
...
UE4.27

UE5.0
UE5.1
UE5.2
UE5.3
UE5.4
UE5.5
UE5.6
UE5.7
UE5.8
```

如果第一阶段只支持：

```text
UE4.27+
```

也至少每个 minor version 有样本。

---

# 107. Asset Corpus

每个版本：

```text
DataAsset

DataTable

Texture2D

StaticMesh

SkeletalMesh

Skeleton

AnimSequence

Material

MaterialInstance

SoundWave

Blueprint

Level
```

---

# 108. 特殊 Corpus

单独：

```text
Cooked

Uncooked

Versioned

Unversioned

USMAP

Separate UExp

Separate UBulk

Optional Bulk

Package Trailer

Pak

IoStore

Encrypted

Compressed

Corrupted
```

---

# 109. Golden Test

输入：

```text
SM_Chair.uasset
```

固定输出：

```text
SM_Chair.expected.json
```

CI：

```text
parse
 ↓
canonicalize
 ↓
diff
```

可以立即发现：

```diff
- "vertexCount": 2048
+ "vertexCount": 0
```

---

# 110. Property Test

每一种 Property 单独构建：

```text
fixture
```

重点覆盖：

```text
Array<Map<...>>

Struct

nested containers

Enum

SoftObject

Optional

Text
```

---

# 111. Fuzz Test

Binary Parser 推荐加入：

```text
AFL++
libFuzzer
cargo-fuzz
```

取决于技术栈。

重点：

```text
PackageSummary

FString

PropertyTag

Array

USMAP

Bulk header
```

---

# 112. Differential Testing

非常推荐。

同一资产分别由：

```text
自己的 Parser
CUE4Parse
UAssetAPI
```

解析。

比较：

```text
Name Count

Import Count

Export Count

Object Names

Class Paths

Properties

References
```

这对格式逆向非常有帮助。

但第三方结果只作为：

```text
cross-check
```

最终仍以 UE 源码和样本验证为准。

---

# 113. Benchmark

至少建立：

```text
Package parse / sec

objects / sec

MB / sec

Peak RAM

Bulk decode throughput
```

三种 Benchmark：

```text
Small Asset

Large Texture

Game Scan
```

---

# 114. 推荐语言

如果项目是新的，可以考虑三种方案。

## C++

优势：

```text
和 UE 类型最接近

容易对照源码

性能最好

SIMD / mmap / codec
```

缺点：

```text
内存安全成本高
开发成本高
```

---

# 115. C#

优势：

```text
开发快

Binary Reader 生态成熟

CUE4Parse / UAssetAPI
已有大量案例

工具 UI 容易开发
```

缺点：

```text
极致性能略弱
大型内存结构需要控制
```

---

# 116. Rust

从“重新设计一个长期 Parser”的角度，非常合适。

优势：

```text
内存安全

Result/Option

enum/variant 很适合 IR

slice 很适合 bounded parsing

零成本抽象

并发安全

Fuzzing 方便
```

缺点：

```text
UE 社区现成代码少于 C++ / C#

复杂 codec 可能需要 FFI
```

---

# 117. 技术选型建议

如果目标主要是：

```text
研究
CLI
大规模扫描
AI 工具链
跨平台
长期维护
```

我会倾向：

> **Rust Core**

然后：

```text
C ABI
Python Binding
Node Binding
```

扩展。

如果目标是：

```text
快速进入成熟 UE 游戏解析生态
Windows GUI
尽快复用现有知识
```

则：

> **C#**

成本最低。

如果目标最终需要：

```text
深度结合 Unreal Engine
插件
编辑器
Runtime
```

则：

> **C++**

最自然。

---

# 118. 推荐总体架构

最终建议：

```text
                 Application

             CLI / GUI / API
                    │
                    ↓
                Exporters
                    │
                    ↓
              Semantic IR
                    │
                    ↓
               Asset IR
                    │
                    ↓
           Asset Type Handlers
                    │
                    ↓
               UObject Layer
                    │
                    ↓
             Property System
                    │
                    ↓
              Object Tables
                    │
                    ↓
              Package Layer
             ┌──────┴──────┐
             │             │
          Legacy       IoPackage
             │             │
             └──────┬──────┘
                    ↓
              Source Layer
        ┌───────────┼────────────┐
        │           │            │
      Loose        Pak        IoStore
                    │
                    ↓
                Storage
```

---

# 119. 第一阶段开发范围

建议 V0.1：

```text
Archive

Loose Source

Legacy Package

Package Summary

Name Map

Import Map

Export Map

FPackageIndex

VersionContext

CustomVersion

Tagged Property

USMAP

Unversioned Property

Generic UObject

Object Resolver

Dependency Graph

DataAsset

DataTable

StringTable

Texture2D metadata

Raw JSON

Semantic JSON

Blob Store

Diagnostics

Strict/Tolerant

Golden Tests
```

这个版本已经可以完成：

```text
大规模 Package 扫描
Property 分析
Data Mining
依赖分析
基础 Texture 分析
```

---

# 120. V0.2

加入：

```text
Pak

BulkData

Texture Decode

MaterialInstance

SoundWave

StaticMesh

SQLite Index

Parallel Scan
```

---

# 121. V0.3

加入：

```text
IoStore
IoPackage
PackageStore

SkeletalMesh
Skeleton

Animation

Material
```

---

# 122. V0.4

加入：

```text
BlueprintGeneratedClass

Kismet

World
Level

LevelSequence
```

---

# 123. V0.5

加入：

```text
WorldPartition

External Actors

Landscape

Niagara

Nanite

Virtualized Payload
```

---

# 124. Writer Roadmap

Writer 单独规划：

```text
V1.0 Read Stable
        ↓
V1.1 Raw Preservation
        ↓
V1.2 Property Modification
        ↓
V1.3 Export Rebuild
        ↓
V1.4 Bulk Rebuild
        ↓
V1.5 Binary Roundtrip
```

不要在 Parser 初期混进去。

---

# 125. Definition of Done

一个类型不能仅因为：

```text
没有 crash
```

就算支持。

建议支持等级：

## L0 Detect

能识别类型。

## L1 Structure

Properties 可以解析。

## L2 Native Metadata

Native Header 可以解析。

## L3 Resource Data

主要 Payload 可以读取。

## L4 Decode

可以转换为标准数据。

## L5 Roundtrip

可以安全重写。

---

# 126. Asset Capability Matrix

例如：

| Asset | Detect | Property | Native | Decode | Export |
|---|---:|---:|---:|---:|---:|
| DataAsset | ✓ | ✓ | N/A | N/A | JSON |
| DataTable | ✓ | ✓ | ✓ | ✓ | JSON/CSV |
| Texture2D | ✓ | ✓ | ✓ | ✓ | PNG/DDS |
| StaticMesh | ✓ | ✓ | ✓ | ✓ | GLTF |
| SkeletalMesh | ✓ | ✓ | ✓ | ✓ | GLTF |
| Skeleton | ✓ | ✓ | ✓ | ✓ | GLTF |
| AnimSequence | ✓ | ✓ | ✓ | 部分 | GLTF |
| Material | ✓ | ✓ | 部分 | — | JSON |
| Blueprint | ✓ | ✓ | 部分 | Kismet | JSON |
| Unknown | ✓ | ✓ | Raw | — | JSON/BIN |

这比简单写：

```text
Supports Texture
Supports Mesh
```

更专业。

---

# 127. Source Traceability

建议每一个 Format Struct 都记录：

```text
Engine source type

Engine source header

Version condition

Reference commit/tag

Implementation test
```

例如：

```text
PackageSummary

UE:
FPackageFileSummary

Header:
UObject/PackageFileSummary.h

Tests:
UE5_3_PackageSummary_01
UE5_4_PackageSummary_01
```

这样未来升级 UE 版本时非常重要。

---

# 128. 代码规范

建议每个 Binary Struct：

```text
Model
Reader
Writer
Tests
```

分开。

不要：

```cpp
struct X {
    void read();
    void write();
    void convert();
    void exportJson();
}
```

---

# 129. 推荐模式

```text
PackageSummary
PackageSummaryReader
PackageSummaryWriter
PackageSummaryValidator
```

资产：

```text
TextureIR
TextureParser
TextureDecoder
TextureExporter
```

---

# 130. 禁止 Parser 中输出日志字符串

Parser 返回：

```text
Diagnostic
```

日志层决定：

```text
Console
JSON
GUI
Telemetry
```

---

# 131. 禁止 Asset Handler 管理文件

Handler 只能接收：

```text
Archive
Context
```

而不是：

```text
filename
filesystem
```

这样才能支持：

```text
Pak
IoStore
Memory
Remote
```

---

# 132. 禁止 Handler 直接引用游戏

错误：

```cpp
if (game == Fortnite)
```

正确：

```cpp
context.features
    .has(
       Feature::X
    );
```

GameProfile 决定 Feature。

---

# 133. 推荐 Feature System

```text
Features

StaticMesh.NewCookedFormat

StaticMesh.RayTracingData

SkeletalMesh.NewCookedFormat

VirtualTexture

Animation.CompressedRawSize

Sound.AudioStreaming
```

CUE4Parse 当前 VersionContainer 已经使用了大量类似 feature option，对处理 forked engine 很有现实价值。citeturn235691search1

---

# 134. 最重要的设计判断

本项目真正需要避免的是：

```text
Asset Parser
├── Texture if UE4
├── Texture if UE5
├── Mesh if UE4
├── Mesh if UE5
├── Fortnite special
├── PUBG special
├── ...
```

这种结构最终必然不可维护。

正确路线：

```text
Source
 ↓
Package Format
 ↓
Version Context
 ↓
Serialization
 ↓
Object Model
 ↓
Typed Handler
 ↓
IR
```

---

# 135. 项目最终能力边界

设计正确以后，系统应该能够回答：

### Package 层

```text
这是哪个版本？
有哪些对象？
有哪些外部依赖？
数据位于哪里？
```

### UObject 层

```text
对象是什么 Class？
有哪些 Properties？
引用什么对象？
Outer 是什么？
```

### Asset 层

```text
这是什么模型？
几个 LOD？
用了什么材质？
绑定什么 Skeleton？
```

### Semantic 层

```text
这个角色相关的全部资源是什么？
```

### Resource 层

```text
导出模型
导出图片
导出声音
```

---

# 136. 最终推荐定位

不建议项目最终定位为：

> UAsset JSON Parser

而建议：

> **Cross-version Unreal Engine Package & Asset Parsing Framework**

核心竞争力应当是：

```text
版本兼容

未知类型容错

统一 Object Model

统一 Property Model

Typed Asset Extension

Container Abstraction

Semantic IR

Large-scale Analysis

Source Traceability
```

---

# 137. 最终结论

一个成熟 Unreal Asset Parser 最合理的核心链路应该固定为：

```text
Container
    ↓
Package
    ↓
Version
    ↓
Tables
    ↓
Object References
    ↓
UObject
    ↓
Properties
    ↓
Native Serialization
    ↓
Typed Asset
    ↓
Canonical IR
    ↓
Exporter
```

而开发优先级应遵循：

```text
先保证任何 Package 都尽量能够安全打开

↓

再保证 UObject / Property
尽可能完整

↓

再逐渐增加 Typed Assets

↓

最后才增加
复杂 Decode 与 Writer
```

第一版最重要的指标不是：

> “支持多少种 Unreal Asset”

而应该是：

> **面对未知 Package、未知 UObject、未知版本细节时，解析器是否还能保持结构完整、错误局部化、数据不丢失，并给开发者留下继续逆向和扩展的入口。**

这决定了它最终是一个：

```text
一次性 UAsset 工具
```

还是一个：

```text
长期可发展的
Unreal Asset Analysis Platform
```

---

# 参考资料

1. Epic Games — `FPackageFileSummary`：官方将其定义为 Unreal Package 顶部的 table of contents，并列出 Name、Import、Export、Dependency、Bulk、Payload 等结构。citeturn256387view0
2. Epic Games — `FObjectExport`：Export 的 Class、Super、Template、SerialOffset、SerialSize 以及依赖信息。citeturn505954view2
3. Epic Games — `FPackageIndex`：Import / Export 索引编码机制。citeturn505954view0
4. Epic Games — `FPropertyTag`：Tagged Property Serialization 基础结构。citeturn355719view1
5. Epic Games — `FBulkData`：Bulk offset、size、flags、IoChunk、streaming 等机制。citeturn505954view1
6. Epic Games — `FPackageTrailer`：现代 Package Payload 与 virtualized payload 管理。citeturn355719view2
7. Epic Games — `FIoStoreReader`：IoStore Chunk、compression、encryption、partition 与读取接口。citeturn505954view3
8. Epic Games — `FPackageStore` / `FPackageStoreEntry`：UE5 PackageStore 抽象。citeturn256387search5turn256387search6
9. Epic Games — `FDerivedData`：现代 Derived Data 与 cooked/Zen payload 体系。citeturn355719search6
10. CUE4Parse — Archives、Package、UObject 与 Typed Asset 解析架构。citeturn191704search0turn191704search4
11. CUE4Parse — VersionContainer / Feature Options。citeturn235691search1
12. CUE4Parse — USMAP Property 类型与 Schema 解析。citeturn235691search0turn235691search2
13. UAssetAPI — Low-level read/write、Property、USMAP、Kismet 与 binary preservation。citeturn191704search1turn191704search2turn191704search3
14. UE Viewer / UModel — Unreal Package、Viewer、Exporter 和长期游戏兼容案例。citeturn798551search0turn798551search3
15. FModel — 将 CUE4Parse 作为解析 Core、上层负责浏览、预览和转换的实际架构案例。citeturn798551search4turn798551search5