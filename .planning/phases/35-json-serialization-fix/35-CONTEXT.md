# Phase 35: JSON 序列化与图解析修复

**里程碑**: v6.0 模块化重构（最终阶段）
**创建日期**: 2026-05-12
**依赖**: Phase 33 (入口与测试适配), Phase 34 (等价验证)
**状态**: 规划中

## 一句话摘要

修复 v6.0 真实资产测试（BP_FirstPersonCharacter.uasset）中发现的 6 个问题，完成 v6.0 收尾。

## 问题来源

对 `BP_FirstPersonCharacter.uasset`（UE5 官方 FirstPerson 示例蓝图）进行全格式解析测试后生成的报告：`BP_FirstPersonCharacter_解析报告.md`

## 问题清单（按优先级）

| # | 优先级 | 问题 | 影响模块 | 严重程度 |
|---|--------|------|----------|----------|
| 1 | P0 | `--json` 模式 StructValue/MapValue 序列化崩溃 | formatters/json_formatter.py | 🔴 阻塞 |
| 2 | P1 | 图节点类型全部识别为 UEdGraphNode 基类 | graph/parser.py, serializers/graph.py | 🟠 严重 |
| 3 | P1 | 执行流和连接数据全部为空 | graph/flows.py, graph/parser.py | 🟠 严重 |
| 4 | P2 | Blueprint 变量提取混杂资产元数据属性 | blueprint/variable_extractor.py | 🟡 中等 |
| 5 | P3 | 循环依赖检测误报（包自引用） | parse_uasset.py | 🟢 轻微 |
| 6 | P3 | ParseResult 无 status 属性（API 不一致） | models/core.py | 🟢 轻微 |

## 成功标准

1. `--json` 模式对 BP_FirstPersonCharacter.uasset 输出完整 JSON，无异常
2. 图节点能正确区分为 K2Node_Event、K2Node_CallFunction、K2Node_Knot 等具体类型
3. EventGraph 的执行流和连接数据非空（至少能识别出已知的节点连接关系）
4. Blueprint 变量只包含用户定义的变量，不含 Blueprint 元数据属性
5. circular_deps 不再报告包自引用
6. `result.is_success` 和 `build_status_info(result)` 均可用，API 文档一致
7. 全部现有测试通过（397+ passed, 0 failed）

## 范围边界

- ✅ 修复现有功能的 bug 和数据质量问题
- ❌ 不新增解析能力（那是 v7.0 的范畴）
- ❌ 不解析 BulkData / 字节码 / UberGraph 增强
- ❌ 不引入新模块或新依赖

## 验收标准 (UAT)

使用 BP_FirstPersonCharacter.uasset 作为测试资产：

| 测试项 | 期望结果 |
|--------|----------|
| `uasset-read file.uasset --json` | 输出完整 JSON，exit code 0 |
| `uasset-read file.uasset --json \| python -m json.tool` | 合法 JSON，可被解析 |
| JSON 中包含 StructProperty | struct_type + fields dict，非 Python repr |
| JSON 中包含 MapProperty | key_type + value_type + entries list |
| 图节点类型 | 至少识别出 K2Node_Event 和 K2Node_CallFunction |
| EventGraph 执行流 | 非空列表，start_event 非 "Unknown" |
| Blueprint 变量数 | 少于 14（排除元数据属性后应为 0 或少量用户变量） |
| circular_deps | 空列表或不包含包自引用 |
| 全测试 | 397+ passed, 0 failed |
