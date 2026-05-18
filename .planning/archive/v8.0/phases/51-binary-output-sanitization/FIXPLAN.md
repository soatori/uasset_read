# Phase 51: 二进制输出清理 — 修复计划

**基于**: UAT gap analysis  
**状态**: 待执行  
**修复类型**: 代码修复 + 单元测试

---

## 修复任务

### Task 1: FString 读取后 null 字符比例检测

**文件**: `src/uasset_read/archive.py` — `read_fstring()` (L232-251)

**问题**: 当前实现只有 `rstrip('\x00')`，无法检测字符串中包含大量 null 字符的情况（表示读取了二进制数据）。

**修复方案**:
```python
def read_fstring(self) -> str:
    """读取 UE FString（带长度前缀的字符串）。"""
    length = self.read_i32()
    if length == 0:
        return ""
    if length < 0:
        utf16_len = -length * 2
        if utf16_len > MAX_FSTRING_LENGTH:
            raise ParseError(f"UTF-16 string length {utf16_len} exceeds maximum {MAX_FSTRING_LENGTH}")
        data = self.read(utf16_len)
        result = data.decode('utf-16', errors='replace').rstrip('\x00')
    else:
        if length > MAX_FSTRING_LENGTH:
            raise ParseError(f"UTF-8 string length {length} exceeds maximum {MAX_FSTRING_LENGTH}")
        data = self.read(length)
        result = data.decode('utf-8', errors='replace').rstrip('\x00')
    
    # 新增：验证 null 字符比例
    null_ratio = result.count('\x00') / max(len(result), 1)
    if null_ratio > 0.3:
        self.logger.warning(
            "FString at pos %d contains %d null chars (ratio %.2f) — likely binary, returning empty",
            self.tell() - length, result.count('\x00'), null_ratio
        )
        return ""
    
    return result
```

**验证**: `test_fstring_null_ratio_detection()`

---

### Task 2: FText None 类型解析 - 无效 history_type 处理

**文件**: `src/uasset_read/serializers/graph.py` — `read_ftext_with_history()` (L154-200)

**问题**: `read_ftext_with_history()` 对无效 history_type（如 -121 = 0x87）没有处理，导致文件位置未前进，后续所有 FString 读取错位。

**修复方案**:
```python
def read_ftext_with_history(
    archive: FArchive,
    history_type: int,
    tolerant: bool = True,
) -> tuple[str, int]:
    """读取 FText，返回 (值, 消耗字节数)。"""
    consumed = 0
    start_pos = archive.tell()
    
    # 新增：验证 history_type 范围
    valid_history_types = list(range(-1, 11))  # -1, 0, 1, ..., 10
    if history_type not in valid_history_types:
        # 无效 history_type：记录 debug 日志并返回空字符串
        archive.logger.debug(
            "Invalid FText history_type %d at pos %d — returning empty",
            history_type, start_pos
        )
        return "", archive.tell() - start_pos
    
    try:
        if history_type == 255 or history_type == -1:  # None (0xFF unsigned or -1 signed)
            # ... 现有 None 处理逻辑 ...
        elif history_type == 0:  # Base
            # ... 现有 Base 处理逻辑 ...
        elif history_type == 1:  # NamedFormat
            # ... 现有 NamedFormat 处理逻辑 ...
        else:
            # 未实现的类型：跳过并记录
            archive.logger.debug("Unsupported FText history_type %d at pos %d", history_type, start_pos)
            return "", archive.tell() - start_pos
    except Exception as e:
        if tolerant:
            archive.logger.debug("FText read failed at pos %d: %s", start_pos, str(e))
            return "", archive.tell() - start_pos
        raise
    
    return "", archive.tell() - start_pos  # FText 不返回实际值，只消耗字节
```

**注意**: 根据 Phase 51 的根因分析，FText 解析失败会导致文件位置未前进，这是二进制泄漏的**根源**。修复必须确保：
1. 无效 history_type 立即返回
2. 记录 debug 日志
3. 返回正确的消耗字节数

**验证**: `test_ftext_invalid_history_type()`

---

### Task 3: JSON 格式化器字符串清理

**文件**: `src/uasset_read/graph/flow_builder.py` — `format_node_dict()` (L89-130)

**问题**: `asdict(pin)` 直接序列化 pin，绕过了任何字符串清理，导致二进制数据进入 JSON 输出。

**修复方案**:
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
    sanitized = {}
    for key, val in pin_dict.items():
        if isinstance(val, str):
            sanitized[key] = _sanitize_string(val)
        elif isinstance(val, (list, dict)):
            sanitized[key] = _sanitize_recursive(val)
        else:
            sanitized[key] = val
    return sanitized


def _sanitize_recursive(obj):
    """递归清理列表/字典中的字符串。"""
    if isinstance(obj, str):
        return _sanitize_string(obj)
    elif isinstance(obj, list):
        return [_sanitize_recursive(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: _sanitize_recursive(v) for k, v in obj.items()}
    return obj


def format_node_dict(node, idx: int = 0) -> dict:
    # ... 现有代码 ...
    
    result = {
        "node_name": node_name,
        "node_type": node.class_name,
        "node_guid": node.node_guid,
        "position": {"x": node.node_pos_x, "y": node.node_pos_y},
        "node_comment": node.node_comment,
        "pins": [_sanitize_pin_dict(asdict(pin)) for pin in node.pins]  # 添加清理
    }
    
    # ... 现有代码 ...
    
    return result
```

**验证**: `test_sanitize_string_unittest()`

---

### Task 4: pin_tooltip 专用二进制检测

**文件**: `src/uasset_read/serializers/graph.py` — `read_ue_graph_pin()` (L381-420)

**问题**: `pin_tooltip` 读取后未检测二进制数据，直接存储到 Pin 对象中。

**修复方案**:
```python
def _contains_binary_data(value: str, threshold: float = 0.3) -> bool:
    """检查字符串是否包含大量二进制/null 字符。"""
    if not value:
        return False
    return value.count('\x00') / len(value) > threshold


def read_ue_graph_pin(archive: FArchive, name_map: list, summary: dict, export_map: list, import_map: list, linker) -> dict:
    # ... 现有代码 ...
    
    # 6. PinFriendlyName (FText)
    # ... FText 读取逻辑 ...
    
    # 7. PinTooltip (FString)
    try:
        pin_tooltip = archive.read_fstring()
        if _contains_binary_data(pin_tooltip):
            archive.logger.debug(
                "Binary pinTooltip at pos %d for pin '%s' — returning empty",
                archive.tell() - len(pin_tooltip), pin_name
            )
            pin_tooltip = ""
    except Exception:
        pin_tooltip = ""
    
    # ... 现有代码 ...
```

**注意**: 这是 Task 1 的补充 — Task 1 覆盖所有 FString，Task 4 针对 pin_tooltip 添加额外日志和安全检查。

**验证**: `test_pin_tooltip_binary_filtering()`

---

## 测试文件

### 新增文件: `tests/test_phase51_binary_sanitization.py`

```python
"""Phase 51: 二进制输出清理验证测试。"""

import pytest
from src.uasset_read.archive import FArchive
from src.uasset_read.serializers.graph import (
    read_ftext_with_history,
    read_ue_graph_pin,
    _contains_binary_data,
)
from src.uasset_read.graph.flow_builder import _sanitize_string, _sanitize_pin_dict


class TestSanitizeString:
    """测试 _sanitize_string() 函数."""
    
    def test_clean_string_unchanged(self):
        """干净字符串保持不变."""
        assert _sanitize_string("hello world") == "hello world"
    
    def test_null_bytes_removed(self):
        """null 字符被移除."""
        assert _sanitize_string("hello\x00world") == "helloworld"
    
    def test_control_chars_removed(self):
        """控制字符被移除（保留 \n \r \t）."""
        assert _sanitize_string("hello\x01world") == "helloworld"
        assert _sanitize_string("line1\x0anode1") == "line1\nnode1"
    
    def test_all_binary_returns_empty(self):
        """全二进制字符串返回空."""
        assert _sanitize_string("\x00\x01\x02") == ""
    
    def test_empty_string(self):
        """空字符串处理."""
        assert _sanitize_string("") == ""
        assert _sanitize_string(None) is None


class TestContainsBinaryData:
    """测试 _contains_binary_data() 函数."""
    
    def test_clean_string_false(self):
        """干净字符串返回 False."""
        assert _contains_binary_data("hello world") is False
    
    def test_null_ratio_high_true(self):
        """null 比例 > 30% 返回 True."""
        assert _contains_binary_data("\x00\x00\x00abc") is True  # 75% null
    
    def test_null_ratio_low_false(self):
        """null 比例 <= 30% 返回 False."""
        assert _contains_binary_data("\x00abc") is False  # 25% null


class TestFStringNullRatioDetection:
    """测试 read_fstring() 的 null_ratio 检测."""
    
    def test_read_fstring_with_nulls(self, tmp_path):
        """读取包含大量 null 字符的 FString."""
        # 创建测试文件
        test_file = tmp_path / "test.uasset"
        # 写入: length(4) + "abc\x00\x00\x00" (75% null)
        data = b'\x07\x00\x00\x00abc\x00\x00\x00'
        test_file.write_bytes(data)
        
        archive = FArchive(test_file.read_bytes())
        result = archive.read_fstring()
        
        assert result == ""  # 返回空字符串


class TestFTextInvalidHistoryType:
    """测试 read_ftext_with_history() 的无效 history_type 处理."""
    
    def test_invalid_history_type_135(self):
        """history_type = 135 (0x87 = -121) 应返回空字符串."""
        data = b'\x00' * 10
        archive = FArchive(data)
        archive.seek(0)
        
        result, consumed = read_ftext_with_history(archive, 135, tolerant=True)
        
        assert result == ""
        assert consumed > 0  # 消耗字节数应 > 0，确保文件位置前进


class TestPinTooltipBinaryFiltering:
    """测试 pin_tooltip 的二进制数据过滤."""
    
    def test_binary_tooltip_sanitized(self):
        """二进制 tooltip 被清理."""
        # 测试数据包含大量 null 字符
        tooltip = "\x00" * 100 + "abc"
        assert _contains_binary_data(tooltip) is True
        assert _sanitize_string(tooltip) == "abc"
```

---

## 验证步骤

### 1. 运行新测试
```bash
pytest tests/test_phase51_binary_sanitization.py -v
```

**预期**: 6 tests pass

### 2. 运行现有测试 (回归测试)
```bash
pytest tests/ -v --tb=short
```

**预期**: 561 tests pass，无新失败

### 3. 手动验证 (如果有测试资产)
```bash
python -m uasset_read tests/assets/BP_FirstPersonCharacter.uasset > output.json
grep -c '\x00' output.json  # 应输出 0
```

---

## 预期结果

修复后 `BP_FirstPersonCharacter.uasset` 的 JSON 输出：
- `pin_tooltip`: 空字符串 `""` 或可读文本
- `default_value`: 有意义的默认值或空字符串
- `auto_default_value`: 同上
- **零** `\x00` 转义出现在 JSON 文件中

---

## 回滚计划

如果修复引入问题：
1. Git revert 修复提交
2. 检查 `git log --oneline | grep "phase51"` 找到相关提交
3. `git revert <commit-hash> --no-edit`

---

## 相关文件

| 文件 | 修改类型 | 风险等级 |
|------|----------|----------|
| `src/uasset_read/archive.py` | 添加验证逻辑 | 低 |
| `src/uasset_read/serializers/graph.py` | 添加 FText 无效类型处理 | 中 |
| `src/uasset_read/graph/flow_builder.py` | 添加字符串清理 | 低 |
| `tests/test_phase51_binary_sanitization.py` | 新建测试文件 | 无 |

**注意**: 所有修改都是防御性/容错性增强，不会改变正常数据的解析结果。
