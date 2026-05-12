# Phase 34: 等价验证 - Context

**Gathered:** 2026-05-12
**Status:** Ready for planning (待 Phase 33 完成后执行)

## Phase Boundary

验证新版模块化代码与旧版单文件的输出完全一致，确保零回归。覆盖范围：
- JSON 输出验证（format_json_full）— 完整 JSON 结构对比
- JSON Summary 验证（format_json_summary）— 精简输出对比
- Text 输出验证（format_text_full）— YAML 风格文本对比
- Markdown 输出验证（format_markdown）— Markdown + Mermaid 对比
- 合成测试资产验证（tests/ 中的合成 .uasset）
- 真实蓝图资产验证（BP_FirstPersonCharacter 等）
- 差异报告生成（VERIFICATION.md）

**依赖:** Phase 33 完成后才能执行验证（新版 CLI 入口可用、旧文件已删除）

**不包含:** 新功能开发、性能测试、边界资产扩展测试（Phase 50）。

## Implementation Decisions

### 验证方法

- **D-01 (验证策略):** 两者结合 — 先用整体 diff 快速验证 JSON/Text/Markdown 输出，发现差异时再用逐字段对比定位具体差异位置。整体 diff 使用 `json.dumps()` 序列化后字符串比较，逐字段对比使用递归遍历 dict 结构。
- **D-02 (验证范围):** 全部四种输出格式 — JSON Full、JSON Summary、Text、Markdown。不跳过任何格式。

### 测试资产

- **D-03 (资产覆盖):** 合成资产 + 真实资产结合 — 既使用 tests/ 中的合成测试资产（覆盖边界场景），也使用真实蓝图资产（如 BP_FirstPersonCharacter）验证实际解析场景。

### 差异处理

- **D-04 (差异策略):** 记录并继续 — 发现差异后记录到差异列表并继续验证其他资产/格式，最后生成完整差异报告。不中断验证流程。
- **D-05 (报告形式):** Markdown 报告 — 在 `.planning/phases/34-equivalence-verification/VERIFICATION.md` 中记录所有发现的差异、修复状态和最终结论。

### 验证工具

- **D-06 (工具形式):** 测试文件 — 在 `tests/test_equivalence.py` 中创建验证测试，使用 pytest 运行。每个资产+格式组合一个测试用例。
- **D-07 (验证函数):** 在测试文件中定义辅助函数 `_compare_outputs(old_output, new_output, format_name)` 实现两种对比策略，不放在 src/uasset_read/ 模块中（验证是测试阶段工具，非生产代码）。

### 执行时机

- **D-08 (前置条件):** Phase 33 完成后才能开始 Phase 34 验证。前置条件包括：
  - (1) `python -m uasset_read` 能正常解析测试资产
  - (2) `uasset-read` CLI 入口可用
  - (3) 旧版 `uasset_read.py` 已删除
  - (4) 全部 411+ 测试通过

### Claude's Discretion

- 测试用例的具体分组和命名（如 `test_json_equivalence_firstperson` vs `test_equivalence_json_firstperson`）由规划阶段确定
- diff 工具的具体实现（使用 Python 标准库 `difflib` 还是直接字符串比较）由规划阶段确定
- 差异报告的具体字段格式（哪些列、如何展示 diff）由规划阶段确定

## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 前期决策（必须阅读）

- `.planning/phases/31-graph-parsing/31-CONTEXT.md` — D-01 至 D-09（graph 模块结构、flow builder 产出格式）
- `.planning/phases/32-output-formatting/32-CONTEXT.md` — D-01 至 D-09（formatters 模块结构、输出字段锁定）
- `.planning/phases/33-entry-test-adapt/33-CONTEXT.md` — D-01 至 D-16（CLI 入口、parse_uasset 管线、测试适配、旧文件删除时机）
- `.planning/ROADMAP.md` §Phase 34 — Phase 34 目标、成功标准
- `.planning/STATE.md` — 当前里程碑状态（确认 Phase 33 是否完成）

### 输出格式参考

- `uasset_read.py` §7188-7248 — format_json_full() 输出结构
- `uasset_read.py` §7360-7428 — format_json_summary() 输出结构
- `uasset_read.py` §7431-7534 — format_text_full() 输出结构
- `uasset_read.py` §7574-7667 — format_markdown() 输出结构

### 测试资产参考

- `tests/test_uasset_read.py` — 合成测试资产创建函数
- `E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\Blueprints\BP_FirstPersonCharacter.uasset` — 真实蓝图资产

## Existing Code Insights

### Reusable Assets

- **pytest 框架:** 已在项目中使用，验证测试可直接运行
- **tests/test_output_formatting.py:** 已有格式化测试，可参考测试结构和 mock 数据模式
- **合成资产函数:** `tests/test_uasset_read.py` 中的 `create_test_uasset()` 可复用创建测试资产
- **difflib 标准库:** Python 内置差异对比工具，可用于逐字段对比和 diff 展示

### Established Patterns

- **pytest 测试结构:** 测试文件按功能分组，使用 fixture 和 parametrize
- **临时文件测试:** 使用 `tempfile.mkstemp()` 创建临时资产，测试后清理
- **JSON 序列化对比:** `json.dumps(obj, indent=2, sort_keys=True)` 确保字段顺序一致

### Integration Points

- `tests/test_equivalence.py` 消费 `parse_uasset` 和所有 `format_xxx` 函数
- 验证测试需要调用新版 CLI（`python -m uasset_read`）和旧版入口（Phase 33 删除前）
- VERIFICATION.md 需要被 `.planning/STATE.md` 引用，记录验证结论

## Specific Ideas

无特定要求 — 采用上述讨论的验证策略和工具设计。

## Deferred Ideas

None — discussion stayed within phase scope.

---

*Phase: 34-等价验证*
*Context gathered: 2026-05-12*