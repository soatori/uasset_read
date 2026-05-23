---
gsd_state_version: 1.2
phase: 72-G
research_type: root-cause-analysis
---

# Phase 72-G Research — Root Cause Analysis

**Researched:** 2026-05-23
**Domain:** UE5 Blueprint parsing, StructProperty serialization, Pin connections, Function metadata
**Confidence:** HIGH (based on CUE4Parse source code analysis + UE C++ source verification)

## Summary

Phase 72-G 调查 4 个反复失败的问题根因。通过三方对照（CUE4Parse C# 实现、UE C++ 源码、当前 Python 实现），定位了以下根本问题：

**Primary findings:**
1. **M-01 StructProperty:** 缺少对常见类型（Vector/Rotator）的专用快速解析，依赖通用 PropertyTags 循环对某些自定义序列化 struct（如 BodyInstance）失败
2. **M-02 Pin 连接:** LinkedTo 数据在序列化层可能正确读取，但 `build_connections_map()` 未验证数据实际填充情况
3. **M-03/M-04 Functions:** 缺少从 BPGC Export 属性提取 `UbergraphFunction` 引用的路径，且依赖 Pin 数据的完整性

**Primary recommendation:** 添加常见 struct 专用解析器 + 验证 LinkedTo 数据填充 + 实现 BPGC 属性提取路径

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| StructProperty parsing | parsers/property_types.py | serializers/property_tags.py | PropertyTypes 负责 struct 字段解析，PropertyTags 提供类型名数据 |
| Pin connection serialization | serializers/graph.py | models/core.py | graph.py 负责 LinkedTo 二进制读取，models 定义输出格式 |
| Pin connection mapping | graph/flow_builder.py | — | flow_builder 将 LinkedTo 数据转换为 connections 数组 |
| Blueprint functions extraction | blueprint/variable_extractor.py | link/linker.py | variable_extractor 从 BPGC 属性和 Graph 节点提取函数 |

---

## M-01: Complex StructProperty 解析失败

### UE Editor 源码分析

**BodyInstance.h (E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\Engine\Classes\PhysicsEngine\BodyInstance.h)**

```cpp
// Line 35: BodyInstance 有自定义 Serialize operator
ENGINE_API FArchive& operator<<(FArchive& Ar, FBodyInstance& BodyInst);
```

**BodyInstance.cpp (Line 422-438) — Serialize 实现：**

```cpp
FArchive& operator<<(FArchive& Ar,FBodyInstance& BodyInst)
{
    if (!Ar.IsLoading() && !Ar.IsSaving())
    {
        Ar << BodyInst.OwnerComponent;
        Ar << BodyInst.PhysMaterialOverride;
    }
    
    if (Ar.IsLoading() && Ar.UEVer() < VER_UE4_MAX_ANGULAR_VELOCITY_DEFAULT)
    {
        if(BodyInst.MaxAngularVelocity != 400.f)
        {
            BodyInst.bOverrideMaxAngularVelocity = true;
        }
    }
    
    return Ar;
}
```

**关键发现：**
- BodyInstance 的 `operator<<` 只序列化 `OwnerComponent` 和 `PhysMaterialOverride`
- 其他属性（CollisionEnabled, ObjectType 等）通过 `UStruct` 基类序列化（PropertyTags 循环）
- **UE5 格式：** `FBodyInstance` 是 `UStruct` 子类，属性通过 tagged properties 序列化

**FVector.cs (CUE4Parse) — Vector 快速解析：**

```csharp
// Line 54-59: FVector 直接读取 3 个 float
public FVector(FArchive Ar)
{
    X = Ar.ReadFReal();  // float/double，取决于版本
    Y = Ar.ReadFReal();
    Z = Ar.ReadFReal();
}
```

**FRotator.cs (CUE4Parse) — Rotator 快速解析：**

```csharp
// Line 47-61: FRotator 直接读取 Pitch/Yaw/Roll
public FRotator(FArchive Ar)
{
    if (Ar.Game < EGame.GAME_UE4_0)
    {
        const float scale = 360f / 65536f;
        Pitch = Ar.Read<int>() * scale;
        Yaw   = Ar.Read<int>() * scale;
        Roll  = Ar.Read<int>() * scale;
        return;
    }
    
    Pitch = Ar.ReadFReal();
    Yaw = Ar.ReadFReal();
    Roll = Ar.ReadFReal();
}
```

### CUE4Parse 解决方案

**FScriptStruct.cs (Line 68-427) — Struct 分发逻辑：**

```csharp
public FScriptStruct(FAssetArchive Ar, string? structName, UStruct? struc, ReadType? type)
{
    StructType = structName switch
    {
        // 专用快速解析（Line 174-178）
        "Vector" => type == ReadType.ZERO ? new FVector() : new FVector(Ar),
        "Vector2D" => type == ReadType.ZERO ? new FVector2D() : new FVector2D(Ar),
        "Rotator" => type == ReadType.ZERO ? new FRotator() : new FRotator(Ar),
        "Rotator3f" => type == ReadType.ZERO ? new FRotator() : new FRotator(Ar.Read<float>(), Ar.Read<float>(), Ar.Read<float>()),
        "Rotator3d" => type == ReadType.ZERO ? new FRotator() : new FRotator(Ar.Read<double>(), Ar.Read<double>(), Ar.Read<double>()),
        
        // Line 403: BodyInstance 特殊处理（仅 ConanExiles）
        "BodyInstance" when Ar.Game is EGame.GAME_ConanExilesEnhanced => new FBodyInstance(Ar),
        
        // Line 424: 默认 fallback
        _ => type == ReadType.ZERO ? new FStructFallback() 
             : struc != null ? new FStructFallback(Ar, struc) 
             : new FStructFallback(Ar, structName)
    };
}
```

**FStructFallback.cs (Line 23-34) — Fallback 机制：**

```csharp
public FStructFallback(FAssetArchive Ar, UStruct? structType = null)
{
    if (Ar.HasUnversionedProperties)
    {
        if (structType == null) throw new ArgumentException("For unversioned struct fallback the struct type cannot be null");
        UObject.DeserializePropertiesUnversioned(Properties = [], Ar, structType);
    }
    else
    {
        UObject.DeserializePropertiesTagged(Properties = [], Ar, true);
    }
}
```

### 当前 Python 实现差异

**property_types.py (Line 141-179) — parse_struct_property()：**

```python
def parse_struct_property(tag: PropertyTag, archive: FArchive, name_map: List[str], 
                          export_map: List[Any], summary: Optional[Any] = None, 
                          depth: int = 0) -> StructValue:
    MAX_DEPTH = 5
    
    if depth > MAX_DEPTH:
        raise ParseError(f"StructProperty nesting depth {depth} exceeds maximum {MAX_DEPTH}")
    
    struct_type = _extract_struct_type_from_tag(tag)  # 关键：类型名提取
    fields: Dict[str, Any] = {}
    property_count = 0
    
    parse_property_value = _get_parse_property_value()
    read_property_tag = _get_read_property_tag()
    
    while property_count < MAX_PROPERTY_COUNT:
        property_count += 1
        inner_tag = read_property_tag(archive, name_map)
        if inner_tag.name == "None":
            break
        field_value = parse_property_value(inner_tag, archive, name_map, export_map, summary, depth + 1)
        # ... fallback logic
        fields[inner_tag.name] = field_value
    
    return StructValue(struct_type=struct_type, fields=fields)
```

**property_types.py (Line 310-350) — _extract_struct_type_from_tag()：**

```python
def _extract_struct_type_from_tag(tag: PropertyTag) -> str:
    type_str = tag.type
    
    if not type_str.startswith("StructProperty"):
        return "UnknownStruct"
    
    # 格式: "StructProperty(...)"
    if "(" in type_str and ")" in type_str:
        # 新格式: "Vector(/Script/CoreUObject)" → 提取第一个部分
        # ...
```

### 根因结论

| 问题 | 根因 | 证据 |
|------|------|------|
| Vector/Rotator 解析失败 | 缺少专用快速解析器，依赖 PropertyTags 循环 | CUE4Parse 对这些类型有专用 `new FVector(Ar)` 路径 |
| BodyInstance 解析失败 | 缺少自定义序列化识别 + 类型名提取失败 | UE C++ `operator<<` 只序列化部分属性，其他通过 tagged properties |
| Size 异常 (16777216) | PropertyTag UE5 格式未正确解析 | Phase 67 已修复 `PROPERTY_TAG_COMPLETE_TYPE_NAME` 分支 |

**核心差距：**
1. **无 Vector/Rotator 专用解析**：CUE4Parse 直接读取 3 float，Python 依赖 PropertyTags 循环
2. **类型名提取复杂**：UE5 `FPropertyTypeNameNode` 链式格式，`_extract_struct_type_from_tag()` 可能提取失败
3. **缺少 BodyInstance 特殊处理**：某些 struct 有自定义 Serialize，不完全依赖 PropertyTags

### 可行修复方案

1. **添加 Vector/Rotator 专用解析器：**

```python
def parse_struct_property(tag: PropertyTag, archive: FArchive, ...):
    struct_type = _extract_struct_type_from_tag(tag)
    
    # 快速路径：Vector/Rotator 直接读取 3 float
    if struct_type == "Vector":
        x = archive.read_f32()
        y = archive.read_f32()
        z = archive.read_f32()
        return StructValue(struct_type="Vector", fields={"X": x, "Y": y, "Z": z})
    
    if struct_type == "Rotator":
        pitch = archive.read_f32()
        yaw = archive.read_f32()
        roll = archive.read_f32()
        return StructValue(struct_type="Rotator", fields={"Pitch": pitch, "Yaw": yaw, "Roll": roll})
    
    # 默认：PropertyTags 循环
    # ...
```

2. **验证类型名提取逻辑：** 添加单元测试，验证 `_extract_struct_type_from_tag()` 对各种 UE5 格式的提取正确性

3. **添加偏移追踪日志：** 在 `parse_struct_property()` 中记录每次 inner_tag 读取后的位置变化，验证是否与 `tag.size` 一致

---

## M-02: Pin 连接映射输出为空

### UE Editor 源码分析

**UEdGraphPin.cpp (UE C++ 源码路径：Engine/Source/Runtime/Engine/Private/EdGraph/EdGraphPin.cpp)**

`UEdGraphPin::Serialize()` 读取顺序：
1. OwningNode (FPackageIndex)
2. PinId (FGuid)
3. PinName (FName)
4. PinFriendlyName (FText, EditorOnly)
5. SourceIndex (int32, UE5)
6. PinToolTip (FString)
7. Direction (u8)
8. PinType (FEdGraphPinType)
9. DefaultValue/AutogeneratedDefaultValue (FString)
10. DefaultObject (FPackageIndex)
11. DefaultTextValue (FText)
12. **LinkedTo array** (SerializePinArray)
13. SubPins array
14. ParentPin
15. ReferencePassThroughConnection
16. PersistentGuid (FGuid, EditorOnly)
17. BitField (uint32, EditorOnly)

### CUE4Parse 解决方案

**UEdGraphPin.cs (Line 57-138) — LinkedTo 读取：**

```csharp
public UEdGraphPin(FAssetArchive Ar) : base(Ar)
{
    // ...
    SerializePinArray(Ar, ref LinkedTo, this, EPinResolveType.LinkedTo);  // Line 86
    // ...
}

public static void SerializePinArray(FAssetArchive Ar, ref UEdGraphPinReference?[] ArrayRef, ...)
{
    var arrayNum = Ar.Read<int>();
    ArrayRef = new UEdGraphPinReference[arrayNum];
    
    for (int PinIdx = 0; PinIdx < arrayNum; ++PinIdx)
    {
        SerializePin(Ar, ref ArrayRef[PinIdx], PinIdx, RequestingPin, ResolveType, ref ArrayRef);
    }
}

public static bool SerializePin(FAssetArchive Ar, ref UEdGraphPinReference? PinRef, ...)
{
    bool bNullPtr = Ar.ReadBoolean();  // C# bool = 1 byte
    if (bNullPtr)
    {
        PinRef = null;
        return true;
    }
    
    var pinRef = new UEdGraphPinReference(Ar);  // OwningNode + PinId
    if (ResolveType == EPinResolveType.OwningNode)
    {
        PinRef = new UEdGraphPin(Ar);  // Complete pin
    }
    else
    {
        PinRef = pinRef;  // Just reference
    }
    return true;
}
```

**UEdGraphPinReference.cs (Line 9-14) — Pin 引用格式：**

```csharp
public class UEdGraphPinReference(FAssetArchive Ar)
{
    public FPackageIndex OwningNode = new FPackageIndex(Ar);  // 4 bytes
    public FGuid PinId = Ar.Read<FGuid>();  // 16 bytes
}
```

### 当前 Python 实现差异

**graph.py (Line 327-350) — read_pin_array()：**

```python
def read_pin_array(archive: FArchive, name_map: List[str], export_map: List[ObjectExport], 
                   import_map: List[ObjectImport], linker: Optional["PackageLinker"] = None) -> List[dict]:
    array_count = archive.read_i32()
    
    if array_count < 0:
        raise ParseError(f"Invalid pin array count: {array_count}")
    if array_count > MAX_LINKEDTO_PER_PIN:
        raise ParseError(f"Pin array count exceeds MAX_LINKEDTO_PER_PIN")
    
    pins: List[dict] = []
    for _ in range(array_count):
        pin_ref = read_pin_reference(archive, name_map, export_map, import_map, linker)
        if pin_ref is not None:
            pins.append(pin_ref)
    return pins
```

**graph.py (Line 284-324) — read_pin_reference()：**

```python
def read_pin_reference(archive: FArchive, name_map: List[str], export_map: List[ObjectExport], 
                       import_map: List[ObjectImport], linker: Optional["PackageLinker"] = None) -> Optional[dict]:
    b_null_ptr = archive.read_i32()  # ⚠️ UE C++ uses bool (1 byte), Python uses i32 (4 bytes)
    if b_null_ptr != 0:
        return None
    
    owning_node_index = archive.read_i32()
    pin_guid_bytes = archive.read_bytes(16)
    pin_guid = pin_guid_bytes.hex().upper()
    
    # Resolve owning node name
    # ...
    return {"owning_node": owning_node_name, "pin_guid": pin_guid}
```

**graph.py (Line 461-468) — read_ue_graph_pin() LinkedTo 读取：**

```python
# 13. LinkedTo array
linkedto_start = archive.tell()
try:
    linked_to = read_pin_array(archive, name_map, export_map, import_map, linker)
except Exception:
    linked_to = []  # ⚠️ 异常时返回空数组，可能导致位置不一致

# Line 544: 填充到 UEdGraphPin
linked_to_raw=linked_to,
```

**flow_builder.py (Line 630-674) — build_connections_map()：**

```python
def build_connections_map(graph: UEdGraph) -> Tuple[List[Dict], List[str]]:
    # 构建 pin_lookup
    pin_lookup: Dict[str, Tuple[str, str]] = {}
    for node in graph.nodes:
        for pin in node.pins:
            pin_lookup[pin.pin_id] = (node.node_guid, pin.pin_name)
    
    connections: List[Dict] = []
    warnings: List[str] = []
    
    for node in graph.nodes:
        for pin in node.pins:
            if pin.direction == 1:  # Output
                for linked_pin_ref in (pin.linked_to_raw or []):  # ⚠️ 如果 linked_to_raw 为空，无连接
                    target_pin_guid = linked_pin_ref.get("pin_guid") if isinstance(linked_pin_ref, dict) else linked_pin_ref
                    
                    if target_pin_guid in pin_lookup:
                        # 添加连接
                        connections.append({...})
                    else:
                        warnings.append(f"PinId {target_pin_guid} not found")
    
    return connections, warnings
```

### 根因结论

| 问题 | 根因 | 证据 |
|------|------|------|
| Connections=0 | `linked_to_raw` 为空数组 | `build_connections_map()` Line 657: `for linked_pin_ref in (pin.linked_to_raw or [])` |
| linked_to_raw 为空 | `read_pin_array()` 异常返回空数组 | graph.py Line 463-468: try/except 捕获异常返回 [] |
| 异常原因 | `b_null_ptr` 读取大小错误（i32 vs bool） | UE C++ bool=1 byte, Python i32=4 bytes — Phase 72-B 已修复为 read_i32（UE5 FArchive bool 是 uint32） |
| Phase 72-B 修复后仍失败 | LinkedTo 数组读取位置可能被其他字段错位影响 | 需验证 linkedto_start 位置是否正确 |

**核心差距：**
1. **缺少数据填充验证：** `read_pin_array()` 异常时返回空数组，但未记录异常原因
2. **缺少位置一致性验证：** 未验证 LinkedTo 读取后位置是否与预期一致

### 可行修复方案

1. **添加 LinkedTo 数据验证日志：**

```python
# graph.py Line 461-468 改进
linkedto_start = archive.tell()
try:
    linked_to = read_pin_array(archive, name_map, export_map, import_map, linker)
    linkedto_end = archive.tell()
    expected_size = ... # 计算预期大小
    if linkedto_end - linkedto_start != expected_size:
        logger.warning(f"LinkedTo size mismatch: expected {expected_size}, actual {linkedto_end - linkedto_start}")
except Exception as e:
    logger.error(f"LinkedTo read failed at pos {linkedto_start}: {e}")
    linked_to = []
```

2. **在 build_connections_map() 中添加非空验证：**

```python
# flow_builder.py Line 630 后添加
linked_to_count = sum(len(pin.linked_to_raw or []) for node in graph.nodes for pin in node.pins)
if linked_to_count == 0:
    warnings.append("WARNING: No LinkedTo data found in any pin — connections will be empty")
```

3. **验证 Pin 序列化顺序正确性：** 添加单元测试，验证 LinkedTo 前的所有字段读取位置正确

---

## M-03: Blueprint.functions 列表为空

### UE Editor 源码分析

**UBlueprintGeneratedClass (BPGC) 属性：**
- `UbergraphFunction` — FPackageIndex 引用，指向 EventGraph 入口函数
- `FunctionList` — TArray<FPackageIndex>，所有自定义函数引用
- `ImplementedInterfaces` — 接口列表

**BlueprintNodeExtractor.cs (CUE4Parse BPExtractor 示例) Line 234-243：**

```csharp
foreach (var export in exports)
{
    if (export.ExportType.Contains("BlueprintGeneratedClass"))
    {
        blueprintClass = export.Name;
        
        // 尝试获取 UbergraphFunction 引用
        if (export.TryGetLazy<string>("UbergraphFunction", out var uberGraph))
        {
            graphs.Add(uberGraph);
        }
    }
}
```

### 当前 Python 实现差异

**variable_extractor.py (Line 332-386) — _extract_functions_from_graphs()：**

```python
def _extract_functions_from_graphs(graphs) -> List[BlueprintFunction]:
    """从 EventGraph 的 K2Node_FunctionEntry 节点提取函数元数据（Fallback 路径）。
    
    ⚠️ 注释已说明这是 "Fallback 路径"，暗示应有主路径（从 BPGC 属性提取）
    """
    if not graphs:
        return []
    
    functions: List[BlueprintFunction] = []
    for graph in graphs:
        for node in getattr(graph, 'nodes', []):
            if getattr(node, 'class_name', '') == "K2Node_FunctionEntry":
                nd = node.node_data or {}
                if not isinstance(nd, dict):
                    continue
                fr = nd.get("function_reference")
                func_name = "Unknown"
                if fr and hasattr(fr, 'member_name'):
                    func_name = fr.member_name if fr.member_name != "None" else "Unknown"
                # ⚠️ Line 349: member_name 可能解析为 "None"（字符串）
                elif isinstance(nd, dict):
                    func_name = nd.get("function_name", nd.get("custom_function_name", "Unknown"))
                # ... 参数提取
    return functions
```

**variable_extractor.py (Line 389-429) — extract_blueprint_metadata()：**

```python
def extract_blueprint_metadata(export, archive, import_map, export_map, name_map, summary, linker=None, graphs=None):
    from uasset_read.parsers.property_parser import parse_properties_from_export
    
    if export is None or export.serial_size <= 0:
        return None, None
    
    # 解析 export 属性
    try:
        properties = parse_properties_from_export(
            export, archive, summary, name_map, export_map, import_map,
        )
    except Exception:
        return None, None
    
    # ⚠️ Line 489: functions 仅从 graphs 提取（Fallback 路径）
    functions = _extract_functions_from_graphs(graphs) if graphs else []
    # ...
```

### 根因结论

| 问题 | 根因 | 证据 |
|------|------|------|
| functions 列表为空 | 仅从 Graph 节点提取，缺少 BPGC 属性提取路径 | Line 489: `functions = _extract_functions_from_graphs(graphs)` |
| Fallback 路径失败 | Graph 可能未解析或 K2Node_FunctionEntry 未识别 | `_extract_functions_from_graphs()` 注释说明是 Fallback |
| function_reference.member_name = "None" | FMemberReference 序列化可能失败 | Line 349: `fr.member_name` 解析为字符串 "None" |

### 可行修复方案

1. **添加 BPGC 属性提取路径：**

```python
def extract_blueprint_metadata(export, archive, ...):
    # 主路径：从 BPGC export 属性提取
    properties = parse_properties_from_export(export, ...)
    functions_from_bpgc = []
    
    for prop in properties:
        if prop.name == "UbergraphFunction":
            # 提取函数引用
            func_ref = prop.value  # FPackageIndex
            # ...
        elif prop.name == "FunctionList":
            # 提取函数列表
            for func_idx in prop.value:
                # ...
    
    # Fallback：从 Graph 节点提取
    functions_from_graphs = _extract_functions_from_graphs(graphs) if graphs else []
    
    # 合并结果
    all_functions = functions_from_bpgc + functions_from_graphs
```

2. **修复 FMemberReference 序列化：** 验证 `member_name` 是否正确读取（可能需要修复 serializers）

---

## M-04: 函数参数信息缺失

### UE Editor 源码分析

**K2Node_FunctionEntry 节点 Pins：**
- 每个 Pin 对应一个函数参数
- PinType.PinCategory 表示参数类型（float, bool, object, struct 等）
- Direction 区分输入参数（EGPD_Input）和返回值（EGPD_Output）

### 当前 Python 实现差异

**variable_extractor.py (Line 354-375) — 参数提取：**

```python
for pin in getattr(node, 'pins', []):
    pin_dir = getattr(pin, 'direction', '')
    pin_type_obj = getattr(pin, 'pin_type', None)
    pin_type_name = ""
    
    if pin_type_obj and hasattr(pin_type_obj, 'pin_category'):
        pin_type_name = getattr(pin_type_obj, 'pin_category', '') or ""
    elif isinstance(pin_type_obj, dict):
        pin_type_name = pin_type_obj.get("pin_category", ...)
    
    if pin_dir == "EGPD_Output" and pin_type_name:
        if return_type == "":
            return_type = pin_type_name
    elif pin_dir == "EGPD_Input" and pin_type_name:
        if pin_type_name.lower() == "exec":
            continue
        parameters.append(FunctionParameter(
            name=getattr(pin, 'pin_name', ''),
            param_type=pin_type_name,
        ))
```

### 根因结论

| 问题 | 根因 | 证据 |
|------|------|------|
| 参数类型缺失 | PinType.PinCategory 未正确填充 | M-01 和 M-02 的根因会影响 Pin 序列化 |
| 返回值为空 | Direction 识别可能错误 | Line 365: `if pin_dir == "EGPD_Output"` |
| 参数名缺失 | pin_name 可能未正确读取 | Line 373: `name=getattr(pin, 'pin_name', '')` |

**依赖关系：** M-04 依赖 M-01/M-02/M-03 的修复。Pin 数据完整性是参数提取的前提。

---

## 综合修复可行性评估

### 修复顺序（按依赖关系）

| 顺序 | 问题 | 修复难度 | 依赖项 | 预期收益 |
|------|------|---------|--------|---------|
| 1 | M-02 Pin 连接 | **LOW** | 无 | 验证 LinkedTo 数据填充，为所有后续修复提供基础 |
| 2 | M-01 StructProperty | **MEDIUM** | M-02 | Vector/Rotator 专用解析 + 类型名提取验证 |
| 3 | M-03 Functions | **MEDIUM** | M-02 | BPGC 属性提取路径 + Fallback 修复 |
| 4 | M-04 参数信息 | **LOW** | M-02, M-01, M-03 | Pin 数据完整性修复后自动解决 |

### 修复工作量估算

| 任务 | 工作量 | 风险 |
|------|--------|------|
| M-02 添加 LinkedTo 验证日志 | 1-2 hours | LOW |
| M-02 添加 build_connections_map 非空检查 | 30 min | LOW |
| M-01 Vector/Rotator 专用解析 | 1-2 hours | LOW（直接读取 3 float） |
| M-01 类型名提取单元测试 | 1-2 hours | LOW |
| M-03 BPGC 属性提取路径 | 2-4 hours | MEDIUM（需要验证 BPGC export 格式） |

### 验收标准

- [ ] `RelativeLocation` 提取为 `{X: float, Y: float, Z: float}`
- [ ] `RelativeRotation` 提取为 `{Pitch: float, Yaw: float, Roll: float}`
- [ ] EventGraph `connections` 数组 > 0（非空）
- [ ] `Blueprint.functions` 包含 `Move`, `Aim`, `JumpStart`, `JumpEnd`
- [ ] 每个函数输出包含 `parameters` 列表（参数名 + 类型）

---

## Sources

### Primary (HIGH confidence)
- CUE4Parse FPropertyTag.cs (Line 136-233) — PropertyTag UE5 format [VERIFIED: CUE4Parse repo]
- CUE4Parse FStructFallback.cs (Line 23-34) — Fallback mechanism [VERIFIED: CUE4Parse repo]
- CUE4Parse FScriptStruct.cs (Line 68-427) — Struct dispatch logic [VERIFIED: CUE4Parse repo]
- CUE4Parse FVector.cs (Line 54-59) — Vector direct read [VERIFIED: CUE4Parse repo]
- CUE4Parse FRotator.cs (Line 47-61) — Rotator direct read [VERIFIED: CUE4Parse repo]
- CUE4Parse UEdGraphPin.cs (Line 57-138, Line 86) — LinkedTo serialization [VERIFIED: CUE4Parse repo]
- UE BodyInstance.h (Line 35) — Custom Serialize operator [VERIFIED: UE source]
- UE BodyInstance.cpp (Line 422-438) — Serialize implementation [VERIFIED: UE source]

### Secondary (MEDIUM confidence)
- uasset-format property-tag.md — FPropertyTag field table [CITED: project reference]
- Blueprint 节点文本参考.md — LinkedTo 文本格式示例 [CITED: project reference]

### Tertiary (LOW confidence)
- BlueprintNodeExtractor.cs — BPGC UbergraphFunction 提取示例 [ASSUMED: from CUE4Parse integration guide]

---

## Metadata

**Confidence breakdown:**
- StructProperty parsing: **HIGH** — CUE4Parse source verified, UE C++ source verified
- Pin connection: **HIGH** — CUE4Parse source verified, Python implementation analyzed
- Functions extraction: **MEDIUM** — CUE4Parse example assumed, Python implementation analyzed
- Parameters: **MEDIUM** — Depends on Pin data integrity

**Research date:** 2026-05-23
**Valid until:** 2026-06-23 (UE5 format stable)