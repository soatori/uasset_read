# 需求：uasset_read v2.0

**定义日期：** 2026-05-02
**核心价值：** 输出足够详细的 JSON，让 AI agent 能理解蓝图逻辑，可作为 C++ 转换参考

## v2.0 需求

### Bug 修复（P0）

- [ ] **BUG-01**: 解析器正确读取 FObjectExport.TemplateIndex 字段（UE4 >= VER_UE4_TemplateIndex_IN_COOKED_EXPORTS）
- [ ] **BUG-02**: 解析器正确读取 FObjectExport.OuterIndex 字段（修复 v1.0 导出表偏移错位）
- [ ] **BUG-03**: 解析器在导出表解析失败时返回清晰错误信息（包含偏移、期望值、实际值）

### 蓝图图结构（P0）

- [ ] **GRAPH-01**: 解析器能识别 UEdGraph 导出类型（ClassIndex 包含 "EdGraph"）
- [ ] **GRAPH-02**: 解析器能提取 UEdGraph 基本信息（Schema、GraphGuid、Nodes 数量）
- [ ] **GRAPH-03**: 解析器能解析 UEdGraphNode 基类字段（NodeGuid、NodePosX/Y、NodeComment、Pins）
- [ ] **GRAPH-04**: 解析器能解析 UEdGraphPin 完整结构（PinId、PinName、Direction、PinType、DefaultValue、LinkedTo、SubPins、ParentPin）
- [ ] **GRAPH-05**: 解析器能识别 K2Node_CallFunction 节点类型并提取 FunctionReference
- [ ] **GRAPH-06**: 解析器能识别 K2Node_Event 节点类型并提取 EventReference
- [ ] **GRAPH-07**: 解析器能识别 K2Node_Knot 节点类型并提取 InputPin/OutputPin 连接
- [ ] **GRAPH-08**: 解析器能识别 EdGraphNode_Comment 注释节点并提取注释文本
- [ ] **GRAPH-09**: 解析器能识别 K2Node_EnhancedInputAction 输入节点并提取 Action 名称
- [ ] **GRAPH-10**: 解析器能构建引脚连接映射（LinkedTo PinId → 目标节点/引脚）
- [ ] **GRAPH-11**: JSON 输出包含蓝图图层级结构（Graph → Nodes → Pins）
- [ ] **GRAPH-12**: JSON 输出包含执行流路径（从 Event → CallFunction 链路）

### 高级属性类型（P1）

- [ ] **ADVP-01**: 解析器能提取 StructProperty 值（嵌套结构体解析，递归深度限制 5）
- [ ] **ADVP-02**: 解析器能提取 MapProperty 值（键值对数组，支持基本类型键）
- [ ] **ADVP-03**: 解析器能提取 SetProperty 值（唯一元素集）
- [ ] **ADVP-04**: 解析器能提取 EnumProperty 值（枚举类型名 + 枚举值名）
- [ ] **ADVP-05**: 解析器能提取 TextProperty 值（FText：Namespace、Key、SourceString）
- [ ] **ADVP-06**: 解析器能提取 DelegateProperty 值（函数引用：对象 + 函数名）

### 依赖分析（P2）

- [ ] **DEPS-01**: 解析器能从 ImportMap 构建依赖列表（包路径、类名、对象名）
- [ ] **DEPS-02**: 解析器能从 SoftObjectPaths 构建软引用依赖列表（AssetReference）
- [ ] **DEPS-03**: 解析器能检测循环依赖（ImportMap 中的相互引用）
- [ ] **DEPS-04**: JSON 输出包含依赖图结构（imports、soft_references、circular_deps）

### 输出格式增强（P1）

- [ ] **OUT2-01**: JSON 输出包含完整的蓝图图数据（与 blueprint 字段同级）
- [ ] **OUT2-02**: JSON 输出包含高级属性解析结果（替换原始字符串值）
- [ ] **OUT2-03**: 文本输出包含图结构摘要（节点数、连接数、执行流概览）
- [ ] **OUT2-04**: CLI 支持 --graph 标志仅输出蓝图图数据

## v3 需求

推迟到未来版本。已跟踪但不在当前路线图中。

### 节点上下文（高级）

- **NODE-01**: 解析器提取节点上下文信息（所属函数、事件图名称）
- **NODE-02**: 解析器生成节点路径追踪（从入口到当前节点的执行路径）
- **NODE-03**: 解析器构建节点依赖倒排索引（变量 → 使用节点列表）

### 蓝图字节码

- **BYTE-01**: 解析器识别 cooked 资产标志（PKG_Cooked = 0x200）
- **BYTE-02**: 解析器解析蓝图字节码（编译后的执行逻辑）

## 超出范围

明确排除。记录以防范围蔓延。

| 功能 | 原因 |
|------|------|
| 自动 C++ 代码生成 | 仅提供参考级别 JSON，不实现自动转换 |
| Cooked 资产解析 | Cooked 资产已剥离图数据；使用不同序列化格式 |
| 蓝图字节码反编译 | 编译蓝图使用字节码格式；专注于编辑器保存的资产 |
| 节点可视化 | 复杂 UI 工作；AI agent 无需视觉预览 |
| 资产修改/写入 | 超出 PROJECT.md 范围；仅支持只读解析 |
| 自定义节点类型处理器 | 游戏特定自定义节点需要游戏特定知识 |

## 可追溯性

v2.0 路线图创建后覆盖的需求。

| 需求 | 阶段 | 状态 |
|------|------|------|
| BUG-01 | Phase 6 | Pending |
| BUG-02 | Phase 6 | Pending |
| BUG-03 | Phase 6 | Pending |
| GRAPH-01 | Phase 7 | Pending |
| GRAPH-02 | Phase 7 | Pending |
| GRAPH-03 | Phase 7 | Pending |
| GRAPH-04 | Phase 7 | Pending |
| GRAPH-05 | Phase 7 | Pending |
| GRAPH-06 | Phase 7 | Pending |
| GRAPH-07 | Phase 7 | Pending |
| GRAPH-08 | Phase 7 | Pending |
| GRAPH-09 | Phase 7 | Pending |
| GRAPH-10 | Phase 7 | Pending |
| GRAPH-11 | Phase 8 | Pending |
| GRAPH-12 | Phase 8 | Pending |
| ADVP-01 | Phase 9 | Pending |
| ADVP-02 | Phase 9 | Pending |
| ADVP-03 | Phase 9 | Pending |
| ADVP-04 | Phase 9 | Pending |
| ADVP-05 | Phase 9 | Pending |
| ADVP-06 | Phase 9 | Pending |
| DEPS-01 | Phase 10 | Pending |
| DEPS-02 | Phase 10 | Pending |
| DEPS-03 | Phase 10 | Pending |
| DEPS-04 | Phase 10 | Pending |
| OUT2-01 | Phase 8 | Pending |
| OUT2-02 | Phase 8 | Pending |
| OUT2-03 | Phase 8 | Pending |
| OUT2-04 | Phase 8 | Pending |

**覆盖率：**
- v2.0 需求总数：29
- 映射到阶段：29
- 未映射：0 ✓

---

*需求定义日期：2026-05-02*
*最后更新：2026-05-02 - v2.0 路线图创建完成*
