---
gsd_state_version: 1.0
milestone: v6.0
milestone_name: 模块化重构（阶段 28-35）— 进行中
status: executing
last_updated: "2026-05-13T01:00:00Z"
progress:
  total_phases: 33
  completed_phases: 26
  total_plans: 98
  completed_plans: 98
  percent: 95
---

# v6.0 模块化重构 — 当前状态

## 已归档（Phase 27-29）

Phase 27-29 已完成并归档到 `milestones/v6.0-ARCHIVE.md`:
- ✓ Phase 27: 项目结构初始化 (`constants.py`, `exceptions.py`)
- ✓ Phase 28: 核心序列化模块 (`FArchive`, `serializers/`)
- ✓ Phase 28a: 测试基线修复
- ✓ Phase 29: 核心数据模型 (`models/core.py`, `node_types.py`, `blueprint.py`, `result.py`)

---

## 已完成（Phase 30-35a）

### Phase 30: 属性解析模块 ✓ Complete
### Phase 31: 蓝图图解析模块 ✓ Complete
### Phase 32: 输出格式化模块 ✓ Complete
### Phase 33: 入口与测试适配 ✓ Complete
### Phase 33a: UE5 序列化问题修复 ✓ Complete
### Phase 34: 等价验证 ✓ Complete
### Phase 35a: 快速修复 ✓ Complete

---

## 当前焦点: Phase 35e — Pin Offset 根因诊断与 UE5 C++ 参考验证

**状态**: 🟢 活跃
**优先级**: P0 - 阻塞
**依赖**: 无（继承 Phase 35b 成果）
**计划**: 4 plans (0 完成)

详情见 [35e-CONTEXT.md](phases/35e-pin-offset-debug/35e-CONTEXT.md)

| Plan | 文件 | 目标 | 状态 |
|------|------|------|------|
| 35e-01 | serializers/graph.py | UE5 EdGraphPin.cpp 字段边界分析 | 待执行 |
| 35e-02 | tools/binary_trace_pin.py | 二进制跟踪增强与 pin body 映射 | 待执行 |
| 35e-03 | serializers/graph.py | Direction/FName 4 字节偏移修复 | 待执行 |
| 35e-04 | tests/ | 集成测试验证 | 待执行 |

---

## 已跳过: Phase 35b — Pin 连接深度调试与修复

**状态**: ⏭️ 已跳过（合并至 Phase 35e）
**优先级**: P0 - 阻塞（已转移）
**说明**: 35b-01~35b-03 的修复代码已合入（read_bool_ue5、BitField、FText），但 linked_to_raw 仍为空。遗留的约 4 字节偏移问题由 Phase 35e 继续解决。
**参考**: [35b-SKIP.md](phases/35b-pin-connection-debug/35b-SKIP.md), [35e-CONTEXT.md](phases/35e-pin-offset-debug/35e-CONTEXT.md)

---

## 部分完成: Phase 35c — 代码审查安全性与健壮性修复

**状态**: 🟡 部分完成
**优先级**: P1 - 高
**依赖**: 无（原依赖 Phase 35b 已跳过，不再阻塞）
**计划**: 8 plans (4 完成)

详情见 [35c-PLAN.md](phases/35c-security-fixes/35c-PLAN.md)

| Plan | 文件 | 问题 | 状态 |
|------|------|------|------|
| 35c-01 | archive.py | 文件描述符泄漏 (CR-01) | ✅ 完成 |
| 35c-02 | archive.py | FString OOM (CR-02) | 待执行 |
| 35c-03a | package_summary.py | 计数验证 (CR-04) | ✅ 完成 |
| 35c-03b | package_summary.py | 偏移验证 (M4) | 待执行 |
| 35c-03c | object_resources.py | 计数与偏移验证 (CR-05) | ✅ 完成 |
| 35c-04 | parse_uasset.py | is_success + tolerant (CR-16/17) | ✅ 完成 |
| 35c-05 | cli.py | 文件类型+异常 (HIGH-01/03) | 待执行 |
| 35c-06 | property_types.py | 条目计数验证 (HIGH-07) | ✅ 完成 |

---

## 已完成: Phase 35d — 代码审查逻辑与质量修复

**状态**: ✅ 已完成  
**优先级**: P1 - 高  
**依赖**: Phase 35b  
**计划**: 6 plans (6 完成)

详情见 [35d-PLAN.md](phases/35d-logic-fixes/35d-PLAN.md)

| Plan | 文件 | 问题 | 状态 |
|------|------|------|------|
| 35d-01 | property_types.py | 数组大小/Map类型提取/计数验证 (CR-09, MED-01) | ✅ 完成 |
| 35d-02 | variable_extractor.py | 标志映射/去重/hasattr (CR-11, LOW-04, HIGH-10) | ✅ 完成 |
| 35d-03 | models/properties.py | 模型字段默认值 (CR-13) | ✅ 完成 |
| 35d-04 | json_formatter/markdown/transform | 递归序列化/转义/KeyError (CR-14/15, HIGH-17/09) | ✅ 完成 |
| 35d-05 | flow_builder.py | 安全迭代 + GUID 检查 (LOW-06/07) | ✅ 完成 |
| 35d-06 | constants/property_parser/property_types | 重复常量/死代码/重复函数 (MED-14, HIGH-08) | ✅ 完成 |

---

## v6.0 范围边界

- **包含**: 等价迁移 + 代码审查修复
- **不包含**: BulkData 解析 (v7.0)、UberGraph 增强 (v8.0)、字节码反编译 (v8.0)、.umap 解析 (v9.0)
