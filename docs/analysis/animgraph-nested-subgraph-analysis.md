# AnimGraph 嵌套子图分析（Issue #178）

## 概述

解析器对标准蓝图图的解析准确率接近 100%，但对动画蓝图（ABP）的 AnimGraph 嵌套子图解析不完整。

## MCP 对比结果

| 蓝图 | 类型 | MCP 图数 | 解析图数 | 匹配率 |
|---|---|---|---|---|
| SandboxCharacter_CMC | 角色 | 24 | 24 | **100%** ✅ |
| SandboxCharacter_Mover | 角色 | 29 | 29 | **96.6%** |
| GM_Sandbox | 游戏模式 | 6 | 6 | **100%** ✅ |
| PC_Sandbox | 玩家控制器 | 3 | 3 | **100%** ✅ |
| SandboxCharacter_CMC_ABP | 动画蓝图 | 101 | 71 | **67.3%** |
| SandboxCharacter_Mover_ABP | 动画蓝图 | 110 | 69 | **60.0%** |

**总计**: 195/273 (71.4%)

## 差异分析

动画蓝图的差异来自 MCP 返回了 AnimGraph 的嵌套子图，例如：

- `AnimGraph.AnimGraphNode_StateMachine_2.State Controller`
- `AnimGraph.AnimGraphNode_StateMachine_2.State Controller.AnimStateNode_0.Idle Loop`
- `AnimGraph.AnimGraphNode_StateMachine_2.State Controller.AnimStateTransitionNode_0.Transition`
- 等状态机节点、过渡节点、混合节点

## 嵌套子图模式

### 1. StateMachine（状态机）
- 包含多个状态（State）
- 每个状态有进入/退出节点
- 状态之间有过渡（Transition）

### 2. Transition（过渡）
- 过渡条件（Transition Result）
- 过渡动画混合

### 3. AnimNode（动画节点）
- 混合空间（BlendSpace）
- 状态机引用
- 骨骼缓存（Bone Cache）

## UE 源码参考

关键源码文件：
- `AnimGraphNode_StateMachine.cpp` — 状态机节点序列化
- `AnimGraphNode_TransitionResult.cpp` — 过渡结果节点
- `AnimGraphNode_BlendListBase.cpp` — 混合列表节点
- `AnimGraph/Classes/AnimNode_StateMachine.h` — 状态机数据结构

## 实现计划

### 阶段 1: 扩展图构建器
- 支持嵌套子图的递归解析
- 识别 StateMachine 节点类型

### 阶段 2: 添加 AnimNode 解析
- 实现 StateMachine 子状态解析
- 实现 Transition 节点解析
- 实现 AnimNode 混合图解析

### 阶段 3: 验证
- 目标：匹配率从 60-67% 提升到 90%+
- 验证资产：SandboxCharacter_CMC_ABP, SandboxCharacter_Mover_ABP

## 当前限制

1. **轻量模式**: export_count > 300 时自动启用，跳过完整蓝图解析
2. **图结构解析**: 仅提取函数入口节点，未解析嵌套子图
3. **变量提取**: 轻量模式下未启用

## 建议

1. 优先实现 StateMachine 嵌套解析（影响最大）
2. 考虑添加动画蓝图专用解析模式
3. 参考 MCP 的 AnimGraph 数据结构设计 IR
