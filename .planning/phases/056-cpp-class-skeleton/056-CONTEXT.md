# Phase 56: C++ 类骨架提取 - Context

**Gathered:** 2026-05-18
**Status:** Ready for planning

<domain>
## Phase Boundary

从蓝图 PackageSummary、ExportMap 和组件/变量数据导出完整的 C++ 类声明骨架（.h 头文件），包括继承链、组件 UPROPERTY 和变量 UPROPERTY。输出为结构化 JSON IR，由后续 phase 57-59 逐步填充函数签名、函数体、构造函数。

不涉及：函数签名映射（Phase 57）、函数体翻译（Phase 58）、组件初始化代码生成（Phase 59）。

</domain>

<decisions>
## Implementation Decisions

### 输出格式
- **D-01:** 采用 JSON IR 中间表示，而非直接生成 .h 文本。`cpp_class` JSON 结构包含 `header_meta`、`properties`、`methods`、`constructor` 四个模块化子对象。Phase 56 只填充 `header_meta` 和 `properties`，`methods` 和 `constructor` 留空数组，后续 phase 57-59 分别填充。

### 继承链推导
- **D-02:** 混合策略 — 先在蓝图包内沿 `ClassParent` 字段追溯继承链（利用 v7.0 已实现的 PackageLinker ImportMap 解析），遇到引擎原生类（如 `/Script/Engine.Character`）时用内置路径→C++ 类名映射表转换（`/Script/Engine.Character` → `ACharacter`）。

### 类型映射
- **D-03:** 混合方案 — 核心 UE 类型（`ScriptStruct'CoreUObject.Vector'` → `FVector`，`Class'Engine.SceneComponent'` → `USceneComponent`，基本类型直连）放在硬编码字典中（`cpp_type_mapper.py`）。额外编写一个从 UE 头文件生成扩展映射字典的脚本（`scripts/generate_cpp_types.py`），用于覆盖不常见的类型。

### UPROPERTY 标记推断
- **D-04:** CPF 标志直接映射。CPF 标记与 UPROPERTY 类别有明确对应关系：`CPF_Edit | CPF_BlueprintVisible` → `UPROPERTY(EditAnywhere, BlueprintReadWrite)`，`CPF_InstancedReference` → `Instanced`。v9.0 已有完整的 CPF 标志常量。

### 头文件组织
- **D-05:** 完整 UE 头文件模板 + JSON IR 结构化字段。`header_meta` 包含 `includes[]`（如 `"ParentClass.h"`、`"Engine/SceneComponent.h"`）、`forward_declarations[]`、`pragma_once`、`generated_include`（`#include "MyClass.generated.h"`，必须在最后）。Formatter 将这些字段组装为标准 UE .h 结构。

### JSON IR 结构
- **D-06:** 模块化子结构：
  ```json
  {
    "cpp_class": {
      "name": "ABP_FirstPersonCharacter",
      "parent_class": "ACharacter",
      "header_meta": {
        "pragma_once": true,
        "includes": ["\"Engine/GameFramework/Character.h\""],
        "forward_declarations": [],
        "generated_include": "\"BP_FirstPersonCharacter.generated.h\""
      },
      "properties": [
        {
          "cpp_type": "USceneComponent*",
          "name": "DefaultSceneRoot",
          "uproperty_marks": ["VisibleAnywhere", "BlueprintReadOnly", "Instanced"],
          "category": "component",
          "default_value": null
        }
      ],
      "methods": [],
      "constructor": {
        "component_creations": [],
        "component_assignments": [],
        "default_values": []
      }
    }
  }
  ```
  每个 phase 独立填充一个子对象。

### 测试资产
- **D-07:** Golden-path 集成测试基于 BP_FirstPersonCharacter 的真实导出 JSON（通过 `parse_uasset_with_linker` 从 `.uasset` 文件生成），覆盖组件层次、变量、继承链。额外用 mock JSON 测试边界情况（无变量、单继承、空组件列表）。

### Claude's Discretion
- CPF → UPROPERTY 映射表中不常见的 CPF 组合，由 planner 根据 UE 惯例决定默认标记。
- 类型映射扩展脚本的具体实现方式（解析哪些 UE 头文件、如何提取类型名）。

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目规划
- `.planning/ROADMAP.md` — Phase 56 目标、需求（CPP-01/02/03）、成功标准
- `.planning/STATE.md` — v10.0 里程碑状态和依赖关系

### 参考数据
- `reference/蓝图节点文本参考.md` — BP_FirstPersonCharacter 真实蓝图节点导出（用于理解数据结构）
- `reference/UnrealEditor_uasset加载流程.md` — UE 编辑器加载 .uasset 的完整流程参考（理解 ClassParent、ImportMap/ExportMap 等字段的语义）

### UE 源码参考
- `E:\Develop\lib\UnrealEngine` — Unreal Engine 源码，遇到不确定的序列化行为或 ClassParent 路径语义时可参考引擎源码，**严禁直接读取字节，必须使用 FArchive 流式解析**

### 现有代码
- `src/uasset_read/link/linker.py` — PackageLinker，包内 ClassParent 追溯依赖此模块
- `src/uasset_read/link/object_instance.py` — UObjectInstance，ImportMap 条目解析
- `src/uasset_read/formatters/json_formatter.py` — JSON 格式化模式参考
- `src/uasset_read/constants.py` — CPF_* 标志常量定义（UPROPERTY 映射数据源）
- `src/uasset_read/models/blueprint.py` — BlueprintVariable/Component 数据模型

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `PackageLinker` (link/linker.py) — 已实现 ImportMap/ExportMap 解析和对象图重建，可直接用于 ClassParent 继承链追溯
- `UObjectInstance` (link/object_instance.py) — UObject 外壳模型，包含 `class_path` 字段，可用于推导 C++ 类名
- `CPF_*` 常量 (constants.py) — 已有完整的 Class Property Flags 定义，是 UPROPERTY 映射的直接数据源
- `PropertyTag/PropertyValue` (serializers/property_tags.py) — 属性类型解析，可用于蓝图变量类型→C++ 类型映射
- JSON formatter (formatters/json_formatter.py) — 现有 JSON 输出模式，新的 CPP JSON IR 可复用其结构化输出风格

### Established Patterns
- 管道模式：`.uasset → FArchive → Serializers → Models → Parsers → Formatters`，新模块遵循此模式
- `extract_blueprint_*` 系列函数 (blueprint/__init__.py) — 提取函数命名模式
- `build_*` 系列函数 (graph/__init__.py) — 图构建函数命名模式
- 零运行时依赖，所有类型映射/常量均为 Python 内置数据结构
- **严禁直接读取字节** — 所有 .uasset 解析必须使用 FArchive 流式解析（已有反馈记忆 `feedback-no-byte-reading.md`），UE 源码仅作参考

### Integration Points
- Phase 56 的输出 JSON IR 需要与 Phase 55 的 `function_graphs` 输出兼容，后续 phase 消费同结构
- `parse_uasset_with_linker` (parse_uasset.py) 是主要入口，新的 C++ 骨架提取应作为可选输出步骤集成

</code_context>

<specifics>
## Specific Ideas

- 生成的 JSON IR 应包含 `output_version` 字段（建议从 1.0 开始），与 v9.0 的 `output_version: "5.0"` 区分
- ClassParent 映射表建议放在新的 `cpp_type_mapper.py` 中，格式为字典：`{"/Script/Engine.Character": "ACharacter", "/Script/Engine.Pawn": "APawn", ...}`
- 测试时可能需要从 `E:\Develop\lib\UnrealEngine\Samples\FirstPerson` 获取真实的 `.uasset` 文件

</specifics>

<deferred>
## Deferred Ideas

None — 讨论严格保持在 phase 范围内。

</deferred>

---

*Phase: 56-C++ 类骨架提取*
*Context gathered: 2026-05-18*
