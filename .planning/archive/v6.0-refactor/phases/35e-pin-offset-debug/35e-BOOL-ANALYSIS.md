# Phase 35e 补充分析 — 布尔值序列化验证结果

**日期：** 2026-05-14
**来源：** Phase 35e 执行后深度审查 + UE 源码验证

---

## 1. 关键发现：UE 编辑器中的 bool 序列化

### 1.1 UE 源码验证

根据 `E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Core/Private/Serialization/Archive.cpp` L511-526：

```cpp
#if WITH_EDITOR
void FArchive::SerializeBool( bool& D )
{
    // Serialize bool as if it were UBOOL (legacy, 32 bit int).
    uint32 OldUBoolValue;
    // ...
    this->Serialize(&OldUBoolValue, sizeof(OldUBoolValue));  // 4 bytes!
}
```

**结论：在 UE 编辑器构建中，`Ar << bool` 序列化为 4 字节 uint32，而非 1 字节。**

### 1.2 EdGraphPin.cpp 验证

```cpp
// EdGraphPin.cpp L248-252
bool bIsReferenceBool = bIsReference;
bool bIsWeakPointerBool = bIsWeakPointer;
Ar << bIsReferenceBool;    // 在编辑器构建中 = 4 bytes
Ar << bIsWeakPointerBool;  // 在编辑器构建中 = 4 bytes
```

---

## 2. 对当前代码的影响

### 2.1 当前代码是正确的

`graph.py` 中使用 `read_bool()`（4 字节）对于**编辑器保存的未烘焙 .uasset 文件**是**正确的**。

Phase 35e 引入的 `read_bool_ue5()`（1 字节）实际上是**错误的方向**——它会导致**额外的 -3 字节偏移 per bool**。

### 2.2 需要修正的 Phase 35e 修复

Phase 35e 的 D2（bSerializeAsSinglePrecisionFloat）和 D3（bIsUObjectWrapper）修复使用了 `read_bool()`，这是**正确的**。

但如果有任何地方改用了 `read_bool_ue5()`，需要改回 `read_bool()`。

---

## 3. 真正的偏移问题

既然 bool 序列化是正确的（4 字节），那么 linked_to_raw 为空的 4 字节偏移来源是什么？

### 3.1 可能的偏移来源

| 可能原因 | 说明 | 验证方式 |
|---------|------|---------|
| **FEdGraphPinType 字段顺序** | 字段读取顺序与 UE 源码不一致 | 逐字段对比 EdGraphPin.cpp L163-346 |
| **缺失的中间字段** | 某些版本条件下有额外字段 | 检查 CustomVersion 条件 |
| **PinType 与 Pin 之间的 padding** | UE 可能在某些版本添加 padding | 二进制跟踪验证 |
| **FMemberReference 字段** | MemberScope 是 FString 而非 FName | 检查 MemberReference.cpp |
| **UE5 ScriptSerializationOffset 计算** | pins_offset 计算可能有误 | 检查 graph.py L818-819 |

### 3.2 需要进一步调查

1. **UE5 资产的 CustomVersion 条件**：某些字段可能在特定 CustomVersion 之后才存在
2. **FText 序列化差异**：history_type=-1 时的 bHasCultureInvariantString 确认为 4 字节（正确）
3. **BitField 位置**：UE5 的 BitField 是 uint32（4 字节），当前代码正确（L515）

---

## 4. 结论

### 4.1 不需要修改的部分

- `read_bool()` 在 graph.py 中的使用是**正确的**（编辑器资产用 4 字节）
- 不需要改为 `read_bool_ue5()`

### 4.2 需要继续调查的部分

1. **FEdGraphPinType 字段顺序**：逐字段对比 UE 源码
2. **CustomVersion 条件**：检查是否有遗漏的版本条件
3. **pins_offset 计算**：验证 script_serial_offset + script_serial_size 是否正确

### 4.3 建议

使用二进制跟踪工具（debug_trace_pin.py 等）逐字节对比 UE 序列化输出，精确定位偏移来源。

---

*分析日期: 2026-05-14*
*UE 源码版本: UE 5.7*
*结论: bool 序列化正确（4 字节），偏移来源需进一步调查*
