# Basic Usage - 基础用法示例

本文档演示 uasset_read skill 的基础用法，包括 CLI 命令和 Python API 调用。

**API版本:** output_version: "3.0" (Phase 14冻结)

---

## 1. CLI基础用法

### 1.1 基础解析命令

```bash
# 解析蓝图文件
python uasset_read.py "E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\FirstPerson\Blueprints\BP_FirstPersonCharacter.uasset"
```

**输出示例：**
```
Asset: /Game/FirstPerson/Blueprints/BP_FirstPersonCharacter
Status: success
Exports: 12 objects
Graphs: 1 (EventGraph)
```

### 1.2 输出格式选项

```bash
# 完整JSON输出
python uasset_read.py "BP_FirstPersonCharacter.uasset" --json

# 精简摘要输出（减少70%+ token）
python uasset_read.py "BP_FirstPersonCharacter.uasset" --summary

# Markdown格式输出
python uasset_read.py "BP_FirstPersonCharacter.uasset" --markdown

# Schema字段描述
python uasset_read.py "BP_FirstPersonCharacter.uasset" --schema
```

### 1.3 输出格式对比

| 格式 | 命令 | 输出大小 | 适用场景 |
|------|------|----------|----------|
| 默认 | 无标志 | ~50行 | 快速查看 |
| JSON | `--json` | 完整输出 | 详细分析 |
| Summary | `--summary` | ~30%大小 | AI交互 |
| Markdown | `--markdown` | 格式化 | 人类阅读 |
| Schema | `--schema` | +描述字段 | 理解含义 |

---

## 2. Python API基础调用

### 2.1 导入和基础调用

```python
from uasset_read import parse_uasset

# 使用FirstPerson模板资产（D-15-04锁定路径）
asset_path = "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"

result = parse_uasset(asset_path)

# 检查解析状态
if result.is_success:
    print(f"解析成功: {result.summary.package_name}")
else:
    for error in result.errors:
        print(f"错误: {error}")
```

### 2.2 结果结构说明

```python
result = parse_uasset("BP_FirstPersonCharacter.uasset")

# 顶层字段
print(f"状态: {result.status.status}")  # success/fail/error
print(f"资产名称: {result.summary.package_name}")
print(f"名称表大小: {len(result.name_map)}")
print(f"导出对象数: {len(result.export_map)}")
print(f"导入依赖数: {len(result.import_map)}")
print(f"执行图数: {len(result.graphs)}")
```

### 2.3 错误处理

```python
from uasset_read import parse_uasset

result = parse_uasset("path/to/file.uasset")

# 状态检查（推荐方式）
if result.status.status == "success":
    # 解析成功，正常处理
    process_blueprint(result)

elif result.status.status == "fail":
    # 部分失败，可能有可用数据
    print("解析部分失败")
    for error in result.errors:
        print(f"  - {error}")
    # 部分数据可能可用
    if result.summary:
        print(f"文件头可用: {result.summary.package_name}")

else:  # error
    # 严重失败
    print("解析严重失败")
    for error in result.errors:
        print(f"  - {error}")
```

---

## 3. 输出格式选择

### 3.1 format_json_full

完整JSON输出，包含所有字段：

```python
from uasset_read import parse_uasset, format_json_full

result = parse_uasset("BP_FirstPersonCharacter.uasset")
full_output = format_json_full(result)

# 包含所有字段
print(full_output.keys())
# ['status', 'output_version', 'summary', 'imports', 'exports', 
#  'graphs', 'graphs_summary', 'errors', 'soft_references', ...]
```

### 3.2 format_json_summary

精简JSON输出，移除非必要字段（减少70%+ token）：

```python
from uasset_read import parse_uasset, format_json_summary

result = parse_uasset("BP_FirstPersonCharacter.uasset")
summary_output = format_json_summary(result)

# 仅包含核心字段
print(summary_output.keys())
# ['status', 'output_version', 'version', 'package_name', 
#  'exports_summary', 'graphs_summary']
```

**移除的字段：**
- `imports` — 导入依赖详情
- `soft_references` — 软引用列表
- `circular_deps` — 循环依赖
- `errors` — 错误详情（仅status保留）
- `exports[].properties` — 仅保留name/class/parent_class

### 3.3 format_markdown

Markdown格式输出，人类和AI友好：

```python
from uasset_read import parse_uasset, format_markdown

result = parse_uasset("BP_FirstPersonCharacter.uasset")
markdown_output = format_markdown(result)

print(markdown_output[:500])
# 输出：
# # Asset: BP_FirstPersonCharacter
# 
# ## Summary
# - Package: /Game/FirstPerson/Blueprints/BP_FirstPersonCharacter
# - Status: success
# 
# ## Variables
# | Name | Type | Default |
# |------|------|---------|
# ...
```

### 3.4 格式选择指南

| 场景 | 推荐格式 | 原因 |
|------|----------|------|
| AI分析蓝图结构 | `format_json_summary` | Token效率高 |
| 详细属性分析 | `format_json_full` | 包含完整properties |
| 人类阅读报告 | `format_markdown` | 格式友好 |
| 调试解析问题 | `format_json_full` | 包含errors字段 |

---

## 4. 字段快速参考

### 4.1 status字段

| 状态 | 含义 | 处理建议 |
|------|------|----------|
| `success` | 解析成功，无错误 | 正常使用 |
| `fail` | 有错误，部分数据可用 | 检查errors，使用可用部分 |
| `error` | 严重错误，无法解析 | 检查资产有效性 |

### 4.2 output_version字段

```json
{
  "output_version": "3.0"
}
```

**含义：** API版本锁定（Phase 14冻结），后续skill可依赖稳定字段。

### 4.3 graphs_summary字段

```json
{
  "graphs_summary": [
    {
      "graph_name": "EventGraph",
      "execution_flows": [
        {
          "function_name": "ReceiveBeginPlay",
          "params": []
        }
      ]
    }
  ]
}
```

**用途：** 快速查看执行流程，无需深入graphs数组。

### 4.4 exports字段

```json
{
  "exports": [
    {
      "name": "BP_Character_C",
      "class": "BlueprintGeneratedClass",
      "parent_class": "ACharacter",
      "properties": [...]
    }
  ]
}
```

**用途：** 查看蓝图类、组件等导出对象。

---

## 5. 完整示例代码

### 5.1 解析并输出基本信息

```python
#!/usr/bin/env python
"""基础解析示例"""

from uasset_read import parse_uasset, format_json_summary

# 测试资产路径（FirstPerson模板）
ASSET_PATH = "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"

def main():
    result = parse_uasset(ASSET_PATH)

    if not result.is_success:
        print("解析失败！")
        for error in result.errors:
            print(f"  错误: {error}")
        return

    # 基本信息
    print(f"资产名称: {result.summary.package_name}")
    print(f"解析状态: {result.status.status}")

    # 导出对象统计
    print(f"\n导出对象 ({len(result.export_map)}):")
    for export in result.export_map[:5]:
        print(f"  - {export.object_name} ({export.class_name})")

    # 执行流程概览
    output = format_json_summary(result)
    print(f"\n执行流程:")
    for flow in output.get("graphs_summary", []):
        print(f"  图: {flow['graph_name']}")
        for exec_flow in flow["execution_flows"][:3]:
            print(f"    - {exec_flow['function_name']}")

if __name__ == "__main__":
    main()
```

### 5.2 批量解析目录

```python
#!/usr/bin/env python
"""批量解析示例"""

import os
from pathlib import Path
from uasset_read import parse_uasset, format_json_summary

def parse_directory(directory):
    """解析目录中所有.uasset文件"""
    results = []

    for file_path in Path(directory).rglob("*.uasset"):
        result = parse_uasset(str(file_path))

        if result.is_success:
            output = format_json_summary(result)
            results.append({
                "file": file_path.name,
                "package": output["package_name"],
                "exports": len(result.export_map),
                "graphs": len(result.graphs)
            })
        else:
            results.append({
                "file": file_path.name,
                "status": "failed"
            })

    return results

# 使用示例
if __name__ == "__main__":
    blueprint_dir = "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints"
    results = parse_directory(blueprint_dir)

    print(f"解析 {len(results)} 个文件:")
    for r in results[:10]:
        if "status" in r and r["status"] == "failed":
            print(f"  [失败] {r['file']}")
        else:
            print(f"  {r['file']}: {r['exports']} exports, {r['graphs']} graphs")
```

---

## 6. 常见用法速查

| 需求 | 代码 |
|------|------|
| 检查解析成功 | `if result.is_success: ...` |
| 获取资产名称 | `result.summary.package_name` |
| 获取执行流程 | `format_json_summary(result)["graphs_summary"]` |
| 查找蓝图类 | `[e for e in result.export_map if "Blueprint" in e.class_name]` |
| 查找组件 | `[e for e in result.export_map if "Component" in e.class_name]` |
| 状态判断 | `result.status.status in ["success", "fail", "error"]` |

---

## 7. 参考链接

- **蓝图语义详解:** [knowledge/blueprint-semantics.md](../knowledge/blueprint-semantics.md)
- **节点类型参考:** [knowledge/node-types.md](../knowledge/node-types.md)
- **故障排除:** [knowledge/troubleshooting.md](../knowledge/troubleshooting.md)

---

*API版本: output_version: "3.0"*
*Skill: uasset-read*
*测试资产: FirstPerson模板 (UE Samples)*
*最后更新: 2026-05-03*