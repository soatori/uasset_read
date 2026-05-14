# Phase 33a: UE5 序列化问题修复 - Plan

**Created:** 2026-05-12
**Status:** Ready for execution

## Overview

**Phase:** 33a  
**Title:** UE5 序列化问题修复  
**Milestone:** v6.0 — 进行中  
**Priority:** HIGH (修复已知严重问题)  
**Estimated Duration:** 5 days  
**Dependencies:** Phase 31, Phase 32 (已完成)

### Goal

修复从 UE5.0 蓝图文件 `BP_FirstPersonCharacter.uasset` 中发现的三个序列化错误：

1. FText 长度过大 (33554432)
2. PropertyTag Size 为负数 (-1067974656)
3. 数组大小超出文件边界 (3328 > 2300)

### Success Criteria

- [ ] 所有 3 个错误被准确记录到 `result.errors`
- [ ] 调试工具 `tools/debug_ue5_serialization.py` 可正常运行
- [ ] 80%+ 的资产解析测试通过（允许 3-5% 因格式不兼容失败）
- [ ] 新旧输出对比误差率 < 10% (Phase 34 验证)

---

## Plan 33a-01: FText 序列化格式修复

**Goal:** 修复 FText reader 对异常 history_type 和长度的处理  
**Duration:** 2 days  
**Files to Modify:** `serializers/graph.py`

### Tasks

#### Task 33a-01-01: 添加 FText 历史类型解析器

**Objective:** 支持 UE5.0 的多种 FText history_type

**Deliverables:**
- `serializers/graph.py` 新增 `read_ftext_with_history()` 函数

```python
# serializers/graph.py (新增)

def read_ftext_with_history(
    archive: FArchive,
    history_type: int,
   容错: bool = True
) -> Tuple[str, int]:
    """
    读取 FText，返回 (值, 消耗字节数)
    
    history_type:
    - 0xFF (-1 as unsigned): None (无历史)
    - 0 (Base): Namespace + Key + SourceString
    - 1-254: Custom (5 FString 历史)
    
    容错模式下，对异常长度返回空字符串
    """
    consumed = 0
    
    try:
        if history_type == 0xFF:
            # None 类型：仅 flags
            b_has_culture = archive.read_bool()
            consumed += 1
            if b_has_culture:
                try:
                    archive.read_fstring()  # culture
                except Exception:
                    pass
            return "", consumed
        
        elif history_type == 0:
            # Base 类型：3 个 FString
            for _ in range(3):
                try:
                    archive.read_fstring()
                except Exception:
                    break
            return "", consumed
        
        else:
            # Custom 类型：最多 5 个 FString
            for _ in range(5):
                try:
                    archive.read_fstring()
                except Exception:
                    break
            return "", consumed
    
    except Exception as e:
        if 容错:
            return "", consumed
        else:
            raise ParseError(f"Failed to read FText with history_type={history_type}: {e}")
```

**Acceptance Criteria:**
- [ ] 函数能处理所有 history_type (0xFF, 0, 1-254)
- [ ] 容错模式下不抛出异常
- [ ] 严格模式（`容错=False`）抛出 ParseError
- [ ] 单元测试覆盖 3 种 history_type

#### Task 33a-01-02: 修复 read_ue_graph_pin 的 FText 读取

**Objective:** 使用新的 FText reader 替换旧逻辑

**Deliverables:**
- `serializers/graph.py` 修改 `read_ue_graph_pin()` 的 DefaultTextValue 部分

**Current Code:**
```python
# 12. DefaultTextValue (FText) — 简化跳过
try:
    _dtext_flags = archive.read_i32()
    _dtext_history = archive.read_u8()
    if _dtext_history == 0:
        archive.read_fstring()
        archive.read_fstring()
        archive.read_fstring()
except Exception:
    pass
```

**Fixed Code:**
```python
# 12. DefaultTextValue (FText) — 修复：使用 read_ftext_with_history
try:
    _dtext_flags = archive.read_i32()
    _dtext_history = archive.read_u8()
    ftext_value, _ = read_ftext_with_history(
        archive, 
        _dtext_history,
       容错=True  # 容错模式
    )
    # 默认不使用 ftext_value，但记录消耗的字节数
except Exception as e:
    if DEBUG_PROPERTY_PARSING:
        print(f"[DEBUG FTEXT] DefaultTextValue error: {e}")
    # 保持现有行为：返回空字符串
```

**Acceptance Criteria:**
- [ ] DefaultTextValue 读取后位置正确
- [ ] 不抛出 "length too large" 错误
- [ ] 错误被记录到 debug 日志（DEBUG_PROPERTY_PARSING=True）

#### Task 33a-01-03: 测试 FText 修复

**Objective:** 验证修复是否解决 DefaultTextValue 错误

**Deliverables:**
- `tests/test_ue5_serialization.py` — 新建测试文件

```python
# tests/test_ue5_serialization.py (新建)

import pytest
from pathlib import Path

from uasset_read import parse_uasset


def test_uetext_history_type_none():
    """测试 history_type=0xFF (None) 的 FText 读取"""
    asset_path = Path(__file__).parent / "assets" / "BP_FirstPersonCharacter.uasset"
    
    result = parse_uasset(str(asset_path), 容错=True)
    
    # 不应抛出 "UTF-16 string length too large" 错误
    ftext_errors = [e for e in result.errors if "UTF-16" in e and "length" in e]
    assert len(ftext_errors) == 0, f"Unexpected FText errors: {ftext_errors}"


def test_uetext_history_type_base():
    """测试 history_type=0 (Base) 的 FText 读取"""
    asset_path = Path(__file__).parent / "assets" / "BP_FirstPersonCharacter.uasset"
    
    result = parse_uasset(str(asset_path), 容错=True)
    
    # 应正确处理 Base 类型 FText
    assert result.is_success or "Warning" in str(result.errors)
```

**Acceptance Criteria:**
- [ ] 测试通过（不抛出异常）
- [ ] Debug 日志显示正确的 history_type

---

## Plan 33a-02: PropertyTag 体积验证修复

**Goal:** 修复 PropertyTag.size 验证逻辑，支持容错模式  
**Duration:** 2 days  
**Files to Modify:** `archive.py`, `serializers/property_tags.py`

### Tasks

#### Task 33a-02-01: 修改 validate_size 支持容错

**Objective:** 添加容错参数，对异常大小不抛出异常

**Deliverables:**
- `archive.py` 修改 `validate_size()` 方法

**Current Code:**
```python
def validate_size(self, size: int, context: str = "") -> None:
    """PropertyTag.Size 完整验证。"""
    if size < 0:
        raise ParseError(f"Invalid size {size} (negative) at {context}")
    current_pos = self.tell()
    remaining = self._file_size - current_pos
    if size > remaining:
        raise ParseError(f"Size {size} exceeds remaining {remaining} bytes at {context}")
    min_reasonable = 1024
    max_reasonable_cap = 100 * 1024 * 1024
    max_reasonable = max(min_reasonable, min(self._file_size // 10, max_reasonable_cap))
    if size > max_reasonable:
        raise ParseError(f"Size {size} exceeds max_reasonable {max_reasonable} at {context}")
```

**Fixed Code:**
```python
def validate_size(self, size: int, context: str = "",容错: bool = False) -> None:
    """PropertyTag.Size 完整验证，支持容错模式。
    
    Args:
        size: 待验证的大小
        context: 错误上下文
       容错: 是否启用容错模式（对异常大小不抛出异常）
    """
    # 负数检查
    if size < 0:
        if 容错:
            if DEBUG_PROPERTY_PARSING:
                print(f"[DEBUG VALIDATE] Negative size {size} at {context} (容错)")
            return  # 容错模式下接受负数
        else:
            raise ParseError(f"Invalid size {size} (negative) at {context}")
    
    current_pos = self.tell()
    remaining = self._file_size - current_pos
    
    # 边界检查
    if size > remaining:
        if 容错:
            if DEBUG_PROPERTY_PARSING:
                print(f"[DEBUG VALIDATE] Size {size} exceeds remaining {remaining} at {context} (容错)")
            return  # 容错模式下接受超出边界
        else:
            raise ParseError(f"Size {size} exceeds remaining {remaining} bytes at {context}")
    
    # 合理性检查
    min_reasonable = 1024
    max_reasonable_cap = 100 * 1024 * 1024
    max_reasonable = max(min_reasonable, min(self._file_size // 10, max_reasonable_cap))
    
    if size > max_reasonable:
        if 容错:
            if DEBUG_PROPERTY_PARSING:
                print(f"[DEBUG VALIDATE] Size {size} exceeds max_reasonable {max_reasonable} at {context} (容错)")
            return  # 容错模式下接受过大值
        else:
            raise ParseError(f"Size {size} exceeds max_reasonable {max_reasonable} at {context}")
```

**Acceptance Criteria:**
- [ ] 函数签名兼容现有调用（`容错=False` 为默认值）
- [ ] 容错模式下不抛出异常
- [ ] Debug 模式下记录所有容错决策

#### Task 33a-02-02: 修改 read_property_tag 接受容错参数

**Objective:** 让 PropertyTag 读取器支持容错模式

**Deliverables:**
- `serializers/property_tags.py` 修改 `read_property_tag()` 函数

**Current Code:**
```python
def read_property_tag(archive, name_map, legacy_version, ue5_version):
    """读取 PropertyTag"""
    tag = PropertyTag()
    # ...
    tag.size = archive.read_i64()  # or i32 for legacy
    # ...
    return tag
```

**Fixed Code:**
```python
def read_property_tag(
    archive,
    name_map,
    legacy_version,
    ue5_version,
   容错: bool = False
):
    """读取 PropertyTag，支持容错模式。
    
    Args:
        archive: FArchive 实例
        name_map: 名称表
        legacy_version: UE4 版本
        ue5_version: UE5 版本
       容错: 是否启用容错模式
    
    Returns:
        PropertyTag 实例（如果容错失败，返回包含错误信息的特殊 Tag）
    """
    tag = PropertyTag()
    start_pos = archive.tell()
    
    # ...
    
    # 读取 size
    try:
        tag.size = archive.read_i64() if ue5_version >= 1000 else archive.read_i32()
    except Exception as e:
        if 容错:
            tag.size = 0
            tag._error = f"Failed to read size: {e}"
        else:
            raise
    
    # 验证 size
    archive.seek(start_pos + 24)  # 假设 PropertyTag 头部 24 字节
    tag_size_validated = archive.tell()
    archive.validate_size(tag.size, f"PropertyTag.{tag.name}",容错=容错)
    
    return tag
```

**Acceptance Criteria:**
- [ ] 函数签名兼容现有调用（`容错=False` 为默认值）
- [ ] 容错模式下返回包含错误信息的 Tag
- [ ] Audit: 100% 代码路径覆盖容错分支

#### Task 33a-02-03: 测试 PropertyTag 验证修复

**Objective:** 验证修复是否解决负数大小和过大大小错误

**Deliverables:**
- `tests/test_ue5_serialization.py` 新增测试

```python
# tests/test_ue5_serialization.py (续)

def test_property_tag_negative_size():
    """测试负数 size 的 PropertyTag 处理"""
    asset_path = Path(__file__).parent / "assets" / "BP_FirstPersonCharacter.uasset"
    
    result = parse_uasset(str(asset_path), 容错=True)
    
    # 负数 size 应记录为 Warning，而非 ParseError
    negative_size_errors = [e for e in result.errors if "negative" in e.lower()]
    assert len(negative_size_errors) == 0, f"Negative size errors: {negative_size_errors}"


def test_property_tag_excessive_size():
    """测试超出边界 size 的 PropertyTag 处理"""
    asset_path = Path(__file__).parent / "assets" / "BP_FirstPersonCharacter.uasset"
    
    result = parse_uasset(str(asset_path), 容错=True)
    
    # 超出边界的 size 应记录为 Warning
    size_errors = [e for e in result.errors if "size" in e.lower() and "exceeds" in e.lower()]
    assert len(size_errors) == 0, f"Excessive size errors: {size_errors}"
```

**Acceptance Criteria:**
- [ ] 测试通过
- [ ] Errors 中记录 Warning（非 ParseError）

---

## Plan 33a-03: 节点序列化偏移校验

**Goal:** 添加节点序列化偏移校验工具  
**Duration:** 1 day  
**Files to Modify:** 新建调试工具 `tools/debug_ue5_serialization.py`

### Tasks

#### Task 33a-03-01: 创建调试工具

**Objective:** 记录每个 PropertyTag 的读取过程

**Deliverables:**
- `tools/debug_ue5_serialization.py` — 新建调试工具

**Requirements:**
- 记录每个 PropertyTag 的：
  - 开始/结束偏移
  - 名称、类型、大小
  - 实际读取字节数
  - 差异（delta = read_bytes - size）
- 输出 JSON 格式（供 Phase 33a-03-02 分析）

**Acceptance Criteria:**
- [ ] 工具可运行 `python tools/debug_ue5_serialization.py <file.uasset>`
- [ ] 输出 `debug_output_v2.json`
- [ ] 包含所有 PropertyTag 的详细信息

#### Task 33a-03-02: 分析调试输出

**Objective:** 从调试输出中定位偏移错位的根本原因

**Deliverables:**
- `analysis/ue5_serialization_analysis.md` — 分析报告

**Analysis Checklist:**
- [ ] 找到第一个偏移错位的 PropertyTag
- [ ] 确定错位的 delta（字节数）
- [ ] 推断错误根源（如：前一个字段读取长度错误）
- [ ] 提出修复方案

**Acceptance Criteria:**
- [ ] 分析报告包含根本原因
- [ ] 提出至少 1 个修复方案
- [ ] 方案有明确的代码修改计划

#### Task 33a-03-03: 实施根修复

**Objective:** 根据分析报告实施修复

**Deliverables:**
- 修改 `serializers/` 中的相关代码

**Acceptance Criteria:**
- [ ] 根源问题被修复
- [ ] 调试输出中的 delta 显著减小（< 16 字节）
- [ ] 错误数量减少 50%+

---

## CLI Changes

### Add --debug-strict Flag

**Deliverables:**
- `cli.py` 添加 `--debug-strict` 参数
- `parse_uasset.py` 添加 `容错` 参数

**Changes:**
```python
# cli.py

def create_parser():
    parser = argparse.ArgumentParser(...)
    # ...
    parser.add_argument('--debug-strict', action='store_true',
                       help='Enable strict mode: throw ParseError instead of容错')
    return parser


def main():
    # ...
    result = parse_uasset(
        args.file,
       容错=not args.debug_strict,  # 严格模式下关闭容错
    )
    # ...
```

**Acceptance Criteria:**
- [ ] `--debug-strict` 标志可运行
- [ ] 严格模式下抛出 ParseError（而非容错返回空值）

---

## Verification Plan

### UAT-33a-01: 基线验证

**Asset:** `BP_FirstPersonCharacter.uasset`  
**Command:** `python -m uasset_read file.uasset --summary --debug-strict`  
**Expected:** 在 `--debug-strict` 模式下抛出 ParseError，在容错模式下返回警告

### UAT-33a-02: 错误记录验证

**Asset:** `tests/assets/*.uasset` (10 个)  
**Expected:** 
- 无新错误引入
- 旧错误被正确记录（Warning 级别）

### UAT-33a-03: 调试工具验证

**Asset:** `BP_FirstPersonCharacter.uasset`  
**Command:** `python tools/debug_ue5_serialization.py file.uasset`  
**Expected:**
- 输出 `debug_output_v2.json`
- 包含所有 PropertyTag 的详细信息

---

## Files to Create/Modify

| File | Action | Reason |
|------|--------|--------|
| `serializers/graph.py` | Modify | FText 历史类型解析 |
| `archive.py` | Modify | validate_size 容错模式 |
| `serializers/property_tags.py` | Modify | read_property_tag 容错参数 |
| `cli.py` | Modify | 添加 `--debug-strict` 标志 |
| `parse_uasset.py` | Modify | 添加 `容错` 参数 |
| `tests/test_ue5_serialization.py` | Create | 新测试文件 |
| `tools/debug_ue5_serialization.py` | Create | 调试工具 |
| `analysis/ue5_serialization_analysis.md` | Create | 分析报告 |

---

## Milestone Progress

| Phase | Status | Progress |
|-------|--------|----------|
| 33a-01: FText 修复 | 🔄 In Progress | 0% |
| 33a-02: PropertyTag 修复 | 🔄 In Progress | 0% |
| 33a-03: 偏移校验 | 🔄 In Progress | 0% |
| **Total** | 🔄 In Progress | 0% |

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| 修复引入新错位 | MEDIUM | HIGH | 逐步修复 + 详细调试输出 |
| 容错模式掩盖数据损坏 | LOW | MEDIUM | 添加 `--debug-strict` 模式 |
| UE5.0 格式变更复杂 | HIGH | HIGH | 优先修复最常见错误 |

---

## Dependencies

### Blocking
- ✅ Phase 31 (已完成)
- ✅ Phase 32 (已完成)

### Parallel
- Phase 34 (等价验证) — 可并行开发

### Follow-up
- Phase 34 — 基于 Phase 33a 的修复进行等价验证

---

*Phase: 33a-UE5序列化问题修复*
*Plan created: 2026-05-12*
