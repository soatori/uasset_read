# Requirements: uasset_read v3.0

**Defined:** 2026-05-03
**Core Value:** 补齐缺失数值解析，输出可用结果，打包成Claude Code skill

## v1 Requirements

### 数据提取 (EXTR)

- [ ] **EXTR-01**: ExportMap属性值提取 — 从ExportMap中提取组件属性值、变量默认值、输入动作引用
- [ ] **EXTR-02**: BlueprintVariables完整提取 — 提取蓝图变量名称、类型、默认值、元数据（Category、BlueprintReadWrite等）
- [ ] **EXTR-03**: 组件变量区分 — 区分组件变量（SkeletalMeshComponent等）和普通变量
- [ ] **EXTR-04**: 组件变换属性解析 — 解析组件的RelativeLocation/RelativeRotation/RelativeScale3D属性
- [ ] **EXTR-05**: 变量默认值类型覆盖 — 支持数值、字符串、布尔、向量、对象引用等类型默认值

### 输出优化 (OUT)

- [ ] **OUT-01**: status字段 — 添加JSend style status字段（success/fail/error），AI一眼判断解析结果
- [ ] **OUT-02**: execution_flows顶层化 — 将execution_flows从graphs[]内提升至顶层graphs_summary字段
- [ ] **OUT-03**: 摘要模式 — 添加--summary标志，输出精简摘要减少70%+ token
- [ ] **OUT-04**: Markdown输出格式 — 添加--markdown标志，输出Markdown格式（人类+AI双重友好）
- [ ] **OUT-05**: Field描述增强 — 关键字段添加语义注释（parent_class、variables等含义说明）
- [ ] **OUT-06**: 输出格式冻结 — Phase 14完成后冻结输出格式，确保API稳定供skill使用

### Skill封装 (SKILL)

- [ ] **SKILL-01**: SKILL.md定义 — 创建SKILL.md主文件（YAML Frontmatter格式，触发词、能力范围）
- [ ] **SKILL-02**: knowledge知识库 — 编写5-6个知识文件：blueprint-semantics.md、node-types.md、pin-type-mapping.md、cpp-conversion.md、common-patterns.md、troubleshooting.md
- [ ] **SKILL-03**: examples示例 — 编写3-4个示例文件：basic-usage.md、blueprint-analysis.md、cpp-conversion.md
- [ ] **SKILL-04**: skill集成测试 — 验证skill触发、调用parse_uasset() API、输出解读正确

## v2 Requirements

Deferred to future release.

### 高级输出格式

- **OUT-07**: 扁平化选项 — 添加--flat标志，深度嵌套资产扁平化（>3层阈值待验证）
- **OUT-08**: JSON Schema文件生成 — 自动生成schema.json供外部验证

### MCP Server集成

- **SKILL-05**: MCP Server封装 — 创建uasset_mcp_server.py，支持MCP协议调用
- **SKILL-06**: MCP错误处理 — 实现McpError错误码体系，符合JSON-RPC 2.0规范

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Pydantic迁移 | 手动Field描述足够；迁移成本待评估 |
| FastMCP封装 | skill封装优先；MCP Server延后 |
| 多资产批量输出 | 超出v3.0范围 |
| TypeScript定义生成 | 次要，可文档化 |
| 实时解析/监控 | 批量解析场景，无需实时功能 |
| Cooked资产解析 | Cooked资产已剥离图数据 |
| 蓝图字节码反编译 | 专注于编辑器保存的资产 |
| 自动C++代码生成 | 仅提供参考级别JSON |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| EXTR-01 | Phase 11 | Pending |
| EXTR-02 | Phase 12 | Pending |
| EXTR-03 | Phase 12 | Pending |
| EXTR-04 | Phase 13 | Pending |
| EXTR-05 | Phase 12 | Pending |
| OUT-01 | Phase 14 | Pending |
| OUT-02 | Phase 14 | Pending |
| OUT-03 | Phase 14 | Pending |
| OUT-04 | Phase 14 | Pending |
| OUT-05 | Phase 14 | Pending |
| OUT-06 | Phase 14 | Pending |
| SKILL-01 | Phase 15 | Pending |
| SKILL-02 | Phase 15 | Pending |
| SKILL-03 | Phase 15 | Pending |
| SKILL-04 | Phase 15 | Pending |

**Coverage:**
- v1 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-03*
*Last updated: 2026-05-03 after initial definition*