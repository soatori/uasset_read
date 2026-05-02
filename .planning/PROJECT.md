# uasset_read

## Current Milestone: v2.0 蓝图图解析

**Goal:** 输出足够详细的 JSON，让 AI agent 能理解蓝图逻辑，可作为 C++ 转换参考

**Target features:**
- 修复导出表解析 bug（OuterIndex 缺失导致解析失败）
- 蓝图图结构解析（节点、引脚、连接、执行流）
- 高级属性类型（Struct、Map、Set、Enum、Text、Delegate）
- 依赖分析（ImportMap + SoftObjectPaths 依赖图）

## 项目简介

Python 工具用于读取 Unreal Engine .uasset 文件，让 AI agent 能直接解析资产内容（尤其是蓝图），避免手动在 UE 编辑器中操作。

## 核心价值

让 AI agent 能直接读取 .uasset 文件内容，无需人工介入 UE 编辑器。

## 需求

### 已验证

- ✓ 能解析 .uasset 文件格式（Phase 1）
- ✓ 提取名称表、导入表、导出表（Phase 1）
- ✓ 解析基本属性类型（Phase 2）
- ✓ 提取蓝图元数据（父类、变量）（Phase 3）
- ✓ 输出 JSON 和文本格式（Phase 4）
- ✓ CLI 工具可用（Phase 4）
- ✓ 安全边界验证（Phase 5）

### 活跃需求

- [ ] 修复导出表 OuterIndex 缺失 bug
- [ ] 解析蓝图图结构（节点类型、引脚、连接）
- [ ] 输出蓝图执行流程（事件图、函数图）
- [ ] 解析 StructProperty 嵌套结构
- [ ] 解析 MapProperty/SetProperty 值
- [ ] 解析 EnumProperty/TextProperty 值
- [ ] 构建 ImportMap + SoftObjectPaths 依赖图
- [ ] 输出可作为 C++ 转换参考的详细 JSON

### 超出范围

- 导出资源文件（纹理、模型等二进制数据）
- 修改/编辑 .uasset 文件
- 实时解析/监控
- UE 编辑器集成

## 背景

### 技术背景
- .uasset 是 Unreal Engine 的资产文件格式
- 包含多种类型：蓝图、材质、纹理、模型、动画等
- 当前项目主要关注蓝图相关的 .uasset

### 源码参考
- 项目内有部分 UE 源码：`UnrealEngine/` 目录
- UE 5.7 完整源码：`D:/Program Files/Epic Games/Engine/UE_5.7`
- 关键模块：CoreUObject（序列化）、BlueprintRuntime（蓝图）

### 目标用户
- AI agents（主要）
- 开发者（次要）

## 约束

- **语言**: Python —— 用户指定
- **性能**: 不能卡死，需响应及时
- **进度管理**: Git 版本控制
- **源码依赖**: 需要参考 UE 源码理解格式

## 关键决策

| 决策 | 理由 | 结果 |
|------|------|------|
| Python 实现 | 易于 agent 调用，快速原型开发 | — 待定 |
| 参考 UE 源码 | .uasset 格式未公开文档，需要从源码推断 | — 待定 |
| 结构化文本优先 | agent 直接理解，无需二次转换 | — 待定 |

---
*最后更新：2026-05-02 v2.0 里程碑启动*

##演进

本文档在阶段过渡和里程碑边界时演进。

**每次阶段过渡后**（通过 `/gsd-transition`）：
1. 需求失效？ → 移至超出范围并注明原因
2. 需求验证？ → 移至已验证并引用阶段
3. 新需求出现？ → 添加至活跃需求
4. 需记录决策？ → 添加至关键决策
5. "项目简介"仍准确？ → 如有偏离则更新

**每个里程碑后**（通过 `/gsd-complete-milestone`）：
1. 全面审查所有章节
2. 核心价值检查 —— 仍是正确优先级？
3. 审计超出范围 —— 原因仍有效？
4. 用当前状态更新背景