# Phase 62: 字节码 → 表达式树 - Discussion Log

**Gathered:** 2026-05-20
**Areas Discussed:** 4

## Discussion Areas

### 1. 字节码入口发现
**Question:** ScriptBytecode 字节流的入口点从哪里获取？
**Selected:** 函数图 + 事件图

**Follow-up:** ScriptBytecode 属性在反序列化后是什么格式？
**Selected:** 不确定，需查 CUE4Parse

**Research Findings:** CUE4Parse UStruct.cs 显示 ScriptBytecode 序列化格式为 bytecodeBufferSize (int) + serializedScriptSize (int) + byte[] 数据段。入口从 UStruct（UFunction/FunctionEntry）读取。

### 2. 控制流结构化
**Question:** 遇到 EX_Jump、EX_JumpIfNot、EMark、EPush 等跳转 token 时，如何还原为结构化的 if/while/for？
**Selected:** CUE4Parse 方式（遍历阶段处理）

**Rationale:** Phase 62 只负责读取表达式列表，JMP 的 CodeOffset 作为属性存储。控制流结构化留给 Phase 63。

### 3. 表达式树连接
**Question:** FKismetArchive.read_expression() 已经能读单条表达式，如何将整个字节流构建成完整的表达式树/列表？
**Selected:** 探索CUE4Parse的方式

**Research Findings:** CUE4Parse ReadExpressionArray() 循环调用 ReadExpression() 直到遇到 endToken（EX_EndOfScript）。每个表达式在构造时自动递归读取子节点。

### 4. 错误处理策略
**Question:** 遇到未知 token 或格式错误时如何处理？
**Selected:** 可切换模式

**Rationale:** 默认严格模式（未知 token 抛 ParseError），可通过构造参数切换为容错模式（跳过未知字节继续解析）。与项目现有 FArchive tolerant 模式一致。

## Deferred Ideas

None.

---

*Phase: 62-字节码 → 表达式树*
*Discussion completed: 2026-05-20*
