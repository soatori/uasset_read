# Blueprint Analysis - 蓝图分析示例

本文档演示如何使用 uasset_read skill 分析蓝图 EventGraph、变量和组件。

**API版本:** output_version: "3.0" (Phase 14冻结)

---

## 1. EventGraph分析流程

### 1.1 基本分析步骤

**步骤1：解析蓝图获取graphs字段**
**步骤2：遍历graphs_summary查看执行流程**
**步骤3：深入graphs[].nodes查看节点详情**

```python
from uasset_read import parse_uasset, format_json_summary

# 解析蓝图
asset_path = "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"
result = parse_uasset(asset_path)

# 步骤1：检查是否有执行图
if not result.graphs:
    print("未找到EventGraph — 可能是Cooked资产")
else:
    print(f"找到 {len(result.graphs)} 个执行图")
```

### 1.2 执行流程概览

```python
# 步骤2：使用graphs_summary快速查看
output = format_json_summary(result)

for flow in output.get("graphs_summary", []):
    print(f"图名称: {flow['graph_name']}")

    for exec_flow in flow["execution_flows"]:
        func_name = exec_flow["function_name"]
        params = exec_flow["params"]

        print(f"  函数: {func_name}")
        if params:
            param_types = [p["type"] for p in params]
            print(f"  参数: {param_types}")
```

### 1.3 深入节点分析

```python
# 步骤3：深入分析节点
for graph in result.graphs:
    if graph.graph_name == "EventGraph":
        print(f"EventGraph节点数: {len(graph.nodes)}")

        for node in graph.nodes:
            # 检查节点类型
            if node.node_type == "K2Node_Event":
                print(f"  事件节点: {node.node_name}")
                print(f"    类型: {node.node_type}")

            elif node.node_type == "K2Node_CallFunction":
                print(f"  函数调用: {node.node_name}")
```

---

## 2. 节点分析示例

### 2.1 分析事件节点

```python
from uasset_read import parse_uasset

result = parse_uasset("BP_FirstPersonCharacter.uasset")

# 查找所有事件节点
for graph in result.graphs:
    if graph.graph_name == "EventGraph":
        print("=== 事件节点列表 ===")

        for node in graph.nodes:
            if node.node_type == "K2Node_Event":
                # 提取事件信息
                event_name = node.node_name

                # 映射到C++函数
                cpp_map = {
                    "Event BeginPlay": "BeginPlay()",
                    "Event Tick": "Tick(float DeltaTime)",
                    "Event Destroyed": "OnDestroyed()",
                }

                cpp_func = cpp_map.get(event_name, f"{event_name}()")
                print(f"蓝图事件: {event_name} → C++: {cpp_func}")

                # 查找后续执行节点
                for pin in node.pins:
                    if pin.pin_name == "then" and pin.connected_to:
                        print(f"  → 连接到: {pin.connected_to}")
```

### 2.2 分析函数调用节点

```python
# 查找所有函数调用节点
for graph in result.graphs:
    if graph.graph_name == "EventGraph":
        print("=== 函数调用列表 ===")

        call_functions = []
        for node in graph.nodes:
            if node.node_type == "K2Node_CallFunction":
                call_functions.append(node.node_name)

        print(f"函数调用数: {len(call_functions)}")
        for func in call_functions[:10]:
            print(f"  - {func}")
```

### 2.3 分析节点连接关系

```python
def analyze_node_connections(graph):
    """分析节点之间的连接关系"""
    connections = []

    for node in graph.nodes:
        for pin in node.pins:
            if pin.connected_to:
                for target in pin.connected_to:
                    connections.append({
                        "from_node": node.node_name,
                        "from_pin": pin.pin_name,
                        "to": target,
                        "type": pin.pin_type
                    })

    return connections

# 使用示例
for graph in result.graphs:
    if graph.graph_name == "EventGraph":
        connections = analyze_node_connections(graph)

        print(f"连接数: {len(connections)}")
        for conn in connections[:10]:
            print(f"  {conn['from_node']}.{conn['from_pin']} → {conn['to']}")
```

---

## 3. 变量提取示例

### 3.1 从exports提取蓝图变量

```python
from uasset_read import parse_uasset

result = parse_uasset("BP_FirstPersonCharacter.uasset")

# 查找蓝图类导出对象
for export in result.export_map:
    if "BlueprintGeneratedClass" in export.class_name:
        print(f"蓝图类: {export.object_name}")
        print(f"父类: {export.parent_class}")

        # 遍历变量
        if hasattr(export, 'properties') and export.properties:
            for prop in export.properties:
                name = prop.get("name")
                type_ = prop.get("type")
                value = prop.get("value")
                is_comp = prop.get("is_component", False)

                if is_comp:
                    print(f"  [组件] {name}: {type_}")
                else:
                    print(f"  [变量] {name}: {type_} = {value}")
```

### 3.2 区分组件变量和普通变量

```python
def categorize_variables(result):
    """区分组件变量和普通变量"""
    components = []
    variables = []

    for export in result.export_map:
        if "BlueprintGeneratedClass" in export.class_name:
            for prop in getattr(export, 'properties', []):
                item = {
                    "name": prop.get("name"),
                    "type": prop.get("type"),
                    "value": prop.get("value")
                }

                if prop.get("is_component"):
                    components.append(item)
                else:
                    variables.append(item)

    return components, variables

# 使用示例
components, variables = categorize_variables(result)

print(f"组件变量 ({len(components)}):")
for comp in components:
    print(f"  - {comp['name']}: {comp['type']}")

print(f"\n普通变量 ({len(variables)}):")
for var in variables:
    print(f"  - {var['name']}: {var['type']} = {var['value']}")
```

### 3.3 读取变量默认值

```python
# 检查变量默认值类型
for export in result.export_map:
    if "BlueprintGeneratedClass" in export.class_name:
        for prop in getattr(export, 'properties', []):
            name = prop.get("name")
            value = prop.get("value")

            if value is None:
                print(f"变量 '{name}' 无默认值或不可解析")
            elif isinstance(value, dict):
                print(f"变量 '{name}' 复合值: {value}")
            elif isinstance(value, list):
                print(f"变量 '{name}' 数组值: {len(value)}元素")
            else:
                print(f"变量 '{name}' = {value}")
```

---

## 4. 组件分析示例

### 4.1 查找组件导出对象

```python
from uasset_read import parse_uasset

result = parse_uasset("BP_FirstPersonCharacter.uasset")

# 查找所有组件导出对象
components = []
for export in result.export_map:
    if "Component" in export.class_name:
        components.append(export)

print(f"找到 {len(components)} 个组件:")
for comp in components:
    print(f"  - {comp.object_name} ({comp.class_name})")
```

### 4.2 解析组件transforms

```python
# 解析组件变换属性
for export in result.export_map:
    if "Component" in export.class_name:
        print(f"组件: {export.object_name}")

        # 检查transforms字段
        if hasattr(export, 'transforms') and export.transforms:
            loc = export.transforms.get("RelativeLocation")
            rot = export.transforms.get("RelativeRotation")
            scale = export.transforms.get("RelativeScale3D")

            if loc:
                print(f"  位置: X={loc['X']}, Y={loc['Y']}, Z={loc['Z']}")

            if rot:
                print(f"  旋转: Roll={rot['Roll']}, Pitch={rot['Pitch']}, Yaw={rot['Yaw']}")

            if scale:
                print(f"  缩放: X={scale['X']}, Y={scale['Y']}, Z={scale['Z']}")
```

### 4.3 组件类型分类

```python
def classify_components(result):
    """按类型分类组件"""
    classified = {}

    for export in result.export_map:
        if "Component" in export.class_name:
            comp_type = export.class_name.replace("Component", "")
            if comp_type not in classified:
                classified[comp_type] = []
            classified[comp_type].append(export.object_name)

    return classified

# 使用示例
classified = classify_components(result)

print("组件分类:")
for comp_type, names in classified.items():
    print(f"  {comp_type}: {names}")
```

---

## 5. 完整分析示例

### 5.1 蓝图完整分析函数

```python
#!/usr/bin/env python
"""蓝图完整分析示例"""

from uasset_read import parse_uasset, format_json_summary

def analyze_blueprint(asset_path):
    """完整分析蓝图文件"""
    result = parse_uasset(asset_path)

    if not result.is_success:
        return {"status": "failed", "errors": result.errors}

    analysis = {
        "package_name": result.summary.package_name,
        "exports_count": len(result.export_map),
        "graphs_count": len(result.graphs),
        "components": [],
        "variables": [],
        "execution_flows": []
    }

    # 分析导出对象
    for export in result.export_map:
        if "BlueprintGeneratedClass" in export.class_name:
            analysis["blueprint_class"] = export.object_name
            analysis["parent_class"] = export.parent_class

            # 提取变量
            for prop in getattr(export, 'properties', []):
                if prop.get("is_component"):
                    analysis["components"].append(prop["name"])
                else:
                    analysis["variables"].append({
                        "name": prop["name"],
                        "type": prop["type"],
                        "value": prop.get("value")
                    })

        elif "Component" in export.class_name:
            analysis["components"].append({
                "name": export.object_name,
                "type": export.class_name
            })

    # 分析执行流程
    output = format_json_summary(result)
    for flow in output.get("graphs_summary", []):
        if flow["graph_name"] == "EventGraph":
            for exec_flow in flow["execution_flows"]:
                analysis["execution_flows"].append({
                    "function": exec_flow["function_name"],
                    "params": exec_flow["params"]
                })

    return analysis

# 使用示例
if __name__ == "__main__":
    asset_path = "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"
    analysis = analyze_blueprint(asset_path)

    print(f"蓝图分析报告:")
    print(f"  资产: {analysis['package_name']}")
    print(f"  蓝图类: {analysis.get('blueprint_class', 'N/A')}")
    print(f"  父类: {analysis.get('parent_class', 'N/A')}")
    print(f"  组件数: {len(analysis['components'])}")
    print(f"  变量数: {len(analysis['variables'])}")
    print(f"  执行流程: {len(analysis['execution_flows'])}")
```

### 5.2 输出分析报告

```python
def print_analysis_report(analysis):
    """输出格式化分析报告"""
    print("=" * 50)
    print(f"蓝图分析报告: {analysis['package_name']}")
    print("=" * 50)

    print(f"\n基本信息:")
    print(f"  蓝图类: {analysis.get('blueprint_class', 'N/A')}")
    print(f"  父类: {analysis.get('parent_class', 'N/A')}")
    print(f"  导出对象: {analysis['exports_count']}")
    print(f"  执行图: {analysis['graphs_count']}")

    print(f"\n组件 ({len(analysis['components'])}):")
    for comp in analysis["components"]:
        if isinstance(comp, dict):
            print(f"  - {comp['name']} ({comp['type']})")
        else:
            print(f"  - {comp}")

    print(f"\n变量 ({len(analysis['variables'])}):")
    for var in analysis["variables"]:
        print(f"  - {var['name']}: {var['type']} = {var['value']}")

    print(f"\n执行流程 ({len(analysis['execution_flows'])}):")
    for flow in analysis["execution_flows"]:
        params = [p["type"] for p in flow["params"]]
        param_str = f"({', '.join(params)})" if params else "()"
        print(f"  - {flow['function']}{param_str}")

    print("=" * 50)
```

---

## 6. 参考链接

- **蓝图语义:** [../knowledge/blueprint-semantics.md](../knowledge/blueprint-semantics.md)
- **节点类型:** [../knowledge/node-types.md](../knowledge/node-types.md)
- **常见模式:** [../knowledge/common-patterns.md](../knowledge/common-patterns.md)
- **基础用法:** [basic-usage.md](basic-usage.md)

---

*API版本: output_version: "3.0"*
*Skill: uasset-read*
*最后更新: 2026-05-03*