---
name: source-audit
description: UE 源码对照与审计——研究 UE 序列化逻辑、审查解析器实现、蓝图与 C++ 对照、MCP 数据对比。当用户提到"UE 源码""序列化逻辑""源码审计""字段对照""蓝图对照""MCP 对比""少读字节""偏移错位""序列化审计""字段顺序""operator<<"时触发。
---

# Source Audit Skill

根据用户意图加载对应子文档执行。输出通常为审计报告或对比报告，保存到 `temp/` 目录。

## 路由

| 关键词 | 子文档 | 说明 |
|--------|--------|------|
| UE 源码、序列化逻辑、FProperty、怎么序列化、operator<< | [ue-source-research.md](references/ue-source-research.md) | 快速定位 UE 序列化源码 |
| 源码审计、逐字段对照、少读多读、偏移错位、序列化审计、字段顺序 | [ue-source-audit.md](references/ue-source-audit.md) | 系统性审计解析器 vs UE 源码 |
| 蓝图对照、C++ 对照、三方对比、解析结果验证 | [bp-cpp-comparison.md](references/bp-cpp-comparison.md) | 解析器 vs MCP vs C++ 三方对照 |
| MCP 对比、Editor 数据、批量对比、匹配率 | [mcp-comparison.md](references/mcp-comparison.md) | 解析器 vs MCP 批量对比 |

## 使用方式

1. 根据上表匹配用户意图
2. 使用 Read 工具加载对应子文档
3. 按子文档指令执行
