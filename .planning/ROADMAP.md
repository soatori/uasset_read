# 路线图

## 里程碑

- ✅ **v7.0** — Phases 41-46 + 44a-c (shipped 2026-05-14)
- ✅ **v8.0** — Phases 47-51 (shipped 2026-05-17)
- 🔲 **v9.0** — Phases 52-55 (函数调用链解析)

## Phases

<details>
<summary>✅ v7.0 — UE FLinkerLoad 对象图重建 (SHIPPED 2026-05-14)</summary>

- [x] Phase 41: link/ 模块 (1/1 plans)
- [x] Phase 42: 集成入口 (1/1 plans)
- [x] Phase 43: PackageIndex (1/1 plans)
- [x] Phase 44: 模型增强 (1/1 plans)
- [x] Phase 44a: 移除旧版本兼容代码
- [x] Phase 44b: 替换直接字节读取
- [x] Phase 44c: 清理测试工具
- [x] Phase 45: 图序列化 linker 变体
- [x] Phase 46: 测试验证 (432 passed, 0 new failures)

详见 `.planning/milestones/v7.0-ROADMAP.md`
</details>

<details>
<summary>✅ v8.0 — BP-to-CPP 翻译能力 (SHIPPED 2026-05-17)</summary>

- [x] Phase 47: Pin LinkedTo 修复 (linked_to_raw 0/30→16/43 pins)
- [x] Phase 48: 组件属性递归解析 (components[] 含数值属性)
- [x] Phase 49: 函数调用引脚解析 (K2Node_CallFunction parameters 数组)
- [x] Phase 50: EnhancedInput 语义增强 (trigger_events 从 pins 提取)
- [x] Phase 51: 二进制输出清理 (ZERO \x00 escapes in JSON)

详见 `.planning/milestones/v8.0-ROADMAP.md`
</details>

<details>
<summary>🔲 v9.0 — 函数调用链解析 (IN PROGRESS)</summary>

- [x] Phase 52: 函数图节点解析 (2 plans) (completed 2026-05-17)
  - [x] 52-01-PLAN.md — K2NodeFunctionEntry 数据模型 + 序列化支持 + function_reference 修复
  - [x] 52-02-PLAN.md — START_EVENT_TYPES 扩展 + 执行流集成 + is_function_graph 判断
- [x] Phase 53: 函数内执行流追踪 (FunctionEntry → CallFunction 链) (2/2 plans complete 2026-05-17)
  - [x] 53-01-PLAN.md — _get_start_event_name 前缀统一 + pure function 标记
  - [x] 53-02-PLAN.md — 4 个新测试（FunctionEntry 前缀/执行流/pure/Knot）
- [x] Phase 54: 数据流追踪 (Pure 函数返回值 → 参数输入) (3/3 plans complete 2026-05-17)
  - [x] 54-01-PLAN.md — 测试基础设施（fixture + 6 个测试骨架）
  - [x] 54-02-PLAN.md — 核心追踪函数（DATA_BOUNDARY_NODES + is_boundary_node + _resolve_knot_chain）
  - [x] 54-03-PLAN.md — 数据标注增强（_trace_data_source + _extract_call_function_parameters 增强 + Pure 函数 data_providers）
- [ ] Phase 55: JSON 输出增强 (function_graphs 数组)

</details>

---

*Updated: 2026-05-17 (Phase 54-03 completed, Wave 2 done)*
