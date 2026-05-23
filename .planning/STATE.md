---
gsd_state_version: 1.2
milestone: v13.0
milestone_name: — Pin 连接修复 + Kismet 字节码导航 + FName/FString 区分
status: active
last_updated: "2026-05-24T12:00:00.000Z"
prev_milestone: v12.0 (archived 2026-05-22)
progress:
  total_phases: 9
  completed_phases: 5
  skipped_phases: 0
  total_plans: 6
  completed_plans: 5
  percent: 89
---

# v13.0 — Pin 连接修复 + Kismet 字节码导航 + FName/FString 区分

**Started:** 2026-05-23
**Status:** Active — Phase 72-A ✅, 72-B ✅, 72-C ✅, 72-D ✅, 72-UAT ✅, 72-E ✅, 72-F ✅, 72-G ✅, 72-H 🔴 插入中, 72-I ✅

## Phase 分解

| Phase | Name | Goal | Requirements | Status |
|-------|------|------|--------------|--------|
| 72 | Pin 连接修复 + Kismet 字节码导航 + FName/FString 区分 | 完整 Pin 序列化 + 字节码导航 + 类型区分 | PIN-01/02/03 | 🔄 Active |

## 当前状态

**当前阶段:** Phase 72-I ✅ (完成于 2026-05-24) | **下一阶段:** Phase 72-H (FString 容错 + LinkedTo 恢复 + StructValue JSON，已部分合并至 72-I)
**Phase 72-A 完成:** 2026-05-23 — 2 bugs 定位 (history_type signed / ParentPin conditional read)
**Phase 72-B 完成:** 2026-05-23 — 2 bugs 修复 + 762 tests passed
**Phase 72-C 完成:** 2026-05-23 — BPGC bytecode extraction module + pipeline fallback integration
**Phase 72-D 完成:** 2026-05-23 — null_ratio 启发式替换为 null-termination 验证 + 20 tests
**Phase 72-UAT 完成:** 2026-05-23 — 1339 tests passed, 0 issues found

## v13.0 完成度

| 版本 | 范围 | 日期 | 状态 |
|------|------|------|------|
| v13.0 P72-A | Pin 连接诊断 ✅ | 2026-05-23 | ✅ Complete |
| v13.0 P72-B | Pin 连接修复 ✅ | 2026-05-23 | ✅ Complete |
| v13.0 P72-C | Kismet 字节码导航 ✅ | 2026-05-23 | ✅ Complete |
| v13.0 P72-UAT | UAT 验证 ✅ | 2026-05-23 | ✅ Complete |
| v13.0 P72-D | FString/FName 区分 ✅ | 2026-05-23 | ✅ Complete |
| v13.0 P72-E | EventGraph 节点解析修复 | 已完成 | ✅ Complete |
| v13.0 P72-F | BPGC 缓存隔离修复 | 完成 | ✅ Complete |
| v13.0 P72-G | 复杂 StructProperty + Pin 连接映射修复 | 完成 | ✅ Complete |
| v13.0 P72-I | BP_FirstPersonCharacter 全量对比修复 | 2026-05-24 | ✅ Complete |

## Phase 72 详细进度

### Phase 72-A: Pin 连接二进制诊断 ✅

**完成日期:** 2026-05-23

| # | Bug | 位置 | 根因 | 修复策略 |
|---|-----|------|------|---------|
| 1 | `history_type` 无符号/有符号不匹配 | `graph.py` L398, L449 | `read_u8()` 返回 255，UE 意图是 -1（None） | 入口处 `if history_type >= 128: history_type -= 256` |
| 2 | ParentPin 总是读 24 字节 | `graph.py` L476-479 | `null != 0` 时应只读 8B | 条件读取：null != 0 → 8B, null == 0 → 24B |

**二进制证据（K2Node_Knot_1 pin 0, body at 132477）:**
- 修复 Bug 1 → `LinkedTo count=1, owning=57, valid GUID` ✅
- 修复 Bug 1+2 → `RefPassThrough null=0, BitField=0x52935405` ✅

### Phase 72-B: Pin 连接修复 ✅

**修复内容:** `serializers/graph.py` — L398/L449 history_type signed 转换 + L476-479 ParentPin 条件读取

**测试结果:** 762 passed, 77 skipped, 1 pre-existing failure (Phase 71 deprecation)

**验收:** `72-01-UAT.md` — 4/4 tests pass

### Phase 72-C: Kismet 字节码导航 (BPGC Fallback) ✅

**完成日期:** 2026-05-23

**新增模块:** `src/uasset_read/kismet/bpgc_bytecode.py` (295 lines)

**新增 API:**
- `extract_bpgc_bytecode()` — 从 BPGC script_serial_region 提取字节码
- `map_bytecode_to_functions()` — 按 ordinal 映射字节码到 Function 导出
- `_parse_cooked_bytecode_buffer()` — 纯函数解析烘焙格式缓冲区

**管线集成:**
- `bytecode_extractor.py` — 添加 BPGC fallback + 模块级缓存
- `pipeline.py` — 添加 cache reset
- `kismet/__init__.py` — 导出新 API

**Bug 修复:**
- `object_resources.py` — `detect_blueprint_generated_class()` 使用 `object_name` 而非 `class_name`

**测试结果:** 5 passed, 3 skipped (integration), 28 passed (existing kismet tests regression)

**验收:** `72c-01-SUMMARY.md`, `72c-02-SUMMARY.md` — 所有标准满足

### Phase 72-D: FString/FName 区分

**根因:** 属性值中的 FName 索引区域被误作 FString 读取，35 处返回空字符串。

**状态:** ⬜ Not Started — 未实施，安排在 future iteration

**修复策略 (pending):**
- 区分 FName index 区域（通常是 NameMap 大小范围内的小整数）
- 在 property value extractor 中添加 FName 专用解析路径
- 更新 `serializers/property_types.py` `parse_struct_property()` 以处理 FName indices

### Phase 72-E: EventGraph 节点解析修复

**插入日期:** 2026-05-23

**根因 (待诊断):**
- EventGraph 节点读取循环存在跳过/遗漏条件
- FMemberReference 序列化逻辑中 member_name 解析异常
- K2Node_Event 解析路径存在未处理的边界情况

**目标:** EventGraph 解析覆盖率从 ~56% 提升至 >90%

### Phase 72-F: BPGC 缓存隔离修复 ✅

**完成日期:** 2026-05-23

**修复内容:** `parse_uasset.py` — `_extract_kismet_decompiled()` 添加 `reset_bpgc_cache()` 调用

**根因:** 连续 `parse_uasset(file_A)` + `parse_uasset(file_B)` 共享 `_bpgc_bytecode_cache` 全局状态，导致 file_B 读取 file_A 的缓存数据。

**测试:** 2 新增测试 passed, 5 现有 BPGC 测试无回归

**验收:** `72f-01-SUMMARY.md` — 所有标准满足

### Phase 72-G: 复杂 StructProperty 解析 + Pin 连接映射修复 (INSERTED)

**插入日期:** 2026-05-23

**状态:** ✅ 完成 — 4 个 wave 执行，21 新测试，1330 回归通过

**反复失败问题清单:**

| # | 问题 | 反复失败历史 |
|---|------|-------------|
| 1 | Complex StructProperty 解析失败 | Phase 67 修复 → 仍失败 |
| 2 | Pin 连接映射输出为空 (Connections=0) | Phase 72-B 修复 → 仍未输出 |
| 3 | Blueprint.functions 列表为空 | 从未修复 |
| 4 | 函数参数信息缺失 | 从未修复 |

**目标:** 解析覆盖率从 ~56% 提升至 >90%

### Phase 72-H: FString 容错 + LinkedTo 恢复 + StructValue JSON 递归序列化 (INSERTED)

**插入日期:** 2026-05-23

**状态:** 🔴 Planned — 计划已创建，待执行

**三个核心问题:**

| # | 问题 | 文件 | 优先级 |
|---|------|------|--------|
| 1 | FString 内部 null 字节导致偏移错位 | `archive.py` read_fstring() | P0 |
| 2 | LinkedTo 数组 count 异常崩溃 | `serializers/graph.py` read_pin_array() | P2 |
| 3 | StructValue JSON 序列化崩溃 | `formatters/json_formatter.py` serialize_property_value() | P1 |

**执行计划:** `.planning/phases/phase-72h/PLAN.md`


## 测试统计

| Category | Count |
|----------|-------|
| Total tests collected | 1463 |
| Passed | 1339 |
| Skipped | 122 |
| XPassed (unexpected pass) | 2 |
| Warnings | 107 |

**Phase 72-specific:** 787 tests (762 from 72-B + 5 from 72-C + 20 from 72-D)

## Gaps

| Gap | Impact | Priority |
|-----|--------|----------|
| Phase 72-D FString/FName 区分 | 35 处空字符串误报 (Phase 51 warning only) | Medium — future iteration |
| Phase 72-E EventGraph 节点解析 | EventGraph 覆盖率 ~56%，函数名解析为 None | High — urgent insertion |
| Phase 72-F BPGC 缓存隔离 | 多文件 parse_uasset() 缓存串扰 | High — blocker from audit |
| Phase 72-H FString/LinkedTo/JSON 修复 | BP_FirstPersonCharacter 解析阻断 | High — 本次插入 |
| Phase 72-I BP_FirstPersonCharacter 全量对比修复 | 12 项解析错误（Pin 连接丢失、EnhancedInputAction 缺失、Rotation 全零等） | High — 三方对比驱动 |
| Cooked UE5 Blueprint integration test | BPGC fallback logic verified, real cooked asset testing deferred | Low — production deployment |

## 下一步行动

1. **Phase 72-I 执行:** BP_FirstPersonCharacter 全量对比修复（12 项解析错误，参考文档精确值验证）
2. **Phase 72-UAT 归档:** ✅ 完成 — 报告已创建 `phases/phase-72/72-UAT.md`
3. **Phase 72归档:** 准备归档 Phase 72 (v13.0 milestone 完成)
4. **Phase 72-D:** 实施 FString/FName 区分修复（安排在 future iteration）
5. **Phase 72-E (INSERTED):** EventGraph 节点解析修复 — 基于三方对比报告插入的紧急修复
6. **Phase 72-F (INSERTED):** BPGC 缓存隔离修复 — 审计发现的阻塞级集成缺陷

---

*Updated: 2026-05-24 (Phase 72-I inserted: BP_FirstPersonCharacter 全量对比修复)*
