# Feature Landscape: Skill输出格式优化

**Domain:** AI工具输出格式设计
**Researched:** 2026-05-02
**Context:** v3.0里程碑需求之一，优化输出格式使AI更易理解

## Table Stakes

AI agents期望的基本功能。缺失会使输出难以理解或使用。

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| JSON输出 | AI原生理解，机器解析首选 | Low | v1.0已实现，需优化结构 |
| 明确的类型标注 | AI需要理解字段含义和数据类型 | Low | 添加schema/类型文档 |
| 错误处理状态 | AI需要知道解析成功或失败及原因 | Low | JSend style: status字段 |
| 层次结构清晰 | Package→Exports→Properties三层易懂 | Medium | 当前已实现，需验证命名一致性 |
| 引用解析 | FPackageIndex→对象名称，AI无需反向查找 | Medium | v2.0已实现，需优化null处理 |

## Differentiators

提升AI理解效率和准确性的功能。非必需但高价值。

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Markdown输出 | 人类+AI双重友好，token效率高 | Medium | 适合文档、代码注释场景 |
| 摘要模式 | 减少70%+ token，AI快速获取关键信息 | Low | `--summary`标志，仅输出元数据 |
| 执行流可视化 | Event→CallFunction链路直接阅读 | Medium | v2.0已实现execution_flows，需优化格式 |
| Schema定义 | AI自动理解结构，无需猜测字段 | Medium | JSON Schema或TypeScript定义 |
| 扁平化选项 | 深度嵌套→浅层结构，减少认知负担 | Medium | 可选`--flat`标志 |
| 自然语言注释 | 关键字段添加语义说明 | Low | 如`"parent_class": "/Game/Character" # 父类路径` |

## Anti-Features

明确不应该实现的输出格式。

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| 深度嵌套（>5层） | AI解析困难，token浪费，易出错 | 扁平化结构或引用ID |
| 二进制格式输出 | AI无法直接理解，需二次转换 | 仅JSON/Markdown/YAML文本格式 |
| 无类型的自由文本 | AI需猜测结构，不确定性高 | 结构化对象，明确字段名 |
| 完整字节转储 | Token消耗巨大，AI难以处理 | 仅输出解析后的语义数据 |
| 依赖外部schema文件 | 增加AI理解成本，需额外查找 | 内嵌schema或自解释结构 |

## Feature Dependencies

```
JSON输出 → Schema定义 (schema需匹配JSON结构)
JSON输出 → 扁平化选项 (扁平化基于JSON结构)
引用解析 → 层次结构清晰 (引用解析依赖层次命名)
执行流可视化 → Markdown输出 (Markdown可包含执行流文本图表)
错误处理状态 → 所有输出格式 (status是顶层字段)
```

## Current Output Format Analysis

### v2.0 JSON结构（from test_output_formatting.py）

```json
{
  "summary": {...},
  "exports": [...],
  "blueprint_metadata": {...},
  "graphs": [...],
  "errors": [...]
}
```

**优点：**
- 层次清晰（Package→Exports→Properties）
- graphs顶层字段（与blueprint同级）
- 引用已解析（FPackageIndex→对象名）

**待优化：**
- 缺少status字段（AI需检查errors判断成功）
- execution_flows在graphs内，不够显眼
- 无schema定义，AI需猜测字段含义
- 深度嵌套（properties数组在export内）

### v2.0文本输出（YAML风格）

```yaml
Package: /Game/Test
Blueprint:
  Parent: Character
Graphs:
  - Name: EventGraph
    Nodes: 2
    Connections: 1
```

**优点：**
- 人类友好，AI可理解
- 简洁，token效率高
- 层次明确

**待优化：**
- 无JSON Schema对应
- 缺少执行流可视化
- 不适合程序化处理

## Output Format Best Practices (Research Findings)

### 1. JSON vs Markdown对比

| Criterion | JSON | Markdown | Recommendation |
|-----------|------|----------|----------------|
| AI解析速度 | 快（原生） | 中（需转换） | JSON主输出，Markdown辅助 |
| Token效率 | 低（结构冗余） | 高（简洁） | 摘要用Markdown，详细用JSON |
| 人类可读性 | 低 | 高 | Markdown用于文档/调试 |
| Schema验证 | 支持 | 不支持 | JSON需schema |
| 机器处理 | 直接 | 需解析 | JSON为程序化首选 |

**结论：JSON为主，Markdown为辅。提供两种格式选项。**

Sources:
- WebSearch: "JSON vs Markdown format AI readability comparison" (LOW confidence - single source)
- WebSearch: "markdown vs JSON for machine reading automated parsing" (MEDIUM confidence - verified with tool comparison)

### 2. JSend响应格式规范

```json
{
  "status": "success",  // 或 "fail" 或 "error"
  "data": { ... },      // 成功时数据
  "message": "...",     // 错误时消息
  "errors": [...]       // 详细错误列表
}
```

**应用：**
- 添加顶层`status`字段：`"success"/"fail"/"error"`
- AI一眼判断解析结果
- 符合API响应最佳实践

Sources:
- JSend specification (https://github.com/omniti-labs/jsend) - HIGH confidence
- WebSearch: "JSON API response design patterns" - MEDIUM confidence

### 3. JSONAPI规范（复杂资产）

适用于包含依赖关系的复杂输出：

```json
{
  "data": [...],
  "included": [...],  // 关联资源
  "meta": {...},      // 元数据
  "links": {...}      // 导航
}
```

**应用场景：**
- ImportMap + ExportMap关联
- 依赖图输出
- 未来扩展（多资产批量）

Sources:
- JSONAPI specification (https://jsonapi.org/) - HIGH confidence
- WebSearch: "JSON API response format JSON schema validation" - MEDIUM confidence

### 4. 扁平化嵌套结构

**原则：**
- 深度≤3层为佳
- >5层应扁平化或使用引用ID
- 展平策略：`parent.child.field` → `parent_child_field`

**示例：**

```json
// 嵌套（5层）
{
  "exports": [{
    "properties": [{
      "value": {
        "struct": {
          "field": 123
        }
      }
    }]
  }]
}

// 扁平化（3层）
{
  "exports": [{
    "properties": [{
      "name": "Health",
      "type": "StructProperty",
      "value_flat": "Struct.field=123"  // 简化表示
    }]
  }]
}
```

Sources:
- WebSearch: "flatten nested JSON structure LLM readability" - LOW confidence (need verification)
- WebSearch: "API response format JSON design hierarchy nested data" - MEDIUM confidence

### 5. Pydantic BaseModel最佳实践

**LangChain/LLM工具模式：**

```python
from pydantic import BaseModel, Field

class BlueprintOutput(BaseModel):
    """Blueprint解析结果，供AI agent理解"""
    
    status: str = Field(description="解析状态: success/fail/error")
    parent_class: str = Field(description="蓝图父类路径")
    variables: List[Variable] = Field(description="蓝图变量列表")
    
    class Config:
        # 生成schema供AI理解
        schema_extra = {
            "examples": [{
                "status": "success",
                "parent_class": "/Game/Character",
                "variables": [{"name": "Health", "type": "int"}]
            }]
        }
```

**应用：**
- ParseResult添加Field描述
- 生成JSON Schema供AI参考
- 保持dataclass兼容（当前实现）

Sources:
- WebSearch: "Pydantic BaseModel JSON output Python LLM" - LOW confidence
- WebSearch: "LangChain output parser structured output" - LOW confidence (connection error)

### 6. Schema定义策略

**选项：**

| Approach | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| JSON Schema | 标准、验证支持 | 文件大、复杂 | 用于API文档 |
| TypeScript定义 | 简洁、IDE友好 | 非标准 | 用于AI理解 |
| 内嵌文档 | 无需外部文件 | 增加token | 用于CLI输出 |
| Field描述 | 自解释 | 需Pydantic | 最佳实践 |

**推荐：混合策略**
- JSON Schema（可选文件）：完整结构定义
- Field描述（内嵌）：关键字段语义
- TypeScript定义（文档）：开发者参考

Sources:
- WebSearch: "JSON schema validation LLM output" - LOW confidence (need deeper research)
- WebSearch: "output format design for AI readability" - MEDIUM confidence

### 7. 自然语言注释

**Python JSON注释模式：**

```python
# 方案1：内嵌注释字段
{
  "parent_class": "/Game/Character",
  "_comment_parent_class": "蓝图继承的父类路径"
}

# 方案2：schema字段
{
  "parent_class": {
    "value": "/Game/Character",
    "description": "蓝图继承的父类路径"
  }
}

# 方案3：Markdown混合
```json
{
  "parent_class": "/Game/Character"  // 蓝图父类
}
```
```

**推荐：方案2（schema字段）用于关键信息，方案1（注释字段）用于摘要。**

Sources:
- WebSearch: "AI agent readable output format" - LOW confidence (need verification)

## MVP Recommendation

**优先级排序（基于AI易用性）：**

1. **添加status字段（P0）** - AI一眼判断成功/失败
   - 实现难度：Low
   - 影响：所有输出格式
   - 代码：<5行改动

2. **优化execution_flows位置（P0）** - 提升至顶层或显眼位置
   - 实现难度：Low
   - 影响：蓝图图解析输出
   - 当前：graphs[].execution_flows
   - 建议：顶层execution_flows或graphs_summary

3. **添加摘要模式增强（P1）** - 减少token 70%+
   - 实现难度：Low
   - 当前：--summary标志存在
   - 建议：添加关键注释字段

4. **添加Field描述（P1）** - Pydantic/BaseModel描述
   - 实现难度：Medium
   - 需dataclass→Pydantic迁移（可选）
   - 或保持dataclass添加手动描述

5. **Markdown输出格式（P2）** - 人类+AI双重友好
   - 实现难度：Medium
   - 当前：YAML风格文本
   - 建议：添加纯Markdown选项

6. **扁平化选项（P2）** - 深度嵌套资产优化
   - 实现难度：Medium
   - 添加--flat标志
   - 展平properties/struct嵌套

**推迟：**
- **JSON Schema文件生成**：非v3.0必需，可后续文档化
- **多资产批量输出**：超出v3.0范围
- **TypeScript定义生成**：次要，可文档化

## Output Format Examples

### Example 1: Optimized JSON（推荐）

```json
{
  "status": "success",
  "package": "/Game/Blueprints/BP_Character",
  
  "blueprint": {
    "parent_class": "/Game/Core/Character",  // 父类路径
    "variables": [
      {
        "name": "Health",
        "type": "int",
        "default": 100,
        "category": "Replicated"
      }
    ]
  },
  
  "graphs_summary": {
    "count": 1,
    "execution_flows": [
      {
        "start_event": "BeginPlay",
        "chain": ["Event→PrintString→SetHealth"],
        "nodes_count": 3
      }
    ]
  },
  
  "exports_count": 5,
  "errors": []
}
```

### Example 2: Markdown Summary（推荐）

```markdown
# Blueprint: BP_Character

## Metadata
- Parent: /Game/Core/Character
- Variables: 3 (Health, Damage, Speed)

## Execution Flows
- BeginPlay → PrintString → SetHealth (3 nodes)

## Status
✓ Success | Exports: 5 | Errors: 0
```

### Example 3: Flat JSON（可选）

```json
{
  "status": "success",
  "blueprint_parent_class": "/Game/Character",
  "blueprint_var_count": 3,
  "blueprint_vars": "Health(int), Damage(float), Speed(float)",
  "graphs_count": 1,
  "graphs_main_flow": "BeginPlay→PrintString→SetHealth",
  "exports_count": 5
}
```

## Implementation Complexity Estimate

| Feature | Lines of Code | Time | Dependencies |
|---------|--------------|------|--------------|
| status字段 | 5 | 10min | 无 |
| execution_flows位置 | 20 | 30min | 无 |
| Field描述 | 50 | 2h | Pydantic可选 |
| Markdown格式 | 100 | 3h | 无（标准库） |
| 扁平化选项 | 80 | 4h | 无 |
| JSON Schema | 30 | 1h | 无（手动） |

**总计：~285 LOC, ~10.5h**

## Sources

### HIGH Confidence
- JSend specification: https://github.com/omniti-labs/jsend
- JSONAPI specification: https://jsonapi.org/
- JSON response design: https://restfulapi.net/json-response-design/

### MEDIUM Confidence
- WebSearch: "JSON vs Markdown format AI readability comparison"
- WebSearch: "API response format JSON design hierarchy nested data"
- WebSearch: "output format design for AI readability concise structured documentation"
- NordAPIs: https://nordicapis.com/best-practices-for-designing-json-api-response-objects/

### LOW Confidence（需后续验证）
- WebSearch: "flatten nested JSON structure LLM readability token efficiency"
- WebSearch: "Pydantic BaseModel JSON output Python best practices LLM"
- WebSearch: "LangChain output parser structured output Pydantic BaseModel"
- WebSearch: "AI agent readable output format natural language processing"

### Not Verified（网络限制）
- Anthropic: https://www.anthropic.com/index/controlling-claudes-output (无法访问)
- OpenAI: https://platform.openai.com/docs/guides/structured-outputs (无法访问)
- LangChain docs: https://python.langchain.com/docs/modules/model_io/output_parsers/ (未验证)

## Open Questions

1. **Pydantic迁移必要性？**
   - 当前dataclass是否足够？
   - Field描述是否需Pydantic？
   - 建议：先手动添加描述，评估后再迁移

2. **扁平化阈值？**
   - 多层嵌套才算"需要扁平化"？
   - 建议：默认不扁平，--flat选项手动触发

3. **Markdown vs YAML风格？**
   - 当前YAML风格文本输出
   - 是否需改为纯Markdown？
   - 建议：保持YAML风格，添加Markdown选项

4. **execution_flows展示层级？**
   - 当前：graphs[].execution_flows
   - 提升顶层是否影响结构一致性？
   - 建议：添加graphs_summary顶层字段，保留原始层级

5. **自然语言注释token开销？**
   - 注释字段增加输出大小
   - 是否影响AI处理效率？
   - 建议：仅在摘要模式添加注释，详细模式不添加

---

**下一步：** 基于FEATURES.md，STACK.md将确定具体实现技术选择（Pydantic vs dataclass、Markdown库选择等）。