# Phase 34: 等价验证报告

**验证日期:** 2026-05-26
**测试资产数:** 3
**总差异数:** 0

## 差异分类

## 结论
- **0 个有意改进** — 新版行为更正确
- **0 个已知差异** — 设计决策导致的结构变化
- **0 个其他差异** — 需人工审查

## 已知差异表

| # | Category | Description | Severity |
|---|----------|-------------|----------|
| 1 | top_level_keys | imports/soft_references/circular_deps 移除 | known |
| 2 | status | blueprint parent 检测修复 | improvement |
| 3 | graphs_summary_keys | 2键→8键扩展 | improvement |
| 4 | ObjectProperty_value | dict→int 格式变化 | diff (需审查) |
| 5 | execution_flows_format | event型→node型 | diff (需审查) |
| 6 | execution_flows_count | 7→4 数量变化 | diff (需审查) |
| 7 | mermaid_missing | mermaid 图表缺失 | bug |
| 8 | parent_class_str | str(dict) bug | bug |
| 9 | json_full_crash | 两版都崩溃 | known |