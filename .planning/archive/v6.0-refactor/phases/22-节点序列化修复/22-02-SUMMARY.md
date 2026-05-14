---
phase: 22-节点序列化修复
plan: 02
status: partial
completed: 2026-05-05
issues_resolved: 1
issues_remaining: 5
---

# Phase 22 Plan 02 Summary: PinFriendlyName FText 跳过逻辑研究

## 执行状态

**状态**: Partial - FText 跳过逻辑不适用，已添加调试工具

## 修复成果

### 代码修改

1. **skip_ftext_editoronly 函数** (行 2786-2859)
   - 实现完整的 FText 格式跳过逻辑
   - 支持 HistoryType 0-12 类型
   - 添加 `--debug-ftext` 调试开关
   - 回退机制：格式不符时回退到起始位置

2. **read_ue_graph 调试日志** (行 3413-3445)
   - 记录解析失败的节点名称
   - `--debug-graph` 参数启用调试输出

### 关键发现

**PinFriendlyName (FText) 未被序列化！**

通过 `--debug-ftext` 调试发现：
- 所有读取位置的 HistoryType = 255/125/47/188 等（非 0-12 有效范围）
- 这说明 FText 数据根本不存在于预期位置
- IsFilterEditorOnly() = true 对于此资产，即使 PKG_FilterEditorOnly 标志 = 0

**package_flags 分析：**
```
package_flags = 262144 (0x40000)
PKG_Cooked (0x200) = 0 (未 cooked)
PKG_FilterEditorOnly (0x80) = 0 (标志未设置)
```

**结论：** IsFilterEditorOnly() 的判断比 package_flags 更复杂，取决于：
- Linker 类型
- 保存上下文
- 其他运行时条件

对于 editor-saved 赞产，EditorOnly 数据可能仍被过滤。

### 测试结果

| 测试类别 | 修复前（有FText跳过） | 修复后（无跳过） |
|---------|---------------------|-----------------|
| 核心测试 | ? | 360 passed |
| 节点 pins | 0 | 1-3 pins |
| Phase 21 TEST-01 | Passed | Passed |
| Phase 21 TEST-02 | Failed | Failed |
| Phase 21 TEST-03 | Failed | Failed |
| Phase 21 TEST-04 | Failed | Failed |

## 剩余问题

### ISSUE-02: PinToolTip 解析位置偏移（重新分析）

**新理解：** 不是 FText 未跳过导致的偏移，而是其他原因。

可能的原因：
1. SerializePin 前置字段处理不完整
2. 版本依赖字段（SourceIndex）判断错误
3. 其他未识别的 EditorOnly 字段

### ISSUE-03: K2Node 数量不匹配

**现状：** 解析 10 个节点，导出表 30 个节点

**根因：** 需要进一步分析节点解析失败的具体原因

### 调试输出分析

`--debug-ftext` 输出示例：
```
DEBUG FText: pos=93365, flags=0, history_type=255
DEBUG FText: pos=94542, flags=0, history_type=255
...
```

这些位置不是 FText 数据，而是：
- 可能是下一个字段的开始
- 或填充/标记数据

## 文件修改

| 文件 | 修改内容 |
|------|---------|
| uasset_read.py:2786-2859 | 添加 skip_ftext_editoronly 函数（保留用于调试） |
| uasset_read.py:2908-2916 | 修改 PinFriendlyName 注释，不跳过 |
| uasset_read.py:3413-3445 | 添加节点解析调试日志 |

## 下一步建议

1. 使用 `--debug-ftext` 分析其他 UE 版本/资产类型的 FText 格式
2. 检查 SourceIndex 版本阈值判断是否正确
3. 分析 SerializePin 完整格式（可能有更多前置字段）
4. 研究 UE 源码中 IsFilterEditorOnly() 的完整判断逻辑

---

*Completed: 2026-05-05 — Phase 22-02 完成，FText 跳过逻辑不适用于当前资产*