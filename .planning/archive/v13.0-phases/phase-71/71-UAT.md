---
status: complete
phase: 71-execution-chain-expression
source: [71-01-SUMMARY.md]
started: 2026-05-23T00:00:00Z
updated: 2026-05-23T00:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. build_execution_chains() API 可用
expected: import 成功，返回 [{"start_event": "...", "chains": ["N->N"], "has_cycle": bool}]
result: pass

### 2. JSON 输出 execution_chains 替代 execution_flows
expected: format_json_full() 输出包含 execution_chains 字段，不再包含 execution_flows
result: pass

### 3. Text formatter 展示链式字符串
expected: text 格式输出中执行流展示为 "N1->N2->N3" 格式，而非逐对连接
result: pass

### 4. Markdown formatter 从 chains 生成 mermaid
expected: markdown 输出中 mermaid flowchart 从 chains 字符串正确解析边
result: pass

### 5. build_execution_flows() deprecated 但可用
expected: 调用 build_execution_flows() 触发 DeprecationWarning，返回格式不变
result: pass

### 6. N2C serializer import 重定向
expected: n2c/serializer.py 从 graph.chain_builder 导入，而非 n2c.flow_extractor
result: pass

### 7. build_function_graphs() 输出一致
expected: execution_chains + nodes 数组同时存在于输出中
result: pass

### 8. 全量测试 0 regression
expected: pytest 全量测试通过（SUMMARY 报告 1290 tests passed）
result: pass

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

