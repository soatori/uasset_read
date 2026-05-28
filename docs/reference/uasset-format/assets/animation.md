# 动画资产文档

动画资产类型 (UAnimSequence) 相关文档导航。

## 子文档

| 文档 | 内容 | 说明 |
|------|------|------|
| [animation-structure.md](animation-structure.md) | 基础结构 | UAnimSequence 和基类字段、骨骼轨道索引机制 |
| [animation-curves.md](animation-curves.md) | 曲线数据 | FRawCurveTracks、FRichCurve、骨骼索引映射 |
| [animation-notifies.md](animation-notifies.md) | 动画通知 | AnimNotify、AnimNotifyState、触发条件 |
| [animation-version.md](animation-version.md) | 版本差异 | VER_UE4_ANIMATION 版本号、UE5 新增字段 |

## 核心源码

- Runtime/Engine/Classes/Animation/AnimSequence.h — UAnimSequence 定义
- Runtime/Engine/Classes/Animation/AnimSequenceBase.h — 基类定义
- Runtime/Engine/Private/Animation/AnimSequence.cpp — 序列化实现

## 相关文档

- [骨骼网格骨骼层级](skeletal-mesh-skeleton.md) — 骨骼索引机制
- [版本兼容机制](../serialization/version-compatibility.md) — 版本判断流程