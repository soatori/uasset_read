# Phase 72-I CUE4Parse 方案校对报告

**校对日期:** 2026-05-24
**参考项目:** CUE4Parse (`E:\Develop\lib\CUE4Parse\`)
**校对文件:** `UEdGraphPin.cs`, `UEdGraphPinReference.cs`, `UEdGraphNode.cs`, `FArchive.cs`, `FPropertyTag.cs`, `FScriptStruct.cs`, `FVector.cs`, `FRotator.cs`

## 1. Pin 序列化格式 — ✅ 完全一致

CUE4Parse `UEdGraphPin` 构造函数 (UEdGraphPin.cs:57-99) 的字段读取顺序与 Python `read_ue_graph_pin()` (graph.py:356-527) **完全一致**：

| 步骤 | CUE4Parse | Python | 匹配 |
|------|-----------|--------|------|
| OwningNode | `base(Ar)` → PinReference | `read_i32()` | ✅ |
| PinName | `ReadFName()` / `ReadFString()` (version check) | `read_name()` | ✅ |
| PinFriendlyName | `new FText(Ar)` (EditorOnly) | `read_ftext_with_history` (try/except) | ✅ |
| SourceIndex | `Ar.Read<int>()` (version check) | `read_i32()` | ✅ |
| PinToolTip | `Ar.ReadFString()` | `read_fstring()` | ✅ |
| Direction | `Ar.Read<EEdGraphPinDirection>()` (u8) | `read_u8()` | ✅ |
| PinType | `new FEdGraphPinType(Ar)` | `read_ed_graph_pin_type()` | ✅ |
| DefaultValue | `Ar.ReadFString()` | `read_fstring()` | ✅ |
| AutoDefaultValue | `Ar.ReadFString()` | `read_fstring()` | ✅ |
| DefaultObject | `new FPackageIndex(Ar)` | `read_i32()` | ✅ |
| DefaultTextValue | `new FText(Ar)` | `read_ftext_with_history` | ✅ |
| LinkedTo | `SerializePinArray(Ar, LinkedTo, LinkedTo)` | `read_pin_array()` | ✅ |
| SubPins | `SerializePinArray(Ar, SubPins, SubPins)` | `read_pin_array()` | ✅ |
| ParentPin | `SerializePin(Ar, ParentPin, ParentPin)` | 条件读取 (8B/24B) | ✅ |
| RefPassThrough | `SerializePin(Ar, RefPassThrough, ...)` | 条件读取 (8B/24B) | ✅ |
| PersistentGuid | `Ar.Read<FGuid>()` (EditorOnly) | `read_bytes(16)` | ✅ |
| BitField | `Ar.Read<uint>()` (EditorOnly) | `read_u32()` | ✅ |

**结论：无需修改 Python Pin 序列化顺序。**

## 2. FString 读取方案 — ✅ CUE4Parse 提供了更好的容错策略

**CUE4Parse `ReadFString()` (FArchive.cs:449-506):**

```csharp
var length = Read<int>();
if (length == int.MinValue) throw;           // 完整性检查
if (Math.Abs(length) > Length - Position)    // 边界检查 ← 关键！
    throw new ParserException($"Invalid FString length '{length}'");
if (length == 0) return string.Empty;
// UTF-16: 检查末尾 2 字节为 0x0000
// UTF-8:  检查末尾 1 字节为 0x00
if (末尾非空终止符) throw;                    // null termination 验证
// 返回 substring(0, length-1) — 去掉终止符
```

**Python 当前 `read_fstring()` (archive.py:233-258):**

```python
length = read_i32()
if length > MAX_FSTRING_LENGTH: raise        # 仅检查上限
# 无边界检查 ← 缺失！
# 无空终止符验证 ← 缺失！
if '\x00' in result: return ""               # 内部 null 检测 ← 问题根因！
```

**Python vs CUE4Parse 关键差异：**

| 特性 | CUE4Parse | Python 当前 | 影响 |
|------|-----------|-----------|------|
| 边界检查 | `Math.Abs(length) > Length - Position` | 无 | 垃圾 length 导致过度读取 |
| 空终止符验证 | 强制验证（含 preprocessor 开关） | 无 | 未检测到格式错误 |
| 内部 null 检测 | **无** | `'\x00' in result` → return "" | 合法短字符串被误杀 |
| 失败处理 | 抛 ParserException | 返回 "" 但位���已消费 | 级联偏移错位 |

**校对结论 — FString 修复方案校准：**

PLAN.md Wave 2 Task 2A 的修复方向与 CUE4Parse 一致：
1. ✅ 添加 `abs(length) > remaining_bytes` 边界检查
2. ✅ 移除内部 null 字节检测（`'\x00' in result`）
3. ✅ 添加空终止符验证（检查最后一个字节为 0x00）
4. ⚠️ 需要增加：失败时 seek 回读取 `length` 前的位置

## 3. 节点发现架构 — ✅ CUE4Parse 不使用 nodes_count

**CUE4Parse `UEdGraphNode.Deserialize()` (UEdGraphNode.cs:11-17):**

```csharp
public override void Deserialize(FAssetArchive Ar, long validPos)
{
    base.Deserialize(Ar, validPos);  // 标准 UObject tagged property 序列化
    if (FBlueprintsObjectVersion >= EdGraphPinOptimized)
    {
        UEdGraphPin.SerializeAsOwningNode(Ar, ref Pins);
    }
}
```

**关键发现：CUE4Parse 没有 `read_ue_graph()` 函数！**

CUE4Parse 的节点发现完全依赖标准的 UE Object 序列化系统：
1. 扫描 ExportMap — 每个 export 有 `outer_index`
2. 找到 `outer_index == graph_export_idx` 的 export → 这是图节点
3. 对每个节点调用 `Deserialize()` → 标准 serialization 处理 tagged properties + pins

**校对结论 — 节点发现方案校准：**

PLAN.md Wave 1 Task 1.2 将 outer_index 扫描改为 PRIMARY 方法，与 CUE4Parse 架构完全一致。

CUE4Parse 的实践证明：在 `.uasset` 格式中，节点通过 **sub-object 关系**（outer_index）关联到 graph，不应依赖 graph 手动序列化的 nodes_count。

## 4. PropertyTag 读取 — ✅ 类型名链式格式一致

**CUE4Parse `FPropertyTag` 构造函数 (FPropertyTag.cs:136-199):**

```csharp
if (Ar.Ver >= PROPERTY_TAG_COMPLETE_TYPE_NAME)
{
    var remaining = 1;
    do {
        var node = new FPropertyTypeNameNode(Ar);  // Name(FName) + InnerCount(i32)
        nodes.Add(node);
        remaining += node.InnerCount - 1;
    } while (remaining > 0);
    PropertyType = nodes.GetName();  // 第一个节点的 Name
    TagData = new FPropertyTagData(nodes, Name.Text);
    Size = Ar.Read<int>();
    PropertyTagFlags = Ar.Read<byte>();
    // ...
}
```

**校对结论：** UE5.4+ FPropertyTypeNameNode 链式读取格式正确。`remaining` 计数器逻辑与 Python 逻辑一致。

## 5. Vector/Rotator 快速路径 — ✅ 格式一致

**CUE4Parse:**
- `FVector(FArchive Ar)` → `ReadFReal(), ReadFReal(), ReadFReal()` (顺序: X, Y, Z)
- `FRotator(FArchive Ar)` → `ReadFReal(), ReadFReal(), ReadFReal()` (顺序: Pitch, Yaw, Roll)

**Python:**
- Vector fast-path: `read_f32(), read_f32(), read_f32()` (顺序: X, Y, Z)
- Rotator fast-path: `read_f32(), read_f32(), read_f32()` (顺序: Pitch, Yaw, Roll)

**校对结论：** 读取顺序完全一致。唯一的差异是 CUE4Parse 使用 `ReadFReal()` (可能读 f64 for UE5 double-precision)，但 BP_FirstPersonCharacter 测试资产使用 f32 格式。

## 6. 校对总结

| PLAN.md 修复点 | CUE4Parse 验证结果 | 需要调整 |
|----------------|-------------------|---------|
| Wave 1 Task 1.1: JSON 递归序列化 | 不适用（CUE4Parse 使用 Newtonsoft.Json） | 无 |
| Wave 1 Task 1.2: 节点发现 fallback | ✅ 确认：outer_index 应为 PRIMARY 方法 | 更新为"始终执行，不做 fallback 条件判断" |
| Wave 2 Task 2A: FString 容错 | ✅ 确认：边界检查 + 空终止符验证 + 移除内部 null 检测 | 增加失败时 seek-back 恢复 |
| Wave 2 Task 2B: LinkedTo 恢复 | ✅ 确认：SerializePinArray 格式正确 | 无 |
| Wave 3 Task 3B: Vector/Rotator 验证 | ✅ 确认：读取顺序 (X,Y,Z) / (Pitch,Yaw,Roll) | 注意 UE5 FReal 可能为 f64 |
| Wave 3 Task 3D: Comment 字段 | ✅ CUE4Parse 通过 tagged properties 自动处理 | 验证 PropertyTag 循环是否覆盖所有 Comment 字段 |

## 7. 方案调整建议

### 建议 1: FString 修复完全对齐 CUE4Parse

```
read_fstring() 修复策略：
1. 记录 pos_before = tell()
2. length = read_i32()
3. 边界检查: abs(length) > remaining_bytes → seek(pos_before) + raise ParseError
4. 读取 data[pos:pos+abs(length)]
5. 空终止符验证: 最后一个字节 != 0 → seek(pos_before) + raise ParseError  
6. 移除 '\x00' in result 检测
7. 返回 rstrip('\x00') 后的内容
```

### 建议 2: 节点发现改为 CUE4Parse 模式

```
read_ue_graph() 改为：
1. 不再读取 nodes_count
2. 扫描 export_map: outer_index == graph_export_idx
3. 对每个匹配的 export 调用 read_ue_graph_node()
4. 保留 Schema/GraphGuid/bEditable 的读取（graph 自身的属性）
```

**风险评估：** 这个改动较大，可能影响除 BP_FirstPersonCharacter 以外的其他资产。建议先扩展 fallback 条件（PLAN.md 当前方案），验证通过后再考虑完全重写。
