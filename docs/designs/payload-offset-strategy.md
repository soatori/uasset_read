# Payload 偏移策略架构决策

> **Issue:** #100, #84  
> **状态:** 已实现，本文档化架构决策

## 概述

本项目 payload 偏移策略默认使用 `SerialOffset/SerialSize`，与 UE `LinkerLoad.cpp:4793` 对齐。
`ScriptSerializationStartOffset` 仅在特定条件下使用。

## UE 源码行为

```cpp
// LinkerLoad.cpp L4786-4806
int64 StartPos = Export.SerialOffset;  // 默认使用 SerialOffset

if (UEVer() >= SCRIPT_SERIALIZATION_OFFSET) {
    if (bIsLoadingToPropertyBagObject || !bDoesSavedClassMatchActualClass) {
        // 仅在特定运行时条件时使用 ScriptSerialization 偏移
        StartPos += Export.ScriptSerializationStartOffset;
    }
}
```

### UE 运行时条件分析

| 条件 | 只读解析器场景 | 结果 |
|------|---------------|------|
| `bIsLoadingToPropertyBagObject` | 不创建 PropertyBag placeholder | 始终 false |
| `!bDoesSavedClassMatchActualClass` | 不加载真正 UClass | 始终 false |

**结论:** UE 运行时条件在只读场景下始终不满足，默认使用 `SerialOffset/SerialSize` 是正确策略。

## 项目实现

### Linker 层 (`link/linker.py`)

```python
# L388-402: Issue #67
seek_offset = instance.serial_offset
effective_serial_size = instance.serial_size
exp = self._export_map[index]

if self._uses_script_serialization_offset(exp):
    sss_offset = getattr(exp, 'script_serialization_start_offset', 0)
    sse_offset = getattr(exp, 'script_serialization_end_offset', 0)
    if sss_offset > 0:
        seek_offset = instance.serial_offset + sss_offset
        effective_serial_size = sse_offset - sss_offset
```

### Property Parser 层 (`parsers/property_parser.py`)

```python
# L347-358: 属性解析起始位置
property_start = export.serial_offset  # 默认使用 SerialOffset

# ScriptSerialization 绝对偏移存储用于诊断
export._script_serialization_start_absolute = (
    export.serial_offset + getattr(export, 'script_serialization_start_offset', 0)
)
export._script_serialization_end_absolute = (
    export.serial_offset + getattr(export, 'script_serialization_end_offset', 0)
)
```

### 条件判断 (`_uses_script_serialization_offset`)

```python
# L436-463
def _uses_script_serialization_offset(self, exp) -> bool:
    """检查是否应使用 ScriptSerializationStartOffset。"""
    # 条件：
    # 1. UE 版本 >= UE5_SCRIPT_SERIALIZATION_OFFSET (1004)
    # 2. 非 UnversionedProperties
    # 3. script_serialization_start_offset > 0
    ...
```

## 简化决策理由

1. **只读解析器不创建运行时对象** — `bIsLoadingToPropertyBagObject` 始终 false
2. **不进行类匹配验证** — `bDoesSavedClassMatchActualClass` 始终 true
3. **UE 运行时条件在只读场景下不满足** — 默认 SerialOffset 是正确策略

## 诊断支持

ScriptSerialization 偏移保留为诊断字段：
- `export._script_serialization_start_absolute`
- `export._script_serialization_end_absolute`
- `export.transforms["serialization_control"]`

这些字段可用于：
- 偏移错位诊断
- UE 版本兼容性分析
- 调试日志输出

## 参考

- UE 源码: `Engine/Source/Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp:4786-4806`
- 项目约束: `.claude/rules/constraints.md` → Payload 偏移默认策略
- 相关 Issue: #67, #100, #84
