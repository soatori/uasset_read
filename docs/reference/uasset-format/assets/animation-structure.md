# 动画基础结构

## 概述

UAnimSequence 是 UE 引擎中的动画序列资产，存储骨骼动画的帧数据和曲线数据。动画序列定义了骨骼在不同时间点的变换（位置、旋转、缩放），以及用于驱动 Morph Target 和材质参数的曲线数据。

继承关系：
- UAnimationAsset: 动画资产基类
- UAnimSequenceBase: 动画序列基类 (时长、帧率、曲线、通知)
- UAnimSequence: 完整动画序列 (骨骼轨道、压缩数据、叠加设置)

## UAnimSequenceBase 基类字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| SequenceLength | float | 动画时长 (秒) | AnimSequenceBase.h 第 49 行 |
| RawCurveData | FRawCurveTracks | 曲线数据容器 | AnimSequenceBase.h 第 56 行 |
| Notifies | TArray&lt;FAnimNotifyEvent&gt; | 动画通知列表，按时间排序 | AnimSequenceBase.h 第 43 行 |
| RateScale | float | 全局播放速率调整系数 | AnimSequenceBase.h 第 61 行 |
| bLoop | bool | 默认循环行为 | AnimSequenceBase.h 第 68 行 |

说明：
- SequenceLength 和 RawCurveData 在 UE5.0 已废弃，推荐通过 UAnimDataModel 获取数据
- Notifies 数组按时间排序，最早的在前
- RateScale 用于全局调整动画播放速度，1.0 为正常速度

## UAnimSequence 主类字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| AuthoredSyncMarkers | TArray&lt;FAnimSyncMarker&gt; | 同步标记列表 | AnimSequence.h 第 747 行 |
| UniqueMarkerNames | TArray&lt;FName&gt; | 唯一标记名称列表 | AnimSequence.h 第 750 行 |
| BoneCompressionSettings | UAnimBoneCompressionSettings* | 骨骼压缩设置 | AnimSequence.h 第 270 行 |
| CurveCompressionSettings | UAnimCurveCompressionSettings* | 曲线压缩设置 | AnimSequence.h 第 274 行 |
| CompressedData | FCompressedAnimSequence | 压缩动画数据 | AnimSequence.h 第 278 行 |
| AdditiveAnimType | EAdditiveAnimationType | 叠加动画类型 | AnimSequence.h 第 285 行 |
| RefPoseType | EAdditiveBasePoseType | 基础姿态类型 | AnimSequence.h 第 289 行 |
| RefFrameIndex | int32 | 参考帧索引 | AnimSequence.h 第 293 行 |
| RefPoseSeq | UAnimSequence* | 基础姿态动画引用 | AnimSequence.h 第 297 行 |
| RetargetSource | FName | 骨骼重定向源名称 | AnimSequence.h 第 301 行 |
| Interpolation | EAnimInterpolationType | 关键帧插值类型 | AnimSequence.h 第 316 行 |
| bEnableRootMotion | bool | 启用根运动提取 | AnimSequence.h 第 320 行 |
| RootMotionRootLock | ERootMotionRootLock::Type | 根骨骼锁定模式 | AnimSequence.h 第 324 行 |
| PlatformTargetFrameRate | FPerPlatformFrameRate | 平台目标帧率 | AnimSequence.h 第 776 行 |

说明：
- AdditiveAnimType 定义叠加动画类型：AAT_None (无)、AAT_Additive (叠加)、AAT_BasePose (基础姿态)
- RefPoseSeq 用于叠加动画的基础姿态参考
- RetargetSource 用于骨骼重定向时指定基础姿态来源
- Interpolation 定义关键帧间插值方式：线性或步进

## 骨骼轨道索引机制

动画序列通过 FTrackToSkeletonMap 结构将动画轨道映射到骨骼层级。

### FTrackToSkeletonMap 结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| BoneTreeIndex | int32 | 骨骼树索引 | AnimTypes.h 第 827 行 |

说明：
- BoneTreeIndex 指向 USkeleton.BoneTree 中的骨骼索引
- 数组索引对应 RawAnimationData 或 AnimationTracks 的轨道索引
- 压缩数据存储在 CompressedTrackToSkeletonMapTable 中

### 索引映射关系

| 概念 | 说明 |
|------|------|
| TrackIndex | 动画轨道数组索引，对应 RawAnimationData[i] |
| BoneTreeIndex | Skeleton.BoneTree 骨骼树索引 |
| BoneName | 通过 Skeleton.GetBoneName(BoneTreeIndex) 获取 |

映射示例：
- TrackToSkeletonMapTable[0].BoneTreeIndex = 5 表示轨道 0 对应骨骼树中的第 5 个骨骼
- RawAnimationData[0] 存储该骨骼的位置/旋转/缩放关键帧数据

注：骨骼索引机制的完整说明见骨骼网格文档 (skeletal-mesh-skeleton.md)。

## FRawAnimSequenceTrack 原始轨道数据

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| PosKeys | TArray&lt;FVector3f&gt; | 位置关键帧数组 | AnimTypes.h 第 858 行 |
| RotKeys | TArray&lt;FQuat4f&gt; | 旋转关键帧数组 | AnimTypes.h 第 862 行 |
| ScaleKeys | TArray&lt;FVector3f&gt; | 缩放关键帧数组 | AnimTypes.h 第 866 行 |

说明：
- 每个关键帧数组长度相等或与时间数组配合使用
- 数据存储骨骼相对于父骨骼的局部变换
- UE5 使用 FVector3f/FQuat4f (单精度)，UE4 使用 FVector/FQuat

## FRawCurveTracks 曲线数据结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| FloatCurves | TArray&lt;FFloatCurve&gt; | 浮点曲线数组 | AnimCurveTypes.h 第 1074 行 |
| VectorCurves | TArray&lt;FVectorCurve&gt; | 向量曲线数组 (EditorOnly) | AnimCurveTypes.h 第 1082 行 |
| TransformCurves | TArray&lt;FTransformCurve&gt; | 变换曲线数组 (EditorOnly) | AnimCurveTypes.h 第 1088 行 |

说明：
- FloatCurves 用于 Morph Target 权重和材质参数
- VectorCurves 和 TransformCurves 仅在编辑器中使用
- UE5.0 后曲线数据通过 UAnimDataModel 管理

## 同步标记

同步标记用于动画同步系统，标记动画中的重要时间点。

### FAnimSyncMarker 结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| MarkerName | FName | 标记名称 | AnimTypes.h 第 495 行 |
| Time | float | 标记时间 (秒) | AnimTypes.h 第 499 行 |
| TrackIndex | int32 (EditorOnly) | 编辑器轨道索引 | AnimTypes.h 第 504 行 |
| Guid | FGuid (EditorOnly) | 唯一标识符 | AnimTypes.h 第 507 行 |

说明：
- AuthoredSyncMarkers 存储用户创建的同步标记
- UniqueMarkerNames 存储本动画中所有唯一的标记名称
- 同步标记用于多动画同步播放和动画蒙太奇中
- 本文档不展开同步机制的详细实现

## 源码引用

- Runtime/Engine/Classes/Animation/AnimSequence.h — UAnimSequence 定义
- Runtime/Engine/Classes/Animation/AnimSequenceBase.h — UAnimSequenceBase 基类定义
- Runtime/Engine/Public/Animation/AnimTypes.h — FTrackToSkeletonMap, FRawAnimSequenceTrack, FAnimSyncMarker 定义
- Runtime/Engine/Public/Animation/AnimCurveTypes.h — FRawCurveTracks, 曲线类型定义
- Runtime/Engine/Public/Animation/AnimCompressionTypes.h — FCompressedAnimSequence 定义
- Runtime/Engine/Private/Animation/AnimSequence.cpp — 序列化实现

## 版本差异

### UE5 特性

| 特性 | 说明 |
|------|------|
| UAnimDataModel | 数据模型分离，原始数据通过 DataModelInterface 管理 |
| 废弃字段 | SequenceLength, RawCurveData, RawAnimationData 已废弃 |
| 平台帧率 | PlatformTargetFrameRate 支持多平台差异化帧率 |
| 异步压缩 | 支持异步动画压缩缓存 |
| FScopedCompressedAnimSequence | 压缩数据访问的安全作用域 |

### UE4 特性

| 特性 | 说明 |
|------|------|
| 直接数据访问 | SequenceLength, RawCurveData 直接可用 |
| RawAnimationData | 直接存储原始骨骼动画数据 |
| SamplingFrameRate | 固定采样帧率 |
| 同步压缩 | 压缩在保存时同步完成 |

### 废弃字段历史

| 字段 | 废弃版本 | 替代方案 |
|------|----------|----------|
| SequenceLength | UE5.0 | GetPlayLength() 或 UAnimDataController::SetPlayLength |
| RawCurveData | UE5.0 | UAnimDataModel 或 GetCurveData() |
| NumFrames | UE5.0 | UAnimDataModel::GetNumberOfFrames |
| NumberOfKeys | UE5.0 | UAnimDataModel::GetNumberOfKeys |
| SamplingFrameRate | UE5.0 | UAnimDataModel::GetFrameRate |
| RawAnimationData | UE5.0 | FBoneAnimationTrack::InternalTrackData |
| RawDataGuid | UE5.1 | GenerateGuidFromModel |
| AnimationTrackNames | UE5.0 | FBoneAnimationTrack::Name |