---
name: ue-source-research
description: Use when implementing or fixing Unreal Engine .uasset binary parsing, serializer behavior, property parsing, Blueprint graph/Kismet handling, or any change that depends on UE C++ source semantics. Enforces source-backed format research instead of guessing from samples.
---

# UE Source Research

## Overview

面向 `.uasset` 格式、序列化管线、蓝图图结构和 Kismet 字节码的源码对照流程。目标是先从 UE C++ 源码确认语义，再修改解析器和测试。

## When to Use

- 新增或修复 serializer、property parser、graph parser、Kismet parser
- 解析结果与 UE 行为不一致，需要确认字段含义或读取顺序
- 遇到二进制偏移错位、GUID/NameMap/ImportMap/ExportMap 异常
- 处理 Blueprint 节点、引脚、执行流、宏展开、函数体生成
- 审查涉及 `.uasset` 格式假设的代码改动

## Inputs

- 目标 UE 类型、函数或模块名，例如 `FPackageFileSummary`、`FPropertyTag`、`UEdGraphPin`
- 失败样本路径、pytest 失败、解析输出差异，或用户描述的异常行为
- 目标 UE 版本；未指定时按样本来源和现有测试约定推断，并明确说明推断依据

## Outputs

- UE 源码位置、相关函数/类型、字段读取顺序或行为规则
- 对解析器、模型、IR、渲染器或测试的最小必要修改
- 回归测试或复现命令
- 仍不确定的版本差异或边界条件

## UE 源码位置

默认源码根目录：

```text
E:\Develop\lib\UnrealEngine
```

常见检索入口：

| 主题 | 典型 UE 源码线索 |
|---|---|
| Package summary | `FPackageFileSummary`、`LinkerLoad.cpp`、`PackageFileSummary.h` |
| Name/Import/Export map | `FLinkerLoad`、`FObjectImport`、`FObjectExport` |
| PropertyTag | `FPropertyTag`、`PropertyTag.cpp`、`SerializeTaggedProperty` |
| Struct/Class/Object property | `FStructProperty`、`FClassProperty`、`FObjectProperty` |
| Blueprint graph | `UEdGraph`、`UEdGraphNode`、`UEdGraphPin` |
| Kismet bytecode | `Script.h`、`KismetCompiler`、`FFrame`、`EExprToken` |
| Macro/flow behavior | `K2Node`、`K2Node_MacroInstance`、`KismetCompiler` |

## Research Flow

1. 定义问题：写清楚当前解析器哪里不确定，是字段顺序、条件分支、版本门控，还是语义映射。
2. 定位 UE 源码：优先用 `rg` 在 `E:\Develop\lib\UnrealEngine` 查类型名、函数名、枚举值或序列化函数。
3. 记录证据：保存文件路径、类型/函数名和关键行为摘要；必要时引用短代码片段，但不要大段复制。
4. 对照本项目实现：结构性问题用 CodeGraph 查调用链和影响范围；字面量和常量用 `rg`。
5. 修改解析逻辑：保持只读、零运行时依赖、直接脚本运行约束。
6. 加测试：优先新增能复现原问题的最小回归测试；样本资产路径放在测试配置或现有 fixture 模式中。
7. 验证：先跑失败用例，再跑相关目录；跨模块修改时运行 `python -m pytest tests/ -q`。

## Evidence Checklist

修改前至少确认以下信息：

- UE 类型或函数来自哪个源码文件
- 字段读取顺序和条件分支
- 版本门控，例如 UE4/UE5、custom version、cooked/editor-only 差异
- 与现有项目模型字段的映射关系
- tolerant/strict 模式下应如何处理异常或缺失字段

## Implementation Rules

- 优先复用现有 serializer、parser、model 和 IR 模式。
- 对二进制读取必须保持偏移可解释；新增容错逻辑要记录 warning 或 partial 状态。
- 对 GUID、Name、ObjectPath 等规范化规则，优先在源头统一。
- UE 源码未确认前，不新增“看起来合理”的字段含义。
- 样本观察只能作为线索，不能替代源码证据。

## Verification

- 最小复现：运行相关失败测试或新增回归测试。
- 影响验证：涉及 `parse_uasset.py`、`ir_builder.py`、`graph/`、`kismet/`、`renderers/` 时运行相关测试目录。
- 质量门禁：大范围解析行为变化后调用或参考 [test-runner](../test-runner/SKILL.md)。

## Boundaries

- 不支持 Cooked 资产图数据恢复；Cooked 资产图数据被剥离时只能报告限制。
- 不修改或写回 `.uasset` 文件。
- 不添加运行时第三方依赖。
- 不使用 `pip install -e .` 安装项目本身。
- 不把临时研究日志放入 skill 目录；放入 `temp/` 或 `.claude/plans/`。

## Common Mistakes

- **只看样本不看源码**：样本能暴露现象，但不能证明字段语义。
- **忽略版本差异**：UE4/UE5 或 custom version 可能改变序列化分支。
- **把 tolerant 当成 silent pass**：容错继续解析时仍需记录 warning、partial 或错误上下文。
- **跨层修复**：不要在 renderer 中弥补 parser 的字段错误；源头解析应先正确。
