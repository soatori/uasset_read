# Phase 14: 输出格式优化并冻结 - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning
**Source:** ROADMAP.md definition + Phase 4 output decisions carry forward

<domain>
## Phase Boundary

Phase 14 专注于优化 JSON 输出格式，添加 status 字段、execution_flows 顶层化、摘要增强、Markdown 格式、字段描述，并冻结 API 供 Phase 15 skill 使用。

**输入:** ParseResult 对象（Phase 1-13 已建立完整数据）
**输出:** 优化后的 JSON/text/Markdown 格式，API 稳定冻结

**关键依赖:**
- Phase 4 输出格式决策（D-01~D-28）作为基础
- Phase 7/8 蓝图图数据（graphs 字段）
- Phase 10 依赖分析字段（imports, soft_references, circular_deps）
- Phase 12/13 变量和变换属性提取

**Requirements:** OUT-01, OUT-02, OUT-03, OUT-04, OUT-05, OUT-06

</domain>

<decisions>
## Implementation Decisions

### Status 字段设计（OUT-01）
- **D-14-01:** 三元分类 — success/fail/error，警告不算 fail
  - success: 解析成功，无错误（可有警告）
  - fail: 有解析错误但部分结果可用
  - error: 无法解析，严重错误
- **D-14-02:** JSend 完整结构 — status + message + code 字段
  - status: "success" | "fail" | "error"
  - message: 可选错误信息（fail/error 时填充）
  - code: 可选错误码（如 "PARSE_ERROR", "FILE_NOT_FOUND"）
- **D-14-03:** 顶层 status 对象位置
  ```json
  {
    "status": {
      "status": "success",
      "message": null,
      "code": null
    },
    "summary": {...},
    "exports": [...],
    ...
  }
  ```

### graphs_summary 结构（OUT-02）
- **D-14-04:** 函数调用链格式
  ```json
  "graphs_summary": [
    {
      "graph": "EventGraph",
      "execution_flows": [
        {"event": "EventBeginPlay", "calls": ["PrintString(InStr:String)", "SetLifeSpan(Lifespan:Float)"]}
      ]
    }
  ]
  ```
- **D-14-05:** 按图分组 — 每个图一个 execution_flows 条目（EventGraph, ConstructionScript 等）
- **D-14-06:** 函数名+参数类型 — 如 "PrintString(InStr:String)"，不含参数名

### 摘要精简策略（OUT-03）
- **D-14-07:** 移除依赖字段 — imports, soft_references, circular_deps, errors 详情
- **D-14-08:** 精简 exports — 仅保留 name, class, parent_class，移除 serial_size, outer_index, super_index
- **D-14-09:** 移除 properties 数组 — 摘要模式不含属性详情
- **目标:** 70%+ token 减少

### Markdown 格式设计（OUT-04）
- **D-14-10:** 三节结构 — Asset Overview / Blueprint Details / Graph Summary / Exports
- **D-14-11:** 表格优先 — exports 和属性列表用 Markdown 表格
- **D-14-12:** Mermaid 流程图 — execution_flows 用 ```mermaid 语法展示调用链
  ```mermaid
  graph LR
    EventBeginPlay --> PrintString
    PrintString --> SetLifeSpan
  ```

### 字段描述增强（OUT-05）
- **D-14-13:** 语义注释作为顶层 _schema 字段（可选）
  - _schema 包含各字段的含义说明
  - 仅在 --verbose 或 --schema 标志时输出
- **Claude's Discretion:** 注释格式（inline vs separate schema）

### 输出格式冻结（OUT-06）
- **D-14-14:** Phase 14 完成后冻结 JSON 结构
- **D-14-15:** 版本标注 — 添加 output_version: "3.0" 顶层字段
- **D-14-16:** 向后兼容承诺 — Phase 15+ 不修改核心字段结构

### CLI 扩展
- **D-14-17:** 新增 --markdown 标志（与 --json/--text/--summary 互斥）
- **D-14-18:** --summary 精简模式（移除依赖字段+properties）
- **D-14-19:** --schema 标志输出字段语义注释

### Claude's Discretion
- status.code 错误码枚举值命名
- Mermaid 图布局方向（LR vs TD）
- _schema 字段的具体内容结构
- 单元测试组织和测试资产选择

</decisions>

<canonical_refs>
## Canonical References

**Phase 4 输出决策（前置依赖）:**
- `.planning/phases/04-output-and-cli/04-CONTEXT.md` — 输出格式基础决策（D-01~D-28）
- `uasset_read.py:4916-5065` — format_json_full, format_json_summary 函数
- `uasset_read.py:5109+` — format_text_full 函数
- `uasset_read.py:5298-5327` — CLI argparse 定义

**蓝图图数据（graphs 来源）:**
- `.planning/phases/07-blueprint-graph-core/07-CONTEXT.md` — 图解析决策
- `.planning/phases/08-blueprint-graph-output/08-CONTEXT.md` — execution_flows 定义
- `uasset_read.py:4716-4915` — format_graphs_json 函数

**需求定义:**
- `.planning/REQUIREMENTS.md` — OUT-01 至 OUT-06 定义

**JSend 规范参考:**
- https://github.com/omniti-labs/jsend — JSend JSON response format specification

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **format_json_full():** 完整 JSON 输出函数，可扩展添加 status 字段
- **format_json_summary():** 精简 JSON 输出函数，可进一步精简
- **format_graphs_json():** 图数据格式化，graphs_summary 可复用其逻辑
- **CLI argparse:** 已有 --json/--text/--summary 互斥组，可添加 --markdown

### Established Patterns
- **dataclasses + asdict():** JSON 输出直接兼容
- **互斥标志组:** argparse mutually_exclusive_group 模式
- **分级输出:** Phase 4 D-01 分级输出模式可扩展

### Integration Points
- format_json_full/format_json_summary 需修改以添加 status 字段
- 新增 format_markdown() 函数实现 Markdown 输出
- graphs_summary 提取逻辑可从 format_graphs_json 衍生

</code_context>

<specifics>
## Specific Ideas

**status 对象示例:**
```json
{
  "status": {
    "status": "success",
    "message": null,
    "code": null
  },
  "output_version": "3.0",
  ...
}
```

**graphs_summary 示例:**
```json
{
  "graphs_summary": [
    {
      "graph": "EventGraph",
      "execution_flows": [
        {"event": "EventBeginPlay", "calls": ["PrintString(InStr:String)"]}
      ]
    },
    {
      "graph": "ConstructionScript",
      "execution_flows": [
        {"event": "ConstructionScript", "calls": ["SetMesh(Mesh:SkeletalMesh)"]}
      ]
    }
  ]
}
```

**Markdown 输出示例结构:**
```markdown
# Asset: BP_FirstPersonCharacter

## Asset Overview
| Field | Value |
|-------|-------|
| Package | /Game/FirstPerson/Blueprints |
| Version | UE 5.5 |

## Blueprint Details
| Field | Value |
|-------|-------|
| Parent Class | ACharacter |
| Variables | 5 (2 components, 3 regular) |

## Graph Summary
### EventGraph
```mermaid
graph LR
  EventBeginPlay --> PrintString
```

## Exports
| Name | Class | Parent |
|------|-------|--------|
| BP_FirstPersonCharacter_C | BlueprintGeneratedClass | ACharacter |
```

</specifics>

<deferred>
## Deferred Ideas

推迟到后续版本：

### v2 高级输出（OUT-07, OUT-08）
- 扁平化选项 --flat（深度嵌套资产扁平化）
- JSON Schema 文件自动生成

### MCP Server（SKILL-05, SKILL-06）
- MCP Server 封装格式输出
- MCP 错误处理集成

None for Phase 14 scope.

</deferred>

---

*Phase: 14-output-format-optimization*
*Context gathered: 2026-05-03 via discuss-phase workflow*