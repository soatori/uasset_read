# BPGC Cooked 字节码格式

## 概述

BlueprintGeneratedClass (BPGC) 是 Unreal Engine 蓝图资产的编译产物。在 cooked 构建中，蓝图函数的字节码不再以独立 UFunction export 的 `ScriptBytecode` 存储，而是集中嵌入到 BPGC export 的 `script_serial_region` 中。本文档描述该 cooked 字节码的二进制布局和格式变体。

**适用范围**: 仅适用于未烘焙/编辑器保存的蓝图资产。Cooked/Pak 资产的图数据已被剥离。

**UE 源码参考**:
- `Engine/Source/Runtime/CoreUObject/Private/UObject/Class.cpp` — `FStructScriptLoader`
- `Engine/Source/Runtime/CoreUObject/Private/UObject/BlueprintGeneratedClass.cpp`

## 字节码布局

BPGC `script_serial_region` 中 PropertyTags 终结符 ("None") 之后的数据为 cooked 字节码区域，布局如下:

```
┌──────────────────────────────────────────────────┐
│ [i32] BytecodeBufferSize                         │  BPGC class 自身脚本大小
│ [i32] SerializedScriptSize                       │  BPGC class 脚本序列化大小
├──────────────────────────────────────────────────┤
│ [SerializedScriptSize bytes] class script data   │  (仅当 SerializedScriptSize > 0)
├──────────────────────────────────────────────────┤
│ [u32] num_functions                              │  函数字节码条目数
├──────────────────────────────────────────────────┤
│ [num_functions × i32] bytecode_size[]            │  各函数字节码大小
├──────────────────────────────────────────────────┤
│ [concatenated bytecode data]                     │  拼接的函数字节码
└──────────────────────────────────────────────────┘
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| BytecodeBufferSize | i32 | BPGC class 自身的脚本缓冲区大小（通常为 0） |
| SerializedScriptSize | i32 | BPGC class 脚本序列化大小；> 0 时存在 class script data |
| num_functions | u32 | 函数字节码条目数（即蓝图中编译的函数数量） |
| bytecode_size[i] | i32 | 第 i 个函数的字节码大小（字节）；-1 或 0 表示空函数 |
| bytecode data | bytes | 按声明顺序拼接的各函数字节码 |

### 字节序

所有多字节整数均为 **小端序 (Little-Endian)**，与 UE 在 Windows/Linux 平台的默认序列化一致。

## 格式变体

### 标准格式 (UE4/UE5 编辑器保存)

最常见的变体。BPGC class 自身脚本为空（`BytecodeBufferSize = 0`, `SerializedScriptSize = -1`），所有字节码数据紧跟在函数数量和大小数组之后。

```
[00 00 00 00] [FF FF FF FF]  BytecodeBufferSize=0, SerializedScriptSize=-1
[0C 00 00 00]                num_functions=12
[14 00 00 00] [1B 00 00 00] ...  各函数字节码大小
[bytecode_0] [bytecode_1] ...    拼接的字节码
```

### 含 Class Script 的格式

少数资产的 BPGC class 自身包含脚本数据（`SerializedScriptSize > 0`）。此时需先跳过 class script 区域再读取函数数量。

```
[00 00 00 00] [10 00 00 00]  BytecodeBufferSize=0, SerializedScriptSize=16
[class_script: 16 bytes]     BPGC class 自身脚本
[08 00 00 00]                num_functions=8
...
```

### 空字节码格式

某些蓝图（如纯数据蓝图或无自定义函数的蓝图）的字节码区域仅包含 header，函数数量为 0 或 SerializedScriptSize 为 0 且无后续数据。

## 哨兵字节

每个函数字节码以操作码流结束，最后一个字节应为结束哨兵:

| 哨兵 | 值 | 说明 |
|------|------|------|
| EX_EndOfScript | 0x53 | 标准 UStruct 字节码结束标记 |
| Cooked End Sentinel | 0xDD | 部分 UE5 cooked 资产中观察到的变体哨兵 |

解析器在容错模式下同时接受两种哨兵。未以预期哨兵结束的缓冲区会被记录到诊断指标中。

## 诊断指标

`BPGCExtractionMetrics` 数据类记录提取过程的质量信息，用于评估结果可信度:

| 指标 | 类型 | 说明 |
|------|------|------|
| total_raw_bytes | int | 脚本区域可用字节总数 |
| declared_function_count | int | header 中声明的函数数量 |
| extracted_buffer_count | int | 实际提取的缓冲区数量 |
| empty_buffer_count | int | 空缓冲区数量 (size <= 0) |
| sentinel_mismatch_count | int | 未以预期哨兵结束的缓冲区数量 |
| truncated_buffer_count | int | 因数据不足而被截断的缓冲区数量 |
| mapped_function_count | int | 成功映射到函数导出的缓冲区数量 |
| mapping_mismatch | bool | 缓冲区数量与函数导出数量是否不一致 |

### 置信度级别

根据指标自动计算:

| 级别 | 条件 |
|------|------|
| HIGH | 所有缓冲区正常提取，哨兵正确，数量一致 |
| MEDIUM | 存在哨兵不匹配或数量不一致，但大部分数据可用 |
| LOW | 存在截断、大量空缓冲区或提前退出 |
| UNRECOVERABLE | 无可用数据 |

## 字节码到函数的映射

BPGC cooked 字节码缓冲区与 Function export 的映射遵循 **顺序对应** 原则: 字节码缓冲区在 BPGC script_serial_region 中的声明顺序与 Function export 在导出表中的顺序一致。

当缓冲区数量与函数导出数量不一致时，按较小数量配对，多余部分被丢弃，并记录 `mapping_mismatch` 诊断。

## 已知限制

1. **仅支持编辑器保存资产**: Cooked/Pak 资产的 BPGC 字节码已被剥离
2. **顺序映射假设**: 依赖字节码缓冲区与 Function export 的顺序一致性；若 UE 内部排序变化可能导致映射错误
3. **哨兵变体**: 0xDD 哨兵的确切来源（UE 版本/平台差异）尚未完全确认
4. **class script 跳过**: SerializedScriptSize 为负值时被视为空，可能遗漏某些格式变体
