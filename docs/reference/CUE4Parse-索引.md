# CUE4Parse 项目框架与功能实现方案索引

> 源码级深度分析 | C# .NET 8.0 | Unreal Engine 4/5 资产解析

## 1. 项目概述

CUE4Parse 是 FModel 团队开源的 C# 资产解析库，专门用于从 UE4/UE5 游戏包文件中提取数据。独立 NuGet 包发布，也可作为 FModel 的内部依赖。

| 维度 | 详情 |
|------|------|
| **语言** | C# (.NET 8.0) |
| **构建** | MSBuild (.csproj) |
| **平台** | Windows / Linux / macOS |
| **定位** | 游戏资源逆向提取 + 3D 格式导出 |
| **覆盖** | 70+ 游戏特定实现，UE4.0 ~ UE5.5 全版本 |

## 2. 目录结构

```
CUE4Parse/                          # 核心库（解析层）
├── UE4/
│   ├── AssetRegistry/              # 资产注册表 (AssetRegistry 格式)
│   ├── Assets/                     # 资产解析核心
│   │   ├── Exports/                # 100+ UObject 导出类实现
│   │   ├── Readers/                # Package/Asset 反序列化器
│   │   └── Objects/                # FPropertyTag / FPropertyTagType 等
│   ├── Readers/                    # 底层归档读取器 (FArchive 系列)
│   ├── Pak/                        # .pak 文件解析 (FPakInfo / PakFileReader)
│   ├── VirtualFileSystem/          # VFS 抽象层 (AES 解密 / 路径映射)
│   ├── Kismet/                     # 蓝图字节码 (EExprToken / KismetExpression)
│   ├── Versions/                   # 版本管理 (VersionContainer / CustomVersions)
│   └── IO/                         # IoStore 读取器 (.utoc/.ucas)
├── UE5/                            # UE5 特定实现 (IoPackage 等)
├── Compression/                    # 压缩算法封装
├── Encryption/                     # 加密算法封装
├── FileProvider/                   # 统一文件访问入口
├── GameTypes/                      # 70+ 游戏特定覆盖
└── ACL/                            # ACL 动画压缩集成

CUE4Parse-Conversion/               # 转换/导出层（可选依赖）
├── Animations/                     # 动画 → psk/ueanim
├── Meshes/                         # 网格 → psk/glb/obj
├── Textures/                       # 纹理解码 → png/tiff/hdr
├── Sounds/                         # 音频解码 → wav/ogg
├── Materials/                      # 材质参数 → json
└── PoseAsset/                      # 姿态资产导出
```

## 3. 核心架构

### 3.1 数据流

```
游戏目录 (.pak/.uasset/.utoc/.ucas)
  ↓
IFileProvider ───────────────────── 文件发现、路径修复、包加载入口
  ↓
FArchive ────────────────────────── 字节流读取 + 版本感知 + 字节交换
  ↓
FAssetArchive ───────────────────── 资产级序列化上下文 (NameMap/版本注入)
  ↓
AbstractUePackage ───────────────── 包结构: Summary → NameMap → ImportMap → ExportMap
  ↓ Lazy<UObject>[]
UObject.Deserialize ─────────────── 属性反序列化 (PropertyTag 驱动)
  ↓
具体类型 (UTexture2D / UStaticMesh / ...)
  ↓ Conversion 层
psk / glb / png / wav 等格式文件
```

### 3.2 核心抽象层

| 抽象层 | 接口/基类 | 关键实现 | 职责 |
|--------|-----------|----------|------|
| 文件提供者 | `IFileProvider` | `DefaultFileProvider`, `StreamedFileProvider`, `ApkFileProvider` | 文件扫描、路径映射、包加载 |
| 归档读取器 | `FArchive` | `FArchiveBigEndian`, `FAssetArchive` | 类型安全的字节流读取 |
| 资产归档 | `FAssetArchive` | 包装 FArchive + 注入 NameMap/Versions | 资产反序列化上下文 |
| 包 | `AbstractUePackage` | `Package`, `IoPackage` | UE 包统一抽象 |
| 对象 | `UObject` | 100+ 派生类 | 所有资产基类 |
| VFS | `IVfsReader` | `PakFileReader`, `IoStoreReader` | 虚拟文件系统 |

### 3.3 设计模式

- **策略模式**: `VersionContainer` 根据不同游戏/版本选择不同序列化行为
- **工厂模式**: `FAssetArchive` 按类型字符串创建对应 `UObject` 派生类
- **装饰器模式**: `FAssetArchive` 包装基础 `FArchive`，注入 NameMap 查找能力
- **依赖注入**: `IFileProvider` 通过构造函数注入每个 `UObject`
- **懒加载**: `Lazy<UObject>[] ExportsLazy` — 仅在访问 `.Value` 时触发反序列化

## 4. 核心模块深度分析

### 4.1 FArchive 归档读取器

**基类 `FArchive`** 是所有序列化读取的基础，提供类型安全的读取原语。

#### 核心方法签名

| 方法 | 说明 |
|------|------|
| `T Read<T>() where T : unmanaged` | 泛型标量读取（int/float/long 等） |
| `T[] ReadArray<T>() where T : unmanaged` | 定长数组读取 |
| `T[] ReadBulkArray<T>()` | BulkData 数组，版本感知的 count 读取 |
| `string ReadFString()` | UE 字符串，长度前缀 + 编码判断 |
| `FName ReadFName()` | FName 读取（NameMap 索引查找） |
| `int ReadIntPacked()` | 变长压缩整数（7 bit 数据 + 1 bit 继续标志） |
| `byte[] Serialize(int length)` | 原始字节块读写 |
| `byte[] SerializeCompressedNew()` | UE5 新型压缩序列化 |

#### ReadFString 实现细节

```
int length = Read<int>()
  if length > 0:  ANSI 编码，读 length-1 字节（含 null 终止符验证）
  if length < 0:  UTF-16 编码，读 |length|-1 个 short（含 null 终止符验证）
  if length == 0: 空字符串
返回去掉 null 终止符的字符串
```

#### ReadFName 实现细节 (`FAssetArchive.ReadFName`)

```
int nameIndex = ReadInt32()        // NameMap 中的索引，-1 表示 None
int extraIndex = 0
if (自定义版本 >= FNAME_CHANGE_NAME_SPLIT):
    extraIndex = ReadInt32()       // 额外的数字部分
从 Owner.NameMap 查找对应字符串，构造 FName(number, extraNumber)
```

#### 字节交换机制 (`FArchiveBigEndian`)

- 通过 `Dictionary<Type, Func<FArchive, object>>` 映射标量类型到 `BinaryPrimitives.Read*BigEndian`
- 数组使用 `ReverseEndian` 方法逐元素翻转
- **64-bit 特殊处理** (`BYTESWAP_ORDER64`): 三步法 — 相邻字节交换 → 16-bit 对交换 → 32-bit 半区交换

#### ReadBulkArray 版本分支

```
if (版本 < ADDED_BULKSERIALIZE_SANITY_CHECKS):
    count = Read<int>()                     // 旧版: 单个 count
else:
    elementSize = Read<int>()               // 新版: 元素大小 + 数量
    elementCount = Read<int>()
    校验 elementSize * elementCount == 总大小
```

### 4.2 包结构解析

#### FPackageFileSummary 字段顺序

```csharp
// 固定头部
uint Tag                   // 0x9E2A83C1 (PACKAGE_FILE_TAG)
int legacyFileVersion      // 旧版文件版本号
// 条件子版本 (根据 legacyFileVersion 正负决定顺序)
int legacyFileVersionUE3
int legacyFileVersionUE4
// UE5 版本
int FileVersionUE5         // EUEVersion.LatestUE5 + 1 时存在
int FileVersionLicenseeUE5
// 通用头部
int LicenseeVersion        // 授权版本号
// 自定义版本 (UE4.23+ / UE5+)
int CustomVersionCount
FCustomVersionEntry[] CustomVersions  // (Guid, Version) 对
// 包名
FPackageName PackageName   // (FString Name, FPackageId InstanceId, FPackageId ContentHash)
// 表信息
int NameCount, int NameOffset
int ExportCount, int ExportOffset
int ImportCount, int ImportOffset
// 条件字段 (根据版本)
bool bUnversioned          // 当 PackageFileTag 全零时设置为 true
int DependsOffset
int GenerationsCount
FGenerationInfo[] Generations
int BulkDataStartOffset    // UE4.24+
```

#### 完整解析流程

```
1. 验证 Tag (0x9E2A83C1)，失败则抛出异常
2. 读取 legacyFileVersion，决定子版本读取顺序
3. 读取 FileVersionUE5 / LicenseeUE5 (UE4.23+)
4. 读取 CustomVersion 列表 (Guid + int32 version)
5. 读取 PackageName (FString + 2x FPackageId)
6. 读取 NameCount + NameOffset → 定位并解析 NameMap (FString 数组)
7. 读取 ImportCount + ImportOffset → 解析 ImportMap (ObjectImport 数组)
8. 读取 ExportCount + ExportOffset → 解析 ExportMap (ExportBundle/Export 数组)
9. 读取 DependsOffset → 解析依赖图
10. 读取 Generations → 解析代信息
11. 条件: 读取 BulkDataStartOffset (UE4.24+)
12. 构造 Lazy<UObject>[] ExportsLazy — 延迟反序列化
```

### 4.3 UObject 对象系统

#### 层次结构

```
UObject (抽象基类)
├── UField
│   ├── UEnum                    // 枚举定义
│   ├── UStruct
│   │   ├── UClass               // 类定义
│   │   └── UScriptStruct        // 脚本结构体
│   └── UFunction                // 函数定义
├── UScriptClass                 // 脚本类 (native class wrapper)
├── UProperty 体系
│   ├── ObjectProperty           // UObject 引用
│   ├── NameProperty             // FName
│   ├── StrProperty / TextProperty
│   ├── IntProperty / FloatProperty / BoolProperty
│   ├── ArrayProperty            // 数组 (InnerType 递归)
│   ├── MapProperty              // 映射 (KeyProperty + ValueProperty)
│   ├── SetProperty              // 集合
│   ├── StructProperty           // 结构体 (UScriptStruct 引用)
│   ├── EnumProperty             // 枚举
│   ├── DelegateProperty         // 委托
│   └── ...
└── 100+ 导出类
    ├── UTexture2D / UTextureCube / UTexture2DArray
    ├── UStaticMesh / USkeletalMesh / USkeleton
    ├── UAnimSequence / UAnimMontage / UPoseAsset
    ├── USoundWave / USoundCue
    ├── UMaterial / UMaterialInterface / UMaterialInstanceConstant
    ├── AActor / ALandscape
    └── ...
```

#### UObject.Deserialize 流程

```csharp
public void Deserialize(FArchive Ar)
{
    // 1. 判断属性版本模式
    if (HasUnversionedProperties)
        DeserializePropertiesUnversioned(Ar);  // 按 UScriptClass 字段顺序读取
    else
        DeserializePropertiesTagged(Ar);       // 按 PropertyTag 驱动读取

    // 2. 读取 ObjectGuid (UE4.27+)
    if (Ar.Ver >= ObjectGuid)
        ObjectGuid = ReadGuid();

    // 3. UE5 sparse class data
    if (Ar.IsUE5Package && HasSparseClassData)
        DeserializeSparseClassData(Ar);
}
```

#### FPropertyTag 系统（属性反序列化核心）

**UE5 路径**:
```
读取 FPropertyTypeNameNode 链表 (TypeName + NextNodeOffset)
→ 解析 flags (PropertyFlags: uint64)
→ 解析 extensions (ArrayProperty 的 InnerType 等)
→ 根据 TypeName 字符串分发到 FPropertyTagType
```

**UE4 路径**:
```
PropertyType (FName)              // 类型名，如 "IntProperty", "StructProperty"
int Size                          // 属性数据大小
int ArrayIndex                    // 数组索引
byte[] TagData                    // 附加数据 (如 StructProperty 的 Guid)
Guid? Guid                        // UE4.27+ 存在
```

**类型分发 (`FPropertyTagType.TryRead`)**:
```
按 PropertyType.Name 字符串匹配:
  "IntProperty"      → IntProperty
  "FloatProperty"    → FloatProperty
  "BoolProperty"     → BoolProperty
  "NameProperty"     → NameProperty
  "ObjectProperty"   → ObjectProperty
  "StrProperty"      → StrProperty
  "TextProperty"     → TextProperty
  "ArrayProperty"    → ArrayProperty (递归 InnerType)
  "MapProperty"      → MapProperty (KeyProperty + ValueProperty)
  "StructProperty"   → StructProperty (按 StructType 名查找 UScriptStruct)
  "EnumProperty"     → EnumProperty (InnerType + Enum 名)
  "SetProperty"      → SetProperty
  "DelegateProperty" → DelegateProperty
  "MulticastDelegateProperty" → MulticastDelegateProperty
  "FieldPathProperty" → FieldPathProperty
  ... 20+ 种类型
```

#### 关键导出类序列化细节

**UTexture2D**:
```
1. ImportedSize (FIntPoint)
2. AddressX, AddressY (纹理寻址模式)
3. bCooked (bool) → if true:
   for each pixel format block:
     PixelFormat (EPixelFormat enum)
     bIsSrgb (bool)
     FCompressedTexture2DPlatformData → 读取每个 MIP 的 BulkData
```

**UStaticMesh**:
```
1. bCooked (bool)
2. if cooked:
   FStaticMeshRenderData:
     → int LODCount
     → for each LOD: FStaticMeshLODResources
       → PositionVertexBuffer (FVector[] + Stride)
       → VertexBuffer (UVs, Normals, Tangents)
       → ColorVertexBuffer (FColor[])
       → IndexBuffer (uint16[] / uint32[])
       → Sections (MaterialIndex, TriangleRange)
     → NaniteResources (UE5): ZOrder 编码顶点 + 多层 LOD cluster 数据
3. StaticMaterials (UMaterialInterface 引用数组)
4. NavCollision (可选)
```

**USkeletalMesh**:
```
1. bCooked (bool)
2. if cooked:
   for each LOD:
     SerializeRenderItem() 或 SerializeRenderItem_Legacy():
       → LODModels: FReferenceSkeleton (骨骼层级)
       → VertexBufferGPUSkin:
         · 半精度位置 (FVectorHalf / FVector) 取决于版本
         · 半精度切线 (TangentX, TangentZ, UVs)
         · 骨骼索引 + 权重 (每顶点 1~4 骨骼)
       → Chunks / Sections: 骨骼映射 + 材质索引
   UE5.5+: FNaniteResources (Nanite 骨骼网格)
```

**USoundWave**:
```
1. bStreaming (bool)
2. if not streaming:
   CompressedFormatData: Dict<FName, byte[]>  // 按平台压缩格式存储
   RawData: byte[]                            // 未压缩 PCM
3. if streaming:
   CompressedDataGuid: Guid                   // 外部引用
   SerializeCookedPlatformData(Ar)            // 流式平台数据
```

### 4.4 Kismet 蓝图字节码

#### FKismetArchive 架构

包装 `byte[] ScriptBytecode`，从 `UStruct` 的字节码字段提取。核心方法 `ReadExpression()` 读取单个字节作为 `EExprToken`，然后通过 switch-case 分发到 ~115 个 `KismetExpression` 子类。

#### EExprToken 关键枚举值

| Token | 十六进制 | 含义 |
|-------|----------|------|
| `EX_LocalVariable` | 0x00 | 局部变量 |
| `EX_InstanceVariable` | 0x01 | 实例变量 |
| `EX_DefaultVariable` | 0x02 | 默认变量 |
| `EX_Return` | 0x04 | 函数返回 |
| `EX_Jump` | 0x08 | 无条件跳转 |
| `EX_JumpIfNot` | 0x09 | 条件跳转 |
| `EX_Assert` | 0x0A | 断言 |
| `EX_Nothing` | 0x0B | 空操作 |
| `EX_Let` | 0x0F | 赋值 |
| `EX_Context` | 0x18 | 上下文调用 (对象.方法) |
| `EX_Context_FailSilent` | 0x19 | 静默失败上下文 |
| `EX_VirtualFunction` | 0x1D | 虚函数调用 |
| `EX_FinalFunction` | 0x1E | 终态函数调用 |
| `EX_IntConst` | 0x1F | int 常量 |
| `EX_FloatConst` | 0x20 | float 常量 |
| `EX_StringConst` | 0x21 | 字符串常量 |
| `EX_ObjectConst` | 0x22 | 对象常量 |
| `EX_StructConst` | 0x2B | 结构体常量 |
| `EX_EndStructConst` | 0x2C | 结构体常量结束 |
| `EX_SetArray` | 0x2D | 数组赋值 |
| `EX_EndArray` | 0x2E | 数组结束 |
| `EX_EndFunctionParms` | 0x30 | 函数参数结束 |
| `EX_Self` | 0x31 | self 引用 |
| `EX_EndOfScript` | 0x41 | 字节码结束 |
| `EX_CrossInterface` | 0x48 | 跨接口调用 |
| `EX_SwitchValue` | 0x53 | switch 表达式 |

#### 关键表达式结构

**EX_Context** (对象.属性/方法访问):
```
ObjectExpression: KismetExpression    // 计算上下文对象
int Offset                          // 跳转偏移 (如果上下文为 null)
KismetExpression RValuePointer       // 在上下文中计算的表达式
```

**EX_Let** (赋值):
```
Property: KismetExpression           // 目标属性
Variable: KismetExpression           // 被赋值的变量
Assignment: KismetExpression          // 赋值表达式
```

**EX_FinalFunction** (函数调用):
```
StackNode: KismetExpression          // 函数引用 (UFunction*)
Parameters: KismetExpression[]        // 参数列表，直到 EX_EndFunctionParms
```

**EX_StructConst** (结构体字面量):
```
Struct: UScriptStruct               // 结构体类型
int StructSize                      // 结构体大小
Properties: KismetExpression[]       // 字段初始化，直到 EX_EndStructConst
```

**EX_SwitchValue** (switch 表达式):
```
int numCases                        // case 数量
int EndGotoOffset                   // 结束跳转偏移
Cases: (Term, KismetExpression)[]   // 匹配值 + 表达式对
DefaultTerm: KismetExpression        // 默认分支
```

#### 游戏特殊 Token

某些游戏在标准 EExprToken 之上添加自定义 token:
- **WuWa (鸣潮)**: `EX_6E`, `EX_6F`
- **Borderlands4 / 2XKO**: `EX_FD`, `EX_F9`, `EX_FE`

### 4.5 游戏特定覆盖机制

#### 加密覆盖

通过 `CustomEncryption` 委托实现 per-game 解密:

```csharp
// 20+ 游戏有自定义加密
ApexLegendsMobile:  AES 变体密钥
Snowbreak:          自定义 XOR
MarvelRivals:       AES-CBC 变体
Undawn:             多层加密
DeadByDaylight:     自定义密钥派生
```

#### PAK 版本覆盖

使用 `UsingCustomPakVersion()` 跳过标准版本校验:

```csharp
// 游戏特殊 FPakInfo magic 值
InfinityNikki:      自定义 magic
MeetYourMaker:      自定义 magic + 字段顺序
WuWa:               自定义 magic + 偏移计算
```

#### Package 特殊处理

```csharp
TowerOfFantasy:     头部 XOR 解密 (key: 0xEEB2CEC7)
SeaOfThieves:       跳过 6 字节头部
GearsOfWar4:        跳过 6 字节头部
DeltaForce:         版本号除以 659
```

#### 版本行为选择

```csharp
Ar.Game switch {
    EGame.GAME_UE5_5              → UE5.5 特殊字段处理
    EGame.GAME_RocoKingdomWorld   → 腾讯罗布乐思特殊处理
    EGame.GAME_Fortnite           → Epic 游戏特殊逻辑
    _                             → 默认行为
}
```

### 4.6 VFS/Pak 系统

#### 继承链

```
AbstractVfsReader
└── AbstractAesVfsReader
    ├── PakFileReader          // .pak 文件
    └── IoStoreReader          // UE5 IoStore (.utoc/.ucas)
```

#### Pak 文件结构

```
[文件头] → 游戏特定 magic (可选)
[Entry 表] → 文件名 → 偏移量 + 大小 + 压缩标志
[FPakInfo] → 文件末尾，Magic: 0x5A6F12E1
             → 版本 1~12
             → AES Key (32 bytes)
             → 多偏移试探读取 (末尾 - 不同偏移量)
```

**PakFileReader 解析**:
```
v10+:  ReadIndexUpdated — 高效索引格式
旧版:  ReadIndexLegacy — 传统条目遍历
Extract 流程:
  1. 定位条目偏移
  2. 游戏特殊解密 (AES/XOR/Custom)
  3. 解压压缩块 (Oodle/LZ4/Zstd)
  4. 返回原始字节
```

#### IoStore (.utoc/.ucas)

```
.utoc: FIoStoreTocResource
  → Chunk ID 表
  → 偏移量 + 大小
  → 压缩块信息
  → 目录索引 (哈希查找)
.ucas: 实际数据存储
  → 按 Chunk ID 寻址
  → 完美哈希 O(1) 查找
  → 分区容器支持
```

### 4.7 转换层 (CUE4Parse-Conversion)

#### 纹理解码

```
1. 获取 MIP BulkData (byte[])
2. 平台反交错 (Deswizzle):
   · Xbox: XBPS 格式解包
   · Nintendo: Switch 特有顺序
3. 按 EPixelFormat 解码:
   · DXT1: 4x4 块，64 bit/块，1:4 压缩
   · DXT3: 4x4 块，128 bit/块 (显式 alpha)
   · DXT5: 4x4 块，128 bit/块 (插值 alpha)
   · BC4: 单通道压缩 (R)
   · BC5: 双通道压缩 (RG, 法线贴图)
   · BC6H: HDR 压缩 (16 bit)
   · BC7: 高质量 RGB/RGBA (3~8 bit/分量)
   · ASTC: 自适应 (4x4 ~ 12x12 块大小)
   · ETC1/2: Android 标准
4. 输出 RGBA byte[]
```

#### 网格转换

**StaticMesh 导出流程**:
```
1. 遍历 LODs (FStaticMeshLODResources)
2. 提取:
   · PositionVertexBuffer → FVector[] 顶点位置
   · VertexBuffer → UVs (FVector2D[]), Normals (FVector[]), Tangents
   · ColorVertexBuffer → FColor[] (可选)
   · IndexBuffer → uint16[] / uint32[] 索引
   · Sections → 材质索引 + 三角范围
3. Nanite LOD: 并行处理 clusters
   · 解码 ZOrder 编码顶点
   · 重建三角形拓扑
4. 按目标格式输出:
   · ActorX (.psk/.pskx): 二进制格式，顶点 + 面 + 材质槽
   · glTF (.glb): JSON + 二进制 buffer
   · OBJ (.obj): 文本格式，v/vt/vn/f
```

**SkeletalMesh 特殊处理**:
```
1. 骨骼层级 (FReferenceSkeleton): 骨骼名 + 父索引 + 变换矩阵
2. 顶点权重: 每顶点 1~4 骨骼索引 + 权重 (需归一化到 0~1)
3. LODModels: 每 LOD 的顶点/索引缓冲区
4. Morph Targets: 顶点位置偏移量
```

#### 音频解码

```
USoundWave / USoundNodeWave / UAkMediaAssetData:
  检测格式 → 选择解码器:
    OGG/Vorbis  →  libvorbis 解码
    WEM         →  Wwise 流解析
    ADPCM       →  微软 ADPCM 解码 (4:1 压缩)
    PCM         →  直接包装
    BINKA       →  Bink Audio 解码
    RADA        →  RAD 音频
    OPUS        →  libopus 解码
    AT9         →  PS5 ATRAC9 解码
  输出 → WAV (PCM 包装) 或 OGG (重新编码)
```

## 5. 版本管理系统

### VersionContainer 结构

```csharp
public class VersionContainer
{
    public EGame Game { get; set; }                    // 游戏枚举 (70+ 游戏)
    public FPackageFileVersion Ver { get; set; }       // UE4/UE5 版本
    public FCustomVersionContainer? CustomVersions { get; set; }
    // 游戏特定标志 (字符串键索引)
    public object this[string key] { get; set; }
}
```

### CustomVersion 查询模式

```csharp
// 通过字符串键查询游戏特定标志
Ar.Versions["SkeletalMesh.UseNewCookedFormat"]
Ar.Versions["Animation.ModifySerializeLayout"]
Ar.Versions["Material.CachedExpressionData"]

// 版本范围分支
if (Ar.Ver >= EUEVersion.UE4_23):
    // UE4.23+ 的行为
else:
    // 旧版行为
```

### EGame 枚举 (部分)

```
GAME_UE4_0 ~ GAME_UE4_27     // UE4 全版本
GAME_UE5_0 ~ GAME_UE5_5      // UE5 全版本
GAME_Fortnite
GAME_PUBG
GAME_Apex
GAME_Borderlands3 / GAME_Borderlands4
GAME_Valorant
GAME_BG3
GAME_RocoKingdomWorld          // 罗布乐思
GAME_Snowbreak
GAME_TowerOfFantasy
GAME_DeadByDaylight
GAME_InfinityNikki
... 70+ 游戏
```

## 6. 压缩系统

| 算法 | 实现 | 使用场景 |
|------|------|----------|
| **Zlib** | `ZlibHelper` | 通用压缩 (COMPRESS_ZLIB) |
| **Gzip** | `System.IO.Compression` | 标准 gzip 流 |
| **Oodle** | `Oodle.NET` (C 原生库) | UE4.25+ 默认游戏压缩 |
| **LZ4** | `LZ4Codec` / 原生 | 快速压缩 (COMPRESS_LZ4) |
| **Zstd** | `ZstdSharp` | 高压缩比 (COMPRESS_ZSTD) |

**FCompressedChunk** 结构:
```
int CompressedSize
int UncompressedSize
ECompressionFlags CompressionFlags  // COMPRESS_ZLIB / COMPRESS_LZ4 / ...
byte[] CompressedData
```

## 7. 加密系统

| 算法 | 实现 | 应用 |
|------|------|------|
| **AES-ECB** | `Aes.cs` (BouncyCastle) | 标准 PAK 加密 |
| **AES-CBC** | 游戏特定变体 | Fortnite / 部分游戏 |
| **XOR** | `ACE7XORKey` 等 | 轻量加密 |
| **Lua 加密** | 游戏特定脚本 | 少数游戏 |

**AES 解密流程**:
```
1. 从 FPakInfo 读取 32 字节 AES Key
2. 按 16 字节块 AES-ECB 解密
3. 某些游戏使用 AES-CBC (需要 IV)
```

## 8. 性能优化策略

| 技术 | 实现 | 效果 |
|------|------|------|
| **懒加载** | `Lazy<UObject>[] ExportsLazy` | 按需反序列化，减少内存峰值 |
| **内存池** | `ArrayPool<byte>.Shared.Rent(size)` | 减少 GC 压力 |
| **零分配读取** | `Unsafe.ReadUnaligned<T>()` / `Memory<byte>` | 避免中间对象分配 |
| **并行处理** | `Parallel.ForEach` (网格转换/纹理导出) | 多核加速 3-5x |
| **原生库** | Oodle / ACL / TextureDecoder (C DLL) | 解码性能 > 纯 C# |
| **Span<T>** | `Span<byte>` 切片操作 | 零拷贝子串提取 |

## 9. 扩展机制

| 扩展点 | 接口/委托 | 用途 |
|--------|-----------|------|
| **类型映射** | `ITypeMappingsProvider` | 自定义未版本化属性类型名称映射 |
| **自定义加密** | `CustomEncryptionDelegate` | 注入游戏特定解密算法 `(path, data) → decrypted` |
| **虚拟路径** | `VirtualPaths` 字典 | 映射 mods/content 目录到游戏路径 |
| **游戏分支** | `Ar.Game switch` 表达式 | 按游戏选择不同序列化行为 |
| **PAK 版本** | `UsingCustomPakVersion()` | 覆盖标准 FPakInfo 格式 |

## 10. 外部依赖

| NuGet 包 | 版本约束 | 用途 |
|----------|----------|------|
| Newtonsoft.Json | ≥13.0 | JSON 序列化/反序列化 |
| Serilog | ≥3.0 | 结构化日志 |
| Zlib-ng.NET | - | Zlib 压缩 |
| LZMA-SDK | - | LZMA 压缩 |
| ZstdSharp.Port | - | Zstd 压缩 |
| Blake3 | - | 哈希校验 (IoStore) |
| BouncyCastle.Cryptography | ≥2.0 | AES 加密实现 |
| VGAudio | - | 音频解码 (ADPCM/AT9/BINKA) |
| TextureDecoder (assetripper) | - | 纹理解码 (DXT/BC/ASTC) |
| Oodle.NET | - | Oodle 压缩 (C 绑定) |

## 11. 与 uasset_read 项目的对比与参考

### 架构对比

| 维度 | CUE4Parse | uasset_read |
|------|-----------|-------------|
| **语言** | C# (.NET 8.0) | Python 3.10+ |
| **定位** | 游戏资源提取 + 3D 导出 | AI 代理蓝图语义读取 |
| **蓝图处理** | Kismet 字节码反编译为表达式树 | 节点/连接语义提取 + N2C 中间格式 |
| **3D 导出** | psk/glb/png/wav (Conversion 层) | N2C JSON + C++ 骨架生成 |
| **包解析** | Package + IoPackage 双模式 | Package 模式 (两阶段: Linker + Preload) |
| **版本覆盖** | UE4.0 ~ UE5.5 + 70+ 游戏 | UE4.23 ~ UE5.3 核心版本 |
| **性能** | 原生库 + 并行 + 零分配 | 纯 Python，mmap 优化 |

### 可借鉴的实现模式

1. **PropertyTag 类型分发**: CUE4Parse 按字符串名分发到不同 Property 类的模式，与 uasset_read 的 `property_parsers` 字典分派高度一致
2. **懒加载 Export**: `Lazy<UObject>[]` 模式可参考到 Python 的 `property` 延迟反序列化
3. **版本行为选择**: `VersionContainer` + `switch` 模式已在 uasset_read 的 `FArchive` 中部分实现
4. **游戏特定覆盖**: `CustomEncryption` 委托模式可参考用于处理特定游戏的 uasset 变体
5. **Kismet 表达式树**: EExprToken → KismetExpression 的 switch 分派模式，对 uasset_read 的字节码解析有参考价值

### 关键差异

| 差异点 | 说明 |
|--------|------|
| 反序列化深度 | CUE4Parse 反序列化完整对象树；uasset_read 侧重语义提取而非完整还原 |
| 3D 数据处理 | CUE4Parse 提取完整顶点/索引缓冲区；uasset_read 仅提取节点连接关系 |
| 加密/压缩 | CUE4Parse 支持 Oodle/AES 等完整解密流程；uasset_read 假设未加密输入 |
| 导出目标 | CUE4Parse 输出可直接导入 DCC 工具的格式；uasset_read 输出 AI 可读的中间表示 |

## 12. 源码文件索引

核心源码文件位置（供深入阅读时参考）:

| 模块 | 关键文件 |
|------|----------|
| FArchive | `CUE4Parse/UE4/Readers/FArchive.cs` |
| 大端序 | `CUE4Parse/UE4/Readers/FArchiveBigEndian.cs` |
| 资产归档 | `CUE4Parse/UE4/Assets/Readers/FAssetArchive.cs` |
| 包摘要 | `CUE4Parse/UE4/Objects/UObject/FPackageFileSummary.cs` |
| UObject 基类 | `CUE4Parse/UE4/Assets/Exports/UObject.cs` |
| 属性标签 | `CUE4Parse/UE4/Assets/Objects/FPropertyTag.cs` |
| 属性类型 | `CUE4Parse/UE4/Assets/Objects/FPropertyTagType.cs` |
| BulkData | `CUE4Parse/UE4/Assets/Objects/TBulkData.cs` |
| 纹理 | `CUE4Parse/UE4/Assets/Exports/Texture/UTexture2D.cs` |
| 静态网格 | `CUE4Parse/UE4/Assets/Exports/StaticMesh/UStaticMesh.cs` |
| 骨骼网格 | `CUE4Parse/UE4/Assets/Exports/SkeletalMesh/USkeletalMesh.cs` |
| 音频 | `CUE4Parse/UE4/Assets/Exports/Sound/USoundWave.cs` |
| Kismet | `CUE4Parse/UE4/Assets/Readers/FKismetArchive.cs` |
| 表达式 Token | `CUE4Parse/UE4/Kismet/EExprToken.cs` |
| Pak 信息 | `CUE4Parse/UE4/Pak/Objects/FPakInfo.cs` |
| Pak 读取器 | `CUE4Parse/UE4/Pak/PakFileReader.cs` |
| IoStore | `CUE4Parse/UE4/IO/IoStoreReader.cs` |
| AES VFS | `CUE4Parse/UE4/VirtualFileSystem/AbstractAesVfsReader.cs` |
| 版本容器 | `CUE4Parse/UE4/Versions/VersionContainer.cs` |
