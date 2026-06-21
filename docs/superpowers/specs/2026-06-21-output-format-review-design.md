# 输出格式精简设计

**日期**: 2026-06-21  
**目标**: JSON 输出精简为 C++ 翻译参考，去掉冗余信息  
**影响范围**: 仅 `json` 和 `markdown` 格式

## 背景

当前 JSON 输出存在以下问题：
- `parent_class` 在每个 export 中重复（与 `blueprint.parent_class` 相同）
- `ue_export_raw` 占 JSON 体积 15-20%，但用户几乎不用
- `diagnostics` 大部分为空，但仍然输出
- `name_map` 占体积 5-10%，用户很少需要
- `resolved_depends_map` 大部分为空数组

## 设计目标

JSON 输出作为 **C++ 翻译参考**，只保留翻译所需的蓝图信息。

## 保留内容

| 数据 | 用途 |
|------|------|
| `summary` | 包信息（名称、类、版本） |
| `exports` | **仅蓝图相关 export**（类名以 `_C` 结尾或有蓝图数据的 export） |
| `blueprint` | 父类、组件、函数、事件 |
| `execution_chains` | 事件执行顺序 |
| `variables` | 变量定义（名称、类型、默认值、标志） |
| `decompiled_functions` | 函数 C++ 实现 |

### 蓝图 Export 定义
- 类名以 `_C` 结尾的 export（如 `BP_Character_C`）
- 或 `graphs` 数组非空的 export

### Export 字段精简
每个 export 保留：
- `object_name`, `object_class`, `serial_size`
- `parent_class`（仅蓝图 export）
- `properties`（仅蓝图相关属性）
- `graphs`（仅蓝图图）

去掉：
- `ue_export_raw`（UE 序列化细节）
- `diagnostics`（调试信息）
- `outer_index_resolved`, `super_index_resolved`（内部链接）

## 去掉内容

| 数据 | 原因 |
|------|------|
| `name_map` | 内部索引，翻译不需要 |
| `imports` | 内部依赖，翻译不需要 |
| `linker` | 内部链接信息 |
| `resolved_depends_map` | 依赖图 |
| `depends_map` | 依赖图 |
| `soft_package_references` | 引用关系 |

## Markdown 同步调整

- 去掉重复的 Linker 小节（summary 已包含）
- 保留完整的蓝图、函数、变量、执行链信息
- Export 表格只显示蓝图 export

## 输出示例

```json
{
  "status": { "status": "success" },
  "summary": {
    "package_name": "/Game/FirstPerson/Blueprints/BP_FirstPersonGameMode",
    "package_class": "",
    "ue_version": "5.x"
  },
  "exports": [
    {
      "object_name": "BP_FirstPersonGameMode_C",
      "object_class": "",
      "serial_size": 1234,
      "parent_class": "/Script/Engine.GameModeBase",
      "properties": [...],
      "graphs": [...]
    }
  ],
  "blueprint": {
    "parent_class": "/Script/Engine.GameModeBase",
    "functions": [...],
    "events": [...],
    "components": [...]
  },
  "execution_chains": [...],
  "variables": [...],
  "decompiled_functions": [...]
}
```

## 实施步骤

1. 修改 `json_renderer.py`，去掉冗余字段
2. 修改 `markdown_renderer.py`，去掉重复 Linker 小节
3. 更新测试用例
4. 更新文档
