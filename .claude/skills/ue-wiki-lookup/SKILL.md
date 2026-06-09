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
