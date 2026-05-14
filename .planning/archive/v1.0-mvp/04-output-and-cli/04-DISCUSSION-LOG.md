# Phase 4: 输出与 CLI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-01
**Phase:** 04-output-and-cli
**Areas discussed:** JSON结构设计, 引用解析策略, 文本/摘要格式, CLI设计与入口, 输出编码, 性能策略, 蓝图格式, 复杂值格式

---

## JSON 结构设计 - JSON层级

| Option | Description | Selected |
|--------|-------------|----------|
| 完整结构 | 与 ParseResult 结构一致，包含 summary、name_map、import_map、export_map、errors、properties 等 | |
| 精简结构 | 仅包含导出对象及其属性，省略 name_map/import_map 等底层细节 | |
| 分级输出 | 两个版本：--json 输出完整，--summary 输出精简 | ✓ |

**User's choice:** 分级输出
**Notes:** 满足 AI agent 和开发者两种用户需求

---

## JSON 结构设计 - 导出层级

| Option | Description | Selected |
|--------|-------------|----------|
| Package → Exports → Properties | exports 数组包含每个导出的对象名、类名、属性列表 | ✓ |
| Package → Types → Objects | 按导出类型分组，如 blueprints、materials、textures | |
| Package → Properties (flat) | 扁平属性列表，无层级分组 | |

**User's choice:** Package → Exports → Properties

---

## JSON 结构设计 - 错误位置

| Option | Description | Selected |
|--------|-------------|----------|
| 顶层 errors 字段 | 顶层 errors 数组包含所有解析错误 | ✓ |
| 嵌入各导出对象 | 每个导出内部包含 partial_errors 数组 | |
| 双重记录 | errors 顶层 + partial_errors 嵌入（两者皆有） | |

**User's choice:** 顶层 errors 字段

---

## JSON 结构设计 - 精简字段

| Option | Description | Selected |
|--------|-------------|----------|
| 最小化（名+值） | 仅导出对象名 + 属性名值对（无类型信息） | |
| 中等（名+类型+值） | 导出对象名 + 类型 + 属性列表（名+类型+值） | ✓ |
| 保留元数据 | 精简版保留所有字段，仅省略 name_map/import_map 原始数据 | |

**User's choice:** 中等（名+类型+值）

---

## JSON 结构设计 - 蓝图位置

| Option | Description | Selected |
|--------|-------------|----------|
| 顶层 blueprint_metadata | blueprint_metadata 顶层字段，包含父类、变量列表（仅蓝图资产有此字段） | ✓ |
| 嵌入导出对象 | blueprint_metadata 嵌入在导出对象内部 | |
| 分散字段 | 蓝图信息分散到 parent_class、variables 等独立字段 | |

**User's choice:** 顶层 blueprint_metadata

---

## JSON 结构设计 - 索引格式

| Option | Description | Selected |
|--------|-------------|----------|
| 原始 int32 | 保留原始 int32 值（如 5 表示导出[4]，-3 表示导入[2]） | ✓ |
| 解析为对象名 | 转换为对象名字符串（如 "AActor"） | |
| 索引+名组合 | 对象格式 {"index": 5, "name": "AActor"} | |

**User's choice:** 原始 int32

---

## JSON 结构设计 - 名称表

| Option | Description | Selected |
|--------|-------------|----------|
| 不包含 | 仅导出对象使用已解析名称，不输出原始 name_map 数组 | ✓ |
| 完整输出 | 顶层 name_map 数组供调试或手动引用解析 | |
| 分级包含 | 仅完整 JSON 包含，精简版省略 | |

**User's choice:** 不包含（推荐）

---

## JSON 结构设计 - 版本字段

| Option | Description | Selected |
|--------|-------------|----------|
| 包含在 summary | 顶层 summary 对象包含 version_ue4、version_ue5、legacy_version | ✓ |
| 错误时输出 | 仅在解析失败或调试时输出版本信息 | |
| 分级包含 | 完整 JSON 包含，精简版省略 | |

**User's choice:** 包含在 summary

---

## JSON 结构设计 - 标志字段

| Option | Description | Selected |
|--------|-------------|----------|
| 原始值 | 顶层 summary.package_flags 输出原始 u32 值 | ✓ |
| 解析为名称 | 解析为可读标志名数组（如 ["Saved", "Cooked"]） | |
| 省略 | 省略 package_flags 字段 | |

**User's choice:** 原始值（推荐）

---

## 引用解析策略 - 解析时机

| Option | Description | Selected |
|--------|-------------|----------|
| 解析阶段 | 解析阶段（Phase 3）已解析 ParentClass；Phase 4 仅格式化输出 | ✓ |
| 输出阶段 | Phase 4 输出阶段统一解析所有引用 | |
| 混合模式 | 两阶段均可，根据引用类型选择 | |

**User's choice:** 解析阶段

---

## 引用解析策略 - 解析范围

| Option | Description | Selected |
|--------|-------------|----------|
| 关键引用 | 仅 ParentClass、SuperIndex、OuterIndex 等关键引用 | ✓ |
| 所有引用 | 解析所有 ObjectProperty 引用 | |
| 仅蓝图引用 | 仅蓝图相关引用（ParentClass、变量默认值中的对象引用） | |

**User's choice:** 关键引用

---

## 引用解析策略 - 解析失败

| Option | Description | Selected |
|--------|-------------|----------|
| 原始值+警告 | 返回原始 int32 值 + warning 字段标记失败 | ✓ |
| 返回 null | 返回 null 并记录错误 | |
| 标记字符串 | 返回字符串 "UnknownRef(5)" 标记原始值 | |

**User's choice:** 原始值+警告

---

## 引用解析策略 - 循环引用

| Option | Description | Selected |
|--------|-------------|----------|
| 不检测 | 仅一层解析，不追溯继承链（Phase 3 D-09 已决定） | ✓ |
| 检测并警告 | 检测引用链中的循环，记录警告 | |
| 检测并标记 | 检测循环，将循环引用标记为 "CircularRef" | |

**User's choice:** 不检测（推荐）

---

## 引用解析策略 - 软引用

| Option | Description | Selected |
|--------|-------------|----------|
| 原始路径列表 | 输出 soft_object_paths 数组（原始路径字符串列表） | ✓ |
| 仅蓝图相关 | 仅解析蓝图使用的软引用，不输出完整列表 | |
| 省略 | 不输出软引用数据 | |

**User's choice:** 原始路径列表

---

## 文本/摘要格式 - 格式目标

| Option | Description | Selected |
|--------|-------------|----------|
| AI agent 优先 | 简洁结构化文本，AI agent 可快速解析 | ✓ |
| 开发者优先 | 类似 UE 编辑器属性面板，开发者友好 | |
| 两者兼顾 | --text 为开发者风格，--summary 为 AI agent 风格 | |

**User's choice:** AI agent 优先

---

## 文本/摘要格式 - 格式风格

| Option | Description | Selected |
|--------|-------------|----------|
| YAML 风格 | 类似 YAML 的层级结构（Package: / Exports: / - Name:） | ✓ |
| INI 风格 | 类似 INI 的块结构（[Package] / [Export:ObjName]） | |
| Markdown 风格 | Markdown 格式（# Package / ## Export / - Property） | |

**User's choice:** YAML 风格

---

## 文本/摘要格式 - 摘要格式

| Option | Description | Selected |
|--------|-------------|----------|
| 单行摘要 | 资产类型 + 对象数 + 错误数（如 "Blueprint, 3 exports, 0 errors"） | |
| 精简 YAML | 仅对象名列表 + 类型 | ✓ |
| JSON 格式 | 同 --summary --json | |

**User's choice:** 精简 YAML

---

## 文本/摘要格式 - 错误显示

| Option | Description | Selected |
|--------|-------------|----------|
| 末尾 ERRORS 区块 | 末尾集中显示 ERRORS: 区块 | ✓ |
| 嵌入对象 | 嵌入在失败对象内部（如 [Export:Obj] Error: ...） | |
| 错误计数 | 仅显示错误总数（"0 errors" 或 "3 errors, see --text"） | |

**User's choice:** 末尾 ERRORS 区块

---

## 文本/摘要格式 - 属性格式

| Option | Description | Selected |
|--------|-------------|----------|
| YAML 键值 | 一行一个属性（name: value） | ✓ |
| 表格格式 | 表格格式（Name | Type | Value） | |
| 类型注释 | 带类型注释（name (Type): value） | |

**User's choice:** YAML 键值

---

## CLI 设计与入口 - 入口模式

| Option | Description | Selected |
|--------|-------------|----------|
| 模块执行 | python -m uasset_read file.uasset（推荐，可配合 __main__.py） | |
| 脚本执行 | python uasset_read.py file.uasset（直接脚本） | |
| 双入口 | 两种方式均可（__main__.py + 脚本入口） | ✓ |

**User's choice:** 双入口

---

## CLI 设计与入口 - 输出标志

| Option | Description | Selected |
|--------|-------------|----------|
| 互斥标志 | --json / --text / --summary 三选一，默认 text | ✓ |
| 可组合 | --json + --text 可同时输出 | |
| 单一 --format | --format=json/text/summary 单一标志 | |

**User's choice:** 互斥标志

---

## CLI 设计与入口 - 错误输出

| Option | Description | Selected |
|--------|-------------|----------|
| stderr 错误 | 错误信息输出到 stderr，正常输出到 stdout | ✓ |
| stdout 统一 | 所有输出到 stdout，包括错误 | |
| 格式区分 | --json 输出到 stdout，错误到 stderr；--text 全部 stdout | |

**User's choice:** stderr 错误

---

## CLI 设计与入口 - 退出码

| Option | Description | Selected |
|--------|-------------|----------|
| 语义退出码 | 0 成功、1 解析错误、2 文件不存在、3 参数错误 | ✓ |
| 简单二元 | 0 成功、非 0 失败（不区分类型） | |
| HTTP 风格 | 错误码匹配 HTTP 状态（如 404 文件不存在） | |

**User's choice:** 语义退出码

---

## CLI 设计与入口 - 其他标志

| Option | Description | Selected |
|--------|-------------|----------|
| --verbose | 包含 SoftObjectPaths、CustomVersions 等完整数据 | ✓ |
| --output FILE | 仅输出到文件，不打印到终端 | ✓ |
| --export INDEX | 仅输出指定导出对象的属性 | ✓ |
| --help/-h | 输出帮助信息后退出 | ✓ |

**User's choice:** 全部选择（多选）

---

## 输出编码

| Option | Description | Selected |
|--------|-------------|----------|
| UTF-8 统一 | JSON 强制 UTF-8，文本输出 UTF-8 | ✓ |
| 文本系统默认 | JSON UTF-8，文本输出使用系统默认编码 | |
| 用户指定 | --encoding 标志让用户指定 | |

**User's choice:** UTF-8 统一

---

## 性能策略

| Option | Description | Selected |
|--------|-------------|----------|
| 推迟到 Phase 5 | Phase 5 处理性能优化，Phase 4 仅正确输出 | ✓ |
| 流式输出 | 大文件（>50MB）直接输出到文件，不缓存内存 | |
| 输出限制 | 限制输出对象数量，--verbose 显示全部 | |

**User's choice:** 推迟到 Phase 5

---

## 蓝图格式

| Option | Description | Selected |
|--------|-------------|----------|
| 嵌入属性列表 | 蓝图元数据嵌入在导出对象的属性列表中 | ✓ |
| 独立区块 | 蓝图元数据单独 BlueprintMetadata 区块 | |
| 格式区分 | 仅 --text 显示蓝图详情，--summary 简化 | |

**User's choice:** 嵌入属性列表

---

## 复杂值格式

| Option | Description | Selected |
|--------|-------------|----------|
| YAML 缩进 | YAML 风格缩进（数组用 - 前缀，嵌套增加缩进） | ✓ |
| JSON 行内 | 一行 JSON 格式（[1, 2, 3]） | |
| 扁平格式 | 扁平显示，嵌套值用 -> 标记 | |

**User's choice:** YAML 缩进

---

## Claude's Discretion

- 具体 JSON 字段命名（如 exports vs objects、properties vs fields）
- YAML 缩进级别（2 空格 vs 4 空格）
- 错误消息格式和详细程度
- --verbose 输出的额外字段列表
- 单元测试组织和测试资产选择

---

## Deferred Ideas

推迟到 Phase 5：
- 大文件性能优化（流式输出、内存映射）
- 输出限制（对象数量限制）

推迟到 v2：
- 特定资产类型输出格式（材质、纹理、关卡）
- 输出模板/自定义格式
- 批量文件处理
- 进度显示

---

*Phase: 04-output-and-cli*
*Discussion log generated: 2026-05-01*