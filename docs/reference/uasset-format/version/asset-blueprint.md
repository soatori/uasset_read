# 蓝图资产版本差异

## 概述

蓝图资产 (UBlueprint/UBlueprintGeneratedClass) 在 UE4 演进过程中经历多项格式变更，涉及 Blueprint 变量限制变更、Skeleton 类处理、蓝图编译机制、节点引用机制等变更。本文档汇总蓝图相关关键版本差异。

## 版本差异表格

| 版本号 | 变更描述 | 影响字段/结构 |
|-------|----------|---------------|
| 216 | Blueprint 变量不再强制只读 (VER_UE4_BLUEPRINT_VARS_NOT_READ_ONLY) | 变量访问控制 |
| 225 | Blueprint Skeleton 类临时瞬态化 | SkeletonClass 生命周期 |
| 227 | Blueprint Skeleton 类重新序列化 | SkeletonClass 序列化 |
| 229 | Blueprint 设置复制 | ReplicationSettings |
| 250 | Blueprint Skeleton Archiver 移除 | Skeleton 引用移除 |
| 253 | Blueprint Skeleton Archiver 移除第二次 | Skeleton 引用处理 |
| 256 | Blueprint Skeleton 类瞬态化 | SkeletonClassTransient |
| 323 | Blueprint 输入绑定覆盖 | InputBindingOverrides |
| 349 | Blueprint Actor 变量默认值阻止 | ActorVariableDefault |
| 364 | Blueprint 成员引用 Guid | MemberReference Guid |
| 406 | Blueprint 变量标志修复 | VariableFlags |
| 430 | Blueprint 节点引用 Guid (VER_UE4_K2NODE_REFERENCEGUIDS) | K2Node Guid |
| 466 | Blueprint 生成类组件模板公开 | ComponentTemplatesPublic |
| 477 | Blueprint Actor 组件创建方法 | ActorComponentCreationMethod |
| 521 | Blueprint 事件节点成员引用 | K2Node_Event MemberReference |
| 533 | Blueprint 自定义事件 Const 输入 | CustomEventConstInput |
| 547 | Blueprint 脚本字节码限制禁用 | ScriptBytecodeLimit |
| 563 | Blueprint 复制后节点 Guid | PostDuplicateNodeGuid |
| 577 | Blueprint UMG 样式资产废弃 | UMGStyleAssets |
| 584 | Blueprint 图表交互注释气泡 | InteractiveCommentBubbles |
| 609 | Blueprint 变量引用 Guid | VariableReferenceGuid |
| 621 | Blueprint SCS 存储 AllNodes 数组 | SCS AllNodes |
| 634 | Blueprint 常函数覆盖 Const | ConstFunctionOverrides |
| 669 | Blueprint 函数调参数转换注入 | StructPinConversionNodes |

## UE5 蓝图变更

| 特性 | 说明 |
|------|------|
| Script Serialization Offset | Export 表添加脚本序列化偏移字段 |
| Property Tag Extension | 属性标签扩展支持 |
| OS Sub Object Shadow Serialization | 子对象阴影序列化 |

## 源码引用

| 文件 | 路径 | 说明 |
|------|------|------|
| ObjectVersion.h | Runtime/Core/Public/UObject/ | 版本枚举定义 |
| Blueprint.h | Runtime/Engine/Classes/Engine/ | 蓝图类定义 |
| BlueprintGeneratedClass.h | Runtime/Engine/Classes/Engine/ | 蓝图生成类定义 |

---

*详见版本演进主文档：[ue4-evolution.md](ue4-evolution.md)、[ue5-evolution.md](ue5-evolution.md)*