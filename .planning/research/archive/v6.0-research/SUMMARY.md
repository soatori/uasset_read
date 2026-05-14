# Project Research Summary

**Project:** uasset_read v3.0
**Domain:** Claude Code Skill封装 + 输出格式优化
**Researched:** 2026-05-02
**Confidence:** HIGH

## Executive Summary

本研究涵盖v3.0里程碑的两个核心方向：Phase 11-14的输出格式优化，以及Phase 15的Claude Code skill封装。研究揭示了一个关键洞察：skill不是代码封装而是知识封装——skill提供"如何使用"指导，Python工具提供"实际能力"。

推荐的双层架构将现有Python解析器（uasset_read.py）作为执行层保持不变，skill作为独立知识层通过`parse_uasset()` API消费解析结果。这种分离确保API稳定性优先（Phase 11-14完成后再封装skill），避免skill与Python能力脱节。

主要风险集中在Phase 15的MCP集成陷阱：stdio污染stdout、阻塞事件循环、类型提示缺失、错误处理不兼容、零依赖破坏、大文件内存问题。所有这些陷阱都有明确预防策略，关键是在skill封装前冻结输出格式，确保Python API稳定。

## Key Findings

### Recommended Stack (Skill封装)

**核心格式技术：**

- **Markdown (.md)**：Skill主文件格式 — Claude Code原生支持，文本格式易版本控制
- **YAML Frontmatter**：元数据配置 — 官方推荐格式，支持name/description/triggers字段
- **UTF-8 编码**：文件编码 — Claude Code默认编码，支持中英文
- **Python CLI调用**：集成方式 — Skill通过Bash工具调用现有uasset_read.py，无需额外代码

**Skill文件结构：**

- **SKILL.md**：`.claude/skills/<skill-name>/SKILL.md` — Skill主入口文件（必需）
- **knowledge/**：知识库目录（可选） — blueprint-semantics.md、node-types.md等
- **examples/**：示例目录（可选） — 使用示例markdown文件

**推荐采用YAML Frontmatter格式**（而非表格式），符合官方规范，自动触发更可靠。

### Expected Features (输出格式优化)

**Must have (table stakes):**

- **JSON输出** — AI原生理解，v1.0已实现，需优化结构
- **status字段** — JSend style: success/fail/error，AI一眼判断解析结果
- **明确的类型标注** — AI需理解字段含义和数据类型
- **层次结构清晰** — Package→Exports→Properties三层易懂
- **引用解析** — FPackageIndex→对象名称，AI无需反向查找

**Should have (competitive):**

- **摘要模式 (`--summary`)** — 减少70%+ token，AI快速获取关键信息
- **execution_flows顶层化** — 从graphs[]内提升至顶层或graphs_summary字段
- **Markdown输出格式** — 人类+AI双重友好，token效率高
- **Schema定义/Field描述** — AI自动理解结构，无需猜测字段含义
- **扁平化选项 (`--flat`)** — 深度嵌套资产优化，减少认知负担

**Defer (v2+):**

- **JSON Schema文件生成** — 可后续文档化，非v3.0必需
- **多资产批量输出** — 超出v3.0范围
- **TypeScript定义生成** — 次要，可文档化

### Architecture Approach (Skill集成架构)

推荐双层架构：Python工具层（执行解析）+ Skill知识层（指导使用）。现有FArchive管道模式无需修改，skill作为独立消费者层通过`parse_uasset()` API调用。

**Major components:**

1. **Python工具层（现有）** — FArchive、ParseResult、GraphParser、AdvancedPropParser、DependencyAnalyzer等，提供解析执行能力
2. **Skill知识层（新增）** — SKILL.md定义元信息和触发词，knowledge/*.md提供蓝图语义、节点类型、C++转换模式等知识库
3. **集成点：`parse_uasset()` API** — 唯一入口，返回ParseResult容器，skill消费结果无需修改Python代码

**构建顺序关键：**

- Phase 11-14完善Python API输出质量 → Phase 15封装skill
- 避免skill → API → skill反复调整
- 知识库依赖实际解析能力验证（Phase 12-13完成后编写knowledge）

### Critical Pitfalls (Phase 15 MCP集成)

**Top 6 Critical Pitfalls:**

1. **stdio传输污染stdout** — MCP使用stdout传输JSON-RPC消息，使用`print()`调试会污染通道。预防：所有日志输出到stderr，使用logging模块配置stream=sys.stderr。

2. **阻塞事件循环** — async工具处理器中调用同步代码（文件I/O、mmap解析）阻塞整个事件循环。预防：使用`asyncio.to_thread()`或`loop.run_in_executor()`将同步代码包装为异步。

3. **类型提示缺失导致JSON Schema生成失败** — FastMCP依赖类型提示生成JSON Schema，缺少类型提示导致工具无法注册。预防：使用完整类型提示，Pydantic BaseModel定义参数结构，mypy strict模式检查。

4. **错误处理不兼容MCP协议** — Python异常（UAssetError、ParseError）不符合MCP JSON-RPC 2.0规范。预防：捕获异常转换为McpError，定义错误码常量，提供详细错误消息。

5. **零依赖特性被破坏** — MCP封装引入过多依赖破坏uasset_read.py零依赖特性。预防：最小化MCP依赖（仅mcp包），核心解析器保持零依赖，独立模块uasset_mcp_server.py。

6. **大文件内存问题** — 未正确处理大文件解析（>50MB），导致内存溢出或超时。预防：添加文件大小限制（500MB），提供摘要模式，使用线程池异步解析。

**Phase 15特定警告：**

所有Critical Pitfalls (1-6)需要在Phase 15代码审查和集成测试中专门检查。使用MCP inspector验证工具Schema，压力测试大文件解析，单元测试验证序列化。

## Implications for Roadmap

Based on combined research, suggested phase structure for v3.0:

### Phase 11: ExportMap属性值提取

**Rationale:** 输出格式优化的基础，需先完善数据提取能力再优化输出结构。

**Delivers:** ExportMap属性值完整提取，ParseResult数据结构增强。

**Addresses:** FEATURES.md table stakes - 层次结构清晰（Package→Exports→Properties三层）

**Avoids:** PITFALLS.md Pitfall U1 - ParseResult序列化兼容性（审计字段类型）

**Research flag:** Standard patterns — ExportMap解析模式在v2.0已建立，沿用FArchive模式。

### Phase 12: BlueprintVariables完整提取

**Rationale:** 蓝图变量提取是skill知识库（cpp-conversion.md）的前提，需验证转换模式实际可行。

**Delivers:** BlueprintVariables完整提取，变量类型、默认值、分类信息。

**Addresses:** FEATURES.md differentiators - Field描述（变量字段添加语义说明）

**Uses:** STACK.md Python CLI调用 — parse_uasset() API增强

**Implements:** ARCHITECTURE.md Python工具层 — GraphParser/BlueprintMetadata扩展

**Research flag:** Needs research — 蓝图变量提取涉及复杂的UE属性系统，可能需要UE源码深入研究。

### Phase 13: 组件变换属性解析

**Rationale:** 组件变换是蓝图转C++的关键数据，需正确处理浮点精度。

**Delivers:** 组件变换属性（Location/Rotation/Scale）完整解析。

**Addresses:** FEATURES.md table stakes - 明确类型标注（Transform结构需类型文档）

**Avoids:** PITFALLS.md Phase 13警告 - 数值精度问题（使用float精度控制，舍入策略）

**Research flag:** Standard patterns — Transform属性结构相对稳定，参考UE源码即可。

### Phase 14: 输出格式优化并冻结

**Rationale:** Skill封装依赖稳定API输出格式，必须冻结后再启动Phase 15。

**Delivers:** status字段、execution_flows顶层化、摘要模式增强、Markdown输出选项。

**Addresses:** FEATURES.md MVP P0/P1 — status字段（AI判断成功/失败）、execution_flows位置优化、摘要模式

**Avoids:** PITFALLS.md Pitfall 8 - JSON序列化问题（验证所有类型序列化）

**Uses:** STACK.md技术栈 — Markdown输出格式、JSend响应规范

**Implements:** ARCHITECTURE.md输出层 — OutputFormatter扩展

**Research flag:** Needs research — AI易用性输出格式设计（扁平化阈值、自然语言注释token开销）需验证。

### Phase 15: Claude Code skill封装

**Rationale:** 所有Python API完善后封装skill，确保知识库与实际能力匹配。

**Delivers:** SKILL.md定义、knowledge知识库（5-6文件）、examples示例（3-4文件）。

**Addresses:** STACK.md Skill文件结构 — SKILL.md + knowledge/ + examples/

**Avoids:** PITFALLS.md所有Critical Pitfalls (1-6) — stdio污染、阻塞事件循环、类型提示、错误处理、零依赖、大文件

**Uses:** ARCHITECTURE.md双层架构 — Skill知识层独立于Python工具层

**Implements:** STACK.md YAML Frontmatter格式 — 推荐官方格式

**Research flag:** Needs research — skill触发词匹配机制、MCP Python SDK集成细节（但已有HIGH置信度文档）。

### Phase Ordering Rationale

**依赖顺序：**

1. **Phase 11-14顺序执行** — 数据提取能力是输出格式优化的前提，输出格式冻结是skill封装的前提。
2. **Phase 15在Phase 14后** — Skill依赖稳定API输出格式，避免反复调整。
3. **Phase 15子阶段串行** — 15-A (SKILL.md) → 15-B (knowledge) → 15-C (examples) → 15-D (测试)，知识库依赖实际能力验证。

**架构分组：**

- **Phase 11-13（数据提取层）** — 完善Python解析能力，扩展ParseResult数据结构。
- **Phase 14（输出优化层）** — 优化输出格式使AI易理解，冻结API。
- **Phase 15（Skill封装层）** — 知识库编写，skill定义，集成测试。

**Pitfall避免：**

- Phase 14验证序列化 → 避免Phase 15 Pitfall 8
- Phase 11-13审计字段类型 → 避免Phase 15 Pitfall 3
- Phase 15使用stderr日志 → 避免Pitfall 1
- Phase 15使用asyncio.to_thread → 避免Pitfall 2

### Research Flags

**Phases likely needing deeper research during planning:**

- **Phase 12:** BlueprintVariables提取涉及复杂的UE属性系统，可能需要`/gsd-research-phase`深入研究UE源码中BlueprintVariable序列化细节。
- **Phase 14:** AI易用性输出格式设计，需研究扁平化阈值、自然语言注释token开销等open questions。
- **Phase 15 (MCP集成部分):** MCP Python SDK集成细节，FastMCP使用模式（虽有HIGH置信度文档，但实际集成可能遇到细节问题）。

**Phases with standard patterns (skip research-phase):**

- **Phase 11:** ExportMap解析模式在v2.0已建立，沿用FArchive管道模式，无需深入研究。
- **Phase 13:** Transform属性结构相对稳定，参考UE源码PackageFileSummary.h即可。
- **Phase 15 (Skill文件编写):** Skill文件格式、目录结构已有项目内3个示例（lyra-course、uasset-format、uecpp-course），可直接参考。

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack (Skill封装技术) | HIGH | 基于项目内3个现有skill示例（lyra-course、uasset-format、uecpp-course），Claude Code官方文档，YAML Frontmatter格式明确 |
| Features (输出格式优化) | MEDIUM | JSend/JSONAPI规范HIGH置信度，但AI易用性部分（扁平化、自然语言注释）LOW置信度需验证 |
| Architecture (双层架构) | HIGH | 基于现有架构分析，lyra-course成功模式验证，集成点parse_uasset() API清晰稳定 |
| Pitfalls (MCP集成陷阱) | HIGH | 基于MCP官方文档、Python SDK源码、FastMCP库文档、JSON-RPC规范，所有陷阱有明确预防策略 |

**Overall confidence:** HIGH

### Gaps to Address

**需要在规划/执行阶段处理的缺口：**

1. **AI易用性输出格式验证**（FEATURES.md Open Questions）：
   - 扁平化阈值（多层嵌套才算"需要扁平化"？）→ Phase 14实际测试不同资产嵌套深度，确定阈值。
   - 自然语言注释token开销 → Phase 14在摘要模式测试注释字段对AI处理效率的影响。
   - execution_flows展示层级是否影响结构一致性 → Phase 14添加graphs_summary顶层字段，保留原始层级，测试AI理解。

2. **BlueprintVariables提取复杂度验证**（Phase 12）：
   - UE属性系统序列化细节 → Phase 12执行时如遇困难，启动`/gsd-research-phase`深入研究UE源码。
   - 默认值提取可行性 → Phase 12测试Lyra蓝图案例，验证默认值解析。

3. **MCP实际集成细节**（Phase 15）：
   - FastMCP vs MCP Python SDK选择 → Phase 15-A评估FastMCP简化开发是否适合本项目。
   - Claude Code配置集成 → Phase 15-D测试claude_desktop_config.json配置。

4. **Pydantic迁移必要性**（FEATURES.md Open Question）：
   - 当前dataclass是否足够 → Phase 14先手动添加Field描述，评估后再决定是否迁移Pydantic。

## Sources

### Primary (HIGH confidence)

- **项目内现有Skill示例** — `.claude/skills/lyra-course/SKILL.md`、`.claude/skills/uasset-format/SKILL.md`、`.claude/skills/uecpp-course/SKILL.md`（Skill文件格式、目录结构）
- **Claude Code Documentation** — [docs.anthropic.com](https://docs.anthropic.com/en/docs/claude-code)（Skill集成指南）
- **MCP官方文档** — [modelcontextprotocol.io](https://modelcontextprotocol.io/)（MCP协议规范、Python SDK指南）
- **MCP Python SDK** — [github.com/modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk)（官方Python SDK仓库）
- **FastMCP** — [github.com/jlowin/fastmcp](https://github.com/jlowin/fastmcp)（简化MCP开发的高级库）
- **JSend specification** — [github.com/omniti-labs/jsend](https://github.com/omniti-labs/jsend)（JSON API响应格式规范）
- **JSONAPI specification** — [jsonapi.org](https://jsonapi.org/)（复杂资产关联输出规范）
- **JSON-RPC 2.0 Specification** — [jsonrpc.org](https://www.jsonrpc.org/specification)（错误码规范）
- **Python Asyncio Best Practices** — [docs.python.org/3/library/asyncio.html](https://docs.python.org/3/library/asyncio.html)（异步编程最佳实践）
- **uasset_read.py源码** — 4901行Python解析器（现有架构分析）

### Secondary (MEDIUM confidence)

- **WebSearch: JSON vs Markdown format AI readability comparison** — JSON为主Markdown为辅结论，需验证token效率
- **WebSearch: API response format JSON design hierarchy nested data** — 扁平化原则（深度≤3层），需验证阈值
- **WebSearch: output format design for AI readability** — 结构化对象优于自由文本，需验证注释字段效果
- **NordAPIs Best Practices** — [nordicapis.com/best-practices-for-designing-json-api-response-objects](https://nordicapis.com/best-practices-for-designing-json-api-response-objects/)（JSON响应设计）
- **MCP GitHub Issues** — [github.com/modelcontextprotocol/python-sdk/issues](https://github.com/modelcontextprotocol/python-sdk/issues)（常见问题和解决方案）

### Tertiary (LOW confidence)

- **WebSearch: flatten nested JSON structure LLM readability token efficiency** — 扁平化token效率，需Phase 14验证
- **WebSearch: Pydantic BaseModel JSON output Python LLM** — Pydantic迁移必要性，需Phase 14评估
- **WebSearch: AI agent readable output format natural language processing** — 自然语言注释效果，需Phase 14测试
- **Anthropic docs** — [anthropic.com/index/controlling-claudes-output](https://www.anthropic.com/index/controlling-claudes-output)（无法访问，网络限制）
- **OpenAI docs** — [platform.openai.com/docs/guides/structured-outputs](https://platform.openai.com/docs/guides/structured-outputs)（未验证）
- **LangChain docs** — [python.langchain.com/docs/modules/model_io/output_parsers](https://python.langchain.com/docs/modules/model_io/output_parsers/)（未验证）

---
*Research completed: 2026-05-02*
*Ready for roadmap: yes*