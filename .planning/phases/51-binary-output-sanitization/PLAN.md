# Phase 51: 二进制输出清理 — 消除 JSON 中的二进制/十六进制泄漏

**目标**: 修复 `pin_tooltip`、`default_value`、`auto_default_value` 等字段输出二进制/null 字节的问题，
确保 JSON 输出仅包含可读文本。

**依赖**: Phase 47/48/49/50（无硬性依赖，可并行插入）

**范围**: 仅修改 FString/FText 读取路径和 JSON 格式化器，不改变图解析结构。

---

## 根因分析

### 二进制泄漏链路

```
UE5 资产 → FArchive → Deserializer → read_ue_graph_pin()
                    → FText (PinFriendlyName) 解析
                    → 遇到无效 history_type（如 -121 = 0x87）
                    → read_ftext_with_history() 消费 0 字节
                    → 文件位置未前进
                    → 后续 SourceIndex/PinToolTip/DefaultValue 全部读取错位
                    → FString 长度字段读到垃圾数据
                    → 二进制/null 字节泄漏到 JSON
```

### 二级根因：asdict() 直接序列化

`flow_builder.py:format_node_dict()` 中：
```python
"pins": [asdict(pin) for pin in node.pins]
```
直接通过 `dataclasses.asdict()` 序列化所有 pin 字段，没有经过任何字符串过滤。

### 实证数据（BP_FirstPersonCharacter.uasset）

| 字段 | 位置 | Null 数量 | 数据长度 |
|------|------|----------|---------|
| pin_tooltip | K2Node_CallFunction (Aim) | 144 | 208 |
| pin_tooltip | K2Node_CallFunction (EventGraph) | **14,638** | 24,362 |
| pin_tooltip | K2Node_CallFunction (EventGraph) | 134 | 214 |
| default_value | K2Node_EnhancedInputAction | 189 | 398 |
| auto_default_value | K2Node_EnhancedInputAction | 60 | 118 |
| auto_default_value | K2Node_CallFunction | 188 | 218 |

**总计**: 9 个字段含二进制数据，15,559 个 `\x00` 转义出现在 JSON 文件中。

---

## 修复方案

### Task 1: 修复 FText None 类型解析

**文件**: `src/uasset_read/serializers/graph.py` — `read_ftext_with_history()` (L154-184)

当前代码（L177-184）：
```python
if history_type == 255 or history_type == -1:  # None
    b_has_culture = archive.read_bool()  # 4 bytes
    if b_has_culture:
        archive.read_fstring()  # CultureInvariantString
```

修复：
- 添加 **SerializationControl** 字节检测（UE5.6+ 可能的格式变化）
- 对无效 history_type（不在 -1..10 范围内），**保守跳过直到遇到合理标记**
  或返回空字符串并记录 debug 日志
- 添加最大消费字节上限（10KB），超过则视为异常并 seek 到安全位置
- 记录 debug 日志输出无效类型的上下文（文件位置 + 原始字节）

### Task 2: FString 读取后验证

**文件**: `src/uasset_read/archive.py` — `read_fstring()` (L232-246)

在 `rstrip('\x00')` 之后添加输出验证：
```python
def read_fstring(self) -> str:
    pos = self.tell()  # 捕获读取前位置
    length = self.read_i32()
    if length == 0:
        return ""
    # ... 现有 UTF-8/UTF-16 读取逻辑 ...
    result = data.decode('utf-8', errors='replace').rstrip('\x00')  # 或 UTF-16 变体
    
    # 验证：如果结果中仍包含大量 null 字符，说明读取了二进制数据
    null_ratio = result.count('\x00') / max(len(result), 1)
    if null_ratio > 0.3:
        logger.warning("FString at pos %d contains %d null chars (ratio %.2f) — likely binary",
                       pos, result.count('\x00'), null_ratio)
        return ""  # 返回空字符串，不输出二进制
    
    return result
```

**注意**: `pos` 必须在 `read_i32()` **之前**捕获，确保日志输出的是字符串起始位置。

### Task 3: JSON 格式化器防御性过滤

**文件**: `src/uasset_read/graph/flow_builder.py` — `format_node_dict()` (L89-96)

**问题**: pins 通过 `[asdict(pin) for pin in node.pins]` 直接序列化，绕过了 json_formatter。
修复方案：在 `format_node_dict()` 中添加 `_sanitize_string()` 辅助函数，
对 `asdict()` 返回的 pin dict 中所有字符串字段进行清理。

```python
def _sanitize_string(value: str) -> str:
    """清理字符串中的二进制/null 字符，确保 JSON 安全输出。"""
    if not value:
        return value
    # 移除 null 字符
    value = value.replace('\x00', '')
    # 移除其他控制字符（保留 \n \r \t）
    value = ''.join(c for c in value if c >= ' ' or c in '\n\r\t')
    return value


def _sanitize_pin_dict(pin_dict: dict) -> dict:
    """清理 pin dict 中所有字符串字段。"""
    for key, val in pin_dict.items():
        if isinstance(val, str):
            pin_dict[key] = _sanitize_string(val)
    return pin_dict
```

在 `format_node_dict()` 的 pin 序列化部分：
```python
pins = [asdict(pin) for pin in node.pins]
pins = [_sanitize_pin_dict(p) for p in pins]  # 新增
```

### Task 4: pin_tooltip 专用修复（源头验证）

**文件**: `src/uasset_read/serializers/graph.py` — `read_ue_graph_pin()` (L382-385)

在 pin_tooltip 读取中添加验证：
```python
def _contains_binary_data(value: str, threshold: float = 0.3) -> bool:
    """检查字符串是否包含大量二进制/null 字符。"""
    if not value:
        return False
    return value.count('\x00') / len(value) > threshold
```

```python
try:
    pin_tooltip = archive.read_fstring()
    if _contains_binary_data(pin_tooltip):
        logger.debug("Binary pin_tooltip at pos %d for pin %s — returning empty",
                     ftext_start_pos, pin_name)
        pin_tooltip = ""
except Exception:
    pin_tooltip = ""
```

### Task 5: 测试

**新增测试文件**: `tests/test_phase51_binary_sanitization.py`

测试用例：
1. `test_no_null_bytes_in_json_output` — 对 `BP_FirstPersonCharacter.uasset` 解析，
   验证 JSON 输出中 `\x00` 出现次数为 0
2. `test_pin_tooltip_is_readable` — 验证所有 pin 的 tooltip 字段为可读文本或空字符串
3. `test_default_value_sanitized` — 验证 default_value 和 auto_default_value 无二进制泄漏
4. `test_sanitize_string_unit` — 对 `_sanitize_string()` 的单元测试（纯文本/null/混合/全二进制）
5. `test_fstring_binary_detection` — 对 `read_fstring()` 的 null_ratio 检测逻辑测试
6. 确保现有 561 tests 不回归

---

## 预期结果

修复后 `BP_FirstPersonCharacter.uasset` 的 JSON 输出：
- `pin_tooltip`: 空字符串 `""` 或可读文本（如 "Adds yaw/pitch to controller"）
- `default_value`: 有意义的默认值（如 `"0.0"`, `"false"`, `"None"`）或空字符串
- `auto_default_value`: 同上
- **零** `\x00` 转义出现在 JSON 文件中

---

## UE 源码参考

FText 序列化: `Runtime/Core/Private/Internationalization/Text.cpp` — `FText::SerializeText()`
FText 历史: `Runtime/Core/Private/Internationalization/TextHistory.cpp` — `FTextHistory_Base::Serialize()`
EdGraphPin 序列化: `Engine/Source/Developer/GraphEditor/Private/EdGraphPin.cpp` — `UEdGraphPin::Serialize()`

关键代码路径（UE5.6+ Text.cpp L850-1044）：
```
FText::SerializeText:
  1. Ar << Flags (uint32)
  2. if (bHasHistory): Ar << HistoryType (int8)
  3. switch (HistoryType):
     - None/AsCultureInvariant: Ar << bHasCultureInvariantString; if(b) Ar << CultureString
     - Base (0): Ar << Namespace << Key << SourceString (3 FStrings)
     - NamedFormat (1): Ar << FormatText (递归) << Arguments (TArray)
     - 其他: 跳过或报错
```
