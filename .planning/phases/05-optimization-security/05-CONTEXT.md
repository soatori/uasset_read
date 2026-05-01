# Phase 5: 优化与安全 - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning

<domain>
## Phase Boundary

添加性能优化（大文件内存映射）和安全加固（边界验证、超时保护、部分结果改进），确保解析器在任何输入下都不会崩溃或卡死。此阶段交付性能和安全增强，不添加新解析功能。

**交付能力：**
- 大文件内存映射支持（>50MB 自动切换 mmap）
- mmap 失败回退机制
- 循环计数超时保护
- 边界验证增强（全偏移、Size、索引验证）
- 错误+警告分类
- 智能继续解析策略

**Requirements:** SAFE-01, SAFE-02, SAFE-03, SAFE-04, SAFE-05

**固定范围（来自 ROADMAP.md）：**
- 偏移前验证文件大小（SAFE-01）
- 定位前检查偏移边界（SAFE-02）
- 超过 50MB 文件使用内存映射（SAFE-03）
- 可恢复错误返回部分结果（SAFE-04）
- 无效/损坏文件不会卡死（SAFE-05）

</domain>

<decisions>
## Implementation Decisions

### 大文件处理策略
- **D-01:** 50MB 阈值切换 mmap —— 超过 50MB 自动使用内存映射（需求 SAFE-03 指定）
- **D-02:** FArchive 内部 mmap 分支 —— 在 FArchive 内部切换读取方式，对外接口一致
- **D-03:** mmap 失败回退 —— mmap 失败时回退到普通文件读取，记录警告
- **D-04:** 全文件映射 —— 映射整个文件而非分段映射（简单直接）
- **D-05:** 统一 close() 方法 —— FArchive.close() 同时关闭 mmap 和文件
- **D-06:** 合成+真实组合测试 —— 合成大文件测试 mmap 分支，真实文件验证回退逻辑
- **D-07:** 统一 mmap 调用 —— 使用 Python mmap 跨平台统一调用
- **原因:** 50MB 阈值来自需求；FArchive 内部分支保持接口一致；回退保证解析继续；全文件映射简单有效

### 超时与卡死防护
- **D-08:** 循环计数限制 —— 在关键循环中加入计数器检查，超过阈值中止解析
- **D-09:** 组合限制 —— 属性循环10000次 + 名称表10000000条 + 导入/导出表1000000条（已实现部分）
- **原因:** 循环计数简单跨平台；组合限制覆盖主要循环风险

### 边界验证增强
- **D-10:** 全偏移验证 —— seek() 前验证 + 表偏移验证 + 导出 SerialOffset 验证
- **D-11:** PropertyTag.Size 完整验证 —— size >= 0 + size <= remaining_bytes + size <= max_reasonable
- **D-12:** 全索引验证 —— 基本索引检查 + 范围溢出检查 + PackageIndex 解析验证
- **原因:** 全偏移验证防止越界；Size 完整验证防止异常值；全索引验证防止表溢出

### 部分结果改进
- **D-13:** 错误+警告分类 —— 区分致命错误（中止）和警告（继续），记录到不同列表
- **D-14:** 智能继续 —— 可恢复错误继续解析 + 记录失败位置 + 尝试跳到下一个有效点
- **D-15:** 上下文信息 —— 错误信息包含错误类型、位置、上下文（当前解析阶段、偏移）
- **原因:** 错误分类便于问题诊断；智能继续最大化数据提取；上下文信息帮助定位问题

### Claude's Discretion
- max_reasonable Size 具体阈值选择
- PackageIndex 解析验证的具体逻辑
- 失败位置记录格式
- 跳到下一个有效点的启发式方法
- 单元测试组织和测试用例设计

</decisions>

<canonical_refs>
## Canonical References

**下游 agent 必须在规划或实现前阅读这些。**

### 项目现有代码
- `uasset_read.py` —— FArchive 类、边界验证实现、ParseError、MAX_* 常量
- `tests/test_uasset_read.py` —— 阶段 1/2/3 测试模式参考

### 项目规划文档
- `.planning/PROJECT.md` —— 项目核心价值、约束（专注于未 cooked 资产）
- `.planning/REQUIREMENTS.md` —— SAFE-01 至 SAFE-05 需求定义
- `.planning/phases/01-core-parsing/01-CONTEXT.md` —— 阶段 1 决策（D-02 阶段 5 mmap，D-14/D-15 部分结果）
- `.planning/phases/02-property-parsing/02-CONTEXT.md` —— 阶段 2 决策（D-25 单属性失败策略）
- `.planning/phases/03-blueprint-extraction/03-CONTEXT.md` —— 阶段 3 决策（警告记录模式）

### Python mmap 文档
- Python stdlib `mmap` 模块 —— 跨平台内存映射 API

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **FArchive 类:** 基础边界验证（read() 检查剩余字节、seek() 检查文件大小）可扩展
- **MAX_* 常量:** MAX_NAME_COUNT/MAX_IMPORT_COUNT/MAX_EXPORT_COUNT 已定义（uasset_read.py lines 33-36）
- **ParseError:** 已携带 partial_result，可扩展错误分类
- **部分结果模式:** 阶段 1 D-14/D-15 已实现基础部分结果

### Established Patterns
- **版本感知解析:** 版本检查模式可复用于阈值检查
- **dataclasses 模型:** ParseResult 可扩展添加 warnings 列表
- **错误记录模式:** 阶段 2 D-25 单属性失败策略可扩展

### Integration Points
- FArchive.read(): 添加 Size 验证
- FArchive.seek(): 增强偏移验证
- 属性循环: 添加计数器检查
- ParseResult: 添加 warnings 字段
- JSON 输出: 需包含 warnings 列表

</code_context>

<specifics>
## Specific Ideas

- "超过 50MB 文件使用内存映射" —— REQUIREMENTS.md SAFE-03 指定阈值
- "阶段 5 添加 MappedArchive 支持大文件" —— 阶段 1 D-02 已规划
- "组合限制（属性循环10000次 + 名称表10000000 + 导入/导出表1000000）" —— 用户确认组合阈值
- "智能继续（可恢复继续 + 失败位置 + 跳到有效点）" —— 用户选择智能继续策略

</specifics>

<deferred>
## Deferred Ideas

推迟到后续阶段的实现：

### v2（高级安全功能）
- 文件签名验证（防止恶意文件）
- 资源限制（CPU、内存使用监控）
- 解析进度回调
- 并行解析支持

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-optimization-security*
*Context gathered: 2026-05-01*