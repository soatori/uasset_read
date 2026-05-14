---
phase: 22-节点序列化修复
plan: 07
status: research
---
# Phase 22 Plan 07 Research: Direction 和 PinType 序列化格式

## 研究目标

确定 UEdGraphPin::Serialize 中 Direction 字段和 PinType 字段的准确序列化格式，解决 TEST-02/03/04 失败问题。

## UE 源码验证

### 1. Direction 字段定义

**源码位置**: `EdGraphPin.h L312`
```cpp
/** Direction of flow of this pin (input or output) */
TEnumAsByte<enum EEdGraphPinDirection> Direction;
```

**源码位置**: `EnumAsByte.h L116`
```cpp
uint8 Value;
```

**结论**: TEnumAsByte 存储 1 byte。

### 2. Direction 序列化位置

**源码位置**: `EdGraphPin.cpp L1870-1872`
```cpp
Ar << PinToolTip;
Ar << Direction;
PinType.Serialize(Ar);
```

**结论**: Direction 紧接在 PinToolTip 之后。

### 3. TEnumAsByte 序列化验证

FArchive::operator<<(TEnumAsByte) 直接序列化为 uint8，没有额外字节。

**结论**: Direction 应该占用 1 byte。

### 4. PinToolTip 序列化验证

**源码位置**: `EdGraphPin.cpp L1870`
```cpp
Ar << PinToolTip;
```

PinToolTip 是 FString，序列化格式：
- Length (int32, 4 bytes)
- Data (if length > 0)

空字符串：Length = 0（4 bytes），Data = 0 bytes

**结论**: 空字符串 PinToolTip 应该占用 4 bytes。

### 5. PinType 序列化验证

**源码位置**: `EdGraphPin.cpp L163-299`
```cpp
bool FEdGraphPinType::Serialize(FArchive& Ar)
{
    Ar << PinCategory;
    Ar << PinSubCategory;
    Ar << Object;  // PinSubCategoryObject
    Ar << ContainerType;
    ...
}
```

PinCategory 是 FName（UE5 格式）：
- Bundle index (int32, 4 bytes)
- Name index (int32, 4 bytes)
- Total: 8 bytes

**结论**: PinCategory 应该占用 8 bytes。

## 22-06-SUMMARY 实测数据分析

| Offset | 字段 | 值 | 预期 | 状态 |
|--------|------|-----|------|------|
| 93357 | PinName | 8 bytes | 8 bytes | ✓ |
| 93365-93374 | PinFriendlyName | 9 bytes | 9 bytes | ✓ |
| 93374-93380 | PinToolTip | 6 bytes | 4 bytes | ✗ |
| 93380 | Direction | 1 byte (0) | 1 byte | ✓ |
| 93381-93382 | 额外数据 | 2 bytes (00 00) | 0 bytes | ✗ |
| 93383 | PinCategory | 8 bytes | 8 bytes | ✓ |

**关键发现**:
- PinToolTip 实测 6 bytes，预期 4 bytes（空字符串）
- Direction 后有 2 bytes 额外数据（00 00）
- PinCategory 位置偏移了 2 bytes

## 根因分析

### 假设 1: PinToolTip 不是 FString

**可能性**: 低
- UE 源码明确显示 `Ar << PinToolTip;`，使用标准 FString 序列化
- PinToolTip 声明为 `FString PinToolTip;`

### 假设 2: 编译器内存对齐

**可能性**: 中
- 不同编译器可能有不同的内存对齐策略
- Direction (TEnumAsByte<uint8>) 可能被对齐到 2 或 4 字节边界

**验证方法**:
- 检查 UE 5.7 编译器配置
- 检查是否有 #pragma pack 指令

### 假设 3: 版本特定的序列化格式

**可能性**: 高
- UE 5.7 可能有新的序列化格式
- PinToolTip 或 Direction 可能有新的序列化方式

**验证方法**:
- 检查 UE 5.7 的 CustomVersion 定义
- 检查是否有版本特定的代码分支

### 假设 4: Python 代码问题

**可能性**: 高
- `read_fstring()` 可能读取了额外的字节
- `read_u8()` 可能有偏移问题

**验证方法**:
- 检查 `read_fstring()` 实现
- 使用 hexdump 验证数据

## 实验验证方案

### 实验 1: PinToolTip 格式验证

```python
# 检查 PinToolTip 的原始字节
offset = 93374
data = archive.read_bytes(6)
print(f"PinToolTip raw: {data.hex()}")  # 预期: 00 00 00 00 ?? ??
```

**预期结果**:
- 如果前 4 bytes 是 00 00 00 00，说明是空字符串
- 后 2 bytes 需要分析

### 实验 2: Direction 格式验证

```python
# 尝试读取 1 和 2 bytes
direction_u8 = archive.read_u8()
direction_u16 = archive.read_u16()
print(f"Direction (u8): {direction_u8}")
print(f"Direction (u16): {direction_u16}")
```

**预期结果**:
- 如果 u8=0 且 u16=0，可能是内存对齐
- 如果 u16!=0，可能是新的序列化格式

### 实验 3: PinCategory 位置验证

```python
# 读取 PinCategory，检查索引是否正确
pin_category = archive.read_name(name_map)
print(f"PinCategory: {pin_category}")  # 预期: "exec"
```

**预期结果**:
- 如果读取的 index=148→"exec"，说明位置正确
- 如果 index 不是 148，说明偏移错误

## 可能的解决方案

### 方案 1: 添加动态字节验证

在读取 Direction 后，验证 PinCategory 的 index 是否合理。如果不合理，尝试跳过 1 或 2 bytes。

### 方案 2: 使用版本检测

检查 UE 版本，对不同版本使用不同的序列化格式。

### 方案 3: 模式扫描

使用模式扫描找到正确的 PinCategory 位置。

## 下一步行动

1. 运行实验验证方案，收集数据
2. 根据实验结果确定正确的序列化格式
3. 修改代码实现正确的解析逻辑
4. 运行 TEST-02/03/04 验证修复效果

---
*Research completed: 2026-05-05*
*Next step: Plan implementation based on experimental results*