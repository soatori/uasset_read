# Phase 1: 核心架构与基础解析 - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

建立完整的解析架构，实现版本检测和文件头部基础结构解析。这是整个解析器的基石，后续所有解析都依赖于此阶段建立的版本感知能力。

**交付能力：**
- 读取 .uasset 文件并验证 PACKAGE_FILE_TAG 魔数正确性
- 解析 FPackageFileSummary 并识别 UE4/UE5 双版本号
- UAssetArchive 包装器支持字节序自动检测和版本感知读取
- FPackageIndex 封装类能正确判断 Import/Export/Null 类型
- CustomVersionContainer 能基于 GUID 解析自定义版本

**Requirements:** CORE-01, CORE-02, CORE-03, CORE-04, CORE-05, CORE-06

</domain>

<decisions>
## Implementation Decisions

### 解析库使用边界
- **D-01:** FPackageFileSummary、CustomVersion、FString 都用 struct.Struct + 手动逻辑
- **D-02:** 边界规则：按需决策（核心结构用 struct，后续复杂结构按需选择 dissect.cstruct）
- **D-03:** struct.Struct 预编译用偏移类封装（定义 SummaryOffsets 类封装偏移常量，支持版本差异）
- **D-04:** 解析结果用 dataclass 封装（便于类型检查和 IDE 支持）
- **D-05:** dissect.cstruct 作为辅助工具引入（不用于主解析，可用于辅助结构定义）

### CustomVersion 映射策略
- **D-06:** GUID 到名称用硬编码常量字典（从 UE ObjectVersion.h 提取）
- **D-07:** 完整提取所有已定义的 CustomVersion（约 100+，完整覆盖）
- **D-08:** 未识别 GUID 记录原始值继续解析（不中断）

### 测试文件来源
- **D-09:** 从 UE 源码示例项目获取测试资产（`E:\Develop\lib\UnrealEngine\Samples`）
- **D-10:** 多版本覆盖（从不同示例项目选择 UE4 到 UE5 版本范围的资产）
- **D-11:** 测试文件存放：灵活支持（默认复制到 tests/fixtures，可选读取原始路径）

### 错误处理策略
- **D-12:** 解析错误记录并继续（适合批量处理）
- **D-13:** 关键错误（魔数不匹配、文件无法打开）立即停止
- **D-14:** 版本不支持时尝试继续并警告（用最新已知版本逻辑）
- **D-15:** 组合方案：logging + ParseError dataclass（logging 输出到 stderr，ParseResult 包含 errors 列表）
- **D-16:** 四级日志：ERROR、WARN、INFO、DEBUG
- **D-17:** 自定义异常类：ParseError, VersionError, MagicError 等
- **D-18:** 异常包含丰富上下文：文件路径、偏移位置、错误类型、上下文信息

### Claude's Discretion
用户未授权 Claude 自行决策的区域。所有关键决策都通过讨论确认。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### UE 源码参考（核心）
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Public\UObject\PackageFileSummary.h` — FPackageFileSummary 结构定义，版本字段，偏移布局
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\Core\Public\UObject\ObjectVersion.h` — 版本号枚举，CustomVersion GUID 定义
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Public\UObject\ObjectResource.h` — FPackageIndex, FObjectImport, FObjectExport 定义
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Public\UObject\LinkerLoad.h` — 8 阶段加载过程，解析顺序参考

### 项目规划文档
- `.planning/PROJECT.md` — 项目核心价值、约束、上下文
- `.planning/REQUIREMENTS.md` — 32 个需求定义，Phase 1 覆盖 CORE-01 到 CORE-06
- `.planning/research/STACK.md` — 技术栈选择理由（struct vs dissect vs construct）
- `.planning/research/ARCHITECTURE.md` — 推荐架构模式，UAssetArchive 包装器模式

### uasset-format 技能文档
- `.claude\skills\uasset-format\SKILL.md` — UE 文件格式完整参考，70+ 文档入口

### 测试资产来源
- `E:\Develop\lib\UnrealEngine\Samples` — UE 源码示例项目，多版本测试资产

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
项目为全新项目，无现有代码可复用。

### Established Patterns
从 research 文件确定的架构模式：
- **包装器模式（Archive Wrapper）** — UAssetArchive 封装 I/O 流，提供 UE 特定读取方法
- **版本感知解析** — 根据版本条件性地解析字段
- **ParseContext 传递** — 避免全局状态，传递版本和字节序状态

### Integration Points
Phase 1 是基础架构，后续 Phase 2-5 都依赖于此：
- Phase 2: NameTable/ImportTable/ExportTable 解析依赖 FPackageFileSummary 偏移
- Phase 3: Property 解析依赖版本信息
- Phase 4: BulkData 依赖 FPackageFileSummary 偏移
- Phase 5: JSON 输出依赖所有解析结果

</code_context>

<specifics>
## Specific Ideas

- 解析结果必须能追溯到 UE 源码定义（核心原则）
- 偏移类封装支持版本差异（不同版本的偏移可能不同）
- 测试资产优先使用 UE 源码示例项目（有对应版本源码可验证）
- 错误信息包含文件路径和偏移位置（便于定位问题）

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 1-核心架构与基础解析*
*Context gathered: 2026-05-01*