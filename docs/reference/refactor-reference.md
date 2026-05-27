# 重构参考文档：CUE4Parse 解析策略 + 蓝图节点文本格式

> 生成日期：2026-05-27
> 目标：为后续 FArchive / Property Parser / Kismet / Blueprint Node 重构提供权威参考
> 参考源 1：E:\Develop\uasset_read\docs\references\CUE4Parse
> 参考源 2：E:\Develop\uasset_read\docs\references\蓝图节点文本参考.md
> 目标 uasset：E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\FirstPerson\Blueprints\BP_FirstPersonCharacter.uasset

---

## 1. CUE4Parse 架构摘要

CUE4Parse 采用 C# 构建，核心架构遵循 UE 引擎的 FArchive 序列化模式：

```
FArchive (抽象基类，继承自 RandomAccessStream)
  ├── FAssetArchive (uasset/uexp 读取，持有 IPackage 引用)
  ├── FKismetArchive (字节码读取，内存字节数组)
  ├── FArchiveLoadCompressedProxy (按需解压缩代理)
  └── FArchiveBigEndian (大端序变体)

Package (IPackage 实现)
  ├── FPackageFileSummary (包头)
  ├── FNameEntrySerialized[] NameMap
  ├── FObjectImport[] ImportMap
  ├── FObjectExport[] ExportMap
  ├── FPackageIndex[][]? DependsMap
  └── FPackageIndex[]? PreloadDependencies
```

### 核心设计模式

1. **FArchive 作为序列化基类**：所有数据读取通过 `Read<T>()` 泛型方法，利用 `Unsafe.SizeOf<T>()` + `Unsafe.ReadUnaligned<T>()` 直接映射内存布局
2. **版本条件序列化**：每个字段读取都包裹在 `if (Ar.Ver >= EUnrealEngineObjectUE4Version.XXX)` 条件中
3. **Lazy vs Eager 加载**：通过 `useLazySerialization` 参数控制，Lazy 模式使用 `Lazy<UObject>` 包装，Eager 模式使用 `ExportLoader` 两阶段（Create + Serialize）加载
4. **FPackageIndex 统一索引**：正数 = ExportMap 索引-1，负数 = ImportMap 索引取反-1，零 = None
5. **Property 类型分派**：基于 `propertyType` 字符串的 switch 表达式映射到具体 `FPropertyTagType` 子类

---

## 2. FArchive 实现模式

### 2.1 字节序

- UE 包默认 **小端序 (little-endian)**
- `PACKAGE_FILE_TAG_SWAPPED` (0xC1832A9E) 标记大端序包，CUE4Parse 直接抛出异常不支持
- Python 项目应使用 `<` 格式符（struct 模块）进行小端序读取

### 2.2 核心读取方法（C# 代码片段）

```csharp
// 泛型读取 — 直接内存映射
public virtual T Read<T>() {
    var size = Unsafe.SizeOf<T>();
    var buffer = ReadBytes(size);
    return Unsafe.ReadUnaligned<T>(ref buffer[0]);
}

// 布尔读取 — UE 标准 4-byte bool
public virtual bool ReadBoolean() {
    var i = Read<int>();
    return i switch { 0 => false, 1 => true, _ => throw new ParserException(...) };
}

// 1-byte flag（紧凑模式，用于 PropertyTag 等）
public bool ReadFlag() {
    var i = Read<byte>();
    return i switch { 0 => false, 1 => true, _ => throw new ParserException(...) };
}

// FString — >0=ANSI, <0=UCS2
public virtual string ReadFString() {
    var length = Read<int>();
    if (length == 0) return string.Empty;
    if (length < 0) { // UCS2 (UTF-16)
        length = -length;
        var ucs2Length = length * sizeof(ushort);
        var ucs2Bytes = stackalloc byte[ucs2Length];
        Serialize(ucs2BytesPtr, ucs2Length);
        // 验证 null terminator: ucs2Bytes[ucs2Length-2] == 0 && ucs2Bytes[ucs2Length-1] == 0
        return new string((char*)ucs2BytesPtr, 0, length - 1);
    } else { // ANSI (UTF-8)
        var ansiBytes = stackalloc byte[length];
        Serialize(ansiBytesPtr, length);
        // 验证 null terminator: ansiBytes[length-1] == 0
        return new string((sbyte*)ansiBytesPtr, 0, length - 1);
    }
}

// FName — 从名称表索引（Kismet 中直接从 nameMap 读取字符串）
public virtual FName ReadFName() => new(ReadFString());  // 通用 FArchive
// FKismetArchive 中：
public override FName ReadFName() {
    var nameIndex = Read<int>();
    var extraIndex = Ver >= UE3.FNAME_CHANGE_NAME_SPLIT ? Read<int>() : 0;
    Index += 4; // 跳过额外 4 字节（与 nameIndex 同步）
    return new FName(Owner.NameMap[nameIndex], nameIndex, extraIndex);
}

// 数组读取（struct 类型 — 直接内存拷贝）
public T[] ReadArray<T>(int length) where T : struct {
    var size = Unsafe.SizeOf<T>();
    var buffer = ReadBytes(size * length);
    var result = new T[length];
    Unsafe.CopyBlockUnaligned(ref Unsafe.As<T, byte>(ref result[0]), ref buffer[0], (uint)(size * length));
    return result;
}

// 数组读取（引用类型 — 逐元素调用 getter）
public T[] ReadArray<T>(int length, Func<T> getter) {
    var result = new T[length];
    for (int i = 0; i < length; i++) result[i] = getter();
    return result;
}

// IntPacked 读取（变长编码，用于 BulkData 等）
public uint ReadIntPacked() {
    uint value = 0; byte cnt = 0; bool more = true;
    while (more) {
        var nextByte = Read<byte>();
        more = (nextByte & 1) != 0;
        nextByte = (byte)(nextByte >> 1);
        value += (uint)(nextByte << (7 * cnt++));
    }
    return value;
}

// 7-bit Encoded Int（用于 C# String 等）
public int Read7BitEncodedInt() {
    int count = 0, shift = 0; byte b;
    do {
        b = Read<byte>();
        count |= (b & 0x7F) << shift;
        shift += 7;
    } while ((b & 0x80) != 0);
    return count;
}

// FReal — LWC 感知
public float ReadFReal() => Ver >= UE5.LARGE_WORLD_COORDINATES ? (float)Read<double>() : Read<float>();
```

### 2.3 FAssetArchive 特点

```csharp
public class FAssetArchive : FArchive {
    private FArchive _baseArchive;           // 底层流（FileStream / MemoryStream）
    public readonly IPackage? Owner;         // 所属 Package
    public int AbsoluteOffset;               // 绝对偏移（用于 uexp 文件定位）
    public bool HasUnversionedProperties => Owner?.HasFlags(PKG_UnversionedProperties);
    public bool IsFilterEditorOnly => Owner?.HasFlags(PKG_FilterEditorOnly);
    public bool IsLoadingFromCookedPackage => Owner?.HasFlags(PKG_Cooked);
}
```

- 所有读取委托给 `_baseArchive`
- `AbsoluteOffset` 用于在 uexp 文件中正确定位 Export 数据
- 支持 Payload 系统（UBULK/UPTNL）

---

## 3. PackageFileSummary 解析流程

### 3.1 读取顺序

```
1. Tag (uint32) — 0x9E2A83C1
2. legacyFileVersion (int32) — 必须 >= -9
3. 如果 legacyFileVersion < 0 (现代版本):
   a. FileVersionUE3 (int32) — legacyFileVersion != -4 时读取
   b. FileVersionUE4 (int32)
   c. FileVersionUE5 (int32) — legacyFileVersion <= -8 时读取
   d. FileVersionLicenseeUE (int32 enum)
   e. SavedHash (SHAHash) — UE5 PACKAGE_SAVED_HASH 之后
   f. TotalHeaderSize (int32)
   g. CustomVersionContainer
4. PackageName (FString)
5. PackageFlags (uint32 enum)
6. NameCount (int32)
7. NameOffset (int32)
8. SoftObjectPathsCount/Offset — UE5 ADD_SOFTOBJECTPATH_LIST 之后
9. LocalizationId (FString) — 非 FilterEditorOnly + ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID
10. GatherableTextDataCount/Offset — SERIALIZE_TEXT_IN_PACKAGES 之后
11. ExportCount (int32)
12. ExportOffset (int32)
13. ImportCount (int32)
14. ImportOffset (int32)
15. CellExportCount/Offset, CellImportCount/Offset — VERSE_CELLS 之后
16. MetaDataOffset — METADATA_SERIALIZATION_OFFSET 之后
17. DependsOffset (int32)
18. ... 更多可选字段 ...
```

### 3.2 关键版本条件

| 版本常量 | 条件 | 影响字段 |
|---------|------|---------|
| `EUnrealEngineObjectUE4Version.e64BIT_EXPORTMAP_SERIALSIZES` | Ver >= | ExportMap SerialSize/SerialOffset 从 int32 升级为 int64 |
| `EUnrealEngineObjectUE5Version.PROPERTY_TAG_COMPLETE_TYPE_NAME` | UE5 | PropertyTag 使用完整类型树（FPropertyTypeNameNode） |
| `EUnrealEngineObjectUE5Version.SCRIPT_SERIALIZATION_OFFSET` | UE5 | ExportMap 中 ScriptSerializationStart/EndOffset |
| `EUnrealEngineObjectUE5Version.ADD_SOFTOBJECTPATH_LIST` | UE5 | Summary 中 SoftObjectPathsCount/Offset |
| `EUnrealEngineObjectUE4Version.PROPERTY_GUID_IN_PROPERTY_TAG` | UE4.12+ | PropertyTag 中 PropertyGuid |

---

## 4. ImportMap / ExportMap 加载

### 4.1 FObjectImport 结构

```
ClassPackage    (FName)
ClassName       (FName)
OuterIndex      (FPackageIndex)
ObjectName      (FName)
PackageName     (FName) — NON_OUTER_PACKAGE_IMPORT 之后，非 FilterEditorOnly
ImportOptional  (bool) — UE5 OPTIONAL_RESOURCES 之后
```

### 4.2 FObjectExport 结构

```
ClassIndex      (FPackageIndex)
SuperIndex      (FPackageIndex)
TemplateIndex   (FPackageIndex) — TemplateIndex_IN_COOKED_EXPORTS 之后
OuterIndex      (FPackageIndex)
ObjectName      (FName)
ObjectFlags     (uint32)
SerialSize      (int32/int64) — 版本决定
SerialOffset    (int32/int64) — 版本决定
ForcedExport    (bool)
NotForClient    (bool)
NotForServer    (bool)
PackageGuid     (FGuid) — 移除之前
IsInheritedInstance (bool) — TRACK_OBJECT_EXPORT_IS_INHERITED
PackageFlags    (uint32)
NotAlwaysLoadedForEditorGame (bool)
IsAsset         (bool)
GeneratePublicHash (bool) — OPTIONAL_RESOURCES 之后
FirstExportDependency / SerializationBeforeSerializationDependencies / ... — PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS
ScriptSerializationStartOffset / EndOffset — 非 HasUnversionedProperties + SCRIPT_SERIALIZATION_OFFSET
ClassName       (从 ClassIndex 推导)
```

### 4.3 加载流程（CUE4Parse Package.cs）

```csharp
// 1. 读取 Summary
Summary = new FPackageFileSummary(uassetAr);

// 2. 读取 NameMap
uassetAr.SeekAbsolute(Summary.NameOffset, SeekOrigin.Begin);
NameMap = new FNameEntrySerialized[Summary.NameCount];
uassetAr.ReadArray(NameMap, () => new FNameEntrySerialized(uassetAr));

// 3. 读取 ImportMap
uassetAr.SeekAbsolute(Summary.ImportOffset, SeekOrigin.Begin);
ImportMap = uassetAr.ReadArray(ImportMap, () => new FObjectImport(uassetAr));

// 4. 读取 ExportMap
uassetAr.SeekAbsolute(Summary.ExportOffset, SeekOrigin.Begin);
ExportMap = uassetAr.ReadArray(ExportMap, () => new FObjectExport(uassetAr));

// 5. Lazy 模式下注册导出加载器
for (var i = 0; i < ExportsLazy.Length; i++) {
    ExportsLazy[i] = new Lazy<UObject>(() => {
        // Create: 构造 UObject 外壳
        var obj = ConstructObject(ResolvePackageIndex(export.ClassIndex), ...);
        // Serialize: 定位到 SerialOffset 并反序列化
        var Ar = (FAssetArchive) uexpAr.Clone();
        Ar.SeekAbsolute(export.SerialOffset, SeekOrigin.Begin);
        DeserializeObject(obj, Ar, export.SerialSize);
        obj.PostLoad();
        return obj;
    });
}
```

### 4.4 FPackageIndex 索引规则

```
Index > 0  → ExportMap[Index - 1]
Index < 0  → ImportMap[-Index - 1]
Index == 0 → Null (None)
```

---

## 5. 属性解析器映射表

### 5.1 类型分派机制

CUE4Parse 使用 **字符串匹配的 switch 表达式** 将 PropertyType 映射到具体解析器：

```csharp
// FPropertyTagType.ReadPropertyTagType() 核心逻辑
var tagType = propertyType switch {
    "ArrayProperty"     => new ArrayProperty(Ar, tagData, type, size),
    "BoolProperty"      => new BoolProperty(Ar, tagData, type),
    "ByteProperty"      => (tagData.EnumName != null) ? new EnumProperty(...) : new ByteProperty(...),
    "ClassProperty"     => new ClassProperty(Ar, type),
    "DelegateProperty"  => new DelegateProperty(Ar, type),
    "DoubleProperty"    => new DoubleProperty(Ar, type),
    "EnumProperty"      => new EnumProperty(Ar, tagData, type),
    "FloatProperty"     => new FloatProperty(Ar, type),
    "IntProperty"       => new IntProperty(Ar, type),
    "Int64Property"     => new Int64Property(Ar, type),
    "Int16Property"     => new Int16Property(Ar, type),
    "Int8Property"      => new Int8Property(Ar, type),
    "MapProperty"       => new MapProperty(Ar, tagData, type),
    "NameProperty"      => new NameProperty(Ar, type),
    "ObjectProperty"    => new ObjectProperty(Ar, type),
    "SetProperty"       => new SetProperty(Ar, tagData, type),
    "SoftObjectProperty"=> new SoftObjectProperty(Ar, type),
    "StrProperty"       => new StrProperty(Ar, type),
    "Utf8StrProperty"   => new Utf8StrProperty(Ar, type),
    "StructProperty"    => new StructProperty(Ar, tagData, type),
    "TextProperty"      => new TextProperty(Ar, type),
    "WeakObjectProperty"=> new WeakObjectProperty(Ar, type),
    "OptionalProperty"  => new OptionalProperty(Ar, tagData, type),
    "LazyObjectProperty"=> new LazyObjectProperty(Ar, type),
    "InterfaceProperty" => new InterfaceProperty(Ar, type),
    "FieldPathProperty" => new FieldPathProperty(Ar, type),
    "MulticastDelegateProperty"       => new MulticastDelegateProperty(Ar, type),
    "MulticastInlineDelegateProperty" => new MulticastInlineDelegateProperty(Ar, type),
    "MulticastSparseDelegateProperty" => new MulticastSparseDelegateProperty(Ar, type),
    "SoftClassProperty"               => new SoftObjectProperty(Ar, type),
    "AssetObjectProperty"             => new AssetObjectProperty(Ar, type),
    "AssetClassProperty"              => new AssetObjectProperty(Ar, type),
    "VerseClassProperty"              => new VerseClassProperty(Ar, type),
    "VerseStringProperty"             => new VerseStringProperty(Ar, type),
    _ => null
};
```

### 5.2 完整属性类型映射表

| 类型名 | C# 类 | 读取方式 | Python 已有 |
|--------|-------|---------|------------|
| BoolProperty | BoolProperty | tagData.Bool / 从 flags 提取 | 有 |
| ByteProperty | ByteProperty | Read<u8>() | 有 |
| Int8Property | Int8Property | Read<u8>() | 有 |
| Int16Property | Int16Property | Read<i16>() | 有 |
| IntProperty | IntProperty | Read<i32>() | 有 |
| Int64Property | Int64Property | Read<i64>() | 有 |
| UInt16Property | UInt16Property | Read<u16>() | 有 |
| UInt32Property | UInt32Property | Read<u32>() | 有 |
| UInt64Property | UInt64Property | Read<u64>() | 有 |
| FloatProperty | FloatProperty | Read<float>() | 有 |
| DoubleProperty | DoubleProperty | Read<double>() | 有 |
| StrProperty | StrProperty | ReadFString() | 有 |
| Utf8StrProperty | Utf8StrProperty | ReadFUtf8String() | 无 |
| NameProperty | NameProperty | ReadFName() | 有 |
| EnumProperty | EnumProperty | ReadFName() | 有 |
| ObjectProperty | ObjectProperty | new FPackageIndex(Ar) → Read<i32>() | 有 (仅 i32) |
| ClassProperty | ClassProperty | new FPackageIndex(Ar) → Read<i32>() | 无 (复用 ObjectProperty) |
| WeakObjectProperty | WeakObjectProperty | new FPackageIndex(Ar) → Read<i32>() | 无 |
| LazyObjectProperty | LazyObjectProperty | new FPackageIndex(Ar) → Read<i32>() | 无 |
| SoftObjectProperty | SoftObjectProperty | ReadFString() + ReadFString() (asset_path + sub_path) | 有 |
| SoftClassProperty | SoftObjectProperty | 同上 | 无 (复用 SoftObjectProperty) |
| ArrayProperty | ArrayProperty | Read<i32>() count + 循环 parse | 有 |
| StructProperty | StructProperty | FScriptStruct (fast-path 或 PropertyTag 循环) | 有 (fast-path) |
| MapProperty | MapProperty | Read<i32>() entries + Key/Value 对 | 有 |
| SetProperty | SetProperty | Read<i32>() elements | 有 |
| DelegateProperty | DelegateProperty | FPackageIndex + ReadFName() | 有 |
| MulticastDelegateProperty | MulticastDelegateProperty | FPackageIndex + FPackageIndex[] | 无 |
| MulticastInlineDelegateProperty | ... | 同上 | 无 |
| MulticastSparseDelegateProperty | ... | FPackageIndex + ReadFName() | 无 |
| TextProperty | TextProperty | flags(i32) + history_type(u8) + strings | 有 |
| InterfaceProperty | InterfaceProperty | FPackageIndex | 无 |
| FieldPathProperty | FieldPathProperty | ReadFString[] + FPackageIndex | 无 |
| OptionalProperty | OptionalProperty | bool + nested property | 无 |
| AssetObjectProperty | AssetObjectProperty | ReadFString() | 无 |

### 5.3 PropertyTag 结构（UE5 版本）

```
Name              (FName) — "None" 终止
PropertyType      (FName 或 FPropertyTypeNameNode 树) — UE5 使用完整类型树
Size              (int32)
PropertyTagFlags  (byte) — 位标志:
  - HasArrayIndex     (0x01)
  - HasPropertyGuid   (0x02)
  - HasPropertyExtensions (0x04)
  - HasBinaryOrNativeSerialize (0x08)
  - BoolTrue          (0x10)
  - SkippedSerialize  (0x20)
ArrayIndex        (int32) — 仅 HasArrayIndex 时读取
PropertyGuid      (FGuid) — 仅 HasPropertyGuid 时读取
TagExtensions     (byte) — 仅 HasPropertyExtensions 时读取
```

UE5 `PROPERTY_TAG_COMPLETE_TYPE_NAME` 之后的类型读取：

```csharp
// 递归读取类型树
var nodes = new List<FPropertyTypeNameNode>();
var remaining = 1;
do {
    var node = new FPropertyTypeNameNode(Ar);  // ReadFName() + Read<int>() InnerCount
    nodes.Add(node);
    remaining += node.InnerCount - 1;
} while (remaining > 0);
PropertyType = nodes[0].Name;  // 根类型名
```

---

## 6. Kismet Token 解析流程

### 6.1 EExprToken 完整枚举

```
EX_LocalVariable           = 0x00    EX_InstanceVariable         = 0x01
EX_DefaultVariable         = 0x02    EX_Return                     = 0x04
EX_Jump                    = 0x06    EX_JumpIfNot                  = 0x07
EX_Assert                  = 0x09    EX_Nothing                    = 0x0B
EX_NothingInt32            = 0x0C    EX_Let                        = 0x0F
EX_BitFieldConst           = 0x11    EX_ClassContext               = 0x12
EX_MetaCast                = 0x13    EX_LetBool                    = 0x14
EX_EndParmValue            = 0x15    EX_EndFunctionParms           = 0x16
EX_Self                    = 0x17    EX_Skip                       = 0x18
EX_Context                 = 0x19    EX_Context_FailSilent         = 0x1A
EX_VirtualFunction         = 0x1B    EX_FinalFunction              = 0x1C
EX_IntConst                = 0x1D    EX_FloatConst                 = 0x1E
EX_StringConst             = 0x1F    EX_ObjectConst                = 0x20
EX_NameConst               = 0x21    EX_RotationConst              = 0x22
EX_VectorConst             = 0x23    EX_ByteConst                  = 0x24
EX_IntZero                 = 0x25    EX_IntOne                     = 0x26
EX_True                    = 0x27    EX_False                      = 0x28
EX_TextConst               = 0x29    EX_NoObject                   = 0x2A
EX_TransformConst          = 0x2B    EX_IntConstByte               = 0x2C
EX_NoInterface             = 0x2D    EX_DynamicCast                = 0x2E
EX_StructConst             = 0x2F    EX_EndStructConst             = 0x30
EX_SetArray                = 0x31    EX_EndArray                   = 0x32
EX_PropertyConst           = 0x33    EX_UnicodeStringConst         = 0x34
EX_Int64Const              = 0x35    EX_UInt64Const                = 0x36
EX_DoubleConst             = 0x37    EX_Cast                       = 0x38
EX_SetSet                  = 0x39    EX_EndSet                     = 0x3A
EX_SetMap                  = 0x3B    EX_EndMap                     = 0x3C
EX_SetConst                = 0x3D    EX_EndSetConst                = 0x3E
EX_MapConst                = 0x3F    EX_EndMapConst                = 0x40
EX_Vector3fConst           = 0x41    EX_StructMemberContext        = 0x42
EX_LetMulticastDelegate    = 0x43    EX_LetDelegate                = 0x44
EX_LocalVirtualFunction    = 0x45    EX_LocalFinalFunction         = 0x46
EX_LocalOutVariable        = 0x48    EX_DeprecatedOp4A             = 0x4A
EX_InstanceDelegate        = 0x4B    EX_PushExecutionFlow          = 0x4C
EX_PopExecutionFlow        = 0x4D    EX_ComputedJump               = 0x4E
EX_PopExecutionFlowIfNot   = 0x4F    EX_Breakpoint                 = 0x50
EX_InterfaceContext        = 0x51    EX_ObjToInterfaceCast         = 0x52
EX_EndOfScript             = 0x53    EX_CrossInterfaceCast         = 0x54
EX_InterfaceToObjCast      = 0x55    EX_WireTracepoint             = 0x5A
EX_SkipOffsetConst         = 0x5B    EX_AddMulticastDelegate       = 0x5C
EX_ClearMulticastDelegate  = 0x5D    EX_Tracepoint                 = 0x5E
EX_LetObj                  = 0x5F    EX_LetWeakObjPtr              = 0x60
EX_BindDelegate            = 0x61    EX_RemoveMulticastDelegate    = 0x62
EX_CallMulticastDelegate   = 0x63    EX_LetValueOnPersistentFrame  = 0x64
EX_ArrayConst              = 0x65    EX_EndArrayConst              = 0x66
EX_SoftObjectConst         = 0x67    EX_CallMath                   = 0x68
EX_SwitchValue             = 0x69    EX_InstrumentationEvent       = 0x6A
EX_ArrayGetByRef           = 0x6B    EX_ClassSparseDataVariable    = 0x6C
EX_FieldPathConst          = 0x6D    EX_AutoRtfmTransact           = 0x70
EX_AutoRtfmStopTransact    = 0x71    EX_AutoRtfmAbortIfNot         = 0x72

EX_F9 = 0xF9 (Borderlands4)   EX_FD = 0xFD (Borderlands4, 2XKO)   EX_FE = 0xFE (Borderlands4)
EX_6E = 0x6E (WutheringWaves/DeltaForce)  EX_6F = 0x6F (WutheringWaves)
```

### 6.2 FKismetArchive 读取流程

```csharp
public KismetExpression ReadExpression() {
    var token = (EExprToken)Read<byte>();
    KismetExpression expression = token switch {
        EExprToken.EX_LocalVariable    => new EX_LocalVariable(this),
        EExprToken.EX_FinalFunction    => new EX_FinalFunction(this),
        EExprToken.EX_CallMath         => new EX_CallMath(this),
        // ... 所有 token 的映射
        _ => throw new ParserException($"Unknown EExprToken {token}")
    };
    expression.StatementIndex = index;  // 记录该表达式的起始位置
    return expression;
}

// 读取表达式数组，直到遇到终止 token
public KismetExpression[] ReadExpressionArray(EExprToken endToken) {
    var newData = new List<KismetExpression>();
    KismetExpression? currExpression = null;
    while (currExpression == null || currExpression.Token != endToken) {
        if (currExpression != null) newData.Add(currExpression);
        currExpression = ReadExpression();
    }
    return newData.ToArray();
}
```

### 6.3 关键表达式解析模式

```csharp
// EX_FinalFunction — 最常见的函数调用
EX_FinalFunction(FKismetArchive Ar) {
    StackNode = new FPackageIndex(Ar);  // 函数引用（Export/Import 索引）
    Parameters = Ar.ReadExpressionArray(EExprToken.EX_EndFunctionParms);
}

// EX_Context — 对象上下文调用
EX_Context(FKismetArchive Ar) {
    ObjectExpression = Ar.ReadExpression();   // 对象表达式
    Offset = Ar.Read<uint>();                 // 偏移量
    RValuePointer = new FKismetPropertyPointer(Ar);  // 属性指针
    ContextExpression = Ar.ReadExpression();  // 上下文表达式
}

// EX_Let — 赋值
EX_Let(FKismetArchive Ar) {
    Property = new FKismetPropertyPointer(Ar);  // 目标属性
    Variable = Ar.ReadExpression();             // 左值
    Assignment = Ar.ReadExpression();           // 右值
}

// EX_StructConst — 结构体常量
EX_StructConst(FKismetArchive Ar) {
    Struct = new FPackageIndex(Ar);     // 结构体类型引用
    StructSize = Ar.Read<int>();        // 结构体大小
    Properties = Ar.ReadExpressionArray(EExprToken.EX_EndStructConst);
}

// EX_SwitchValue — switch 表达式
EX_SwitchValue(FKismetArchive Ar) {
    ushort numCases = Ar.Read<ushort>();
    EndGotoOffset = Ar.Read<uint>();
    IndexTerm = Ar.ReadExpression();
    Cases = Ar.ReadArray(numCases, () => new FKismetSwitchCase(Ar));
    DefaultTerm = Ar.ReadExpression();
}
```

### 6.4 FKismetPropertyPointer

```csharp
// UE4.25+ 使用 FFieldPath（新格式）
// UE4.25 之前使用 FPackageIndex（旧格式）
FKismetPropertyPointer(FKismetArchive Ar) {
    if (Ar.Game >= GAME_UE4_25) {
        New = new FFieldPath(Ar);  // FName[] Path + FPackageIndex ResolvedOwner
    } else {
        Old = new FPackageIndex(Ar);
    }
}
```

### 6.5 Kismet 特殊字符串读取

```csharp
// XFERSTRING — ASCII 字符串，以 null 结尾
public string XFERSTRING() {
    var eos = Array.IndexOf<byte>(_data, 0, (int)Position);
    return Encoding.ASCII.GetString(ReadBytes(eos - (int)Position));
}

// XFERUNICODESTRING — UTF-16 字符串，以 null-null 结尾
public string XFERUNICODESTRING() {
    // 查找双字节 null terminator
    ...
    return Encoding.Unicode.GetString(ReadBytes(length));
}
```

---

## 7. 压缩与解压缩策略

### 7.1 包级别压缩

```csharp
// FPackageFileSummary 中的 CompressionFlags 检查
CompressionFlags = Ar.Read<EcompressionFlags>();
var compressedChunks = Ar.ReadArray<FCompressedChunk>();
if (compressedChunks.Length > 0)
    throw new ParserException("Package level compression is enabled");
```

- UE 包通常不使用包级别压缩（cooked 包）
- `FCompressedChunk` 结构：`CompressedOffset`, `CompressedSize`, `UncompressedSize`

### 7.2 BulkData 压缩

```csharp
// FArchive.SerializeCompressedNew()
// 支持三种 header 版本:
//   v1: PACKAGE_FILE_TAG (4 bytes) + FCompressedChunkInfo
//   v1 swapped: PACKAGE_FILE_TAG_SWAPPED
//   v2: ARCHIVE_V2_HEADER_TAG (8 bytes) + CompressionFormat 枚举
// 分块解压: loadingCompressionChunkSize 为块大小
// 支持格式: None, Oodle, Zlib, Gzip, LZ4
```

### 7.3 FArchiveLoadCompressedProxy

```csharp
// 惰性解压代理 — 按需解压单个 chunk
// LOADING_COMPRESSION_CHUNK_SIZE 默认值
// DecompressMoreData() 按需填充 _tmpData 缓冲区
// Seek 通过向前序列化实现（传入 null dstData 仅解压不拷贝）
```

### 7.4 Python 项目已实现

`src/uasset_read/pak/decompress.py` 已支持：
- Oodle (brotli / oodle)
- Zlib
- LZ4

---

## 8. Lazy vs Eager 加载模式

### 8.1 Lazy 模式（默认）

```csharp
// Package 构造函数中:
for (var i = 0; i < ExportsLazy.Length; i++) {
    var export = ExportMap[i];
    ExportsLazy[i] = new Lazy<UObject>(() => {
        // 仅在首次访问时执行:
        // 1. ConstructObject — 创建外壳
        // 2. DeserializeObject — 反序列化属性
        // 3. PostLoad — 后处理
        return obj;
    });
}
```

**优点**：内存高效，只加载需要的 Export
**缺点**：首次访问时有延迟

### 8.2 Eager 模式（ExportLoader）

```csharp
// 两阶段加载：Create → Serialize → Complete
// 依赖追踪：
//   - SerializationBeforeSerializationDependencies
//   - CreateBeforeSerializationDependencies
//   - SerializationBeforeCreateDependencies
//   - CreateBeforeCreateDependencies
// 使用 PreloadDependencies 表解析依赖
```

**优点**：确保加载顺序正确，适合需要完整对象图的场景
**缺点**：初始加载慢

### 8.3 Python 项目当前实现

`src/uasset_read/link/linker.py` (PackageLinker) 实现了两阶段模式：
1. `link()` — 从 ImportMap/ExportMap 创建 UObjectInstance 外壳
2. `preload()` — 按需反序列化属性

这与 CUE4Parse 的 Lazy 模式等价。

---

## 9. 蓝图节点格式规范

### 9.1 整体结构

蓝图文件由多个 `Begin Object ... End Object` 块组成，每个块代表一个节点：

```
Begin Object Class=<ClassPath> Name=<ObjectName> ExportPath="<ExportPath>"
   <字段1>=<值>
   <字段2>=<值>
   CustomProperties Pin (PinId=..., PinName=..., ...)
   CustomProperties Pin (PinId=..., PinName=..., ...)
End Object
```

### 9.2 Begin Object 行格式

| 字段 | 说明 | 示例 |
|------|------|------|
| Class | 节点类路径 | `/Script/BlueprintGraph.K2Node_CallFunction` |
| Name | 节点唯一名称 | `K2Node_CallFunction_1193` |
| ExportPath | 完整导出路径 | `/Script/BlueprintGraph.K2Node_CallFunction'/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter.BP_FirstPersonCharacter:EventGraph.K2Node_CallFunction_1193'` |

### 9.3 节点类型

| 节点类型 | 说明 | 关键特有字段 |
|---------|------|-------------|
| `K2Node_CallFunction` | 函数调用节点 | `FunctionReference=(MemberName=..., bSelfContext=...)` |
| `K2Node_Event` | 事件节点 | `EventReference=(MemberParent=..., MemberName=..., MemberGuid=...)` |
| `K2Node_EnhancedInputAction` | 增强输入动作节点 | `InputAction="<资源路径>"`, `AdvancedPinDisplay=Hidden` |
| `K2Node_FunctionEntry` | 自定义函数入口 | `ExtraFlags=...`, `bIsEditable=True`, `CustomProperties UserDefinedPin` |
| `EdGraphNode_Comment` | 注释框节点 | `NodeComment="..."`, `NodeWidth=...`, `NodeHeight=...`, `CommentColor=(R=...,G=...,B=...,A=...)` |
| `K2Node_Knot` | 连线转接节点 (Reroute) | 仅有引脚，无特有字段 |

### 9.4 节点标准字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `FunctionReference` | `(MemberName=..., bSelfContext=...)` | 函数引用（CallFunction 节点） |
| `EventReference` | `(MemberParent=..., MemberName=..., MemberGuid=...)` | 事件引用（Event 节点） |
| `InputAction` | 字符串 | 输入动作资源路径（EnhancedInputAction 节点） |
| `NodePosX` | 整数 | 画布 X 坐标 |
| `NodePosY` | 整数 | 画布 Y 坐标 |
| `NodeGuid` | 32 位十六进制 | 节点唯一标识（如 `F923268743B7B52D669FFB960CA79833`） |
| `ErrorType` | 整数 | 错误类型标记（如 `1` 表示有错误） |
| `AdvancedPinDisplay` | `Hidden` / `Shown` | 高级引脚显示控制 |
| `bDefaultsToPureFunc` | `True`/`False` | 是否默认为纯函数（CallFunction） |
| `bOverrideFunction` | `True`/`False` | 是否覆盖接口函数（Event 节点） |
| `bIsEditable` | `True`/`False` | 是否可编辑（FunctionEntry） |
| `ExtraFlags` | 整数 | 额外标志（FunctionEntry） |
| `NodeComment` | 字符串 | 注释文本（Comment 节点） |
| `NodeWidth` / `NodeHeight` | 整数 | 注释框尺寸 |
| `CommentColor` | `(R=...,G=...,B=...,A=...)` | 注释框颜色 |
| `CommentDepth` | 整数 | 注释框层级 |
| `FontSize` | 整数 | 字体大小 |
| `MoveMode` | `NoGroupMovement` 等 | 移动模式 |
| `bCommentBubblePinned` | `True`/`False` | 注释气泡固定 |
| `bCommentBubbleVisible` | `True`/`False` | 注释气泡可见 |
| `bCommentBubbleVisible_InDetailsPanel` | `True`/`False` | 详情面板可见 |

### 9.5 特殊字段格式

```
FunctionReference=(MemberName="Jump",bSelfContext=True)
FunctionReference=(MemberName="Move",MemberGuid=B96BAB4744AF0F8F393A3DB6EADCB59F,bSelfContext=True)
EventReference=(MemberParent="/Script/Engine.BlueprintGeneratedClass'/Game/Input/Touch/BPI_TouchInterface.BPI_TouchInterface_C'",MemberName="Primary Thumbstick",MemberGuid=97FB41A24EDF9FFD7D921D9A90178379)
CommentColor=(R=0.050980,G=0.050980,B=0.050980,A=1.000000)
InputAction="/Script/EnhancedInput.InputAction'/Game/Input/Actions/IA_Look.IA_Look'"
```

---

## 10. 引脚格式规范

### 10.1 引脚语法

```
CustomProperties Pin (PinId=HEX_GUID, PinName="name", PinType.PinCategory="category", PinType.PinSubCategory="sub", ..., LinkedTo=(Node Guid1, Node Guid2,), ...)
```

### 10.2 引脚字段完整清单

#### 基础字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `PinId` | 32 位十六进制 | 引脚唯一标识 |
| `PinName` | 字符串 | 引脚名称（"execute", "then", "self", 参数名等） |
| `PinFriendlyName` | 本地化字符串 | 显示名称 |
| `Direction` | `EGPD_Input` / `EGPD_Output` | 引脚方向（默认 Input，仅 Output 时显式标注） |

#### PinType 字段

| 字段 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| `PinType.PinCategory` | 字符串 | 引脚类别 | `exec`, `object`, `struct`, `real`, `bool`, `delegate` |
| `PinType.PinSubCategory` | 字符串 | 子类别 | `""`, `"self"`, `"float"`, `"double"` |
| `PinType.PinSubCategoryObject` | 路径/None | 对象类型引用 | `"/Script/CoreUObject.Class'/Script/Engine.Character'"`, `None` |
| `PinType.PinSubCategoryMemberReference` | `()` | 成员引用 | 通常为空 |
| `PinType.PinValueType` | `()` | 值类型 | 通常为空 |
| `PinType.ContainerType` | None/Array/Set/Map | 容器类型 | `None` |
| `PinType.bIsReference` | bool | 是否引用 | `False` |
| `PinType.bIsConst` | bool | 是否 const | `False` |
| `PinType.bIsWeakPointer` | bool | 是否弱指针 | `False` |
| `PinType.bIsUObjectWrapper` | bool | 是否 UObject 包装 | `False` |
| `PinType.bSerializeAsSinglePrecisionFloat` | bool | 是否单精度浮点 | `False` |

#### 连接字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `LinkedTo` | `(NodeName Guid, ...)`, 或空 `()` | 连接的引脚列表 |
| `PersistentGuid` | 32 位十六进制（通常全零） | 持久化 GUID |

#### 可见性字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `bHidden` | bool | 是否隐藏 |
| `bNotConnectable` | bool | 是否不可连接 |
| `bDefaultValueIsReadOnly` | bool | 默认值是否只读 |
| `bDefaultValueIsIgnored` | bool | 默认值是否忽略 |
| `bAdvancedView` | bool | 是否高级视图 |
| `bOrphanedPin` | bool | 是否孤立引脚 |

#### 默认值字段

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `DefaultValue` | 字符串 | 默认值 | `"0.0"`, `"false"`, `"1.000000"`, `"0, 0, 0"` |
| `AutogeneratedDefaultValue` | 字符串 | 自动生成的默认值 | 通常同 DefaultValue |
| `DefaultObject` | 字符串 | 默认对象引用 | `"/Game/Input/Actions/IA_Look.IA_Look"` |

### 10.3 子引脚系统 (SubPins / ParentPin)

**父引脚**定义：
```
PinId=B1FD31FC..., PinName="ActionValue", PinCategory="struct", ...,
SubPins=(K2Node_EnhancedInputAction_2 19CFB869..., K2Node_EnhancedInputAction_2 F4EF3775...),
bHidden=True
```

**子引脚**定义：
```
PinId=19CFB869..., PinName="ActionValue_X", PinCategory="real", PinSubCategory="double", ...,
DefaultValue="0.0", ..., ParentPin=K2Node_EnhancedInputAction_2 B1FD31FC...
```

关键关系：
- **SubPins**：父引脚字段，列出所有子引脚的 `NodeName PinId` 对
- **ParentPin**：子引脚字段，引用父引脚的 `NodeName PinId`
- **PinCategory 转换**：父引脚为 `struct`（如 Vector2D），子引脚为具体类型（`real/double`）
- **PinFriendlyName 格式**：子引脚使用 `LOCGEN_FORMAT_NAMED(...)` 格式：`{PinDisplayName} {ProtoPinDisplayName}`
- **bHidden**：父引脚通常 `bHidden=True`，子引脚 `bHidden=False`

### 10.4 引脚方向模式

| 节点类型 | 输出引脚 (EGPD_Output) | 输入引脚 (默认) |
|---------|----------------------|----------------|
| K2Node_Event | `OutputDelegate`, `then`, 参数 | 无 |
| K2Node_CallFunction | `then`, `ReturnValue` | `execute`, `self`, 参数 |
| K2Node_EnhancedInputAction | `Triggered`, `Started`, `Ongoing`, `Canceled`, `Completed`, `ActionValue`, `ElapsedSeconds`, `TriggeredSeconds`, `InputAction` | 无 |
| K2Node_FunctionEntry | `then`, 参数 | 无 |
| K2Node_Knot | `OutputPin` | `InputPin` |

### 10.5 PinCategory 类型映射

| PinCategory | PinSubCategory | C++ 等价类型 |
|------------|---------------|-------------|
| `exec` | `""` | 执行流 |
| `object` | `""` | `UObject*` |
| `object` | `"self"` | 自身引用 |
| `struct` | `""` | `FStructType`（由 PinSubCategoryObject 确定具体类型） |
| `real` | `"float"` | `float` |
| `real` | `"double"` | `double` |
| `bool` | `""` | `bool` |
| `delegate` | `""` | 委托 |
| `byte` | `""` | `uint8` |
| `int` | `""` | `int32` |
| `name` | `""` | `FName` |
| `string` | `""` | `FString` |
| `text` | `""` | `FText` |
| `class` | `""` | `UClass*` |
| `interface` | `""` | `UInterface*` |

### 10.6 UserDefinedPin（FunctionEntry 专用）

```
CustomProperties UserDefinedPin (PinName="Left / Right", PinType=(PinCategory="real",PinSubCategory="double"), DesiredPinDirection=EGPD_Output)
```

- 仅出现在 `K2Node_FunctionEntry` 中
- 定义用户自定义输入/输出参数
- `DesiredPinDirection` 指定方向

---

## 11. 与当前 Python 项目的差异分析

### 11.1 FArchive

| 特性 | CUE4Parse | 当前 Python 项目 | 差距 |
|------|-----------|-----------------|------|
| 泛型读取 `Read<T>()` | `Unsafe.ReadUnaligned<T>()` 直接映射内存 | 逐个类型 `read_i32()`, `read_f32()` | 中：Python 无 Unsafe 等效，但 struct.unpack 可实现类似功能 |
| `ReadArray<T>(getter)` | 泛型数组读取 | 部分实现 | 低 |
| `ReadMap` / `ReadMultiMap` | 内置字典读取 | 无 | 中 |
| `ReadIntPacked` | 变长编码读取 | 无 | 低（BulkData 相关） |
| `Read7BitEncodedInt` | 7-bit 编码 | 无 | 低 |
| `ReadFReal` | LWC 感知 float/double | 无 | 低（Transform 中已手动处理） |
| `ReadBulkArray` | 带元素大小校验 | 无 | 中 |
| SkipBulkArrayData | 跳过 bulk 数据 | 无 | 中 |
| Clone | ICloneable 支持 | 无 | 低 |

### 11.2 PackageFileSummary

| 特性 | CUE4Parse | 当前 Python 项目 | 差距 |
|------|-----------|-----------------|------|
| 版本条件读取 | 完整实现所有版本分支 | 部分实现 | 中：缺少 UE5 新增字段 |
| CustomVersionContainer | 完整解析 | 无 | 高：影响跨版本兼容 |
| SoftObjectPaths | UE5 支持 | 无 | 低 |
| MetaDataOffset | UE5 支持 | 无 | 低 |
| CellExport/Import | VERSE_CELLS 支持 | 无 | 低 |
| ImportTypeHierarchies | UE5 支持 | 无 | 低 |
| DataResourceOffset | UE5 DATA_RESOURCES 支持 | 无 | 低 |
| PayloadTocOffset | UE5 PAYLOAD_TOC 支持 | 无 | 低 |

### 11.3 属性解析器

| 特性 | CUE4Parse | 当前 Python 项目 | 差距 |
|------|-----------|-----------------|------|
| 完整类型树 | UE5 FPropertyTypeNameNode 递归读取 | 从字符串解析括号内类型 | 高：UE5 完整类型树未实现 |
| PropertyTagFlags | 位标志解析 | 无 | 高：UE5 必须 |
| PropertyGuid | 条件读取 | 无 | 低 |
| TagExtensions | OverridableInformation 支持 | 无 | 低 |
| Utf8StrProperty | ReadFUtf8String() | 无 | 低 |
| InterfaceProperty | FPackageIndex | 无 | 中 |
| FieldPathProperty | FName[] + FPackageIndex | 无 | 中 |
| OptionalProperty | bool + nested | 无 | 中 |
| MulticastDelegateProperty | FPackageIndex + array | 无 | 低 |
| AssetObjectProperty | ReadFString() | 无 | 低 |
| Verse 系列属性 | VerseString/Function/Dynamic/Class | 无 | 低（特定游戏） |
| StructProperty fast-path | 完整 fast-path 列表 | 部分实现 | 低 |
| BoolProperty | tagData.Bool / flags 提取 | 有 | 低 |

### 11.4 Kismet

| 特性 | CUE4Parse | 当前 Python 项目 | 差距 |
|------|-----------|-----------------|------|
| EExprToken 完整枚举 | 全部 ~120 个 token | 大部分实现 | 低：缺少 EX_6E/EX_6F/EX_F9/EX_FD/EX_FE |
| FKismetPropertyPointer | UE4.25 分叉 (FFieldPath vs FPackageIndex) | 有 | 低 |
| EX_SwitchValue | 完整 switch 解析 | 有 | 低 |
| EX_InstrumentationEvent | 事件类型解析 | 有 | 低 |
| EX_TextConst / FScriptText | 5 种文本类型 | 有 | 低 |
| ReadExpressionArray | 自动直到终止 token | 有 | 低 |
| XFERSTRING / XFERUNICODESTRING | 特殊字符串读取 | 有 | 低 |
| FKismetArchive 独立索引 | Index 字段同步 | 有 | 低 |

### 11.5 链接器与加载

| 特性 | CUE4Parse | 当前 Python 项目 | 差距 |
|------|-----------|-----------------|------|
| Lazy 加载 | Lazy<T> 包装 | 类似实现 | 低 |
| Eager 加载 | ExportLoader 两阶段 + 依赖追踪 | 部分实现 | 中：依赖追踪不完整 |
| Import 解析 | 递归 outer 查找 + 跨包加载 | 基本实现 | 中：跨包加载未实现 |
| ResolvedObject 缓存 | WeakReference 缓存 | 无 | 低 |
| PreloadDependencies | 完整依赖表 | 部分 | 中 |

---

## 12. 关键差距清单

按优先级排序，供规划师制定实施计划：

### P0 — 高优先级（影响正确性）

1. **UE5 PropertyTag 完整类型树解析** (`FPropertyTypeNameNode` 递归读取)
   - 当前项目从字符串解析 `StructProperty(Vector)` 格式
   - UE5 序列化时使用嵌套类型树：`ReadFName() + InnerCount` 循环
   - 影响：所有 UE5 包的属性解析

2. **UE5 PropertyTagFlags 位标志解析**
   - `HasArrayIndex`, `HasPropertyGuid`, `HasPropertyExtensions`, `BoolTrue`, `SkippedSerialize`, `HasBinaryOrNativeSerialize`
   - 影响：UE5 包 PropertyTag 读取位置偏移

3. **CustomVersionContainer 解析**
   - 决定正确的版本条件分支
   - 影响：跨 UE 版本兼容性

### P1 — 中优先级（影响功能完整性）

4. **缺失属性类型解析器**
   - `InterfaceProperty`, `FieldPathProperty`, `OptionalProperty`, `MulticastDelegateProperty`, `AssetObjectProperty`, `Utf8StrProperty`
   - 影响：特定蓝图节点属性无法解析

5. **FKismetPropertyPointer UE4.25+ FFieldPath 支持**
   - 当前项目使用旧格式 `FPackageIndex`
   - UE4.25+ 使用 `FFieldPath`（`FName[]` 路径）

6. **Eager 加载依赖追踪完善**
   - 当前项目缺少完整的 `SerializationBeforeSerializationDependencies` 等依赖类型处理

7. **Import 跨包解析**
   - CUE4Parse 支持通过 `Provider.TryLoadPackage` 加载外部包中的 Export
   - 当前项目仅处理单包

### P2 — 低优先级（功能增强）

8. **FArchive 工具方法**
   - `ReadMap`, `ReadMultiMap`, `ReadIntPacked`, `Read7BitEncodedInt`, `ReadFReal`, `ReadBulkArray`, `SkipBulkArrayData`

9. **Kismet 游戏特定 Token**
   - `EX_6E` (WutheringWaves/DeltaForce), `EX_6F` (WutheringWaves), `EX_F9/EX_FD/EX_FE` (Borderlands4)

10. **ResolvedObject 缓存机制**
    - `WeakReference` 缓存避免重复解析

11. **PackageFileSummary UE5 字段**
    - `SoftObjectPaths`, `MetaDataOffset`, `CellExport/Import`, `ImportTypeHierarchies`, `DataResourceMap`, `PayloadTocOffset`

12. **BulkData 压缩代理**
    - `FArchiveLoadCompressedProxy` 惰性解压

---

## 附录 A：版本枚举关键值参考

```
EUnrealEngineObjectUE4Version:
  OLDEST_LOADABLE_PACKAGE       = 214
  NON_OUTER_PACKAGE_IMPORT       = ...
  PROPERTY_GUID_IN_PROPERTY_TAG  = ...
  ADD_STRING_ASSET_REFERENCES_MAP = ...
  TEMPLATEIndex_IN_COOKED_EXPORTS = ...
  e64BIT_EXPORTMAP_SERIALSIZES   = ...
  PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS = ...

EUnrealEngineObjectUE5Version:
  PROPERTY_TAG_COMPLETE_TYPE_NAME = ...
  ADD_SOFTOBJECTPATH_LIST        = ...
  SCRIPT_SERIALIZATION_OFFSET    = ...
  OPTIONAL_RESOURCES             = ...
  METADATA_SERIALIZATION_OFFSET  = ...
  NAMES_REFERENCED_FROM_EXPORT_DATA = ...
  PAYLOAD_TOC                    = ...
  DATA_RESOURCES                 = ...
  VERSE_CELLS                    = ...
  TRACK_OBJECT_EXPORT_IS_INHERITED = ...
  REMOVE_OBJECT_EXPORT_PACKAGE_GUID = ...
```

> 注意：具体数值因 CUE4Parse 版本而异，请参考 `UE4/Versions/ObjectVersion.cs`

## 附录 B：蓝图节点连接示例（从参考文件提取）

### 示例 1：Jump 按钮 → Jump 函数

```
K2Node_EnhancedInputAction_5 [Started pin: 6412140B...] → K2Node_CallFunction_1193 [execute pin: 13FD260E...]
```

连接链：`EnhancedInputAction.Started → CallFunction(Jump).execute`

### 示例 2：子引脚拆分

```
K2Node_EnhancedInputAction_2.ActionValue (struct Vector2D, bHidden=True)
  SubPins → ActionValue_X (real/double), ActionValue_Y (real/double)
```

### 示例 3：Reroute 链

```
K2Node_FunctionEntry_0 [Left / Right] → K2Node_Knot_2 [Input→Output] → K2Node_Knot_1 [Input→Output] → K2Node_CallFunction_7445 [ScaleValue]
```

---

*文档结束。此文档为规划师制定重构实施计划提供技术参考。*
