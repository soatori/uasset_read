# 需求：uasset_read

**定义日期：** 2026-04-27
**核心价值：** 让 AI agent 能直接读取 .uasset 文件内容，无需人工介入 UE 编辑器

## v1 需求

### 核心解析

- [x] **CORE-01**: 解析器能读取 .uasset 文件头（PackageFileSummary），包含魔术标签、版本信息和各区块偏移 ✓ Phase 1
- [x] **CORE-02**: 解析器能从魔术标签检测字节序，并在需要时启用字节交换 ✓ Phase 1
- [x] **CORE-03**: 解析器能从 NameOffset/NameCount 提取名称表（NameMap） ✓ Phase 1
- [x] **CORE-04**: 解析器能从 ImportOffset 提取导入表（外部依赖） ✓ Phase 1
- [x] **CORE-05**: 解析器能从 ExportOffset 提取导出表（内部对象） ✓ Phase 1
- [x] **CORE-06**: 解析器能从导出的 ClassIndex 识别资产类型/类别 ✓ Phase 1
- [x] **CORE-07**: 解析器能处理 UE4/UE5 版本号和自定义版本 GUID ✓ Phase 1
- [x] **CORE-08**: 解析器在不支持的版本时能优雅失败并输出清晰错误信息 ✓ Phase 1

### 属性解析

- [x] **PROP-01**: 解析器能读取 PropertyTag 结构（名称、类型、大小、标志） ✓ Phase 2
- [x] **PROP-02**: 解析器能提取 IntProperty 值（int32、int64） ✓ Phase 2
- [x] **PROP-03**: 解析器能提取 FloatProperty 值（float、double） ✓ Phase 2
- [x] **PROP-04**: 解析器能提取 BoolProperty 值 ✓ Phase 2
- [x] **PROP-05**: 解析器能提取 StrProperty 值（带长度前缀的 FString） ✓ Phase 2
- [x] **PROP-06**: 解析器能提取 NameProperty 值（从 NameMap 解析的 FName） ✓ Phase 2
- [x] **PROP-07**: 解析器能提取 ObjectProperty 值（FPackageIndex 引用） ✓ Phase 2
- [x] **PROP-08**: 解析器能提取 ArrayProperty 值（嵌套元素解析） ✓ Phase 2
- [x] **PROP-09**: 解析器能处理 PropertyTag 标志（HasPropertyGuid、HasPropertyExtensions） ✓ Phase 2

### 蓝图提取

- [ ] **BLUE-01**: 解析器能从类名或包路径检测蓝图资产类型
- [ ] **BLUE-02**: 解析器能提取蓝图父类（ParentClass 引用）
- [ ] **BLUE-03**: 解析器能提取蓝图变量定义（FBPVariableDescription：名称、类型、默认值）
- [ ] **BLUE-04**: 解析器能提取蓝图类型（Normal、Interface、MacroLibrary）*（deferred per D-04）*
- [ ] **BLUE-05**: 解析器能从 FEdGraphPinType 解析变量类型
- [ ] **BLUE-06**: 解析器能提取变量元数据（Category、PropertyFlags）

### 输出格式

- [ ] **OUT-01**: 解析器能输出包含完整资产数据的结构化 JSON
- [ ] **OUT-02**: 解析器能输出人类可读的文本摘要
- [ ] **OUT-03**: JSON 输出遵循层级结构（Package → Exports → Properties）
- [ ] **OUT-04**: 输出包含解析后的引用（而非原始索引）
- [ ] **OUT-05**: 输出能优雅处理缺失/未解析数据（null 标记）

### CLI 与执行

- [ ] **CLI-01**: 工具接受单个 .uasset 文件路径作为参数
- [ ] **CLI-02**: 工具支持 --json 标志输出 JSON 格式
- [ ] **CLI-03**: 工具支持 --text 标志输出文本格式
- [ ] **CLI-04**: 工具支持 --summary 标志输出精简格式
- [ ] **CLI-05**: 工具在解析失败时输出错误码和错误信息
- [ ] **CLI-06**: 工具无需外部依赖即可运行（仅使用 Python 标准库）

### 性能与安全

- [ ] **SAFE-01**: 解析器在读取偏移前验证文件大小
- [ ] **SAFE-02**: 解析器在定位前检查偏移边界
- [ ] **SAFE-03**: 解析器对超过 50MB 的文件使用内存映射访问
- [ ] **SAFE-04**: 解析器在可恢复错误时返回部分结果
- [ ] **SAFE-05**: 解析器不会在无效/损坏文件上卡死（设置超时或大小限制）

## v2 需求

推迟到未来版本。已跟踪但不在当前路线图中。

### 蓝图图（高级）

- **GRAPH-01**: 解析器提取蓝图图结构（UEdGraph：Nodes、Schema）
- **GRAPH-02**: 解析器识别节点类型（UK2Node 子类：CallFunction、VariableGet、Event 等）
- **GRAPH-03**: 解析器提取节点引脚（UEdGraphPin：Name、Direction、Type、DefaultValue）
- **GRAPH-04**: 解析器映射引脚连接（LinkedTo 数组 → 源到目标）
- **GRAPH-05**: 解析器生成语义节点描述（"调用函数 X"、"获取变量 Y"）
- **GRAPH-06**: 解析器提取函数图（FunctionGraphs 数组）
- **GRAPH-07**: 解析器提取事件图（UbergraphPages 数组）

### 高级属性

- **ADVP-01**: 解析器提取 StructProperty 值（嵌套结构解析）
- **ADVP-02**: 解析器提取 MapProperty 值（键值对）
- **ADVP-03**: 解析器提取 SetProperty 值（唯一元素集）
- **ADVP-04**: 解析器提取 EnumProperty 值（枚举名 + 值）
- **ADVP-05**: 解析器提取 TextProperty 值（带区域设置的 FText）
- **ADVP-06**: 解析器提取 DelegateProperty 值（函数引用）

### 依赖分析

- **DEPS-01**: 解析器从 ImportMap + SoftObjectPaths 构建完整依赖图
- **DEPS-02**: 解析器输出带包路径的依赖列表
- **DEPS-03**: 解析器识别循环依赖

### 其他资产类型

- **TYPE-01**: 解析器处理材质资产（基本属性提取）
- **TYPE-02**: 解析器处理纹理资产（仅元数据，无二进制数据）
- **TYPE-03**: 解析器处理 .umap 文件（关卡包）

## 超出范围

明确排除。记录以防范围蔓延。

| 功能 | 原因 |
|------|------|
| 二进制资产导出 | 超出 PROJECT.md 范围；纹理/模型是复杂的二进制格式 |
| 资产修改/写入 | 超出 PROJECT.md 范围；仅支持只读解析 |
| 蓝图字节码反编译 | 编译蓝图使用不同格式；专注于编辑器保存的资产 |
| Pak 文件提取 | 不同领域；.pak 是归档格式，非资产格式 |
| 实时解析/监控 | 超出 PROJECT.md 范围；仅支持单文件解析 |
| UE 编辑器集成 | 超出 PROJECT.md 范围；独立 Python 工具 |
| Cooked 资产解析 | Cooked 资产已剥离编辑器数据；使用不同的序列化格式 |
| 资产预览/可视化 | 复杂 UI 工作；AI agent 无需视觉预览 |
| 资产转换/转码 | 不同领域；读取并输出结构，而非转换格式 |
| 自定义属性类型处理器 | 游戏特定自定义类型需要游戏特定知识 |

## 可追溯性

各阶段覆盖的需求。在路线图创建时更新。

| 需求 | 阶段 | 状态 |
|------|------|------|
| CORE-01 | 阶段 1 | 待定 |
| CORE-02 | 阶段 1 | 待定 |
| CORE-03 | 阶段 1 | 待定 |
| CORE-04 | 阶段 1 | 待定 |
| CORE-05 | 阶段 1 | 待定 |
| CORE-06 | 阶段 1 | 待定 |
| CORE-07 | 阶段 1 | 待定 |
| CORE-08 | 阶段 1 | 待定 |
| PROP-01 | 阶段 2 | 待定 |
| PROP-02 | 阶段 2 | 待定 |
| PROP-03 | 阶段 2 | 待定 |
| PROP-04 | 阶段 2 | 待定 |
| PROP-05 | 阶段 2 | 待定 |
| PROP-06 | 阶段 2 | 待定 |
| PROP-07 | 阶段 2 | 待定 |
| PROP-08 | 阶段 2 | 待定 |
| PROP-09 | 阶段 2 | 待定 |
| BLUE-01 | 阶段 3 | 待定 |
| BLUE-02 | 阶段 3 | 待定 |
| BLUE-03 | 阶段 3 | 待定 |
| BLUE-04 | 阶段 3 | 待定 (deferred D-04) |
| BLUE-05 | 阶段 3 | 待定 |
| BLUE-06 | 阶段 3 | 待定 |
| OUT-01 | 阶段 4 | 待定 |
| OUT-02 | 阶段 4 | 待定 |
| OUT-03 | 阶段 4 | 待定 |
| OUT-04 | 阶段 4 | 待定 |
| OUT-05 | 阶段 4 | 待定 |
| CLI-01 | 阶段 4 | 待定 |
| CLI-02 | 阶段 4 | 待定 |
| CLI-03 | 阶段 4 | 待定 |
| CLI-04 | 阶段 4 | 待定 |
| CLI-05 | 阶段 4 | 待定 |
| CLI-06 | 阶段 4 | 待定 |
| SAFE-01 | 阶段 5 | 待定 |
| SAFE-02 | 阶段 5 | 待定 |
| SAFE-03 | 阶段 5 | 待定 |
| SAFE-04 | 阶段 5 | 待定 |
| SAFE-05 | 阶段 5 | 待定 |

**覆盖率：**
- v1 需求总数：37
- 映射到阶段：37
- 未映射：0 ✓

---

*需求定义日期：2026-04-27*
*最后更新：2026-05-01 - BLUE-04 marked deferred per D-04*
