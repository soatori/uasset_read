# BP_FirstPersonCharacter 差异分析与修复计划

## 文档目的

本文档用于整理 `BP_FirstPersonCharacter.uasset` 与以下参考资料之间的差异，并给出可执行的修复计划：

- `references/蓝图节点文本参考.md`
- `references/测试对照C++类/FirstPersonCCharacter.h`
- `references/测试对照C++类/FirstPersonCCharacter.cpp`
- `references/测试对照C++类/BP_FirstPersonCharacter.uasset`

目标不是判断“是否完全一致”，而是明确：

1. 当前解析器已经恢复了哪些结构。
2. 哪些关键信息仍然缺失、错误或不稳定。
3. 应该按什么顺序修复，才能支撑更高质量的蓝图对比、图结构输出和 C++ 翻译。

## 当前事实

基于项目现有解析入口 `parse_uasset_with_linker()` 的实测结果，需要区分两类参考资产：

- 外部样例资产：`E:/Develop/lib/UnrealEngine/Samples/FirstPerson/.../BP_FirstPersonCharacter.uasset`
- 仓库内参考资产：`references/测试对照C++类/BP_FirstPersonCharacter.uasset`

两者都能成功解析，但图规模不同。

外部样例资产结果：

- 解析整体成功：`is_success = True`
- 无硬错误：`errors = 0`
- 存在告警：`warnings = 1`
- 成功恢复 Package / NameMap / ImportMap / ExportMap / Graphs / BlueprintMetadata / Components 的基础结构
- 成功识别父类：`/Script/Engine.Character`
- 成功识别函数图：`Aim`、`Move`、`UserConstructionScript`
- 成功识别图数量：`4`，图名为 `Aim`、`EventGraph`、`Move`、`UserConstructionScript`
- 成功识别组件数量：`6`

仓库内参考资产结果：

- 解析整体成功：`is_success = True`
- 无硬错误：`errors = 0`
- 图数量：`2`，图名为 `EventGraph`、`UserConstructionScript`
- 组件数量：`6`
- EventGraph 中可稳定识别：
  - `DoMove`
  - `DoAim`
  - `DoJumpStart`
  - `DoJumpEnd`
  - `Primary Thumbstick`
  - `Secondary Thumbstick`
  - `Touch Jump Start`
  - `Touch Jump End`

但同时存在以下现象：

- `decompiled_functions = 0`
- 运行中出现大量 `LinkedTo read failed` / `P73-RECOVERY` / `FString ... corrupted`
- `Aim` 触发了 BPGC fallback，但未形成可用反编译结果

## 参考资料与当前解析的一致部分

### 与蓝图节点文本参考一致的部分

- 可以确认该资产确实包含 `K2Node_CallFunction`、`K2Node_EnhancedInputAction`、`K2Node_Event`、`K2Node_FunctionEntry` 等节点类别。
- 可以确认核心输入与行为链路存在：
  - `Jump`
  - `StopJumping`
  - `Move`
  - `Aim`
- 可以确认存在 First Person 模板中的增强输入动作资源路径语义：
  - `IA_Move`
  - `IA_Look`
  - `IA_MouseLook`

### 与 C++ 参考实现一致的部分

- 蓝图父类与 C++ 基类一致：`Character`
- 蓝图和 C++ 都包含相同的核心行为语义：
  - 移动
  - 瞄准/视角输入
  - 起跳
  - 停止跳跃
- 蓝图节点文本中的主链路可以映射到 C++ 中的：
  - `DoMove`
  - `DoAim`
  - `DoJumpStart`
  - `DoJumpEnd`

## 差异与问题清单

### 问题 1：图结构已恢复，但连接语义仍不稳定

现象：

- 图名本身已经可以恢复。
- 但节点整体虽然存在，仍不能稳定生成完整的“图名 -> 节点 -> Pin -> 连接”高置信度结构。

影响：

- 无法对照 `蓝图节点文本参考.md` 做逐节点核验。
- 无法稳定生成高质量图摘要、链式执行流和 N2C 图结构。

初步判断：

- `extract_blueprint_graphs()` 已拿到基本对象。
- 主要缺口更可能在 Pin 连接恢复和后续流构建，而不是图名本身。

### 问题 2：组件名称可读，但组件对照能力仍不完整

现象：

- `components = 6`
- 组件名和组件类已经可读，例如：
  - `First Person Camera`
  - `First Person Mesh`
  - `CharacterMesh0`
  - `CharMoveComp`

影响：

- 虽然可以做基础对照，但仍不能稳定恢复“成员变量语义名 -> 组件实例 -> 附着/变换”的完整映射。
- 无法验证组件树、附着关系和变换属性是否与参考实现一致。

初步判断：

- `extract_components()` 已能恢复基础名称。
- 下一步问题转为：如何恢复更高层的组件语义关系。

### 问题 3：Pin / LinkedTo 恢复依赖容错，稳定性不足

现象：

- 解析时大量出现：
  - `LinkedTo read failed`
  - `P73-RECOVERY`
  - `FString ... corrupted`
- 说明读取 Pin 连接数组时存在错位或恢复逻辑过于激进的问题。

影响：

- 执行流和数据流可能不完整。
- 节点间连接关系可能部分丢失或误判。
- 图结构虽然“可用”，但不能作为精确对照依据。

初步判断：

- 问题更像是图属性序列化边界不稳定，而不是资产本身损坏。
- `LinkedTo`、`SubPins`、字符串字段恢复可能共享同一处偏移管理问题。

### 问题 4：函数元信息只恢复到“存在”，还没有恢复到“可验证”

现象：

- `blueprint.functions` 当前仅稳定识别到：
  - `Aim`
  - `Move`
  - `UserConstructionScript`
- 但没有稳定形成和参考 C++ 一一对应的函数体级结构。

影响：

- 只能判断“函数存在”，不能判断“函数逻辑是否一致”。
- 不能支撑高置信度的蓝图到 C++ 翻译。

初步判断：

- 函数名提取已有基础，但执行流和参数恢复仍受图解析质量限制。

### 问题 5：Kismet fallback 触发了，但结果为空

现象：

- 运行中出现 `Falling back to BPGC bytecode extraction for 'Aim'`
- 但最终 `decompiled_functions = 0`

影响：

- 用户看到 fallback 已发生，但实际上没有产出。
- 这会让“是否成功提取了函数逻辑”变得不透明。

初步判断：

- 当前资产更可能是编辑器态 uncooked 蓝图，不一定适用 BPGC cooked bytecode 提取路径。
- 当前 warning 文案没有把“路径被尝试”和“产出为空”的区别表达清楚。

### 问题 6：测试覆盖偏结构存在性，缺少参考对齐验证

现状：

- 现有测试已经覆盖：
  - `FMemberReference.member_name`
  - Pin 名称/类型基础有效性
  - FunctionEntry 存在性
  - 执行流可追踪性
  - BPGC fallback 路径

不足：

- 没有把 `BP_FirstPersonCharacter` 的参考文本作为金标准做逐项断言。
- 没有把 C++ 对照中的关键函数/组件/输入动作映射固化为验收条件。

影响：

- 当前测试更适合发现“彻底坏掉”，不适合发现“对不上参考”。

## 根因假设

当前问题更可能来自以下组合，而不是单点失败：

### 假设 A：图相关属性的读取边界仍不稳定

- 某些 Pin 字段读取后发生偏移错位。
- 后续 `LinkedTo` / `SubPins` / `FString` 都受到影响。

### 假设 B：名称字段提取和对象绑定路径不完整

- 图、组件、函数等对象已经找到，但缺少从 Export / Property / Linker 对象中恢复稳定显示名的逻辑。

### 假设 C：Kismet 回退路径的适用条件与当前资产类型不匹配

- 当前资产可能没有 cooked bytecode。
- 因此 fallback 被尝试不等于应当产出结果。

### 假设 D：测试策略与“参考对齐”目标不匹配

- 现在的测试在设计上更关注“可解析”，不是“与参考一致”。

## 修复目标

本轮修复应聚焦以下三个目标：

1. 让 `BP_FirstPersonCharacter` 的图、节点、Pin、连接恢复到可对照参考文本的程度。
2. 让组件名、函数名、输入动作名等关键语义字段稳定可读。
3. 把参考资料转化为自动化断言，避免后续回归。

## 分阶段修复计划

### Phase 1：稳定图结构读取

目标：

- 降低 `LinkedTo` / `SubPins` / `FString` 容错恢复的噪声。
- 确认是否存在真实偏移错位。

工作项：

- 审查图解析入口和相关属性读取逻辑。
- 在 `LinkedTo`、`SubPins` 的读取点增加更严格的结构校验。
- 把“低置信度恢复”与“高置信度恢复”区分开，避免误恢复污染后续状态。

优先级：最高

完成标准：

- 针对 `BP_FirstPersonCharacter` 的解析日志中，`LinkedTo read failed` 明显下降。
- 图节点总数、Pin 数量、连接数量稳定，不随小改动波动。

### Phase 2：补齐图与组件的显示名恢复

目标：

- 让图名、组件名、关键节点名可直接用于报告和 diff。

工作项：

- 为 graph 对象恢复稳定 `name`。
- 为组件恢复 `name` 与 `class/type` 的可读输出。
- 校对是否能命中：
  - `EventGraph`
  - `Aim`
  - `Move`
  - `FirstPersonMesh`
  - `FirstPersonCameraComponent`

优先级：最高

完成标准：

- `graphs` 输出中包含可读图名。
- `components` 输出中包含可读组件名。
- 能和参考文档、C++ 参考类做逐项映射。

### Phase 3：提升函数语义恢复质量

目标：

- 让 `Aim`、`Move` 的图级结构可核验。
- 明确 `Jump` / `StopJumping` 处于函数体还是事件图调用链。

工作项：

- 基于现有 `function_graphs` / `execution_flows` 补充函数签名与调用链恢复。
- 检查 `FMemberReference` 与 `FunctionReference.MemberName` 是否覆盖所有关键节点。

优先级：高

完成标准：

- 至少对 `Aim`、`Move` 输出稳定的函数签名和主执行链。
- 能判断与参考 C++ 的关键调用关系是否一致。

### Phase 4：重构 Kismet fallback 的结果表达

目标：

- 明确区分：
  - fallback 已尝试
  - 资产不适用
  - 提取失败
  - 成功提取但反编译为空

工作项：

- 调整 warning 文案和状态记录。
- 对 uncooked 蓝图避免给出误导性“反编译已尝试但无结果”的模糊结论。

优先级：中

完成标准：

- 用户能从结果中明确知道：
  - 当前资产是否适合 BPGC bytecode 路径
  - 空结果是正常情况还是缺陷

### Phase 5：增加参考对齐测试

目标：

- 把“参考资料”转化为验收标准。

建议新增测试：

- 关键图名存在测试
- 关键组件名存在测试
- 关键输入动作存在测试
- `Aim` / `Move` / `Jump` / `StopJumping` 节点存在测试
- 节点连接关键链路测试

优先级：最高

完成标准：

- 测试不再只验证“有节点”，而是验证“命中参考结构”。

## 代码与测试落点

建议优先检查以下位置：

### 解析与后处理

- `src/uasset_read/parse_uasset.py`

关注点：

- `_post_process()`
- `parse_uasset_with_linker()`
- 图提取、蓝图元数据提取、组件提取、Kismet 提取的衔接顺序

### 图解析

- `src/uasset_read/graph/`

关注点：

- `extract_blueprint_graphs()`
- `build_execution_flows()`
- `build_connections_map()`
- `build_function_graphs()`

### 现有图测试

- `tests/test_graph_parser_fix.py`

当前价值：

- 已覆盖 member name、基础 Pin、FunctionEntry、执行流

需要补强：

- 引入基于参考资料的强断言

### Kismet fallback 测试

- `tests/test_kismet_bpgc.py`

当前价值：

- 已验证 cooked UE5 Blueprint 的 BPGC 路径

需要补强：

- 明确 uncooked 资产的预期行为，并把 warning/状态做成可断言结果

## 建议执行顺序

1. 先修图解析边界问题。
2. 再修图名、组件名、函数语义名恢复。
3. 然后补 `BP_FirstPersonCharacter` 参考对齐测试。
4. 最后再处理 Kismet fallback 的状态表达和日志质量。

原因：

- 如果连接和名称本身不稳定，先做 C++ 对照或反编译层修复，收益不高。
- 先把结构层稳定下来，后面的翻译和对照才有可信基础。

## 验收标准

当以下条件同时满足时，可视为本轮修复完成：

- `BP_FirstPersonCharacter` 解析成功且无新增硬错误
- 图名、组件名、关键函数名可读
- 关键输入动作与关键节点可与参考文本对齐
- `LinkedTo` 容错日志显著减少
- 新增的参考对齐测试全部通过
- 对 `decompiled_functions = 0` 的原因有清晰、可断言的状态表达

## 后续产出建议

修复完成后，建议补两类文档：

- 面向开发者：
  - `BP_FirstPersonCharacter` 参考资产专项回归说明
- 面向用户：
  - 当前解析器对蓝图图结构、组件、Kismet 的支持边界说明
