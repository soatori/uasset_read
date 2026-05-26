# Phase 63: 表达式树 → C++ 伪代码 - Discussion Log

**Date:** 2026-05-20
**Mode:** default (interactive)

## Areas Discussed

### 1. 输出格式
**Question:** 每个表达式翻译成 C++ 后，输出应该是什么粒度？

**Options:**
- 完整函数体 — 带缩进、分号、花号
- 行级表达式 — 每行一个字符串
- 两者都提供 — line_cpp() + to_function_body()

**Decision:** 两者都提供 — `line_cpp()` (单行) 和 `to_function_body()` (完整函数体)

### 2. 控制流恢复
**Question:** Jump/JumpIfNot/PushExecutionFlow/PopExecutionFlow 应该还原到什么程度？

**Options:**
- 结构化 if/for/while — 完整还原为块结构
- goto + 缩进 — 保留 goto 标签但分组
- 两者都提供 — line_cpp() 用 goto，to_function_body() 尝试结构化

**Decision:** 两者都提供 — `line_cpp()` 使用 goto（简单可靠），`to_function_body()` 尝试结构化 if/for/while 还原

**Note:** 结构化算法不需要完美，优先处理常见模式，无法识别时回退到 goto

### 3. MathFunctionCleaner
**Question:** MathFunctionCleaner 应该在哪里执行？

**Options:**
- 翻译时内联 — 在 to_cpp() 方法内部调用
- 独立后处理步骤 — 生成后做 regex 替换
- 两者结合 — 内联 + 可选后处理钩子

**Decision:** 翻译时内联执行（与 CUE4Parse 一致）

### 4. 类型推断
**Question:** 表达式中引用的变量，类型信息如何获取？

**Options:**
- 从 blueprint 元数据推断 — 依赖 upstream 变量信息
- auto / 占位符 — 全部用 auto
- 混合：优先推断，回退 auto

**Decision:** 混合策略 — 优先从 blueprint 元数据推断，获取不到时回退 auto

## Decisions Summary

| # | Decision | Details |
|---|----------|---------|
| D-01 | 输出格式 | line_cpp() + to_function_body() 双 API |
| D-02 | 控制流恢复 | line_cpp() 用 goto，to_function_body() 结构化 |
| D-03 | 结构化容错 | 常见模式优先，无法识别回退 goto |
| D-04 | MathFunctionCleaner | 翻译时内联执行 |
| D-05 | Math 覆盖范围 | 对齐 CUE4Parse 各库函数映射 |
| D-06 | 类型映射 | 混合：优先 blueprint 推断，回退 auto |
| D-07 | 类型注册表 | TypeRegistry 接口：register/lookup |

---

*Phase: 63-表达式树 → C++ 伪代码*
*Discussion completed: 2026-05-20*
