# Blueprint Semantics - 蓝图语义详解

本文档详细解释 Unreal Engine 蓝图系统的核心概念，帮助 AI 正确解读 `parse_uasset()` 输出。

**API版本:** output_version: "3.0" (Phase 14冻结)

---

## 1. 蓝图概述

### 1.1 UE蓝图系统介绍

Unreal Engine 蓝图（Blueprint）是一种可视化脚本系统，允许开发者通过节点连接的方式创建游戏逻辑，无需编写传统代码。蓝图系统基于 UObject 反射机制，提供了完整的类定义、事件处理、变量管理等功能。

**蓝图核心特性：**
- **可视化编辑** — 节点图表示执行流程，连线表示数据流
- **实时编译** — 编辑器即时编译蓝图字节码
- **类继承** — 蓝图可继承 C++ 类或其他蓝图
- **组件集成** — 蓝图类可包含组件（SkeletalMesh、Camera等）

### 1.2 蓝图类型

UE 中主要有两种蓝图类型：

| 类型 | UClass 类型 | 说明 |
|------|-------------|------|
| **UBlueprint** | `Blueprint` | 资产文件，定义蓝图类结构 |
| **BlueprintGeneratedClass** | `BlueprintGeneratedClass` | 运行时生成的类，继承自父类 |

`.uasset` 文件存储 `UBlueprint` 数据，解析后可提取：
- `parent_class` — 父类名称（C++ 或蓝图）
- `variables` — 蓝图定义的变量
- `graphs` — 执行图（EventGraph、函数图等）
- `components` — 组件列表

### 1.3 .uasset文件结构

`.uasset` 文件是 UE 的二进制资产格式，包含：

```
.uasset 文件结构:
├── PackageFileSummary    # 文件头（版本、名称、偏移量）
├── NameMap               # 名称表（所有字符串引用）
├── ImportMap             # 导入表（外部依赖）
├── ExportMap             # 导出表（本资产包含的对象）
│   ├── BlueprintGeneratedClass  # 蓝图类
│   ├── UEdGraph                # 执行图
│   ├── UEdGraphNode            # 节点
│   ├── Components              # 组件对象
│   └── ...
└── PayloadTables         # 数据表
```

**解析示例：**
```python
from uasset_read import parse_uasset

# 解析蓝图文件
result = parse_uasset("BP_FirstPersonCharacter.uasset")

# 检查解析状态
if result.is_success:
    print(f"资产名称: {result.summary.package_name}")
    print(f"导出对象数: {len(result.export_map)}")
else:
    for error in result.errors:
        print(f"错误: {error}")
```

---

## 2. EventGraph执行图

### 2.1 EventGraph概念

**EventGraph（事件图）** 是蓝图的核心执行流程图，采用事件驱动模式。当特定事件发生时（如游戏开始、每帧更新），EventGraph 中对应的节点被触发，执行后续逻辑链。

**EventGraph特点：**
- **事件入口点** — 红色节点表示事件开始（如 Event BeginPlay）
- **执行流连线** — 白色连线表示执行顺序
- **数据流连线** — 其他颜色连线表示数据传递

### 2.2 常见事件节点

| 事件名称 | 触发时机 | C++ 对应函数 |
|----------|----------|--------------|
| `ReceiveBeginPlay` | 游戏开始时 | `BeginPlay()` |
| `ReceiveTick` | 每帧更新 | `Tick(float DeltaTime)` |
| `ReceiveActorBeginOverlap` | 碰撞开始 | `OnActorBeginOverlap()` |
| `ReceiveDestroyed` | 销毁时 | `OnDestroyed()` |
| `ReceiveAnyDamage` | 受到伤害 | `TakeAnyDamage()` |

**JSON映射：**
```json
{
  "graphs_summary": [
    {
      "graph_name": "EventGraph",
      "execution_flows": [
        {
          "function_name": "ReceiveBeginPlay",
          "params": []
        },
        {
          "function_name": "ReceiveTick",
          "params": [{"type": "float"}]
        }
      ]
    }
  ]
}
```

### 2.3 解析EventGraph

使用 `parse_uasset()` 解析 EventGraph：

```python
from uasset_read import parse_uasset, format_json_summary

result = parse_uasset("BP_FirstPersonCharacter.uasset")

# 检查解析成功
if result.is_success:
    # 遍历所有图
    for graph in result.graphs:
        if graph.graph_name == "EventGraph":
            print(f"找到 EventGraph，节点数: {len(graph.nodes)}")

            # 遍历节点
            for node in graph.nodes:
                print(f"节点: {node.node_name}")
                print(f"类型: {node.node_type}")

                # 检查是否是事件节点
                if node.node_type == "K2Node_Event":
                    print("  → 这是事件入口点")

# 获取执行流程概览
output = format_json_summary(result)
for flow in output.get("graphs_summary", []):
    print(f"图名称: {flow['graph_name']}")
    for exec_flow in flow["execution_flows"]:
        print(f"  函数: {exec_flow['function_name']}")
        print(f"  参数: {exec_flow['params']}")
```

### 2.4 EventGraph→C++函数映射

EventGraph 中的事件节点对应 C++ 的虚函数重写：

| EventGraph节点 | C++函数签名 |
|-----------------|-------------|
| `Event BeginPlay` | `virtual void BeginPlay() override` |
| `Event Tick` | `virtual void Tick(float DeltaTime) override` |
| `Event Destroyed` | `virtual void OnDestroyed() override` |
| `Event Construction Script` | `virtual void OnConstruction(const FTransform& Transform) override` |

**从JSON推导C++函数示例：**
```python
# 从 execution_flows 推导 C++ 函数
for flow in result.graphs_summary[0]["execution_flows"]:
    func_name = flow["function_name"]
    params = flow["params"]

    # 映射到 C++ 函数名
    cpp_func_map = {
        "ReceiveBeginPlay": "void BeginPlay() override",
        "ReceiveTick": "void Tick(float DeltaTime) override",
        "ReceiveDestroyed": "void OnDestroyed() override"
    }

    cpp_signature = cpp_func_map.get(func_name, f"void {func_name}()")
    print(f"蓝图事件: {func_name} → C++: {cpp_signature}")
```

---

## 3. 蓝图变量

### 3.1 变量类型

蓝图变量分为三类：

| 类型 | 说明 | 存储位置 |
|------|------|----------|
| **实例变量** | 类成员变量，每个实例独立 | `exports[].properties[]` |
| **局部变量** | 函数内临时变量 | `graphs[].nodes[]`（VariableSet节点） |
| **组件变量** | 组件引用（如 Mesh） | `exports[].properties[]` + `is_component: true` |

**实例变量特征：**
- 在蓝图编辑器的 "My Blueprint" 面板可见
- 有默认值设置
- 可设置访问权限（Public/Private）
- 可标记为 EditAnywhere/BlueprintReadWrite 等

### 3.2 JSON映射

蓝图变量在 `exports[].properties[]` 中表示：

```json
{
  "exports": [
    {
      "name": "BP_FirstPersonCharacter_C",
      "class": "BlueprintGeneratedClass",
      "parent_class": "FirstPersonCharacter",
      "properties": [
        {
          "name": "Camera",
          "type": "ObjectProperty",
          "value": "SimpleCameraComponent",
          "is_component": true
        },
        {
          "name": "Health",
          "type": "FloatProperty",
          "value": 100.0,
          "is_component": false
        },
        {
          "name": "PlayerName",
          "type": "StrProperty",
          "value": "Player1",
          "is_component": false
        }
      ]
    }
  ]
}
```

### 3.3 is_component字段

`is_component` 字段区分组件变量和普通变量：

| is_component | 含义 | 例子 |
|--------------|------|------|
| `true` | 组件引用变量 | SkeletalMeshComponent、CameraComponent |
| `false` | 普通变量 | Health、PlayerName、bIsAlive |

**解析示例：**
```python
from uasset_read import parse_uasset

result = parse_uasset("BP_FirstPersonCharacter.uasset")

# 遍历导出对象
for export in result.export_map:
    if "BlueprintGeneratedClass" in export.class_name:
        print(f"蓝图类: {export.object_name}")

        # 遍历变量
        for prop in export.properties:
            if prop.get("is_component"):
                print(f"  [组件] {prop['name']}: {prop['type']}")
            else:
                print(f"  [变量] {prop['name']}: {prop['value']}")
```

### 3.4 默认值类型

蓝图变量支持多种默认值类型：

| 蓝图类型 | JSON类型 | 示例值 |
|----------|----------|--------|
| `BoolProperty` | boolean | `true`, `false` |
| `IntProperty` | number | `42`, `-1` |
| `FloatProperty` | number | `100.0`, `3.14` |
| `StrProperty` | string | `"Player1"` |
| `Vector` | object | `{"X": 0, "Y": 0, "Z": 0}` |
| `Rotator` | object | `{"Roll": 0, "Pitch": 0, "Yaw": 0}` |
| `ObjectProperty` | string | `"SkeletalMeshComponent"` |
| `SoftObjectProperty` | string | `"/Game/Assets/MyMesh.MyMesh"` |

### 3.5 变量元数据

蓝图变量可包含元数据标签：

| 标签 | 含义 | C++ 对应 |
|------|------|----------|
| `Category` | 编辑器分类 | `UPROPERTY(Category = "...")` |
| `BlueprintReadWrite` | 蓝图可读写 | `UPROPERTY(BlueprintReadWrite)` |
| `EditAnywhere` | 编辑器可编辑 | `UPROPERTY(EditAnywhere)` |
| `EditDefaultsOnly` | 仅默认值可编辑 | `UPROPERTY(EditDefaultsOnly)` |
| `VisibleAnywhere` | 编辑器可见不可编辑 | `UPROPERTY(VisibleAnywhere)` |

---

## 4. 组件系统

### 4.1 组件概念

**组件（Component）** 是 UE 的模块化设计模式，允许将功能分解为独立模块附加到 Actor。蓝图类通常包含多个组件，每个组件负责特定功能。

**常见组件类型：**

| 组件类型 | 功能 | JSON class字段 |
|----------|------|----------------|
| `SkeletalMeshComponent` | 骨骼模型渲染 | `SkeletalMeshComponent` |
| `StaticMeshComponent` | 静态模型渲染 | `StaticMeshComponent` |
| `CameraComponent` | 相机视角 | `CameraComponent` |
| `AudioComponent` | 音效播放 | `AudioComponent` |
| `CapsuleComponent` | 碰撞检测 | `CapsuleComponent` |
| `MovementComponent` | 移动逻辑 | `CharacterMovementComponent` |

### 4.2 JSON映射

组件在 `exports[]` 数组中作为独立对象存在：

```json
{
  "exports": [
    {
      "name": "CharacterMesh0",
      "class": "SkeletalMeshComponent",
      "parent_class": "SkeletalMeshComponent",
      "transforms": {
        "RelativeLocation": {"X": 0, "Y": 0, "Z": -90},
        "RelativeRotation": {"Roll": 0, "Pitch": 0, "Yaw": 0},
        "RelativeScale3D": {"X": 1.0, "Y": 1.0, "Z": 1.0}
      },
      "properties": [
        {
          "name": "SkeletalMesh",
          "type": "SoftObjectProperty",
          "value": "/Game/Characters/Mannequin/Character/Mesh/SK_Mannequin.SK_Mannequin"
        },
        {
          "name": "AnimClass",
          "type": "SoftObjectProperty",
          "value": "/Game/Characters/Mannequin/Animations/ABP_Mannequin.ABP_Mannequin_C"
        }
      ]
    },
    {
      "name": "FirstPersonCameraComponent",
      "class": "CameraComponent",
      "transforms": {
        "RelativeLocation": {"X": 0, "Y": 0, "Z": 64}
      }
    }
  ]
}
```

### 4.3 transforms字段

组件的变换属性（相对父物体的位置/旋转/缩放）存储在 `transforms` 字段：

| 字段 | 含义 | 格式 |
|------|------|------|
| `RelativeLocation` | 相对位置（厘米） | `{"X": number, "Y": number, "Z": number}` |
| `RelativeRotation` | 相对旋转（度数） | `{"Roll": number, "Pitch": number, "Yaw": number}` |
| `RelativeScale3D` | 相对缩放 | `{"X": number, "Y": number, "Z": number}` |

**解析组件变换：**
```python
from uasset_read import parse_uasset

result = parse_uasset("BP_FirstPersonCharacter.uasset")

# 查找组件导出对象
for export in result.export_map:
    if "Component" in export.class_name:
        print(f"组件: {export.object_name}")

        # 获取变换
        transforms = export.transforms
        if transforms:
            loc = transforms.get("RelativeLocation")
            if loc:
                print(f"  位置: X={loc['X']}, Y={loc['Y']}, Z={loc['Z']}")

            rot = transforms.get("RelativeRotation")
            if rot:
                print(f"  旋转: Roll={rot['Roll']}, Pitch={rot['Pitch']}, Yaw={rot['Yaw']}")

            scale = transforms.get("RelativeScale3D")
            if scale:
                print(f"  缩放: X={scale['X']}, Y={scale['Y']}, Z={scale['Z']}")
```

### 4.4 组件→C++成员映射

蓝图组件对应 C++ 的 `UActorComponent*` 指针成员：

```cpp
// 蓝图组件 → C++ UPROPERTY
UPROPERTY(VisibleAnywhere)
USkeletalMeshComponent* CharacterMesh0;

UPROPERTY(VisibleAnywhere)
UCameraComponent* FirstPersonCameraComponent;

// 变换属性在组件类内部
CharacterMesh0->SetRelativeLocation(FVector(0, 0, -90));
CharacterMesh0->SetRelativeRotation(FRotator(0, 0, 0));
CharacterMesh0->SetRelativeScale3D(FVector(1.0f, 1.0f, 1.0f));
```

---

## 5. JSON字段映射表

### 5.1 顶层字段

| JSON字段 | UE概念 | 说明 |
|----------|--------|------|
| `status.status` | 解析状态 | "success" / "fail" / "error" (JSend style) |
| `output_version` | API版本 | "3.0" — Phase 14冻结 |
| `summary.package_name` | Package名称 | 如 "/Game/Blueprints/BP_Character" |
| `summary.tag` | 文件魔数 | `0x9E2A83C1` (未交换) |
| `graphs_summary` | 执行流程概览 | 顶层字段，无需深入 graphs 数组 |
| `exports` | 导出对象列表 | 蓝图类、组件等对象 |

### 5.2 graphs_summary字段

| 字段 | UE概念 | 说明 |
|------|--------|------|
| `graph_name` | 图名称 | "EventGraph" 或函数图名称 |
| `execution_flows` | 执行流程列表 | 函数调用链 |
| `execution_flows[].function_name` | 函数名 | 如 "ReceiveBeginPlay" |
| `execution_flows[].params` | 参数类型列表 | `[{type: "float"}]` |

### 5.3 exports字段

| 字段 | UE概念 | 说明 |
|------|--------|------|
| `name` | 对象名称 | 如 "BP_Character_C" |
| `class` | UClass类型 | "BlueprintGeneratedClass"、"SkeletalMeshComponent" |
| `parent_class` | 父类名称 | 蓝图继承的基类 |
| `properties` | 属性列表 | 变量、组件引用等 |
| `transforms` | 变换属性 | 仅组件对象有此字段 |

### 5.4 properties字段

| 字段 | UE概念 | 说明 |
|------|--------|------|
| `name` | 变量名 | 如 "Health"、"Camera" |
| `type` | 属性类型 | "FloatProperty"、"ObjectProperty" |
| `value` | 默认值 | 类型依赖（数值/字符串/对象） |
| `is_component` | 是否组件 | `true` 表示组件引用变量 |

### 5.5 transforms字段

| 字段 | UE概念 | 单位 |
|------|--------|------|
| `RelativeLocation.X/Y/Z` | 相对位置 | 厘米（UE单位） |
| `RelativeRotation.Roll/Pitch/Yaw` | 相对旋转 | 度数 |
| `RelativeScale3D.X/Y/Z` | 相对缩放 | 倍数（1.0 = 原始大小） |

---

## 6. 完整解析示例

### 6.1 解析蓝图并提取关键信息

```python
from uasset_read import parse_uasset, format_json_summary, format_markdown

# 解析蓝图文件（使用FirstPerson模板资产）
asset_path = "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"
result = parse_uasset(asset_path)

# 检查解析状态
print(f"解析状态: {result.status.status}")

if result.is_success:
    # 获取基本信息
    print(f"资产名称: {result.summary.package_name}")

    # 遍历导出对象，查找蓝图类
    for export in result.export_map:
        if "BlueprintGeneratedClass" in export.class_name:
            print(f"\n蓝图类: {export.object_name}")
            print(f"父类: {export.parent_class}")

            # 分离组件变量和普通变量
            components = []
            variables = []

            for prop in export.properties:
                if prop.get("is_component"):
                    components.append(prop)
                else:
                    variables.append(prop)

            print(f"\n组件 ({len(components)}):")
            for comp in components:
                print(f"  - {comp['name']}: {comp['type']}")

            print(f"\n变量 ({len(variables)}):")
            for var in variables:
                print(f"  - {var['name']}: {var['value']}")

    # 获取EventGraph执行流程
    print("\n执行流程:")
    output = format_json_summary(result)
    for flow in output.get("graphs_summary", []):
        if flow["graph_name"] == "EventGraph":
            for exec_flow in flow["execution_flows"]:
                print(f"  - {exec_flow['function_name']}({exec_flow['params']})")

else:
    print("解析失败！")
    for error in result.errors:
        print(f"错误: {error}")
```

### 6.2 输出格式选择

```python
from uasset_read import parse_uasset, format_json_full, format_json_summary, format_markdown

result = parse_uasset("BP_FirstPersonCharacter.uasset")

# 完整JSON输出（包含所有字段）
full_output = format_json_full(result)
# 包含: status, output_version, summary, imports, exports, graphs, graphs_summary, errors, ...

# 精简JSON输出（移除imports、errors等，减少70%+ token）
summary_output = format_json_summary(result)
# 仅包含: status, output_version, summary, exports_summary, graphs_summary

# Markdown输出（人类和AI友好）
markdown_output = format_markdown(result)
# 包含: Asset标题、Variables表格、Components表格、Execution Flow Mermaid图
```

---

## 7. 常见问题

### Q1: 为什么看不到EventGraph？

**可能原因：**
1. 资产是 **Cooked** 状态（已烘焙，蓝图数据被剥离）
2. 解析失败（检查 `status.status` 字段）

**解决方案：**
```python
result = parse_uasset("MyBlueprint.uasset")

# 检查状态
if result.status.status == "error":
    print("严重错误，无法解析")
elif result.status.status == "fail":
    print("部分解析失败，可能有部分数据可用")
else:
    # 检查 graphs 字段
    if not result.graphs:
        print("未找到执行图 — 可能是Cooked资产")
    else:
        for graph in result.graphs:
            print(f"图: {graph.graph_name}")
```

### Q2: 如何区分蓝图类和普通UObject？

**判断方法：**
检查 `class` 字段是否包含 `BlueprintGeneratedClass`：

```python
for export in result.export_map:
    if "BlueprintGeneratedClass" in export.class_name:
        print(f"蓝图类: {export.object_name}")
        print(f"父类: {export.parent_class}")
```

### Q3: 变量默认值为什么是None？

**可能原因：**
1. 资产是 **Cooked** 状态
2. 变量类型不支持默认值提取（如复杂对象）
3. 变量未设置默认值

**检查方法：**
```python
for prop in export.properties:
    if prop.get("value") is None:
        print(f"变量 {prop['name']} 无默认值")
        print(f"  类型: {prop['type']}")
```

---

## 8. 参考链接

- **API冻结说明:** Phase 14 VERIFICATION.md — output_version: "3.0"
- **节点类型详解:** [node-types.md](node-types.md)
- **Pin类型映射:** [pin-type-mapping.md](pin-type-mapping.md)
- **蓝图→C++转换:** [cpp-conversion.md](cpp-conversion.md)
- **常见模式:** [common-patterns.md](common-patterns.md)
- **故障排除:** [troubleshooting.md](troubleshooting.md)

---

*API版本: output_version: "3.0"*
*Skill: uasset-read*
*最后更新: 2026-05-03*