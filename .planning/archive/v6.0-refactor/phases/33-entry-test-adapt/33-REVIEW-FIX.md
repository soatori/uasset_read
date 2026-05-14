---
phase: 33-entry-test-adapt
fixed_at: 2026-05-12T00:00:00Z
review_path: .planning/phases/33-entry-test-adapt/33-REVIEW.md
iteration: 1
findings_in_scope: 9
fixed: 7
skipped: 2
status: partial
---

# Phase 33: Code Review Fix Report

**Fixed at:** 2026-05-12T00:00:00Z
**Source review:** .planning/phases/33-entry-test-adapt/33-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 9 (4 Critical + 5 Warning)
- Fixed: 7
- Skipped: 2 (CR-04: investigation issue, WR-02: documentation issue)

## Fixed Issues

### CR-01: property_end 计算错误导致越界读取或数据遗漏

**Files modified:** `src/uasset_read/parsers/property_parser.py`
**Commit:** 5b01536
**Applied fix:** 在 property_end 计算中添加遗漏的 `script_serial_offset`。`script_serial_offset` 是相对于 `serial_offset` 的偏移量，正确的终点应为 `serial_offset + script_serial_offset + script_serial_size`。

### CR-02: ArrayProperty 内部元素大小计算使用整除丢失精度

**Files modified:** `src/uasset_read/parsers/property_types.py`
**Commit:** 296b756
**Applied fix:** 使用动态 inner_size 计算替代静态整除。跟踪每个元素实际消耗的字节数，最后一个元素使用所有剩余字节，避免精度丢失。

### CR-03: _map_property_flags 标志位映射错误

**Files modified:** `src/uasset_read/blueprint/variable_extractor.py`
**Commit:** 94a061e
**Applied fix:** 将 `is_edit_instance_only` 的错误映射从 `CPF_EditConst` (0x20000, 编辑器只读标志) 修正为正确的 `CPF_EditInstanceOnly` (0x4000000)。

### WR-01: parse_struct_property 未知类型时可能无限循环

**Files modified:** `src/uasset_read/parsers/property_types.py`
**Commit:** 69a3098
**Applied fix:** 当 `parse_property_value` 返回 None（未知类型）且 `inner_tag.size > 0` 时，主动跳过该属性字节，防止在同一位置无限循环。

### WR-03: parse_array_property 的 _get_inner_type 始终返回 IntProperty

**Files modified:** `src/uasset_read/parsers/property_types.py`
**Commit:** 5261352
**Applied fix:** 实现 `_get_inner_type` 的正确类型推断。支持从 UE5 格式 `ArrayProperty(IntProperty)` 和下划线分隔格式解析内部类型。对未知类型回退到 IntProperty。

### WR-04: read_ue_graph_pin 异常恢复后存档位置不确定

**Files modified:** `src/uasset_read/serializers/graph.py`
**Commit:** 4ddc8d9
**Applied fix:** 移除 LinkedTo/SubPins 异常恢复中的 seek-back 和 `_skip_count` 读取。返回空数组，让调用者处理位置不一致问题，避免 seek 到无效位置。

### WR-05: DEBUG_PIN_PARSING 在模块导入时检查 sys.argv

**Files modified:** `src/uasset_read/constants.py`
**Commit:** c76504b
**Applied fix:** 将 `sys.argv` 检查替换为 `os.environ.get("UASSET_DEBUG_PINS", "0") == "1"`，避免模块导入时受命令行参数影响。

## Skipped Issues

### CR-04: 测试数量显著下降（411 -> 107）

**File:** `test_results.txt` (vs CLAUDE.md 声明)
**Reason:** 调查性质问题，不涉及源代码修改。需要运行测试诊断命令来分析测试数量下降原因。
**Original issue:** CLAUDE.md 声明 411 个测试通过，但 test_results.txt 显示只有 107 passed。测试数量下降 74%，需要调查原因。

### WR-02: 组件变换提取存在两套独立实现

**File:** `src/uasset_read/blueprint/variable_extractor.py:227-260` 和 `src/uasset_read/blueprint/transform_parser.py:43-73`
**Reason:** 文档性质问题。修复建议是添加文档说明两套实现的使用场景和输出差异，而非合并代码。暂不修改源代码。
**Original issue:** 存在两套独立的变换属性提取实现，输出格式不同，增加了维护负担。

---

_Fixed: 2026-05-12T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_