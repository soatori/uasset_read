# 动画版本差异

## 概述

动画序列 (UAnimSequence) 结构在 UE4 到 UE5 版本间经历了多次变更，主要通过 VER_UE4_ANIMATION 系列版本号控制序列化兼容性。UE5 引入了 UAnimDataModel 数据模型分离架构，改变了动画数据的存储和访问方式。

版本控制机制：
- EUnrealEngineObjectUE4Version: UE4 版本号，定义在 ObjectVersion.h
- EUnrealEngineObjectUE5Version: UE5 版本号，从 1000 开始
- FPackageFileVersion: 组合版本结构，包含 UE4 和 UE5 两个版本号

## 关键版本号

动画相关的核心版本号定义：

| 版本号 | 用途 | 源码位置 |
|--------|------|----------|
| VER_UE4_REFERENCE_SKELETON_REFACTOR | USkeleton 和 FBoneContainer 改用 FReferenceSkeleton 结构 | ObjectVersion.h 第 309 行 |
| VER_UE4_FIX_ANIMATIONBASEPOSE_SERIALIZATION | 修复叠加动画基础姿态序列化问题 | ObjectVersion.h 第 351 行 |
| VER_UE4_ANIM_SUPPORT_NONUNIFORM_SCALE_ANIMATION | 支持非均匀缩放动画轨道 | ObjectVersion.h 第 358 行 |
| VER_UE4_SKELETON_GUID_SERIALIZATION | 骨骼 GUID 序列化支持 | ObjectVersion.h 第 364 行 |
| VER_UE4_ANIMATION_REMOVE_NANS | 加载时移除动画数据中的 NaN 值 | ObjectVersion.h 第 405 行 |
| VER_UE4_SKELETON_ADD_SMARTNAMES | 骨骼添加 SmartNames 曲线名称映射 | ObjectVersion.h 第 467 行 |
| VER_UE4_ANIMATION_ADD_TRACKCURVES | 添加轨道曲线数据支持 | ObjectVersion.h 第 529 行 |
| VER_UE4_MONTAGE_BRANCHING_POINT_REMOVAL | 移除蒙太奇 BranchingPoint，转换为普通 AnimNotify | ObjectVersion.h 第 530 行 |

说明：
- 版本号按数值递增顺序排列
- 每个版本号对应一次序列化格式的变更
- 加载旧版本资产时通过版本号判断是否需要执行兼容性转换

## UE5 新增字段

UE5 在动画序列中新增了以下字段：

| 字段 | 类型 | 用途 | 源码位置 |
|------|------|------|----------|
| PlatformTargetFrameRate | FPerPlatformFrameRate | 多平台差异化目标帧率 | AnimSequence.h 第 776 行 |
| VariableFrameStrippingSettings | UVariableFrameStrippingSettings* | 可变帧剥离设置 | AnimSequence.h 第 281 行 |
| StripAnimDataOnDedicatedServer | EStripAnimDataOnDedicatedServerSettings | 专用服务器动画数据剥离策略 | AnimSequence.h 第 369 行 |
| bUseNormalizedRootMotionScale | bool | 根运动使用归一化缩放 | AnimSequence.h 第 332 行 |
| bForceRootLock | bool | 强制根骨骼锁定 | AnimSequence.h 第 328 行 |
| bAllowFrameStripping | bool | 允许帧剥离优化 | AnimSequence.h 第 257 行 |
| CompressionErrorThresholdScale | float | 压缩误差阈值缩放因子 | AnimSequence.h 第 265 行 |
| AttributeCurves | TMap&lt;FAnimationAttributeIdentifier, FAttributeCurve&gt; | 自定义属性曲线 | AnimSequence.h 第 799 行 |

说明：
- PlatformTargetFrameRate 支持为不同平台配置不同的目标帧率
- StripAnimDataOnDedicatedServer 用于优化专用服务器内存占用
- AttributeCurves 用于驱动自定义动画属性

## UE4 到 UE5 结构变更

| 变更类型 | 描述 | 影响范围 |
|----------|------|----------|
| 数据模型分离 | 引入 UAnimDataModel，原始数据通过 DataModelInterface 管理 | 数据存储方式 |
| 曲线标识变更 | 曲线从 FSmartName (UID + Name) 改为 FName 标识 | 曲线查找逻辑 |
| 压缩缓存机制 | 支持多平台异步压缩缓存，通过 FIoHash 管理 | 压缩流程 |
| 废弃字段迁移 | NumFrames, SamplingFrameRate, RawAnimationData 废弃 | 数据访问 API |
| 平台帧率支持 | SamplingFrameRate 改为 PlatformTargetFrameRate | 帧率配置 |
| 属性曲线系统 | 新增 AttributeCurves 支持自定义属性动画 | 动画驱动范围 |
| 根运动扩展 | 新增 bUseNormalizedRootMotionScale, bForceRootLock | 根运动提取 |
| 安全访问作用域 | FScopedCompressedAnimSequence 提供线程安全压缩数据访问 | 运行时访问 |

### UAnimDataModel 数据模型

UE5 引入 UAnimDataModel 作为动画数据的统一管理接口：

| 数据类型 | UE4 存储位置 | UE5 存储位置 |
|----------|--------------|--------------|
| 骨骼帧数 | NumFrames | UAnimDataModel::GetNumberOfFrames |
| 采样键数 | NumberOfKeys | UAnimDataModel::GetNumberOfKeys |
| 采样帧率 | SamplingFrameRate | UAnimDataModel::GetFrameRate |
| 原始动画数据 | RawAnimationData | FBoneAnimationTrack::InternalTrackData |
| 曲线数据 | RawCurveData | UAnimDataModel 或 GetCurveData() |
| 轨道名称 | AnimationTrackNames | FBoneAnimationTrack::Name |

说明：
- UE5 中原始数据不再直接存储在 UAnimSequence 中
- 通过 UAnimDataController 进行数据修改
- GetPlayLength() 替代直接访问 SequenceLength

## 废弃字段历史

| 字段 | 废弃版本 | 替代方案 | 源码位置 |
|------|----------|----------|----------|
| NumFrames | UE5.0 | UAnimDataModel::GetNumberOfFrames 或 GetNumberOfSampledKeys | AnimSequence.h 第 217 行 |
| NumberOfKeys | UE5.0 | UAnimDataModel::GetNumberOfKeys 或 GetNumberOfSampledKeys | AnimSequence.h 第 223 行 |
| SamplingFrameRate | UE5.0 | UAnimDataModel::GetFrameRate 或 GetSamplingFrameRate | AnimSequence.h 第 228 行 |
| SequenceLength | UE5.0 | GetPlayLength() 或 UAnimDataController::SetPlayLength | AnimSequenceBase.h 第 49 行 |
| RawAnimationData | UE5.0 | FBoneAnimationTrack::InternalTrackData | AnimSequence.h 第 232 行 |
| AnimationTrackNames | UE5.0 | FBoneAnimationTrack::Name | AnimSequence.h 第 243 行 |
| RawCurveData | UE5.0 | GetCurveData() 或 UAnimDataModel | AnimSequenceBase.h 第 56 行 |
| RawDataGuid | UE5.1 | GenerateGuidFromModel | AnimSequence.h 第 235 行 |
| SourceRawAnimationData_DEPRECATED | UE5.0 | 无替代 (内部使用) | AnimSequence.h 第 249 行 |
| PerBoneCustomAttributeData | UE5.0 | UAnimDataModel::AnimatedBoneAttributes | AnimSequence.h 第 793 行 |
| TargetFrameRate | UE5.6 | PlatformTargetFrameRate.Default | AnimSequence.h 第 780 行 |

说明：
- 废弃字段在编辑器中仍可读取，用于兼容旧版本资产
- 运行时数据访问应使用新 API
- CompressedData 公共访问在 UE5.6 废弃，使用 GetCompressedData()

## 向后兼容处理

加载旧版本动画资产时的兼容性转换：

| 版本号判定 | 兼容性操作 |
|------------|------------|
| VER_UE4_REFERENCE_SKELETON_REFACTOR 之前 | 转换旧骨骼结构为 FReferenceSkeleton |
| VER_UE4_FIX_ANIMATIONBASEPOSE_SERIALIZATION 之前 | 修复基础姿态序列化错误 |
| VER_UE4_ANIM_SUPPORT_NONUNIFORM_SCALE_ANIMATION 之前 | 缩放数据初始化为 FVector(1,1,1) |
| VER_UE4_ANIMATION_REMOVE_NANS 之前 | 检测并移除 NaN 值 |
| VER_UE4_SKELETON_ADD_SMARTNAMES 之前 | 曲线名称转换为 SmartName |
| VER_UE4_ANIMATION_ADD_TRACKCURVES 之前 | 轨道曲线数据初始化 |
| VER_UE4_MONTAGE_BRANCHING_POINT_REMOVAL 之前 | BranchingPoint 转换为 AnimNotify |

兼容性处理流程：
1. 读取 FPackageFileVersion 判断资产版本
2. 根据版本号执行必要的转换
3. 部分废弃字段在加载时忽略并替换为默认值
4. 压缩数据自动重建以匹配当前平台

### 曲线标识转换

UE5.3 曲线标识变更：

| UE4 标识 | UE5 标识 | 说明 |
|----------|----------|------|
| FSmartName (UID + Name) | FName | 曲线标识简化为 FName |
| LastObservedName_DEPRECATED | CurveName | 直接使用 CurveName |
| Name_DEPRECATED | CurveName | 废弃智能名称，使用 FName |

说明：
- FSmartName 包含 UID 和 DisplayName，用于曲线的唯一标识
- UE5.3 简化为直接使用 FName，降低复杂度
- 旧版本曲线数据加载时自动转换

## 版本号使用示例

序列化中的版本判断通过 Ar.UE4Version() 检查版本号，对旧版本执行兼容处理（如 VER_UE4_ANIM_SUPPORT_NONUNIFORM_SCALE_ANIMATION 判断缩放动画支持、VER_UE4_ANIMATION_ADD_TRACKCURVES 判断轨道曲线序列化、VER_UE4_MONTAGE_BRANCHING_POINT_REMOVAL 处理 BranchingPoint 转换）。

说明：
- 版本判断使用 FArchive 的 UE4Version() 或 UE5Version() 方法
- 低于某版本号时执行兼容性转换
- 高于某版本号时使用新格式序列化

## 源码引用

- Runtime/Core/Public/UObject/ObjectVersion.h — 版本号定义，FPackageFileVersion 结构
- Runtime/Engine/Classes/Animation/AnimSequence.h — UAnimSequence 定义，废弃字段声明
- Runtime/Engine/Classes/Animation/AnimSequenceBase.h — UAnimSequenceBase 基类定义
- Runtime/Engine/Private/Animation/AnimSequence.cpp — 序列化实现，版本判断逻辑
- Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp — 加载兼容性处理
- Runtime/Engine/Public/Animation/AnimData/IAnimationDataModel.h — UAnimDataModel 数据模型接口
- Runtime/Engine/Public/Animation/AnimCurveTypes.h — 曲线类型定义，废弃曲线标识

## 版本差异总结

### UE5 动画系统特性

| 特性 | 说明 |
|------|------|
| UAnimDataModel | 数据模型分离，原始数据通过 DataModelInterface 管理 |
| 异步压缩 | 支持异步动画压缩缓存，通过 FAnimSequenceCompilingManager 管理 |
| 多平台缓存 | DataByPlatformKeyHash 存储多平台压缩数据 |
| FScopedCompressedAnimSequence | 压缩数据访问的安全作用域，线程安全 |
| 属性曲线 | AttributeCurves 支持自定义属性动画 |
| 平台帧率 | PlatformTargetFrameRate 支持多平台差异化帧率 |
| 根运动扩展 | bUseNormalizedRootMotionScale, bForceRootLock |
| 曲线标识简化 | FSmartName 改为 FName (UE5.3) |

### UE4 动画系统特性

| 特性 | 说明 |
|------|------|
| 直接数据访问 | NumFrames, RawAnimationData, RawCurveData 直接可用 |
| FSmartName 标识 | 曲线使用 FSmartName (UID + Name) 标识 |
| 同步压缩 | 压缩在保存时同步完成 |
| BranchingPoint | 蒙太奇中使用 BranchingPoint (UE4 早期版本) |
| 固定采样帧率 | SamplingFrameRate 单一帧率配置 |
| TargetFrameRate | 编辑器目标帧率 (非多平台) |