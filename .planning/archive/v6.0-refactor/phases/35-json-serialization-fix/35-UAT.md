---
status: testing
phase: 35-json-serialization-fix
source: [35-01-SUMMARY.md, 35-02-SUMMARY.md, 35-03-SUMMARY.md, 35-04-SUMMARY.md, 35-05-SUMMARY.md, 35-CONTEXT.md]
started: "2026-05-12T15:28:00Z"
updated: "2026-05-12T15:30:00Z"
---

## Current Test

[testing complete]

## Tests

### 1. JSON 序列化崩溃修复 (P0)
expected: |
  使用 BP_FirstPersonCharacter.uasset 测试 --json 模式：
  - `python -m uasset_read file.uasset --json` 应输出完整 JSON，exit code 0
  - `python -m uasset_read file.uasset --json | python -m json.tool` 应产生合法 JSON
  - JSON 中 StructProperty 应包含 struct_type + fields dict（而非 Python repr）
  - JSON 中 MapProperty 应包含 key_type + value_type + entries list
result: pass

### 2. 图节点类型分发 (P1)
expected: |
  解析 BP_FirstPersonCharacter.uasset 的 EventGraph：
  - 图节点应正确区分为 K2Node_Event、K2Node_CallFunction、K2Node_Knot、EdGraphNode_Comment 等具体类型
  - 不应全部识别为 UEdGraphNode 基类
  - 应至少识别出 K2Node_Event 和 K2Node_CallFunction
result: pass

### 3. 执行流和连接数据 (P1)
expected: |
  EventGraph 应包含非空的执行流和连接数据：
  - execution_flows 应为非空列表，start_event 不应为 "Unknown"
  - 至少能识别出已知的节点连接关系（如 EventBeginPlay → PrintString）
  - 如果是编译后蓝图（Ubergraph），LinkedTo=0 属于正常状态
result: issue
reported: "部分节点的 execution_flows 有 start_event='Unknown'，连接数据为空"
severity: major

### 4. Blueprint 变量提取 (P2)
expected: |
  BP_FirstPersonCharacter.uasset 的 Blueprint.variables 列表：
  - 应少于 14 个变量（排除元数据属性后应为 0 或少量用户变量）
  - 不应包含 ParentClass、BlueprintGuid、BlueprintDescription 等 UE 元数据属性
  - 如有变量，应为用户定义的属性（如 CharacterMovement）
result: pass

### 5. 循环依赖检测误报 (P3)
expected: |
  解析任何包含多个 /Script/Engine 条目的资产：
  - circular_deps 应返回空列表 []，而非误报 [pkg, pkg]
  - 原算法只是统计包出现次数，不是真正的循环检测
  - 真正的循环检测需要构建有向图 + DFS/Tarjan 算法（v7.0 范围）
result: pass

### 6. ParseResult API 一致性 (P3)
expected: |
  ParseResult 对象应具备以下属性：
  - `result.status` 可直接访问（映射三种状态：success / fail / error）
  - `result.is_success` 属性应存在
  - `build_status_info(result)` 应能正确构建 StatusInfo
  - API 文档应与实现一致
result: pass

## Summary

total: 6
passed: 5
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "EventGraph execution_flows 包含非空节点列表且 start_event 正确识别"
  status: failed
  reason: "User reported: 部分节点的 execution_flows 有 start_event='Unknown'，连接数据为空"
  severity: major
  test: 3
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""
