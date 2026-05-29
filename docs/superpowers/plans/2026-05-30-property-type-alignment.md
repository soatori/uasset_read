# CUE4Parse 属性类型对齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补充缺失的 17 种属性类型，使 Python 实现与 CUE4Parse 完全对齐

**Architecture:** 在 `parsers/property_types.py` 中添加新的解析函数，在 `parsers/property_parser.py` 中注册分派表，每个类型独立测试

**Tech Stack:** Python 3.10+, pytest, 现有项目测试框架

---

## 一、缺失属性类型清单

根据 CUE4Parse 分析，Python 实现缺失以下 17 种属性类型：

### 1.1 无符号整数类型 (3 种)

| 类型 | CUE4Parse 类 | Python 实现 |
|------|--------------|-------------|
| `UInt16Property` | `UInt16Property` | 需要添加 |
| `UInt32Property` | `UInt32Property` | 需要添加 |
| `UInt64Property` | `UInt64Property` | 需要添加 |

### 1.2 字符串类型 (1 种)

| 类型 | CUE4Parse 类 | Python 实现 |
|------|--------------|-------------|
| `Utf8StrProperty` | `Utf8StrProperty` | 需要添加 |

### 1.3 对象引用类型 (5 种)

| 类型 | CUE4Parse 类 | Python 实现 |
|------|--------------|-------------|
| `WeakObjectProperty` | `WeakObjectProperty` | 需要添加 |
| `LazyObjectProperty` | `LazyObjectProperty` | 需要添加 |
| `ClassProperty` | `ClassProperty` | 需要添加 |
| `SoftClassProperty` | `SoftObjectProperty` | 需要添加 |
| `AssetObjectProperty` | `AssetObjectProperty` | 需要添加 |

### 1.4 委托类型 (3 种)

| 类型 | CUE4Parse 类 | Python 实现 |
|------|--------------|-------------|
| `MulticastDelegateProperty` | `MulticastDelegateProperty` | 需要添加 |
| `MulticastInlineDelegateProperty` | `MulticastInlineDelegateProperty` | 需要添加 |
| `MulticastSparseDelegateProperty` | `MulticastSparseDelegateProperty` | 需要添加 |

### 1.5 特殊类型 (3 种)

| 类型 | CUE4Parse 类 | Python 实现 |
|------|--------------|-------------|
| `InterfaceProperty` | `InterfaceProperty` | 需要添加 |
| `FieldPathProperty` | `FieldPathProperty` | 需要添加 |
| `OptionalProperty` | `OptionalProperty` | 需要添加 |

### 1.6 Verse 语言类型 (4 种)

| 类型 | CUE4Parse 类 | Python 实现 |
|------|--------------|-------------|
| `VerseStringProperty` | `VerseStringProperty` | 需要添加 |
| `VerseClassProperty` | `VerseClassProperty` | 需要添加 |
| `VerseFunctionProperty` | `ObjectProperty` | 需要添加 |
| `VerseDynamicProperty` | `ObjectProperty` | 需要添加 |

---

## 二、实现计划

### Phase 1: 无符号整数类型 (Task 1-3)

---

#### Task 1: 添加 UInt16Property

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py`
- Modify: `src/uasset_read/parsers/property_parser.py`
- Create: `tests/test_uint_properties.py`

- [ ] **Step 1: 创建测试**

```python
# tests/test_uint_properties.py
"""测试无符号整数属性类型"""
import pytest
from unittest.mock import MagicMock


def test_parse_uint16_property():
    """测试 UInt16Property 解析"""
    from uasset_read.parsers.property_types import parse_uint16_property

    archive = MagicMock()
    archive.read_u16.return_value = 65535

    tag = MagicMock()
    tag.type = "UInt16Property"

    result = parse_uint16_property(archive, tag)
    assert result == 65535
    archive.read_u16.assert_called_once()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_uint_properties.py::test_parse_uint16_property -v
```

Expected: FAIL with "parse_uint16_property not defined"

- [ ] **Step 3: 实现解析函数**

```python
# 在 src/uasset_read/parsers/property_types.py 中添加

def parse_uint16_property(archive, tag) -> int:
    """解析 UInt16Property"""
    return archive.read_u16()


def parse_uint32_property(archive, tag) -> int:
    """解析 UInt32Property"""
    return archive.read_u32()


def parse_uint64_property(archive, tag) -> int:
    """解析 UInt64Property"""
    return archive.read_u64()
```

- [ ] **Step 4: 注册到分派表**

```python
# 在 src/uasset_read/parsers/property_parser.py 的 _get_parse_functions() 中添加

"UInt16Property": parse_uint16_property,
"UInt32Property": parse_uint32_property,
"UInt64Property": parse_uint64_property,
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_uint_properties.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(property): 添加 UInt16Property, UInt32Property, UInt64Property 支持"
```

---

#### Task 2: 添加 UInt32Property

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py`
- Modify: `tests/test_uint_properties.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_uint_properties.py 中添加

def test_parse_uint32_property():
    """测试 UInt32Property 解析"""
    from uasset_read.parsers.property_types import parse_uint32_property

    archive = MagicMock()
    archive.read_u32.return_value = 4294967295

    tag = MagicMock()
    tag.type = "UInt32Property"

    result = parse_uint32_property(archive, tag)
    assert result == 4294967295
    archive.read_u32.assert_called_once()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_uint_properties.py::test_parse_uint32_property -v
```

Expected: FAIL

- [ ] **Step 3: 实现已在 Task 1 中完成**

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_uint_properties.py::test_parse_uint32_property -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test(property): 添加 UInt32Property 测试用例"
```

---

#### Task 3: 添加 UInt64Property

**Files:**
- Modify: `tests/test_uint_properties.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_uint_properties.py 中添加

def test_parse_uint64_property():
    """测试 UInt64Property 解析"""
    from uasset_read.parsers.property_types import parse_uint64_property

    archive = MagicMock()
    archive.read_u64.return_value = 18446744073709551615

    tag = MagicMock()
    tag.type = "UInt64Property"

    result = parse_uint64_property(archive, tag)
    assert result == 18446744073709551615
    archive.read_u64.assert_called_once()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_uint_properties.py::test_parse_uint64_property -v
```

Expected: FAIL

- [ ] **Step 3: 实现已在 Task 1 中完成**

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_uint_properties.py::test_parse_uint64_property -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test(property): 添加 UInt64Property 测试用例"
```

---

### Phase 2: 字符串类型 (Task 4)

---

#### Task 4: 添加 Utf8StrProperty

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py`
- Modify: `src/uasset_read/parsers/property_parser.py`
- Create: `tests/test_utf8_property.py`

- [ ] **Step 1: 创建测试**

```python
# tests/test_utf8_property.py
"""测试 Utf8StrProperty 属性类型"""
import pytest
from unittest.mock import MagicMock


def test_parse_utf8_str_property():
    """测试 Utf8StrProperty 解析"""
    from uasset_read.parsers.property_types import parse_utf8_str_property

    archive = MagicMock()
    archive.read_utf8_string.return_value = "Hello UTF-8"

    tag = MagicMock()
    tag.type = "Utf8StrProperty"

    result = parse_utf8_str_property(archive, tag)
    assert result == "Hello UTF-8"
    archive.read_utf8_string.assert_called_once()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_utf8_property.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现解析函数**

```python
# 在 src/uasset_read/parsers/property_types.py 中添加

def parse_utf8_str_property(archive, tag) -> str:
    """解析 Utf8StrProperty"""
    return archive.read_utf8_string()
```

- [ ] **Step 4: 注册到分派表**

```python
# 在 src/uasset_read/parsers/property_parser.py 的 _get_parse_functions() 中添加

"Utf8StrProperty": parse_utf8_str_property,
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_utf8_property.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(property): 添加 Utf8StrProperty 支持"
```

---

### Phase 3: 对象引用类型 (Task 5-9)

---

#### Task 5: 添加 WeakObjectProperty

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py`
- Modify: `src/uasset_read/parsers/property_parser.py`
- Create: `tests/test_object_properties.py`

- [ ] **Step 1: 创建测试**

```python
# tests/test_object_properties.py
"""测试对象引用属性类型"""
import pytest
from unittest.mock import MagicMock


def test_parse_weak_object_property():
    """测试 WeakObjectProperty 解析"""
    from uasset_read.parsers.property_types import parse_weak_object_property

    archive = MagicMock()
    archive.read_int32.return_value = 5

    tag = MagicMock()
    tag.type = "WeakObjectProperty"

    result = parse_weak_object_property(archive, tag)
    assert result == 5
    archive.read_int32.assert_called_once()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_object_properties.py::test_parse_weak_object_property -v
```

Expected: FAIL

- [ ] **Step 3: 实现解析函数**

```python
# 在 src/uasset_read/parsers/property_types.py 中添加

def parse_weak_object_property(archive, tag) -> int:
    """解析 WeakObjectProperty"""
    return archive.read_int32()
```

- [ ] **Step 4: 注册到分派表**

```python
# 在 src/uasset_read/parsers/property_parser.py 的 _get_parse_functions() 中添加

"WeakObjectProperty": parse_weak_object_property,
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_object_properties.py::test_parse_weak_object_property -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(property): 添加 WeakObjectProperty 支持"
```

---

#### Task 6: 添加 LazyObjectProperty

**Files:**
- Modify: `tests/test_object_properties.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_object_properties.py 中添加

def test_parse_lazy_object_property():
    """测试 LazyObjectProperty 解析"""
    from uasset_read.parsers.property_types import parse_lazy_object_property

    archive = MagicMock()
    archive.read_int32.return_value = 10

    tag = MagicMock()
    tag.type = "LazyObjectProperty"

    result = parse_lazy_object_property(archive, tag)
    assert result == 10
    archive.read_int32.assert_called_once()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_object_properties.py::test_parse_lazy_object_property -v
```

Expected: FAIL

- [ ] **Step 3: 实现解析函数**

```python
# 在 src/uasset_read/parsers/property_types.py 中添加

def parse_lazy_object_property(archive, tag) -> int:
    """解析 LazyObjectProperty"""
    return archive.read_int32()
```

- [ ] **Step 4: 注册到分派表**

```python
# 在 src/uasset_read/parsers/property_parser.py 的 _get_parse_functions() 中添加

"LazyObjectProperty": parse_lazy_object_property,
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_object_properties.py::test_parse_lazy_object_property -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(property): 添加 LazyObjectProperty 支持"
```

---

#### Task 7: 添加 ClassProperty

**Files:**
- Modify: `tests/test_object_properties.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_object_properties.py 中添加

def test_parse_class_property():
    """测试 ClassProperty 解析"""
    from uasset_read.parsers.property_types import parse_class_property

    archive = MagicMock()
    archive.read_int32.return_value = 15

    tag = MagicMock()
    tag.type = "ClassProperty"

    result = parse_class_property(archive, tag)
    assert result == 15
    archive.read_int32.assert_called_once()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_object_properties.py::test_parse_class_property -v
```

Expected: FAIL

- [ ] **Step 3: 实现解析函数**

```python
# 在 src/uasset_read/parsers/property_types.py 中添加

def parse_class_property(archive, tag) -> int:
    """解析 ClassProperty"""
    return archive.read_int32()
```

- [ ] **Step 4: 注册到分派表**

```python
# 在 src/uasset_read/parsers/property_parser.py 的 _get_parse_functions() 中添加

"ClassProperty": parse_class_property,
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_object_properties.py::test_parse_class_property -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(property): 添加 ClassProperty 支持"
```

---

#### Task 8: 添加 SoftClassProperty

**Files:**
- Modify: `tests/test_object_properties.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_object_properties.py 中添加

def test_parse_soft_class_property():
    """测试 SoftClassProperty 解析"""
    from uasset_read.parsers.property_types import parse_soft_class_property

    archive = MagicMock()
    tag = MagicMock()
    tag.type = "SoftClassProperty"

    # SoftClassProperty 解析与 SoftObjectProperty 相同
    result = parse_soft_class_property(archive, tag)
    assert result is not None
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_object_properties.py::test_parse_soft_class_property -v
```

Expected: FAIL

- [ ] **Step 3: 实现解析函数**

```python
# 在 src/uasset_read/parsers/property_types.py 中添加

def parse_soft_class_property(archive, tag) -> dict:
    """解析 SoftClassProperty"""
    # SoftClassProperty 与 SoftObjectProperty 解析方式相同
    return parse_soft_object_property(archive, tag)
```

- [ ] **Step 4: 注册到分派表**

```python
# 在 src/uasset_read/parsers/property_parser.py 的 _get_parse_functions() 中添加

"SoftClassProperty": parse_soft_class_property,
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_object_properties.py::test_parse_soft_class_property -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(property): 添加 SoftClassProperty 支持"
```

---

#### Task 9: 添加 AssetObjectProperty

**Files:**
- Modify: `tests/test_object_properties.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_object_properties.py 中添加

def test_parse_asset_object_property():
    """测试 AssetObjectProperty 解析"""
    from uasset_read.parsers.property_types import parse_asset_object_property

    archive = MagicMock()
    archive.read_string.return_value = "/Game/Assets/MyAsset"

    tag = MagicMock()
    tag.type = "AssetObjectProperty"

    result = parse_asset_object_property(archive, tag)
    assert result == "/Game/Assets/MyAsset"
    archive.read_string.assert_called_once()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_object_properties.py::test_parse_asset_object_property -v
```

Expected: FAIL

- [ ] **Step 3: 实现解析函数**

```python
# 在 src/uasset_read/parsers/property_types.py 中添加

def parse_asset_object_property(archive, tag) -> str:
    """解析 AssetObjectProperty"""
    return archive.read_string()
```

- [ ] **Step 4: 注册到分派表**

```python
# 在 src/uasset_read/parsers/property_parser.py 的 _get_parse_functions() 中添加

"AssetObjectProperty": parse_asset_object_property,
"AssetClassProperty": parse_asset_object_property,  # 别名
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_object_properties.py::test_parse_asset_object_property -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(property): 添加 AssetObjectProperty 和 AssetClassProperty 支持"
```

---

### Phase 4: 委托类型 (Task 10-12)

---

#### Task 10: 添加 MulticastDelegateProperty

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py`
- Modify: `src/uasset_read/parsers/property_parser.py`
- Create: `tests/test_delegate_properties.py`

- [ ] **Step 1: 创建测试**

```python
# tests/test_delegate_properties.py
"""测试委托属性类型"""
import pytest
from unittest.mock import MagicMock


def test_parse_multicast_delegate_property():
    """测试 MulticastDelegateProperty 解析"""
    from uasset_read.parsers.property_types import parse_multicast_delegate_property

    archive = MagicMock()
    archive.read_int32.return_value = 2  # 委托数量

    tag = MagicMock()
    tag.type = "MulticastDelegateProperty"

    result = parse_multicast_delegate_property(archive, tag)
    assert result is not None
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_delegate_properties.py::test_parse_multicast_delegate_property -v
```

Expected: FAIL

- [ ] **Step 3: 实现解析函数**

```python
# 在 src/uasset_read/parsers/property_types.py 中添加

def parse_multicast_delegate_property(archive, tag) -> list:
    """解析 MulticastDelegateProperty"""
    count = archive.read_int32()
    delegates = []
    for _ in range(count):
        # 每个委托包含对象索引和函数名
        obj_index = archive.read_int32()
        func_name = archive.read_string()
        delegates.append({"object": obj_index, "function": func_name})
    return delegates
```

- [ ] **Step 4: 注册到分派表**

```python
# 在 src/uasset_read/parsers/property_parser.py 的 _get_parse_functions() 中添加

"MulticastDelegateProperty": parse_multicast_delegate_property,
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_delegate_properties.py::test_parse_multicast_delegate_property -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(property): 添加 MulticastDelegateProperty 支持"
```

---

#### Task 11: 添加 MulticastInlineDelegateProperty

**Files:**
- Modify: `tests/test_delegate_properties.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_delegate_properties.py 中添加

def test_parse_multicast_inline_delegate_property():
    """测试 MulticastInlineDelegateProperty 解析"""
    from uasset_read.parsers.property_types import parse_multicast_inline_delegate_property

    archive = MagicMock()
    tag = MagicMock()
    tag.type = "MulticastInlineDelegateProperty"

    # MulticastInlineDelegateProperty 解析与 MulticastDelegateProperty 相同
    result = parse_multicast_inline_delegate_property(archive, tag)
    assert result is not None
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_delegate_properties.py::test_parse_multicast_inline_delegate_property -v
```

Expected: FAIL

- [ ] **Step 3: 实现解析函数**

```python
# 在 src/uasset_read/parsers/property_types.py 中添加

def parse_multicast_inline_delegate_property(archive, tag) -> list:
    """解析 MulticastInlineDelegateProperty"""
    # 与 MulticastDelegateProperty 解析方式相同
    return parse_multicast_delegate_property(archive, tag)
```

- [ ] **Step 4: 注册到分派表**

```python
# 在 src/uasset_read/parsers/property_parser.py 的 _get_parse_functions() 中添加

"MulticastInlineDelegateProperty": parse_multicast_inline_delegate_property,
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_delegate_properties.py::test_parse_multicast_inline_delegate_property -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(property): 添加 MulticastInlineDelegateProperty 支持"
```

---

#### Task 12: 添加 MulticastSparseDelegateProperty

**Files:**
- Modify: `tests/test_delegate_properties.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_delegate_properties.py 中添加

def test_parse_multicast_sparse_delegate_property():
    """测试 MulticastSparseDelegateProperty 解析"""
    from uasset_read.parsers.property_types import parse_multicast_sparse_delegate_property

    archive = MagicMock()
    tag = MagicMock()
    tag.type = "MulticastSparseDelegateProperty"

    # MulticastSparseDelegateProperty 解析与 MulticastDelegateProperty 相同
    result = parse_multicast_sparse_delegate_property(archive, tag)
    assert result is not None
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_delegate_properties.py::test_parse_multicast_sparse_delegate_property -v
```

Expected: FAIL

- [ ] **Step 3: 实现解析函数**

```python
# 在 src/uasset_read/parsers/property_types.py 中添加

def parse_multicast_sparse_delegate_property(archive, tag) -> list:
    """解析 MulticastSparseDelegateProperty"""
    # 与 MulticastDelegateProperty 解析方式相同
    return parse_multicast_delegate_property(archive, tag)
```

- [ ] **Step 4: 注册到分派表**

```python
# 在 src/uasset_read/parsers/property_parser.py 的 _get_parse_functions() 中添加

"MulticastSparseDelegateProperty": parse_multicast_sparse_delegate_property,
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_delegate_properties.py::test_parse_multicast_sparse_delegate_property -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(property): 添加 MulticastSparseDelegateProperty 支持"
```

---

### Phase 5: 特殊类型 (Task 13-15)

---

#### Task 13: 添加 InterfaceProperty

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py`
- Modify: `src/uasset_read/parsers/property_parser.py`
- Create: `tests/test_special_properties.py`

- [ ] **Step 1: 创建测试**

```python
# tests/test_special_properties.py
"""测试特殊属性类型"""
import pytest
from unittest.mock import MagicMock


def test_parse_interface_property():
    """测试 InterfaceProperty 解析"""
    from uasset_read.parsers.property_types import parse_interface_property

    archive = MagicMock()
    archive.read_int32.return_value = 20

    tag = MagicMock()
    tag.type = "InterfaceProperty"

    result = parse_interface_property(archive, tag)
    assert result == 20
    archive.read_int32.assert_called_once()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_special_properties.py::test_parse_interface_property -v
```

Expected: FAIL

- [ ] **Step 3: 实现解析函数**

```python
# 在 src/uasset_read/parsers/property_types.py 中添加

def parse_interface_property(archive, tag) -> int:
    """解析 InterfaceProperty"""
    return archive.read_int32()
```

- [ ] **Step 4: 注册到分派表**

```python
# 在 src/uasset_read/parsers/property_parser.py 的 _get_parse_functions() 中添加

"InterfaceProperty": parse_interface_property,
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_special_properties.py::test_parse_interface_property -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(property): 添加 InterfaceProperty 支持"
```

---

#### Task 14: 添加 FieldPathProperty

**Files:**
- Modify: `tests/test_special_properties.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_special_properties.py 中添加

def test_parse_field_path_property():
    """测试 FieldPathProperty 解析"""
    from uasset_read.parsers.property_types import parse_field_path_property

    archive = MagicMock()
    tag = MagicMock()
    tag.type = "FieldPathProperty"

    result = parse_field_path_property(archive, tag)
    assert result is not None
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_special_properties.py::test_parse_field_path_property -v
```

Expected: FAIL

- [ ] **Step 3: 实现解析函数**

```python
# 在 src/uasset_read/parsers/property_types.py 中添加

def parse_field_path_property(archive, tag) -> dict:
    """解析 FieldPathProperty"""
    # FieldPath 包含路径字符串列表
    count = archive.read_int32()
    path = []
    for _ in range(count):
        path.append(archive.read_string())
    return {"path": path}
```

- [ ] **Step 4: 注册到分派表**

```python
# 在 src/uasset_read/parsers/property_parser.py 的 _get_parse_functions() 中添加

"FieldPathProperty": parse_field_path_property,
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_special_properties.py::test_parse_field_path_property -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(property): 添加 FieldPathProperty 支持"
```

---

#### Task 15: 添加 OptionalProperty

**Files:**
- Modify: `tests/test_special_properties.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_special_properties.py 中添加

def test_parse_optional_property():
    """测试 OptionalProperty 解析"""
    from uasset_read.parsers.property_types import parse_optional_property

    archive = MagicMock()
    tag = MagicMock()
    tag.type = "OptionalProperty"

    result = parse_optional_property(archive, tag)
    assert result is not None
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_special_properties.py::test_parse_optional_property -v
```

Expected: FAIL

- [ ] **Step 3: 实现解析函数**

```python
# 在 src/uasset_read/parsers/property_types.py 中添加

def parse_optional_property(archive, tag) -> dict:
    """解析 OptionalProperty"""
    # OptionalProperty 包含一个内层属性
    # 需要递归解析内层属性
    has_value = archive.read_bool()
    if has_value:
        # 解析内层属性
        inner_value = parse_property_value(archive, tag)
        return {"has_value": True, "value": inner_value}
    return {"has_value": False, "value": None}
```

- [ ] **Step 4: 注册到分派表**

```python
# 在 src/uasset_read/parsers/property_parser.py 的 _get_parse_functions() 中添加

"OptionalProperty": parse_optional_property,
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_special_properties.py::test_parse_optional_property -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(property): 添加 OptionalProperty 支持"
```

---

### Phase 6: Verse 语言类型 (Task 16-19)

---

#### Task 16: 添加 VerseStringProperty

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py`
- Modify: `src/uasset_read/parsers/property_parser.py`
- Create: `tests/test_verse_properties.py`

- [ ] **Step 1: 创建测试**

```python
# tests/test_verse_properties.py
"""测试 Verse 语言属性类型"""
import pytest
from unittest.mock import MagicMock


def test_parse_verse_string_property():
    """测试 VerseStringProperty 解析"""
    from uasset_read.parsers.property_types import parse_verse_string_property

    archive = MagicMock()
    archive.read_string.return_value = "Verse String"

    tag = MagicMock()
    tag.type = "VerseStringProperty"

    result = parse_verse_string_property(archive, tag)
    assert result == "Verse String"
    archive.read_string.assert_called_once()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_verse_properties.py::test_parse_verse_string_property -v
```

Expected: FAIL

- [ ] **Step 3: 实现解析函数**

```python
# 在 src/uasset_read/parsers/property_types.py 中添加

def parse_verse_string_property(archive, tag) -> str:
    """解析 VerseStringProperty"""
    return archive.read_string()
```

- [ ] **Step 4: 注册到分派表**

```python
# 在 src/uasset_read/parsers/property_parser.py 的 _get_parse_functions() 中添加

"VerseStringProperty": parse_verse_string_property,
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_verse_properties.py::test_parse_verse_string_property -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(property): 添加 VerseStringProperty 支持"
```

---

#### Task 17: 添加 VerseClassProperty

**Files:**
- Modify: `tests/test_verse_properties.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_verse_properties.py 中添加

def test_parse_verse_class_property():
    """测试 VerseClassProperty 解析"""
    from uasset_read.parsers.property_types import parse_verse_class_property

    archive = MagicMock()
    archive.read_int32.return_value = 25

    tag = MagicMock()
    tag.type = "VerseClassProperty"

    result = parse_verse_class_property(archive, tag)
    assert result == 25
    archive.read_int32.assert_called_once()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_verse_properties.py::test_parse_verse_class_property -v
```

Expected: FAIL

- [ ] **Step 3: 实现解析函数**

```python
# 在 src/uasset_read/parsers/property_types.py 中添加

def parse_verse_class_property(archive, tag) -> int:
    """解析 VerseClassProperty"""
    return archive.read_int32()
```

- [ ] **Step 4: 注册到分派表**

```python
# 在 src/uasset_read/parsers/property_parser.py 的 _get_parse_functions() 中添加

"VerseClassProperty": parse_verse_class_property,
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_verse_properties.py::test_parse_verse_class_property -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(property): 添加 VerseClassProperty 支持"
```

---

#### Task 18: 添加 VerseFunctionProperty

**Files:**
- Modify: `tests/test_verse_properties.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_verse_properties.py 中添加

def test_parse_verse_function_property():
    """测试 VerseFunctionProperty 解析"""
    from uasset_read.parsers.property_types import parse_verse_function_property

    archive = MagicMock()
    archive.read_int32.return_value = 30

    tag = MagicMock()
    tag.type = "VerseFunctionProperty"

    result = parse_verse_function_property(archive, tag)
    assert result == 30
    archive.read_int32.assert_called_once()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_verse_properties.py::test_parse_verse_function_property -v
```

Expected: FAIL

- [ ] **Step 3: 实现解析函数**

```python
# 在 src/uasset_read/parsers/property_types.py 中添加

def parse_verse_function_property(archive, tag) -> int:
    """解析 VerseFunctionProperty"""
    # 与 ObjectProperty 解析方式相同
    return archive.read_int32()
```

- [ ] **Step 4: 注册到分派表**

```python
# 在 src/uasset_read/parsers/property_parser.py 的 _get_parse_functions() 中添加

"VerseFunctionProperty": parse_verse_function_property,
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_verse_properties.py::test_parse_verse_function_property -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(property): 添加 VerseFunctionProperty 支持"
```

---

#### Task 19: 添加 VerseDynamicProperty

**Files:**
- Modify: `tests/test_verse_properties.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_verse_properties.py 中添加

def test_parse_verse_dynamic_property():
    """测试 VerseDynamicProperty 解析"""
    from uasset_read.parsers.property_types import parse_verse_dynamic_property

    archive = MagicMock()
    archive.read_int32.return_value = 35

    tag = MagicMock()
    tag.type = "VerseDynamicProperty"

    result = parse_verse_dynamic_property(archive, tag)
    assert result == 35
    archive.read_int32.assert_called_once()
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_verse_properties.py::test_parse_verse_dynamic_property -v
```

Expected: FAIL

- [ ] **Step 3: 实现解析函数**

```python
# 在 src/uasset_read/parsers/property_types.py 中添加

def parse_verse_dynamic_property(archive, tag) -> int:
    """解析 VerseDynamicProperty"""
    # 与 ObjectProperty 解析方式相同
    return archive.read_int32()
```

- [ ] **Step 4: 注册到分派表**

```python
# 在 src/uasset_read/parsers/property_parser.py 的 _get_parse_functions() 中添加

"VerseDynamicProperty": parse_verse_dynamic_property,
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_verse_properties.py::test_parse_verse_dynamic_property -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(property): 添加 VerseDynamicProperty 支持"
```

---

## 三、验收标准

### 3.1 功能完整性

- [ ] 所有 17 种属性类型都已实现
- [ ] 所有类型都已注册到分派表
- [ ] 每个类型都有独立的测试用例

### 3.2 测试覆盖

- [ ] 所有测试通过
- [ ] 每个类型至少 1 个测试用例
- [ ] 边界条件测试（如有）

### 3.3 代码质量

- [ ] 代码风格一致
- [ ] 无未使用导入
- [ ] 所有函数都有 docstring

---

## 四、预期收益

| 指标 | 改进 |
|------|------|
| 新增属性类型 | 17 种 |
| 新增测试用例 | 19 个 |
| 代码行数增加 | ~200 行 |
| CUE4Parse 对齐度 | 从 18/35 提升到 35/35 |

---

## 五、文件变更清单

| 文件 | 操作 | Task |
|------|------|------|
| `parsers/property_types.py` | 修改 | 1-19 |
| `parsers/property_parser.py` | 修改 | 1-19 |
| `tests/test_uint_properties.py` | 新建 | 1-3 |
| `tests/test_utf8_property.py` | 新建 | 4 |
| `tests/test_object_properties.py` | 新建 | 5-9 |
| `tests/test_delegate_properties.py` | 新建 | 10-12 |
| `tests/test_special_properties.py` | 新建 | 13-15 |
| `tests/test_verse_properties.py` | 新建 | 16-19 |

**总计:** 2 个修改文件，6 个新建文件
