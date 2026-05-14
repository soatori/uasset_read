# Phase 35a: 快速修复（UAT 收尾项）

**里程碑**: v6.0 模块化重构（最终收尾）
**创建日期**: 2026-05-12
**依赖**: Phase 35 (JSON 序列化与图解析修复)
**状态**: 规划中

## 一句话摘要

修复 AUDIT-REPORT.md 中标识的可自动清理项和 Phase 35 UAT 遗留的小问题，无需深入二进制调试。

## 问题来源

`.planning/AUDIT-REPORT.md` + Phase 35 UAT Test 3 已知 issue

## 问题清单（按优先级）

| # | 优先级 | 问题 | 影响模块 | 严重程度 |
|---|--------|------|----------|----------|
| 1 | P1 | execution_flows start_event='Unknown' 改善（非根因修复，仅改善 fallback 逻辑） | graph/flow_builder.py | 🟠 严重 |
| 2 | P2 | 10 个 debug/test 脚本散落在项目根目录 | 工作目录 | 🟡 中等 |
| 3 | P3 | DEBUG_PIN_PARSING print 改为 logging 模块 | serializers/graph.py | 🟢 轻微 |

## 成功标准

1. execution_flows 的 start_event 不再显示 "Unknown"（改善 fallback 识别逻辑）
2. 10 个 debug/test 脚本已移至 `tools/` 目录或加入 `.gitignore`
3. `DEBUG_PIN_PARSING` 相关的 `print()` 替换为 Python `logging` 模块
4. 全部现有测试通过（397+ passed, 0 failed）

## 范围边界

- ✅ 改善 start_event fallback 识别逻辑（不修复 pin 连接根因）
- ✅ 清理工作目录中的调试脚本
- ✅ 将调试输出从 print 迁移到 logging
- ❌ 不修复 pin linked_to_raw 为空的根因（属于 Phase 35b）
- ❌ 不修改 UE5 序列化解析逻辑

## 验收标准 (UAT)

| 测试项 | 期望结果 |
|--------|----------|
| `uasset-read BP_FirstPersonCharacter.uasset --json` | execution_flows 中 start_event 不再为 "Unknown"（至少显示节点类型名） |
| git status | 无 debug_*.py / test_*.py 散落文件 |
| grep -rn "DEBUG_PIN_PARSING.*print" src/ | 无匹配（已全部替换为 logging） |
| pytest tests/ | 397+ passed, 0 failed |

## 计划分解

| Plan | 内容 |
|------|------|
| 35a-01 | execution_flows start_event fallback 改善 |
| 35a-02 | 清理 debug/test 脚本（移至 tools/ + .gitignore） |
| 35a-03 | DEBUG_PIN_PARSING print → logging 迁移 |
