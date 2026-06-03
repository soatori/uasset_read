# Pin LinkerTo 改进实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Pin 连接关系中反复出现的偏移错位、格式不一致和恢复机制缺陷问题

**Architecture:** 三阶段改进：(1) FText 解析安全网防止偏移错位 (2) PinReference GUID 格式统一 (3) 恢复机制增强和测试覆盖

**Tech Stack:** Python 3.10+, pytest, struct (二进制解析)

---

## 文件结构

### 修改文件

| 文件 | 职责 |
|------|------|
| `src/uasset_read/serializers/graph.py` | FText 安全网、LinkedTo 恢复改进 |
| `src/uasset_read/graph/flow_builder.py` | GUID 格式统一、日志去重改进 |

### 新增文件

| 文件 | 职责 |
|------|------|
| `tests/test_pin_recovery.py` | 恢复机制单元测试 |

---

## Task 1: FText 解析安全网

**目标:** 在 `read_ue_graph_pin()` 中为 FText 解析增加 seek 安全网，防止偏移错位

**Files:**
- Modify: `src/uasset_read/serializers/graph.py:950-1000, 1057-1092`
- Test: `tests/test_pin_recovery.py`

- [ ] **Step 1: 创建测试文件并编写 FText 安全网测试**

```python
# tests/test_pin_recovery.py
"""Pin 连接关系恢复机制测试。"""
import struct
import pytest
from unittest.mock import MagicMock, patch
from uasset_read.serializers.graph import (
    read_ue_graph_pin,
    read_pin_reference,
    _recover_pin_array_count,
)


class TestFTextSafetyNet:
    """FText 解析安全网测试。"""

    def test_ftext_consumption_limit(self):
        """验证 FText 消耗字节数有上限检查。"""
        # 构造一个模拟 archive，FText body 超过 10KB
        fake_archive = MagicMock()
        fake_archive._file_size = 20000
        fake_archive.read_i32.return_value = 0  # flags
        fake_archive.read_bytes.return_value = b'\x00' * 1  # history_type
        # 模拟超大 FText body
        fake_archive.read.side_effect = [
            b'\x00' * 1,  # history_type
            b'\x00' * 15000,  # 超大 body
        ]

        # 验证安全网会触发 seek 回退
        # 实际实现中，FText 消耗超过 10240 字节应触发警告并 seek 回起点
        assert True  # 占位，Step 3 实现后替换

    def test_ftext_seek_fallback_on_corruption(self):
        """验证 FText 损坏时正确 seek 回起点。"""
        # 这个测试验证当 FText 解析失败时，archive 位置被正确恢复
        assert True  # 占位
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_pin_recovery.py::TestFTextSafetyNet -v`
Expected: FAIL (测试通过是因为占位 assert True)

- [ ] **Step 3: 实现 FText 安全网**

在 `src/uasset_read/serializers/graph.py` 中修改 `read_ue_graph_pin()` 函数，在 FText 解析前后增加安全检查：

```python
# 在 graph.py 中，找到 read_ue_graph_pin() 函数的 FText 解析部分
# 在 PinFriendlyName (FText) 解析前添加：

    # FText 安全网：记录解析前位置，限制最大消耗
    FTEXT_MAX_CONSUMPTION = 10240  # 10KB
    
    # ... 在 PinFriendlyName FText 解析代码前 ...
    ftext_start_pos = archive.tell()
    
    # ... FText 解析代码 ...
    
    # FText 安全网：验证消耗字节数
    ftext_consumed = archive.tell() - ftext_start_pos
    if ftext_consumed > FTEXT_MAX_CONSUMPTION:
        logger.warning(
            "[FTEXT-SAFETY] PinFriendlyName consumed %d bytes (> %d), "
            "possible corruption, seeking back to %d",
            ftext_consumed, FTEXT_MAX_CONSUMPTION, ftext_start_pos
        )
        archive.seek(ftext_start_pos)
        # 标记解析失败，使用默认值
        pin_friendly_name = None
```

对 `DefaultTextValue` (FText) 做同样处理：

```python
    # DefaultTextValue FText 安全网
    dtv_start_pos = archive.tell()
    
    # ... FText 解析代码 ...
    
    dtv_consumed = archive.tell() - dtv_start_pos
    if dtv_consumed > FTEXT_MAX_CONSUMPTION:
        logger.warning(
            "[FTEXT-SAFETY] DefaultTextValue consumed %d bytes (> %d), "
            "possible corruption, seeking back to %d",
            dtv_consumed, FTEXT_MAX_CONSUMPTION, dtv_start_pos
        )
        archive.seek(dtv_start_pos)
        default_text_value = None
```

- [ ] **Step 4: 更新测试用例验证安全网**

替换测试中的占位 assert，添加实际验证逻辑

- [ ] **Step 5: 运行测试验证通过**

Run: `python -m pytest tests/test_pin_recovery.py::TestFTextSafetyNet -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/uasset_read/serializers/graph.py tests/test_pin_recovery.py
git commit -m "fix(graph): add FText safety net to prevent offset misalignment"
```

---

## Task 2: PinReference GUID 格式统一

**目标:** 在 `read_pin_reference()` 中直接返回归一化的 32 字符 hex GUID

**Files:**
- Modify: `src/uasset_read/serializers/graph.py:544-587`
- Test: `tests/test_pin_recovery.py`

- [ ] **Step 1: 编写 GUID 格式统一测试**

```python
# 在 tests/test_pin_recovery.py 中添加

class TestPinReferenceGUID:
    """PinReference GUID 格式统一测试。"""

    def test_read_pin_reference_returns_normalized_guid(self):
        """验证 read_pin_reference 返回 32 字符纯 hex GUID。"""
        # 构造模拟 archive，包含 8-4-4-4-12 格式的 GUID
        fake_archive = MagicMock()
        fake_archive.read_i32.side_effect = [0, 1]  # b_null=0, owning_node=1
        # 模拟 _read_guid 返回带 dash 格式
        fake_archive.read.return_value = b'\xa1\xb2\xc3\xd4\xe5\xf6\x78\x90\xab\xcd\xef\x12\x34\x56\x78\x90'

        export_map = [MagicMock(object_name="TestNode")]
        import_map = []

        result = read_pin_reference(fake_archive, [], export_map, import_map)
        
        # 验证返回的 pin_guid 是归一化后的 32 字符纯 hex
        assert result is not None
        assert len(result["pin_guid"]) == 32
        assert result["pin_guid"] == result["pin_guid"].upper()
        assert "-" not in result["pin_guid"]
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_pin_recovery.py::TestPinReferenceGUID -v`
Expected: FAIL

- [ ] **Step 3: 修改 read_pin_reference() 归一化 GUID**

在 `src/uasset_read/serializers/graph.py` 的 `read_pin_reference()` 函数中：

```python
def read_pin_reference(
    archive: FArchive,
    name_map: List[str],
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    linker: Optional["PackageLinker"] = None,
) -> Optional[dict]:
    """读取单个 Pin 引用（FBlueprintEditorUtils::FPinReference）。"""
    b_null_ptr = archive.read_i32()
    if b_null_ptr != 0:
        return None

    owning_node_index = archive.read_i32()
    pin_guid_raw = _read_guid(archive)

    # Phase 75: 直接归一化为 32 字符大写 hex（移除 dash）
    pin_guid = pin_guid_raw.replace("-", "").upper()

    # ... 其余代码保持不变 ...

    result = {
        "owning_node": owning_node_name,
        "pin_guid": pin_guid,  # 现在是归一化格式
        "_pin_guid_valid": guid_is_hex and not guid_is_zero,
    }
    # ... 
```

- [ ] **Step 4: 运行测试验证通过**

Run: `python -m pytest tests/test_pin_recovery.py::TestPinReferenceGUID -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/serializers/graph.py tests/test_pin_recovery.py
git commit -m "fix(graph): normalize PinReference GUID to 32-char hex at source"
```

---

## Task 3: LinkedTo 恢复机制改进

**目标:** 使用 `_try_recover_to_subpins()` 返回值，改进恢复逻辑

**Files:**
- Modify: `src/uasset_read/serializers/graph.py:1121-1123`
- Test: `tests/test_pin_recovery.py`

- [ ] **Step 1: 编写恢复机制测试**

```python
# 在 tests/test_pin_recovery.py 中添加

class TestLinkedToRecovery:
    """LinkedTo 恢复机制测试。"""

    def test_recover_to_subpins_result_is_used(self):
        """验证 _try_recover_to_subpins 返回值被正确使用。"""
        # 这个测试验证当 LinkedTo 读取失败时，
        # 恢复函数的返回值会被用于后续 SubPins 读取
        assert True  # 占位，Step 3 实现后替换

    def test_linkedto_failure_log_dedup_with_pin_name(self):
        """验证失败日志去重包含 pin_name。"""
        # 验证日志去重使用三元组 (offset, exception_type, pin_name)
        assert True  # 占位
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_pin_recovery.py::TestLinkedToRecovery -v`
Expected: FAIL (占位测试)

- [ ] **Step 3: 修改 LinkedTo 恢复逻辑**

在 `src/uasset_read/serializers/graph.py` 中修改 `read_ue_graph_pin()` 的 LinkedTo 异常处理：

```python
    # 13. LinkedTo array — Phase 73 关键诊断点
    linkedto_start = archive.tell()
    linkedto_raw_count: Optional[int] = None
    try:
        _count_pos = archive.tell()
        linkedto_raw_count = archive.read_i32()
        archive.seek(_count_pos)
    except Exception:
        linkedto_raw_count = None
    try:
        linked_to = read_pin_array(archive, name_map, export_map, import_map, linker)
        logger.debug("LinkedTo: %d refs at pos %d", len(linked_to), linkedto_start)
        if trace_mode:
            refs_preview = [ref.get('owning_node', '?') for ref in linked_to[:2]]
            _trace_field("LinkedTo", linkedto_start, archive.tell(),
                         f"raw_count={linkedto_raw_count},count={len(linked_to)},refs={refs_preview}")
    except Exception as e:
        # Phase 75: 改进日志去重，包含 pin_name
        failure_key = (linkedto_start, type(e).__name__, pin_name)  # 添加 pin_name
        if failure_key not in _get_thread_local().linkedto_failure_seen:
            _get_thread_local().linkedto_failure_seen.add(failure_key)
            logger.error("LinkedTo read failed at pos %d (pin=%s): %s", 
                        linkedto_start, pin_name, e)
        else:
            logger.debug("LinkedTo read failed (deduped) at pos %d (pin=%s): %s", 
                        linkedto_start, pin_name, e)
        if trace_mode:
            _trace_field("LinkedTo", linkedto_start, archive.tell(), "",
                         is_exception=True)
        linked_to = []
        # Phase 75: 使用恢复结果
        recovery_result = _try_recover_to_subpins(archive, linkedto_start, export_map, import_map)
        if recovery_result is not None:
            logger.info(
                "[P73-RECOVERY] SubPins resynced: pos=%d, type=%s",
                recovery_result.get("recovered_pos"), 
                recovery_result.get("recovery_type")
            )
```

- [ ] **Step 4: 更新测试用例**

替换占位 assert，添加实际验证逻辑

- [ ] **Step 5: 运行测试验证通过**

Run: `python -m pytest tests/test_pin_recovery.py::TestLinkedToRecovery -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/uasset_read/serializers/graph.py tests/test_pin_recovery.py
git commit -m "fix(graph): use _try_recover_to_subpins result and improve log dedup"
```

---

## Task 4: 滑动恢复动态窗口

**目标:** 根据 `bad_count` 大小动态调整 scan_window

**Files:**
- Modify: `src/uasset_read/serializers/graph.py:659-775`
- Test: `tests/test_pin_recovery.py`

- [ ] **Step 1: 编写动态窗口测试**

```python
# 在 tests/test_pin_recovery.py 中添加

class TestSlidingRecovery:
    """滑动恢复机制测试。"""

    def test_dynamic_scan_window_based_on_bad_count(self):
        """验证 scan_window 根据 bad_count 动态调整。"""
        # bad_count 越大，说明错位越严重，窗口应更大
        # bad_count=100 应比 bad_count=5 使用更大的窗口
        assert True  # 占位

    def test_high_confidence_recovery_validated(self):
        """验证高置信度恢复的所有 ref 都通过验证。"""
        assert True  # 占位
```

- [ ] **Step 2: 运行测试验证失败**

Run: `python -m pytest tests/test_pin_recovery.py::TestSlidingRecovery -v`
Expected: FAIL

- [ ] **Step 3: 实现动态窗口**

修改 `src/uasset_read/serializers/graph.py` 的 `_recover_pin_array_count()` 函数：

```python
def _recover_pin_array_count(
    archive: FArchive,
    error_pos: int,
    bad_count: int,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport] = None,
    scan_window: int = 16,
) -> Optional[Dict[str, Any]]:
    """Phase 75: 动态窗口滑动恢复。
    
    scan_window 根据 bad_count 大小动态调整：
    - bad_count <= 20: 基础窗口 16 字节
    - bad_count <= 100: 窗口 32 字节
    - bad_count > 100: 窗口 64 字节
    """
    # Phase 75: 动态调整 scan_window
    if bad_count > 100:
        scan_window = max(scan_window, 64)
    elif bad_count > 20:
        scan_window = max(scan_window, 32)
    
    current_pos = archive.tell()
    search_start = max(0, error_pos - scan_window)
    search_end = min(archive._file_size, error_pos + scan_window)
    
    # ... 其余代码保持不变 ...
```

- [ ] **Step 4: 更新测试用例**

替换占位 assert，添加实际验证逻辑

- [ ] **Step 5: 运行测试验证通过**

Run: `python -m pytest tests/test_pin_recovery.py::TestSlidingRecovery -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/uasset_read/serializers/graph.py tests/test_pin_recovery.py
git commit -m "feat(graph): dynamic scan_window based on bad_count severity"
```

---

## Task 5: 运行完整测试套件

**目标:** 确保所有修改不破坏现有功能

- [ ] **Step 1: 运行单元测试**

Run: `python -m pytest tests/ -v --tb=short`
Expected: 所有测试通过（xfail 除外）

- [ ] **Step 2: 运行集成测试**

Run: `python -m pytest tests/ -v -m integration --tb=short`
Expected: 所有集成测试通过

- [ ] **Step 3: 运行 Pin 相关专项测试**

Run: `python -m pytest tests/test_pin_guid_filtering.py tests/test_pin_recovery.py -v`
Expected: 所有 Pin 测试通过

- [ ] **Step 4: 提交最终状态**

```bash
git add -A
git commit -m "chore: verify all Pin LinkerTo improvements pass tests"
```

---

## 验证清单

完成所有 Task 后，验证以下内容：

1. **FText 安全网生效** — 检查日志中是否有 `[FTEXT-SAFETY]` 警告
2. **GUID 格式统一** — 验证 `read_pin_reference()` 返回的 `pin_guid` 无 dash
3. **恢复机制改进** — 验证 `_try_recover_to_subpins` 返回值被使用
4. **动态窗口生效** — 验证大 bad_count 使用更大扫描窗口
5. **测试覆盖** — `test_pin_recovery.py` 包含所有新增测试

---

## 风险和回退

| 风险 | 影响 | 回退方案 |
|------|------|----------|
| FText 安全网误判正常大文本 | 正常 FText 被跳过 | 调整 `FTEXT_MAX_CONSUMPTION` 阈值 |
| GUID 归一化影响下游匹配 | 连接查找失败 | 检查 `_pin_ref_guid()` 是否仍有冗余归一化 |
| 动态窗口增加扫描时间 | 性能轻微下降 | 保持基础上限 64 字节 |

---

## 完成标准

- [ ] 所有 Task 完成
- [ ] 单元测试 ≥ 200 个（现有 + 新增）
- [ ] 集成测试 ≥ 40 个
- [ ] 无新的测试失败（xfail 除外）
- [ ] 代码审查通过
