# Phase 10: 依赖分析 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 10-dependency-analysis
**Areas discussed:** ImportMap 依赖格式, SoftObjectPaths 解析, 循环依赖检测, 依赖数组处理

---

## ImportMap 依赖格式

| Question | Option | Description | Selected |
|----------|--------|-------------|----------|
| Import 条目 JSON 结构 | {class, package, object} 对象格式 | 结构清晰，便于 AI agent 理解引用来源 | ✓ |
| | [package, class, object] 数组格式 | 更紧凑，但可读性略低 | |
| | 单字符串格式 | 最紧凑，但需要字符串解析 | |
| Import 类型区分 | 统一处理，不区分 | 简单实现，满足 DEPS-01 需求 | ✓ |
| | 区分类型，添加 type 字段 | 信息更丰富，但需要额外逻辑 | |
| 输出顺序 | 原始顺序 | 保持与 UE 文件一致的顺序 | ✓ |
| | 按名称排序 | 便于查找，但丢失原始顺序信息 | |
| OuterIndex 处理 | 忽略 OuterIndex | 简单实现，满足 DEPS-01 | ✓ |
| | 解析 OuterIndex | 信息完整，但增加复杂度（需要递归解析） | |
| 重复引用处理 | 合并重复 | 减少输出冗余 | ✓ |
| | 保留重复 | 每个条目代表一个引用点，信息完整 | |
| 合并后引用次数 | 仅保留依赖信息 | 简洁输出 | ✓ |
| | 添加 count 字段 | 信息完整，但增加输出复杂度 | |
| 字段名称 | imports 字段 | 与 DEPS-04 的 JSON 结构一致 | ✓ |
| | dependencies 字段 | 更通用的术语，但与 ROADMAP.md 不一致 | |
| 字段位置 | 顶层 imports 字段 | 便于快速访问依赖信息 | ✓ |
| | blueprint.imports 字段 | 仅蓝图相关依赖，但不适用于非蓝图资产 | |
| 空数组处理 | 同级结构，始终输出 | 统一结构，所有资产都有依赖信息 | ✓ |
| | 条件输出 | 减少空数组输出，但结构不一致 | |

**Notes:** 用户选择简洁输出，合并重复依赖，不记录引用次数。顶层 imports 字段与非蓝图资产兼容。

---

## SoftObjectPaths 解析

| Question | Option | Description | Selected |
|----------|--------|-------------|----------|
| 是否实现解析 | 实现完整解析 | 满足 DEPS-02，从 soft_object_paths_offset 读取数据 | ✓ |
| | 不解析，仅记录元信息 | 简化实现，但输出不完整 | |
| JSON 输出结构 | {asset_path, sub_path} 对象格式 | 与 UE FSoftObjectPath 一致 | ✓ |
| | 仅 asset_path 字符串 | 简化输出，但信息不完整 | |
| 字段位置 | 顶层 soft_references 字段 | 统一结构，与 imports 同级 | ✓ |
| | imports.soft_references 字段 | 与硬依赖组合，但层级混乱 | |
| 版本条件 | 仅 UE5 >= 1008 | 满足 DEPS-02 版本条件 | ✓ |
| | 尝试所有版本 | 过度尝试，不满足版本条件 | |

**Notes:** 用户选择完整解析，严格版本条件（UE5 >= 1008），UE4 文件返回空数组。

---

## 循环依赖检测

| Question | Option | Description | Selected |
|----------|--------|-------------|----------|
| 检测算法 | DFS 图遍历 | 标准算法，满足 DEPS-03 | ✓ |
| | 不实现检测 | 简化实现，但不满足 DEPS-03 | |
| 循环定义范围 | 跨包循环检测 | ImportMap 仅包含跨包引用 | ✓ |
| | 任意循环检测 | 过度检测，ImportMap 仅包含跨包引用 | |
| 输出格式 | 路径数组格式 | 满足 DEPS-04 示例 ["A.Package", "B.Package", "A.Package"] | ✓ |
| | 对象格式 | 信息更多，但与 ROADMAP 示例不一致 | |
| 字段位置 | 顶层 circular_deps 字段 | 满足 DEPS-04 JSON 结构 | ✓ |
| | imports.circular_deps 字段 | 与 imports 组合，但不符合 DEPS-04 示例 | |

**Notes:** 用户选择 DFS 图遍历，跨包循环检测，路径数组格式展示循环路径。

---

## 依赖数组处理

| Question | Option | Description | Selected |
|----------|--------|-------------|----------|
| 导出依赖数组 | 不处理导出依赖数组 | 满足 ROADMAP 范围，简化实现 | ✓ |
| | 实现导出依赖数组解析 | 信息完整，但增加复杂度，超出 ROADMAP 范围 | |
| preload_dependencies | 不处理 preload_dependencies | 仅 PackageFileSummary 元信息 | ✓ |
| | 实现 preload_dependencies 解析 | 信息完整，但超出 ROADMAP 范围 | |

**Notes:** Phase 6 D-06 推迟的导出依赖数组不在此阶段处理，满足 DEPS-01~04 仅涉及 ImportMap 和 SoftObjectPaths。

---

## Claude's Discretion

- ImportMap 合并重复的具体实现（去重算法选择）
- DFS 循环检测的具体实现细节（节点标识、路径记录）
- soft_references 数组的解析函数实现细节
- 单元测试组织
- 错误处理和边界情况（空 ImportMap、无循环依赖）

## Deferred Ideas

推迟到 v3 高级依赖分析：
- FirstExportDependency + 4 个导出依赖数组解析
- preload_dependencies 解析
- 导出条目依赖关系分析
- 依赖关系可视化输出（DOT/SVG 格式）
- 更复杂的循环依赖检测

None — discussion stayed within phase scope