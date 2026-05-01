# Phase 4: 输出与 CLI - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

交付输出格式化和命令行接口。此阶段将 Phase 1-3 解析的数据输出为 JSON、文本、摘要格式，并通过 CLI 提供用户访问。

**交付能力：**
- JSON 输出（完整版和精简版）
- YAML 风格文本输出
- 精简摘要输出
- 命令行接口（argparse）
- 错误处理和退出码

**Requirements:** OUT-01, OUT-02, OUT-03, OUT-04, OUT-05, CLI-01, CLI-02, CLI-03, CLI-04, CLI-05, CLI-06

**固定范围（来自 REQUIREMENTS.md）：**
- 结构化 JSON 输出（层级结构）
- 人类可读文本摘要
- JSON 输出遵循 Package → Exports → Properties 层级
- 输出包含解析后的引用
- 输出优雅处理缺失/未解析数据
- CLI 接受单个 .uasset 文件路径
- CLI 支持 --json/--text/--summary 标志
- CLI 解析失败时输出错误码和错误信息
- CLI 无需外部依赖

</domain>

<decisions>
## Implementation Decisions

### JSON 结构设计
- **D-01:** 分级输出 —— --json 输出完整结构，--summary 输出精简结构
- **D-02:** Package → Exports → Properties 层级 —— exports 数组包含每个导出的对象名、类名、属性列表
- **D-03:** 顶层 errors 字段 —— 解析错误集中在顶层 errors 数组
- **D-04:** 顶层 blueprint_metadata —— 蓝图元数据作为顶层字段（仅蓝图资产有此字段）
- **D-05:** 原始 int32 索引 —— 完整 JSON 中未解析的 FPackageIndex 保留原始 int32 值
- **D-06:** 不包含 name_map —— 名称表原始数据不输出在 JSON 中（已解析到对象名）
- **D-07:** summary 含版本信息 —— 顶层 summary 对象包含 version_ue4、version_ue5、legacy_version
- **D-08:** package_flags 原始值 —— 顶层 summary.package_flags 输出原始 u32 值
- **原因:** 分级输出满足 AI agent（精简）和开发者（完整）需求；层级结构清晰；顶层字段便于快速访问

### 精简 JSON (--summary) 字段
- **D-09:** 中等详细度 —— 导出对象名 + 类型 + 属性列表（名+类型+值）
- **D-10:** 省略底层细节 —— 不包含 name_map、import_map 原始数组、CustomVersions 等
- **原因:** 精简版满足 AI agent 快速理解资产内容需求

### 引用解析策略
- **D-11:** 解析阶段处理 —— Phase 3 已解析 ParentClass 等；Phase 4 仅格式化输出
- **D-12:** 关键引用范围 —— 仅 ParentClass、SuperIndex、OuterIndex 等关键引用解析为对象名
- **D-13:** 原始值+警告 —— 引用解析失败时返回原始 int32 值 + warning 字段标记
- **D-14:** 不检测循环引用 —— 仅一层解析，无循环风险（Phase 3 D-09 已决定）
- **D-15:** 软引用原始路径列表 —— soft_object_paths 输出原始路径字符串数组
- **原因:** 关键引用满足基本理解需求；失败 fallback 保证原始数据不丢失

### 文本/摘要格式
- **D-16:** AI agent 优先 —— 简洁结构化文本，AI agent 可快速解析
- **D-17:** YAML 风格 —— 类似 YAML 的层级结构（Package: / Exports: / - Name:）
- **D-18:** 精简 YAML 摘要 —— --summary 输出精简 YAML（仅对象名列表 + 类型）
- **D-19:** 末尾 ERRORS 区块 —— 解析错误集中在末尾 ERRORS: 区块
- **D-20:** YAML 键值属性 —— 一行一个属性（name: value）
- **原因:** YAML 风格结构清晰且 AI agent 易解析；末尾区块便于错误汇总

### 蓝图元数据文本格式
- **D-21:** 嵌入属性列表 —— 蓝图元数据（父类、变量列表）嵌入在导出对象的属性列表中
- **原因:** 保持结构一致，无需特殊格式化

### 复杂值文本格式
- **D-22:** YAML 缩进 —— 数组用 - 前缀，嵌套值增加缩进
- **原因:** 保持 YAML 风格一致

### CLI 设计
- **D-23:** 双入口 —— python -m uasset_read 和 python uasset_read.py 均可执行
- **D-24:** 互斥输出标志 —— --json / --text / --summary 三选一，默认 --text
- **D-25:** stderr 错误输出 —— 错误信息输出到 stderr，正常输出到 stdout
- **D-26:** 语义退出码 —— 0 成功、1 解析错误、2 文件不存在、3 参数错误
- **D-27:** 可选标志 —— --verbose（完整数据）、--output FILE（输出到文件）、--export INDEX（仅指定导出）、--help/-h（帮助）
- **原因:** 双入口提供灵活性；互斥标志简化使用；语义退出码便于 CI/脚本集成

### 输出编码
- **D-28:** UTF-8 统一 —— JSON 和文本输出均使用 UTF-8 编码
- **原因:** 与 Phase 1 D-10 UTF-8 FString 一致

### 性能策略
- **D-29:** 推迟到 Phase 5 —— Phase 4 仅正确输出，性能优化（大文件、内存）在 Phase 5
- **原因:** Phase 5 专门处理性能和安全（SAFE-01 至 SAFE-05）

### Claude's Discretion
- 具体 JSON 字段命名（如 exports vs objects、properties vs fields）
- YAML 缩进级别（2 空格 vs 4 空格）
- 错误消息格式和详细程度
- --verbose 输出的额外字段列表
- 单元测试组织和测试资产选择

</decisions>

<specifics>
## Specific Ideas

- "分级输出" —— 用户选择 --json 完整版和 --summary 精简版
- "语义退出码便于 CI/脚本集成" —— 用户确认 CI 使用需求
- 双入口模式 —— 用户希望两种执行方式都支持

</specifics>

<canonical_refs>
## Canonical References

**下游 agent 必须在规划或实现前阅读这些。**

### 项目规划文档
- `.planning/PROJECT.md` —— 项目核心价值、约束（零运行时依赖）
- `.planning/REQUIREMENTS.md` —— OUT-01 至 OUT-05、CLI-01 至 CLI-06 需求定义
- `.planning/ROADMAP.md` —— 阶段 4 成功标准、主要工作、风险
- `.planning/phases/01-core-parsing/01-CONTEXT.md` —— 阶段 1 决策（dataclasses + asdict() → JSON）
- `.planning/phases/02-property-parsing/02-CONTEXT.md` —— 阶段 2 决策（PropertyValue 结构、Python 原生类型）
- `.planning/phases/03-blueprint-extraction/03-CONTEXT.md` —— 阶段 3 决策（蓝图检测、父类解析、变量提取）

### 项目现有代码
- `uasset_read.py` —— FArchive 类、ParseResult dataclass、PropertyValue dataclass
- `tests/test_uasset_read.py` —— 阶段 1/2 测试模式参考

### UE 源码参考（输出格式参考）
- 无直接 UE 源码参考 —— 输出格式为项目自定义设计

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **ParseResult dataclass:** 阶段 1 D-06 已定义，可直接 asdict() → JSON
- **PropertyValue dataclass:** 阶段 2 D-09 已定义 `{name, type, value}` 结构
- **FArchive 类:** 所有解析方法已完成
- **get_asset_class() 函数:** 阶段 1 已实现类名获取

### Established Patterns
- **dataclasses + asdict():** JSON 输出直接兼容
- **Python 原生类型:** 阶段 2 D-07 已确定 int、float、str、list → JSON-ready
- **部分结果模式:** D-15 优雅降级，errors 数组收集错误
- **零依赖约束:** 仅使用标准库（argparse、json、sys）

### Integration Points
- Phase 1 ParseResult: 输出数据源
- Phase 2 PropertyValue: 属性值结构
- Phase 3 BlueprintMetadata: 蓝图元数据结构（待实现）
- CLI 入口: 需 __main__.py 或 main() 函数

</code_context>

<deferred>
## Deferred Ideas

推迟到后续阶段的实现：

### Phase 5（优化与安全）
- 大文件性能优化（流式输出、内存映射）
- 输出限制（对象数量限制）
- 错误恢复策略

### v2（高级输出）
- 特定资产类型输出格式（材质、纹理、关卡）
- 输出模板/自定义格式
- 批量文件处理
- 进度显示

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-output-and-cli*
*Context gathered: 2026-05-01*