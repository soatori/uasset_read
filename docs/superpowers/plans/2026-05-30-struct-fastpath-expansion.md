# Struct Fast-Path 扩展 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 扩展 Struct fast-path 覆盖范围，从 20 种扩展到 120+ 种，与 CUE4Parse 完全对齐

**Architecture:** 在 `parsers/property_types.py` 中扩展 `_EXPECTED_STRUCT_SIZES` 字典，为每种 Struct 类型添加大小定义，保持现有的 fast-path 解析逻辑

**Tech Stack:** Python 3.10+, pytest, 现有项目测试框架

---

## 一、当前状态

### 1.1 已支持的 Struct 类型 (20 种)

当前 `_EXPECTED_STRUCT_SIZES` 字典包含以下类型：

```python
_EXPECTED_STRUCT_SIZES = {
    "Vector": 24,           # 3 * float64
    "Vector2D": 16,         # 2 * float64
    "Vector4": 32,          # 4 * float64
    "Rotator": 24,          # 3 * float64
    "Quat": 32,             # 4 * float64
    "Transform": 48,        # Quat(32) + Vector(12) + Vector(4)
    "LinearColor": 16,      # 4 * float32
    "Color": 4,             # 4 * uint8
    "Guid": 16,             # 4 * uint32
    "IntPoint": 8,          # 2 * int32
    "IntVector": 12,        # 3 * int32
    "Plane": 32,            # 4 * float64
    "Sphere": 16,           # 3 * float32 + float32
    "Box": 24,              # 2 * Vector(12)
    "Box2D": 20,            # 2 * Vector2D(16) + 1
    "TwoVectors": 48,       # 2 * Vector(24)
    "Matrix": 64,           # 4 * Plane(32)
    "FrameNumber": 4,       # int32
    "Timespan": 8,          # int64
    "DateTime": 8,          # int64
}
```

### 1.2 需要添加的 Struct 类型 (100+ 种)

根据 CUE4Parse 分析，需要添加以下类型的 fast-path 支持：

---

## 二、实现计划

### Phase 1: 核心数学类型扩展 (Task 1-5)

---

#### Task 1: 添加 UE5 LWC 数学类型

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py`
- Create: `tests/test_struct_fastpath_math.py`

- [ ] **Step 1: 创建测试**

```python
# tests/test_struct_fastpath_math.py
"""测试数学类型 Struct fast-path"""
import pytest


def test_vector2f_size():
    """测试 Vector2f 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Vector2f") == 8  # 2 * float32


def test_vector3f_size():
    """测试 Vector3f 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Vector3f") == 12  # 3 * float32


def test_vector3d_size():
    """测试 Vector3d 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Vector3d") == 24  # 3 * float64


def test_vector4f_size():
    """测试 Vector4f 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Vector4f") == 16  # 4 * float32


def test_vector4d_size():
    """测试 Vector4d 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Vector4d") == 32  # 4 * float64
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_struct_fastpath_math.py -v
```

Expected: FAIL (size is None)

- [ ] **Step 3: 添加 Struct 大小定义**

```python
# 在 src/uasset_read/parsers/property_types.py 的 _EXPECTED_STRUCT_SIZES 中添加

# UE5 LWC 数学类型
"Vector2f": 8,           # 2 * float32
"Vector3f": 12,          # 3 * float32
"Vector3d": 24,          # 3 * float64
"Vector4f": 16,          # 4 * float32
"Vector4d": 32,          # 4 * float64
"Rotator3f": 12,         # 3 * float32
"Rotator3d": 24,         # 3 * float64
"Quat4f": 16,            # 4 * float32
"Quat4d": 32,            # 4 * float64
"Plane4f": 16,           # 4 * float32
"Plane4d": 32,           # 4 * float64
"Sphere3f": 16,          # 4 * float32
"Sphere3d": 32,          # 4 * float64
"Box2f": 16,             # 2 * Vector2f(8)
"Box3f": 24,             # 2 * Vector3f(12)
"Matrix44f": 64,         # 4 * Plane4f(16)
"Transform3f": 48,       # Quat4f(16) + Vector3f(12) + Vector3f(4) + padding
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_fastpath_math.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(struct): 添加 UE5 LWC 数学类型 fast-path 支持"
```

---

#### Task 2: 添加整数向量类型

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py`
- Modify: `tests/test_struct_fastpath_math.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_struct_fastpath_math.py 中添加

def test_int_vector2_size():
    """测试 IntVector2 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("IntVector2") == 8  # 2 * int32


def test_int_vector4_size():
    """测试 IntVector4 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("IntVector4") == 16  # 4 * int32


def test_uint_vector_size():
    """测试 UintVector 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("UintVector") == 12  # 3 * uint32


def test_uint_vector2_size():
    """测试 UintVector2 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("UintVector2") == 8  # 2 * uint32


def test_uint_vector4_size():
    """测试 UintVector4 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("UintVector4") == 16  # 4 * uint32
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_struct_fastpath_math.py::test_int_vector2_size -v
```

Expected: FAIL

- [ ] **Step 3: 添加 Struct 大小定义**

```python
# 在 src/uasset_read/parsers/property_types.py 的 _EXPECTED_STRUCT_SIZES 中添加

# 整数向量类型
"IntVector2": 8,         # 2 * int32
"Int32Vector2": 8,       # 别名
"IntVector4": 16,        # 4 * int32
"UintVector": 12,        # 3 * uint32
"UintVector2": 8,        # 2 * uint32
"Uint32Point": 8,        # 别名
"UintVector4": 16,       # 4 * uint32

# 64 位整数向量类型
"Int64Vector2": 16,      # 2 * int64
"Int64Point": 16,        # 别名
"Int64Vector": 24,       # 3 * int64
"Int64Vector4": 32,      # 4 * int64
"UInt64Vector2": 16,     # 2 * uint64
"UInt64Point": 16,       # 别名
"UInt64Vector": 24,      # 3 * uint64
"UInt64Vector4": 32,     # 4 * uint64
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_fastpath_math.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(struct): 添加整数向量类型 fast-path 支持"
```

---

#### Task 3: 添加别名类型

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py`
- Modify: `tests/test_struct_fastpath_math.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_struct_fastpath_math.py 中添加

def test_deprecate_slate_vector2d_size():
    """测试 DeprecateSlateVector2D 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("DeprecateSlateVector2D") == 16  # 别名


def test_vector_double_size():
    """测试 VectorDouble 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("VectorDouble") == 24  # Wuthering Waves
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_struct_fastpath_math.py::test_deprecate_slate_vector2d_size -v
```

Expected: FAIL

- [ ] **Step 3: 添加 Struct 大小定义**

```python
# 在 src/uasset_read/parsers/property_types.py 的 _EXPECTED_STRUCT_SIZES 中添加

# 别名类型
"DeprecateSlateVector2D": 16,  # 别名 Vector2D
"VectorDouble": 24,            # Wuthering Waves 别名 Vector3d
"Int32Point": 8,               # 别名 IntPoint
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_fastpath_math.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(struct): 添加别名类型 fast-path 支持"
```

---

#### Task 4: 添加时间/帧类型

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py`
- Modify: `tests/test_struct_fastpath_math.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_struct_fastpath_math.py 中添加

def test_timespan_size():
    """测试 Timespan 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Timespan") == 8  # int64


def test_datetime_size():
    """测试 DateTime 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("DateTime") == 8  # int64


def test_frame_number_size():
    """测试 FrameNumber 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("FrameNumber") == 4  # int32
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_struct_fastpath_math.py::test_timespan_size -v
```

Expected: FAIL

- [ ] **Step 3: 实现已在 Task 1 中完成**

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_fastpath_math.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test(struct): 添加时间/帧类型测试用例"
```

---

#### Task 5: 添加 TwoVectors 和 Matrix 类型

**Files:**
- Modify: `tests/test_struct_fastpath_math.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_struct_fastpath_math.py 中添加

def test_two_vectors_size():
    """测试 TwoVectors 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("TwoVectors") == 48  # 2 * Vector(24)


def test_matrix_size():
    """测试 Matrix 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    assert _EXPECTED_STRUCT_SIZES.get("Matrix") == 64  # 4 * Plane(32)
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_struct_fastpath_math.py::test_two_vectors_size -v
```

Expected: FAIL

- [ ] **Step 3: 实现已在 Task 1 中完成**

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_fastpath_math.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "test(struct): 添加 TwoVectors 和 Matrix 测试用例"
```

---

### Phase 2: 引擎核心类型 (Task 6-10)

---

#### Task 6: 添加 SoftObjectPath 类型

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py`
- Create: `tests/test_struct_fastpath_engine.py`

- [ ] **Step 1: 创建测试**

```python
# tests/test_struct_fastpath_engine.py
"""测试引擎核心类型 Struct fast-path"""
import pytest


def test_soft_object_path_size():
    """测试 SoftObjectPath 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    # SoftObjectPath 是变长的，不在 fast-path 中
    assert _EXPECTED_STRUCT_SIZES.get("SoftObjectPath") is None


def test_gameplay_tag_container_size():
    """测试 GameplayTagContainer 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    # GameplayTagContainer 是变长的，不在 fast-path 中
    assert _EXPECTED_STRUCT_SIZES.get("GameplayTagContainer") is None
```

- [ ] **Step 2: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_fastpath_engine.py -v
```

Expected: PASS (这些类型不在 fast-path 中)

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test(struct): 添加引擎核心类型测试用例"
```

---

#### Task 7: 添加 PerPlatform 类型

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py`
- Modify: `tests/test_struct_fastpath_engine.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_struct_fastpath_engine.py 中添加

def test_per_platform_bool_size():
    """测试 PerPlatformBool 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    # PerPlatformBool 是变长的，不在 fast-path 中
    assert _EXPECTED_STRUCT_SIZES.get("PerPlatformBool") is None


def test_per_platform_float_size():
    """测试 PerPlatformFloat 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    # PerPlatformFloat 是变长的，不在 fast-path 中
    assert _EXPECTED_STRUCT_SIZES.get("PerPlatformFloat") is None
```

- [ ] **Step 2: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_fastpath_engine.py -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test(struct): 添加 PerPlatform 类型测试用例"
```

---

#### Task 8: 添加材质输入类型

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py`
- Modify: `tests/test_struct_fastpath_engine.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_struct_fastpath_engine.py 中添加

def test_expression_input_size():
    """测试 ExpressionInput 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    # ExpressionInput 是变长的，不在 fast-path 中
    assert _EXPECTED_STRUCT_SIZES.get("ExpressionInput") is None


def test_material_attributes_input_size():
    """测试 MaterialAttributesInput 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    # MaterialAttributesInput 是变长的，不在 fast-path 中
    assert _EXPECTED_STRUCT_SIZES.get("MaterialAttributesInput") is None
```

- [ ] **Step 2: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_fastpath_engine.py -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test(struct): 添加材质输入类型测试用例"
```

---

#### Task 9: 添加动画曲线类型

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py`
- Modify: `tests/test_struct_fastpath_engine.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_struct_fastpath_engine.py 中添加

def test_rich_curve_key_size():
    """测试 RichCurveKey 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    # RichCurveKey 是变长的，不在 fast-path 中
    assert _EXPECTED_STRUCT_SIZES.get("RichCurveKey") is None


def test_simple_curve_key_size():
    """测试 SimpleCurveKey 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    # SimpleCurveKey 是变长的，不在 fast-path 中
    assert _EXPECTED_STRUCT_SIZES.get("SimpleCurveKey") is None
```

- [ ] **Step 2: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_fastpath_engine.py -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test(struct): 添加动画曲线类型测试用例"
```

---

#### Task 10: 添加 MovieScene 类型

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py`
- Modify: `tests/test_struct_fastpath_engine.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_struct_fastpath_engine.py 中添加

def test_movie_scene_frame_range_size():
    """测试 MovieSceneFrameRange 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    # MovieSceneFrameRange 是变长的，不在 fast-path 中
    assert _EXPECTED_STRUCT_SIZES.get("MovieSceneFrameRange") is None


def test_movie_scene_segment_size():
    """测试 MovieSceneSegment 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    # MovieSceneSegment 是变长的，不在 fast-path 中
    assert _EXPECTED_STRUCT_SIZES.get("MovieSceneSegment") is None
```

- [ ] **Step 2: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_fastpath_engine.py -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test(struct): 添加 MovieScene 类型测试用例"
```

---

### Phase 3: 游戏特定类型 (Task 11-15)

---

#### Task 11: 添加 Fortnite 类型

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py`
- Create: `tests/test_struct_fastpath_game.py`

- [ ] **Step 1: 创建测试**

```python
# tests/test_struct_fastpath_game.py
"""测试游戏特定类型 Struct fast-path"""
import pytest


def test_fortnite_bundle_size():
    """测试 Fortnite Bundle 大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    # Fortnite 特定类型不在 fast-path 中
    assert _EXPECTED_STRUCT_SIZES.get("FortniteBundle") is None
```

- [ ] **Step 2: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_fastpath_game.py -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test(struct): 添加 Fortnite 类型测试用例"
```

---

#### Task 12: 添加 Borderlands 4 类型

**Files:**
- Modify: `tests/test_struct_fastpath_game.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_struct_fastpath_game.py 中添加

def test_borderlands4_type_size():
    """测试 Borderlands4 类型大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    # Borderlands4 特定类型不在 fast-path 中
    assert _EXPECTED_STRUCT_SIZES.get("GbxDefPtrProperty") is None
```

- [ ] **Step 2: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_fastpath_game.py -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test(struct): 添加 Borderlands4 类型测试用例"
```

---

#### Task 13: 添加 Wuthering Waves 类型

**Files:**
- Modify: `tests/test_struct_fastpath_game.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_struct_fastpath_game.py 中添加

def test_wuthering_waves_type_size():
    """测试 Wuthering Waves 类型大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    # Wuthering Waves 特定类型已在 Task 3 中添加 (VectorDouble)
    assert _EXPECTED_STRUCT_SIZES.get("VectorDouble") == 24
```

- [ ] **Step 2: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_fastpath_game.py -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test(struct): 添加 Wuthering Waves 类型测试用例"
```

---

#### Task 14: 添加 PUBG 类型

**Files:**
- Modify: `tests/test_struct_fastpath_game.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_struct_fastpath_game.py 中添加

def test_pubg_type_size():
    """测试 PUBG 类型大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    # PUBG 特定类型不在 fast-path 中
    assert _EXPECTED_STRUCT_SIZES.get("PUBGType") is None
```

- [ ] **Step 2: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_fastpath_game.py -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test(struct): 添加 PUBG 类型测试用例"
```

---

#### Task 15: 添加其他游戏类型

**Files:**
- Modify: `tests/test_struct_fastpath_game.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_struct_fastpath_game.py 中添加

def test_other_game_types_size():
    """测试其他游戏类型大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES
    # 其他游戏特定类型不在 fast-path 中
    assert _EXPECTED_STRUCT_SIZES.get("StarWarsJediType") is None
    assert _EXPECTED_STRUCT_SIZES.get("LEGOType") is None
    assert _EXPECTED_STRUCT_SIZES.get("StateOfDecay2Type") is None
    assert _EXPECTED_STRUCT_SIZES.get("DeltaForceType") is None
    assert _EXPECTED_STRUCT_SIZES.get("GothicRemakeType") is None
```

- [ ] **Step 2: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_fastpath_game.py -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test(struct): 添加其他游戏类型测试用例"
```

---

### Phase 4: 变长类型处理 (Task 16-20)

---

#### Task 16: 确认变长类型不在 fast-path 中

**Files:**
- Create: `tests/test_struct_fastpath_variable.py`

- [ ] **Step 1: 创建测试**

```python
# tests/test_struct_fastpath_variable.py
"""测试变长类型 Struct fast-path"""
import pytest


def test_variable_length_types_not_in_fastpath():
    """确认变长类型不在 fast-path 中"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES

    # 这些类型是变长的，不应在 fast-path 中
    variable_types = [
        "SoftObjectPath",
        "StringAssetReference",
        "StringClassReference",
        "SoftClassPath",
        "GameplayTagContainer",
        "PerPlatformBool",
        "PerPlatformFloat",
        "PerPlatformInt",
        "PerPlatformFrameRate",
        "PerPlatformFString",
        "PerQualityLevelInt",
        "PerQualityLevelFloat",
        "ExpressionInput",
        "MaterialAttributesInput",
        "ColorMaterialInput",
        "ScalarMaterialInput",
        "VectorMaterialInput",
        "Vector2MaterialInput",
        "RichCurveKey",
        "SimpleCurveKey",
        "NameCurveKey",
        "CompressedRichCurve",
        "RawAnimSequenceTrack",
        "AnimationAttributeIdentifier",
        "AttributeCurve",
        "MovieSceneFrameRange",
        "MovieSceneSegment",
        "MovieSceneFloatChannel",
        "MovieSceneDoubleChannel",
        "MovieSceneSubSequenceTree",
        "MovieSceneTrackFieldData",
        "MovieSceneSubSectionFieldData",
        "SectionEvaluationDataTree",
        "MovieSceneEvalTemplatePtr",
        "MovieSceneEvaluationFieldEntityTree",
        "MovieSceneEventParameters",
        "MovieSceneTrackImplementationPtr",
        "MovieSceneSequenceInstanceDataPtr",
        "MovieSceneTimeWarpVariant",
        "NiagaraVariable",
        "NiagaraVariableBase",
        "NiagaraVariableWithOffset",
        "NiagaraDataInterfaceGPUParamInfo",
        "NiagaraDataChannelVariable",
        "ClothLODDataCommon",
        "ClothLODData",
        "ClothTetherData",
        "InstancedStruct",
        "InstancedStructContainer",
        "InstancedPropertyBag",
        "InstancedOverridablePropertyBag",
        "WorldConditionQueryDefinition",
        "UniversalObjectLocatorFragment",
        "UniqueNetIdRepl",
        "Spline",
        "TypedParameter",
        "EdGraphPinType",
        "NavAgentSelector",
        "SmartName",
        "MaterialOverrideNanite",
        "MaterialLayersFunctionsTree",
        "LevelSequenceObjectReferenceMap",
        "MidiEvent",
        "PCGPoint",
        "PCGDataPtrWrapper",
        "PCGPointArray",
        "SkeletalMeshSamplingLODBuiltData",
        "SkeletalMeshSamplingRegionBuiltData",
    ]

    for type_name in variable_types:
        assert _EXPECTED_STRUCT_SIZES.get(type_name) is None, f"{type_name} should not be in fast-path"
```

- [ ] **Step 2: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_fastpath_variable.py -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test(struct): 确认变长类型不在 fast-path 中"
```

---

#### Task 17: 验证 fast-path 解析逻辑

**Files:**
- Modify: `tests/test_struct_fastpath_variable.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_struct_fastpath_variable.py 中添加

def test_fastpath_parsing_logic():
    """测试 fast-path 解析逻辑"""
    from unittest.mock import MagicMock
    from uasset_read.parsers.property_types import parse_struct_property

    # 模拟一个已知大小的 Struct
    archive = MagicMock()
    archive.read_bytes.return_value = b'\x00' * 24  # Vector 大小

    tag = MagicMock()
    tag.type = "StructProperty"
    tag.struct_type = "Vector"

    # 这应该使用 fast-path
    result = parse_struct_property(archive, tag)
    assert result is not None
```

- [ ] **Step 2: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_fastpath_variable.py::test_fastpath_parsing_logic -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test(struct): 验证 fast-path 解析逻辑"
```

---

#### Task 18: 验证 fallback 解析逻辑

**Files:**
- Modify: `tests/test_struct_fastpath_variable.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_struct_fastpath_variable.py 中添加

def test_fallback_parsing_logic():
    """测试 fallback 解析逻辑"""
    from unittest.mock import MagicMock
    from uasset_read.parsers.property_types import parse_struct_property

    # 模拟一个未知大小的 Struct
    archive = MagicMock()
    tag = MagicMock()
    tag.type = "StructProperty"
    tag.struct_type = "UnknownStruct"

    # 这应该使用 fallback 解析
    result = parse_struct_property(archive, tag)
    assert result is not None
```

- [ ] **Step 2: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_fastpath_variable.py::test_fallback_parsing_logic -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test(struct): 验证 fallback 解析逻辑"
```

---

#### Task 19: 验证 tagged fallback 解析逻辑

**Files:**
- Modify: `tests/test_struct_fastpath_variable.py`

- [ ] **Step 1: 添加测试**

```python
# 在 tests/test_struct_fastpath_variable.py 中添加

def test_tagged_fallback_parsing_logic():
    """测试 tagged fallback 解析逻辑"""
    from unittest.mock import MagicMock
    from uasset_read.parsers.property_types import parse_struct_property

    # 模拟一个 tagged fallback Struct
    archive = MagicMock()
    tag = MagicMock()
    tag.type = "StructProperty"
    tag.struct_type = "TaggedFallbackStruct"

    # 这应该使用 tagged fallback 解析
    result = parse_struct_property(archive, tag)
    assert result is not None
```

- [ ] **Step 2: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_fastpath_variable.py::test_tagged_fallback_parsing_logic -v
```

Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test(struct): 验证 tagged fallback 解析逻辑"
```

---

#### Task 20: 完整测试套件验证

**Files:**
- Modify: `tests/test_struct_fastpath_variable.py`

- [ ] **Step 1: 添加完整测试**

```python
# 在 tests/test_struct_fastpath_variable.py 中添加

def test_all_fastpath_types_have_valid_sizes():
    """验证所有 fast-path 类型都有有效的大小"""
    from uasset_read.parsers.property_types import _EXPECTED_STRUCT_SIZES

    for type_name, size in _EXPECTED_STRUCT_SIZES.items():
        assert isinstance(size, int), f"{type_name} size should be int, got {type(size)}"
        assert size > 0, f"{type_name} size should be positive, got {size}"
```

- [ ] **Step 2: 运行完整测试套件**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: 所有测试通过

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "test(struct): 完整测试套件验证"
```

---

## 三、验收标准

### 3.1 功能完整性

- [ ] 所有固定大小的 Struct 类型都已添加到 fast-path
- [ ] 所有变长类型确认不在 fast-path 中
- [ ] fast-path 解析逻辑正常工作
- [ ] fallback 解析逻辑正常工作

### 3.2 测试覆盖

- [ ] 所有测试通过
- [ ] 每种类型至少 1 个测试用例
- [ ] 边界条件测试覆盖

### 3.3 代码质量

- [ ] 代码风格一致
- [ ] 无未使用导入
- [ ] 所有常量都有注释说明

---

## 四、预期收益

| 指标 | 改进 |
|------|------|
| 新增 fast-path 类型 | ~30 种 |
| 确认变长类型 | ~70 种 |
| 新增测试用例 | ~50 个 |
| 代码行数增加 | ~200 行 |
| CUE4Parse 对齐度 | 从 20/120 提升到 50/120 |

---

## 五、文件变更清单

| 文件 | 操作 | Task |
|------|------|------|
| `parsers/property_types.py` | 修改 | 1-3 |
| `tests/test_struct_fastpath_math.py` | 新建 | 1-5 |
| `tests/test_struct_fastpath_engine.py` | 新建 | 6-10 |
| `tests/test_struct_fastpath_game.py` | 新建 | 11-15 |
| `tests/test_struct_fastpath_variable.py` | 新建 | 16-20 |

**总计:** 1 个修改文件，4 个新建文件

---

## 六、总结

本计划扩展了 Struct fast-path 覆盖范围：

1. **Phase 1**: 添加 UE5 LWC 数学类型和整数向量类型（~30 种）
2. **Phase 2**: 验证引擎核心类型不在 fast-path 中（~20 种）
3. **Phase 3**: 验证游戏特定类型不在 fast-path 中（~10 种）
4. **Phase 4**: 确认变长类型处理逻辑正确（~70 种）

最终实现 50+ 种 fast-path 类型，覆盖所有固定大小的 Struct，与 CUE4Parse 的 fast-path 逻辑对齐。
