---
name: ue-wiki-lookup
description: Use when the agent needs Unreal Engine source-guided knowledge,
  UE architecture explanations, module/class/source-path lookup, editor extension
  points, plugin references, or agent-ready context from the UE wiki.
---

# UE Wiki Lookup

## 触发条件

当用户的问题涉及以下内容时使用此 skill：
- UE 架构、模块、类的解释
- UE 源码路径查询
- UE 编辑器扩展点
- UE 插件参考
- 需要从 wiki 获取上下文后进一步查源码

## 输入

- 用户关于 UE 架构、模块、类、源码路径、编辑器扩展点或插件参考的问题。
- 可选：目标 UE 版本、模块名、类名、函数名或希望检索的源码范围。

## 输出

- 命中的 wiki context pack 摘要、相关源码路径、模块或符号列表。
- 需要进一步源码确认时，给出 CodeGraph 查询结果或建议继续使用 [ue-source-research](../ue-source-research/SKILL.md)。
- 未命中或配置不可用时，明确说明缺失的配置、路径或索引状态。

## 执行步骤

### 1. 解析配置

运行配置发现脚本获取本地 wiki 路径：

```bash
python <skill_dir>/scripts/resolve_uewiki.py
```

输出 JSON 包含 `uewiki_root`、`pack_command`、`query_command` 等。

### 2. Wiki 检索

使用 `pack` 命令获取 agent-ready context pack：

```bash
python -m tools.uewiki.uewiki pack "<用户问题>" --budget 6000 --json
```

### pack 输出说明

`pack` 命令的 JSON 输出包含以下关键字段：

| 字段 | 说明 |
|---|---|
| `best_matches[*].source_roots` | 命中页面的 UE 源码路径列表 |
| `source_paths` | 所有命中页面的源码路径汇总 |
| `codegraph_project_path` | 推荐的 CodeGraph 项目路径 |
| `suggested_codegraph[*].args.projectPath` | 每个 CodeGraph 建议的具体项目路径 |
| `symbols` | 命中页面的关键符号汇总 |

### 3. 判断是否需要 CodeGraph

根据 pack 输出决定：

| pack 输出特征 | CodeGraph 策略 |
|---|---|
| 包含具体符号名（如 FRDGBuilder） | 使用 L1: `codegraph_search` |
| 架构/流程/扩展点问题 | 通常不需要 CodeGraph |
| 用户明确要求调用链/影响范围 | 使用 L2: `codegraph_callers` |

### 4. CodeGraph 查询（如需要）

根据 pack 输出的 `suggested_codegraph` 执行查询。

**规则**：
- 最多 3 次 CodeGraph 调用
- 第一次必须是 `search` 或 `node(includeCode=false)`
- 任意一次超时后停止
- 超时后基于 wiki context 回答

### 5. 综合回答

结合 wiki context pack 和 CodeGraph 结果回答用户问题。
引用源码路径时使用 wiki 中的相对路径格式（`Engine/Source/...`）。

## Verification

- 确认 `resolve_uewiki.py` 输出包含可用的 `uewiki_root` 或明确报告配置缺失。
- 引用源码路径时确认路径来自 pack 输出或 CodeGraph 结果，不凭记忆编造。
- 如果 CodeGraph 超时或不可用，在回答中标明只使用了 wiki context。

## Boundaries

- wiki context 只能作为定位和背景材料；涉及 `.uasset` 序列化行为、字段含义或解析器修改时，继续使用 [ue-source-research](../ue-source-research/SKILL.md)。
- 不修改 wiki、UE 源码或本项目解析器文件。
- 不把 pack 输出、查询日志或临时结果写入 skill 目录；需要保存时放入 `temp/`。
