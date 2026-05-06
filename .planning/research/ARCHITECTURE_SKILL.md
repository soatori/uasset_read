# Skill集成架构

**领域：** Claude Code skill 与 Python uasset_read 工具集成
**研究日期：** 2026-05-03
**里程碑：** v3.0 解析完善 + Skill打包

---

## 执行摘要

**核心问题：** 如何将现有单文件Python解析器（uasset_read.py）封装成Claude Code skill，使AI agent能高效理解和使用蓝图解析能力？

**推荐架构：** 双层架构 —— Python工具层（执行解析）+ Skill知识层（指导使用）。

**关键发现：**

1. **skill不是代码封装，而是知识封装** —— skill提供"如何使用"指导，Python工具提供"实际能力"
2. **现有架构无需大改** —— FArchive管道模式已足够灵活，skill作为独立消费者层
3. **集成点明确** —— `parse_uasset()` API是唯一入口，skill通过标准调用消费结果
4. **构建顺序关键** —— 先完善API输出质量（v3.0 Phase 11-14），再封装skill（Phase 15）

---

## 推荐架构

### 总体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Claude Code Agent                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  用户查询： "分析 BP_Character 的移动逻辑"                            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                       Skill 层（知识指导）                            │   │
│  │  .claude/skills/uasset-read/SKILL.md                                 │   │
│  │  - 触发词匹配：uasset、蓝图解析、蓝图转C++                            │   │
│  │  - 能力定义：能做什么、不能做什么                                     │   │
│  │  - 使用指导：如何调用parse_uasset()、如何解读结果                     │   │
│  │  - 知识库：knowledge/*.md（蓝图语义、节点类型、转换模式）             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    Python 工具层（执行解析）                          │   │
│  │  uasset_read.py                                                       │   │
│  │  - parse_uasset(path) → ParseResult                                   │   │
│  │  - FArchive 管道模式                                                   │   │
│  │  - 分层解析器（Header/NameMap/ImportMap/ExportMap）                   │   │
│  │  - 扩展组件（GraphParser/AdvancedPropParser/DependencyAnalyzer）      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         输出层                                        │   │
│  │  ParseResult → JSON/Text                                              │   │
│  │  - graphs: 蓝图图结构                                                  │   │
│  │  - blueprint: 元数据                                                   │   │
│  │  - exports: 导出对象                                                   │   │
│  │  - dependencies: 依赖图                                               │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    Skill 解读层（语义增强）                           │   │
│  │  knowledge/blueprint-semantics.md                                     │   │
│  │  - 节点语义：K2Node_CallFunction = 函数调用                           │   │
│  │  - 执行流：Event → CallFunction 链路                                  │   │
│  │  - 转换模式：蓝图节点 → C++ 等价代码                                  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                         用户响应                                      │   │
│  │  "BP_Character 的移动逻辑：                                           │   │
│  │   - 输入事件：IA_Move（EnhancedInput）                                │   │
│  │   - 处理函数：Move(Vector2D ActionValue)                             │   │
│  │   - 等价C++：void Move(FVector2D ActionValue) {...}"                 │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 组件边界

### Python 工具层组件（现有）

| 组件 | 职责 | 与谁通信 |
|------|------|----------|
| **FArchive** | 二进制读取、字节序、边界验证 | 文件输入、所有解析器 |
| **ParseResult** | 解析结果容器、错误聚合 | 所有解析器、输出格式化 |
| **read_package_summary** | 文件头解析 | FArchive |
| **read_name_table** | 名称表解析 | FArchive、Summary |
| **read_import_map** | 导入表解析（依赖） | FArchive、Summary、NameMap |
| **read_export_map** | 导出表解析（对象） | FArchive、Summary、NameMap |
| **GraphParser** | 蓝图图解析（Phase 7） | FArchive、ExportMap |
| **AdvancedPropParser** | 高级属性解析（Phase 9） | FArchive、PropertyTag |
| **DependencyAnalyzer** | 依赖图构建（Phase 10） | ImportMap、SoftObjectPaths |
| **OutputFormatter** | JSON/Text输出 | ParseResult |
| **CLI (main)** | 命令行入口 | parse_uasset、OutputFormatter |

### Skill 层组件（新增）

| 组件 | 职责 | 与谁通信 |
|------|------|----------|
| **SKILL.md** | Skill元信息定义、触发词、能力范围 | Claude Code（匹配） |
| **knowledge/blueprint-semantics.md** | 蓝图节点语义解释 | Claude Code（解读） |
| **knowledge/node-types.md** | K2Node类型详解 | Claude Code（解读） |
| **knowledge/cpp-conversion.md** | 蓝图→C++转换模式 | Claude Code（生成建议） |
| **knowledge/common-patterns.md** | Lyra/UE常见蓝图模式 | Claude Code（模式识别） |
| **examples/usage.md** | skill调用示例 | Claude Code（学习） |

---

## 数据流详解

### 流程 1：蓝图分析请求

```
用户查询："分析 BP_FirstPersonCharacter 的射击逻辑"
    ↓
Claude Code 匹配 skill（触发词：蓝图、uasset）
    ↓
skill 提供：
    - 调用指导：parse_uasset('BP_FirstPersonCharacter.uasset')
    - 解读指导：关注 graphs[].nodes 中 EventGraph
    - 转换指导：K2Node_EnhancedInputAction → InputAction 映射
    ↓
Agent 调用 Python：
    from uasset_read import parse_uasset
    result = parse_uasset('path/to/BP_FirstPersonCharacter.uasset')
    ↓
Python 返回 ParseResult：
    {
      "graphs": [
        {
          "graph_name": "EventGraph",
          "nodes": [
            {"class_name": "K2Node_EnhancedInputAction", "input_action": "IA_Fire"},
            {"class_name": "K2Node_CallFunction", "function_name": "Fire"}
          ]
        }
      ]
    }
    ↓
skill 解读结果：
    - IA_Fire 是射击输入动作
    - Fire 函数在 EventGraph 中被调用
    - 等价C++：绑定 IA_Fire 到 Fire()
    ↓
Agent 输出：
    "射击逻辑：
     - 输入：IA_Fire（EnhancedInput Action）
     - 处理：Fire() 函数调用
     - C++参考：在 SetupPlayerInputComponent 中绑定 IA_Fire → Fire"
```

### 流程 2：蓝图转C++请求

```
用户查询："将 BP_Move 转换为C++代码"
    ↓
skill 提供：
    - 转换模式：从 knowledge/cpp-conversion.md
    - 关键步骤：识别 Event → 提取函数调用 → 映射类型 → 生成C++
    ↓
Agent 执行：
    1. parse_uasset('BP_Move.uasset')
    2. 提取 EventGraph nodes
    3. 按 knowledge/cpp-conversion.md 模式转换
    ↓
skill 知识应用：
    - K2Node_Event → 重写函数
    - K2Node_CallFunction → 方法调用
    - K2Node_VariableGet → 成员变量访问
    - FEdGraphPinType → C++类型映射
    ↓
Agent 输出：
    "// C++ 等价代码（参考级别）
    void AMyCharacter::Move(FVector2D ActionValue)
    {
        AddMovementInput(FVector(ActionValue.X, 0.0f, ActionValue.Y));
    }"
```

---

## 集成点详解

### 集成点 1：API调用

**位置：** `parse_uasset()` 函数

**现状：**
```python
# uasset_read.py (line 3864)
def parse_uasset(path: str) -> ParseResult:
    """主入口：解析 .uasset 文件"""
    result = ParseResult()
    archive = FArchive(path)
    result.summary = read_package_summary(archive)
    result.name_map = read_name_table(archive, result.summary)
    result.import_map = read_import_map(archive, result.summary, result.name_map)
    result.export_map = read_export_map(archive, result.summary, result.name_map)
    # ... 蓝图检测、图解析、依赖分析
    return result
```

**skill调用模式：**
```python
# skill 示例调用（不修改现有代码）
from uasset_read import parse_uasset

# 基本用法
result = parse_uasset('path/to/blueprint.uasset')

# 检查解析成功
if result.is_success:
    # 获取蓝图图
    for graph in result.graphs:
        print(f"图：{graph.graph_name}")
        for node in graph.nodes:
            print(f"  节点：{node.node_name} ({node.class_name})")

    # 获取蓝图元数据
    if result.blueprint:
        print(f"父类：{result.blueprint.parent_class}")
        print(f"变量：{result.blueprint.variables}")

# 错误处理
else:
    for error in result.errors:
        print(f"错误：{error}")
```

**无需修改原因：**
- API已足够清晰（ParseResult容器）
- 输出已结构化（graphs、blueprint、exports）
- 错误处理已内置（is_success、errors）
- JSON输出已支持（format_json_full）

### 集成点 2：输出格式

**位置：** `format_json_full()` 函数

**现状：**
```python
# uasset_read.py (line 4269)
def format_json_full(result: ParseResult) -> Dict:
    """完整JSON输出"""
    return {
        "file": result.summary.file_path,
        "name_map": result.name_map[:50],  # 截断避免过长
        "imports": format_exports_list(result),
        "exports": format_exports_list(result),
        "blueprint": format_blueprint_dict(result.blueprint),
        "graphs": format_graphs_json(result.graphs),  # v2.0 新增
        "dependencies": result.dependencies,  # v2.0 新增
    }
```

**skill消费模式：**
```json
{
  "graphs": [
    {
      "graph_name": "EventGraph",
      "nodes": [
        {
          "node_name": "K2Node_EnhancedInputAction_2",
          "class_name": "K2Node_EnhancedInputAction",
          "node_pos": {"x": 2368, "y": -1600},
          "pins": [
            {"pin_name": "Triggered", "pin_type": {"pin_category": "exec"}},
            {"pin_name": "ActionValue", "pin_type": {"pin_category": "struct"}}
          ]
        }
      ]
    }
  ]
}
```

**skill解读关键：**
- `class_name` → 节点类型语义（knowledge/node-types.md）
- `pins[].pin_type` → C++类型映射（knowledge/cpp-conversion.md）
- `node_pos` → 逻辑分组（注释框位置）
- `linked_to` → 执行流追踪

### 集成点 3：错误处理

**位置：** `ParseResult.errors` 字段

**现状：**
```python
# uasset_read.py (line 1045)
class ParseResult:
    errors: List[str] = field(default_factory=list)
    is_success: bool = False
```

**skill处理模式：**
```python
# skill指导错误处理
if not result.is_success:
    # 优雅降级
    if result.partial_result:
        # 使用部分结果
        print("警告：解析不完整，但可使用部分数据")
        print(f"已解析：{len(result.name_map)} 名称")
    else:
        # 完全失败
        print("错误：无法解析文件")
        for err in result.errors:
            print(f"  - {err}")
```

---

## 新组件组织

### 目录结构

```
.claude/skills/uasset-read/
├── SKILL.md                      # Skill主定义（必需）
├── knowledge/                    # 知识库目录
│   ├── blueprint-semantics.md    # 蓝图语义解释
│   ├── node-types.md             # K2Node类型详解
│   ├── pin-type-mapping.md       # PinType → C++类型映射
│   ├── cpp-conversion.md         # 蓝图→C++转换模式
│   ├── common-patterns.md        # UE/Lyra常见蓝图模式
│   └── troubleshooting.md        # 常见问题排查
├── examples/                     # 示例目录
│   ├── basic-usage.md            # 基本用法示例
│   ├── blueprint-analysis.md     # 蓝图分析示例
│   └── cpp-conversion.md         # C++转换示例
└── templates/                    # 模板目录（可选）
    └── cpp-template.md           # C++代码生成模板
```

### SKILL.md 结构（参考 lyra-course）

```markdown
# uasset-read

| 字段 | 值 |
|------|-----|
| Skill 名称 | uasset-read |
| 版本 | v3.0 |
| 分类 | Unreal Engine 蓝图解析 |
| 触发词 | uasset、蓝图解析、蓝图转C++、蓝图分析 |

---

## Skill 说明

### 能做什么

- 解析未烘焙的 .uasset 蓝图文件（无需UE编辑器）
- 提取蓝图图结构（EventGraph、函数图）
- 分析节点执行流（Event → CallFunction 链路）
- 解析蓝图元数据（父类、变量、组件）
- 生成C++转换参考代码（非自动生成，需人工审查）

### 不能做什么

- **不解析cooked资产** —— cooked资产已剥离图数据
- **不修改.uasset文件** —— 仅支持只读解析
- **不自动生成C++代码** —— 输出为参考级别，需人工审查
- **不解析蓝图字节码** —— 仅支持编辑器保存的资产
- **不保证100%转换准确** —— 某些节点需游戏特定知识

---

## Python API

### 主入口

\`\`\`python
from uasset_read import parse_uasset, ParseResult

result = parse_uasset('path/to/blueprint.uasset')
\`\`\`

### 结果结构

\`\`\`python
class ParseResult:
    is_success: bool          # 解析成功标志
    errors: List[str]         # 错误列表
    summary: PackageFileSummary  # 文件头
    name_map: List[str]       # 名称表
    import_map: List[ObjectImport]  # 导入表
    export_map: List[ObjectExport]  # 导出表
    blueprint: BlueprintMetadata    # 蓝图元数据
    graphs: List[UEdGraph]    # 蓝图图（v2.0+）
    dependencies: Dict        # 依赖图（v2.0+）
\`\`\`

### 使用示例

\`\`\`python
# 解析蓝图
result = parse_uasset('BP_Character.uasset')

if result.is_success:
    # 分析EventGraph
    event_graph = next((g for g in result.graphs if g.graph_name == "EventGraph"), None)
    if event_graph:
        for node in event_graph.nodes:
            if node.class_name == "K2Node_CallFunction":
                print(f"调用函数：{node.function_name}")

    # 获取父类
    if result.blueprint:
        print(f"父类：{result.blueprint.parent_class}")
\`\`\`

---

## 知识库索引

| 文档 | 内容 |
|------|------|
| [blueprint-semantics.md](knowledge/blueprint-semantics.md) | 蓝图节点语义解释 |
| [node-types.md](knowledge/node-types.md) | K2Node类型详解 |
| [cpp-conversion.md](knowledge/cpp-conversion.md) | 蓝图→C++转换模式 |
| [common-patterns.md](knowledge/common-patterns.md) | UE常见蓝图模式 |

---

## 使用示例

### 示例1：分析蓝图执行流

> 问：分析 BP_FirstPersonCharacter 的射击逻辑
>
> 步骤：
> 1. 调用 parse_uasset('BP_FirstPersonCharacter.uasset')
> 2. 定位 EventGraph
> 3. 查找 K2Node_EnhancedInputAction（输入动作）
> 4. 追踪 LinkedTo 连接找到函数调用
> 5. 解读节点语义（参考 node-types.md）

### 示例2：生成C++转换参考

> 问：将 BP_Move 转换为C++
>
> 步骤：
> 1. 解析蓝图获取函数图
> 2. 按 cpp-conversion.md 模式转换
> 3. 映射 PinType → C++类型
> 4. 输出参考代码（需人工审查）
```

---

## 构建顺序建议

### Phase依赖图

```
[Phase 11-14: Python工具完善] ──────┐
  ↓                                  │
  Phase 11: ExportMap属性值提取      │
  ↓                                  │
  Phase 12: BlueprintVariables完整   │
  ↓                                  │
  Phase 13: 组件变换属性解析          │
  ↓                                  │
  Phase 14: 输出格式优化             │
  ↓                                  │
[Phase 15: Skill封装] ──────────────┘
  ↓
  Phase 15-A: SKILL.md定义
  ↓
  Phase 15-B: knowledge/知识库编写
  ↓
  Phase 15-C: examples/示例编写
  ↓
  Phase 15-D: 测试skill触发
```

### 为什么这个顺序？

**原因 1：API稳定性**
- skill依赖稳定API输出格式
- Phase 14优化输出格式后再封装skill
- 避免 skill → API → skill 反复调整

**原因 2：知识库依赖实际能力**
- knowledge/cpp-conversion.md 需验证转换模式实际可行
- Phase 12-13完善变量/组件解析后才能编写转换知识
- 避免"理论转换模式"与"实际解析能力"脱节

**原因 3：示例依赖完整功能**
- examples/ 需展示完整能力
- Phase 11-14完成后才能编写真实示例
- 避免"示例无法运行"问题

### Phase 15 子阶段建议

| 子阶段 | 任务 | 依赖 | 输出 |
|--------|------|------|------|
| **15-A** | SKILL.md定义 | Phase 14输出格式 | .claude/skills/uasset-read/SKILL.md |
| **15-B** | knowledge知识库 | Phase 12-13解析能力 | knowledge/*.md（5-6文件） |
| **15-C** | examples示例 | Phase 11-14完整功能 | examples/*.md（3-4文件） |
| **15-D** | skill测试 | 15-A/B/C完成 | 触发词测试、调用测试 |

---

## 组件修改 vs 新增

### 无需修改的现有组件

| 组件 | 原因 |
|------|------|
| **FArchive** | skill不直接调用，API足够 |
| **ParseResult** | 已是良好容器，无需扩展 |
| **parse_uasset()** | 主入口稳定，skill仅消费 |
| **format_json_full()** | 输出格式足够，skill可解读 |
| **GraphParser** | 已实现，skill仅消费结果 |
| **CLI (main)** | skill通过Python API调用，不通过CLI |

### 可能需要微调的组件

| 组件 | 调整 | 原因 |
|------|------|------|
| **__all__ exports** | 确认API导出完整 | skill需导入关键函数 |
| **ParseResult文档** | 增强docstring | skill需理解字段含义 |
| **输出格式文档** | 增加JSON结构说明 | skill需解读输出 |

### 新增组件

| 组件 | 位置 | 职责 |
|------|------|------|
| **SKILL.md** | .claude/skills/uasset-read/ | Skill主定义 |
| **knowledge/** | .claude/skills/uasset-read/knowledge/ | 知识库（5-6文件） |
| **examples/** | .claude/skills/uasset-read/examples/ | 示例（3-4文件） |

---

## 风险与缓解

### 风险 1：skill与Python能力脱节

**问题：** skill声称能力超出Python实际解析范围

**缓解：**
- Phase 15-B 在 Phase 11-14 完成后开始
- 每个knowledge文件验证实际可解析案例
- SKILL.md明确"不能做什么"

### 风险 2：输出格式变化导致skill失效

**问题：** Phase 14调整JSON格式，skill解读规则失效

**缓解：**
- Phase 14冻结输出格式后再启动Phase 15
- 输出格式变更需更新knowledge文档
- 使用 `--json` 输出而非依赖内部结构

### 风险 3：skill知识库过于庞大

**问题：** 知识库文件过多，维护困难

**缓解：**
- 初始仅5-6核心knowledge文件
- 按实际使用频率扩展
- 避免覆盖所有UE节点类型（仅核心节点）

### 风险 4：C++转换模式不准确

**问题：** 转换建议与实际C++不等价

**缓解：**
- knowledge/cpp-conversion.md标注"参考级别"
- 强调"需人工审查"
- 提供验证方法（对比蓝图和C++行为）

---

## 关键设计决策

### 决策 1：skill不调用CLI

**选择：** skill通过Python API调用，不通过命令行

**理由：**
- API更灵活（返回ParseResult对象）
- CLI需要解析stdout文本
- API支持程序化消费结果
- 测试中可直接调用API

**替代方案（未选）：**
```bash
# CLI调用方式（未选）
python uasset_read.py file.uasset --json
# 需解析stdout，不如API直接
```

### 决策 2：knowledge独立于Python代码

**选择：** 知识库以markdown文件形式，不嵌入Python

**理由：**
- Claude Code skill标准格式（参考lyra-course）
- 知识库易于更新（修改markdown）
- 知识库可跨项目复用
- 避免Python代码膨胀

**替代方案（未选）：**
```python
# 嵌入Python方式（未选）
NODE_TYPE_MAPPING = {
    "K2Node_CallFunction": "函数调用...",
}
# 不符合skill标准格式
```

### 决策 3：skill聚焦蓝图解析

**选择：** skill能力范围限定为蓝图解析和C++参考

**理由：**
- uasset_read.py核心能力是蓝图
- 避免"全能skill"维护困难
- 其他资产类型可后续扩展

**超出范围：**
- 材质解析（非蓝图）
- 纹理解析（非蓝图）
- 动画解析（非蓝图）

---

## 来源

- **现有架构**：.planning/research/ARCHITECTURE.md（v2.0）
- **skill示例**：.claude/skills/lyra-course/SKILL.md
- **Python源码**：uasset_read.py（4901行）
- **Claude Code文档**：[docs.anthropic.com](https://docs.anthropic.com/en/docs/claude-code)
- **PROJECT.md**：项目上下文、v3.0需求

---

## 置信度评估

| 区域 | 水平 | 原因 |
|------|------|------|
| 双层架构合理性 | 高 | 参考lyra-course成功模式 |
| 集成点识别 | 高 | 现有API已足够清晰 |
| 组件边界划分 | 高 | skill知识层 vs Python执行层分明 |
| 构建顺序建议 | 高 | 依赖关系明确 |
| knowledge文件列表 | 中 | 初始建议5-6文件，实际可能调整 |
| C++转换准确性 | 中 | 需Phase 11-14验证后确认 |

---

## 下一步行动

### Phase 15启动前检查清单

- [ ] Phase 11 完成：ExportMap属性值提取
- [ ] Phase 12 完成：BlueprintVariables完整提取
- [ ] Phase 13 完成：组件变换属性解析
- [ ] Phase 14 完成：输出格式优化并冻结
- [ ] 验证：至少3个蓝图解析成功案例
- [ ] 验证：C++转换参考至少1个案例可用

### Phase 15实施步骤

1. **创建目录**：`.claude/skills/uasset-read/`
2. **编写SKILL.md**：基于本文架构建议
3. **编写knowledge**：5-6核心文件（先node-types.md）
4. **编写examples**：3-4示例文件
5. **测试触发**：验证skill被正确匹配
6. **测试调用**：验证API调用成功
7. **测试解读**：验证输出正确解读

---

*最后更新：2026-05-03 — v3.0 skill集成架构研究*