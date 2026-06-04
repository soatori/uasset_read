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

---

# animation-structure.md 修正内容

## UAnimSequenceBase 基类字段表

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Notifies | TArray<FAnimNotifyEvent> | 动画通知列表，按时间排序 | AnimSequenceBase.h 第 43 行 |
| SequenceLength | float | 动画时长 (秒) | AnimSequenceBase.h 第 49 行 |
| RawCurveData | FRawCurveTracks | 曲线数据容器 | AnimSequenceBase.h 第 56 行 |
| RateScale | float | 全局播放速率调整系数 | AnimSequenceBase.h 第 61 行 |
| bLoop | bool | 默认循环行为 | AnimSequenceBase.h 第 68 行 |
| AnimNotifyTracks | TArray<FAnimNotifyTrack> (EditorOnly) | 通知轨道数据 | AnimSequenceBase.h 第 72 行 |

说明：
- SequenceLength、RawCurveData 在 UE5.0 已废弃，推荐通过 UAnimDataModel 获取数据
- Notifies 数组按时间排序，最早的在前
- RateScale 用于全局调整动画播放速度，1.0 为正常速度
- AnimNotifyTracks 仅在编辑器中使用，存储通知的轨道分组信息

## UAnimSequence 主类字段表

### 通用字段 (所有构建)

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| BoneCompressionSettings | TObjectPtr<UAnimBoneCompressionSettings> | 骨骼压缩设置 | AnimSequence.h 第 270 行 |
| CurveCompressionSettings | TObjectPtr<UAnimCurveCompressionSettings> | 曲线压缩设置 | AnimSequence.h 第 274 行 |
| CompressedData | FCompressedAnimSequence | 压缩动画数据 | AnimSequence.h 第 278 行 |
| VariableFrameStrippingSettings | TObjectPtr<UVariableFrameStrippingSettings> | 可变帧剥离设置 | AnimSequence.h 第 281 行 |
| AdditiveAnimType | EAdditiveAnimationType | 叠加动画类型 | AnimSequence.h 第 285 行 |
| RefPoseType | EAdditiveBasePoseType | 基础姿态类型 | AnimSequence.h 第 289 行 |
| RefFrameIndex | int32 | 参考帧索引 | AnimSequence.h 第 293 行 |
| RefPoseSeq | TObjectPtr<UAnimSequence> | 基础姿态动画引用 | AnimSequence.h 第 297 行 |
| RetargetSource | FName | 骨骼重定向源名称 | AnimSequence.h 第 301 行 |
| RetargetSourceAssetReferencePose | TArray<FTransform> | RetargetSourceAsset 的参考姿态变换数据 | AnimSequence.h 第 312 行 |
| Interpolation | EAnimInterpolationType | 关键帧插值类型 | AnimSequence.h 第 316 行 |
| bEnableRootMotion | bool | 启用根运动提取 | AnimSequence.h 第 320 行 |
| RootMotionRootLock | ERootMotionRootLock::Type | 根骨骼锁定模式 | AnimSequence.h 第 324 行 |
| bForceRootLock | bool | 强制根骨骼锁定，即使未启用根运动 | AnimSequence.h 第 328 行 |
| bUseNormalizedRootMotionScale | bool | 根运动使用归一化缩放 FVector(1,1,1) | AnimSequence.h 第 332 行 |
| bRootMotionSettingsCopiedFromMontage | bool | 根运动设置是否从蒙太奇复制 | AnimSequence.h 第 336 行 |
| StripAnimDataOnDedicatedServer | EStripAnimDataOnDedicatedServerSettings | 专用服务器动画数据剥离策略 | AnimSequence.h 第 369 行 |
| PlatformTargetFrameRate | FPerPlatformFrameRate | 平台目标帧率 | AnimSequence.h 第 776 行 |
| AttributeCurves | TMap<FAnimationAttributeIdentifier, FAttributeCurve> | 自定义属性曲线 | AnimSequence.h 第 799 行 |
| AuthoredSyncMarkers | TArray<FAnimSyncMarker> | 同步标记列表 | AnimSequence.h 第 747 行 |
| UniqueMarkerNames | TArray<FName> | 唯一标记名称列表 | AnimSequence.h 第 750 行 |

### EditorOnly 字段 (仅编辑器构建)

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| ImportFileFramerate | float | 导入文件的 DCC 帧率 (UI 显示) | AnimSequence.h 第 209 行 |
| ImportResampleFramerate | int32 | 导入时的重采样帧率 (UI 显示) | AnimSequence.h 第 213 行 |
| NumFrames | int32 | 骨骼帧数 (UE5.0 废弃) | AnimSequence.h 第 219 行 |
| NumberOfKeys | int32 | 采样键数 (UE5.0 废弃) | AnimSequence.h 第 224 行 |
| SamplingFrameRate | FFrameRate | 采样帧率 (UE5.0 废弃) | AnimSequence.h 第 229 行 |
| RawAnimationData | TArray<FRawAnimSequenceTrack> | 原始骨骼动画数据 (UE5.0 废弃) | AnimSequence.h 第 232 行 |
| RawDataGuid | FGuid | 原始数据 GUID (UE5.1 废弃) | AnimSequence.h 第 237 行 |
| AnimationTrackNames | TArray<FName> | 动画轨道名称 (UE5.0 废弃) | AnimSequence.h 第 244 行 |
| SourceRawAnimationData_DEPRECATED | TArray<FRawAnimSequenceTrack> | 源原始动画数据 (内部使用) | AnimSequence.h 第 249 行 |
| bAllowFrameStripping | bool | 允许帧剥离优化 | AnimSequence.h 第 257 行 |
| CompressionErrorThresholdScale | float | 压缩误差阈值缩放因子 | AnimSequence.h 第 265 行 |
| RetargetSourceAsset | TSoftObjectPtr<USkeletalMesh> | 重定向源骨骼网格 (UE5.5 废弃) | AnimSequence.h 第 307 行 |
| CompressCommandletVersion | int32 | CompressAnimations 命令行工具版本号 | AnimSequence.h 第 341 行 |
| bDoNotOverrideCompression | uint32:1 | 不允许覆盖压缩方案 | AnimSequence.h 第 348 行 |
| AssetImportData | TObjectPtr<UAssetImportData> | 资产导入数据和选项 | AnimSequence.h 第 352 行 |
| SourceFilePath_DEPRECATED | FString | 源文件路径 (废弃) | AnimSequence.h 第 357 行 |
| SourceFileTimestamp_DEPRECATED | FString | 源文件时间戳 (废弃) | AnimSequence.h 第 361 行 |
| TargetFrameRate | FFrameRate | 编辑器目标帧率 | AnimSequence.h 第 780 行 |
| NumberOfSampledKeys | int32 | 采样键数 (运行时) | AnimSequence.h 第 783 行 |
| NumberOfSampledFrames | int32 | 采样帧数 (运行时) | AnimSequence.h 第 786 行 |
| bBlockCompressionRequests | bool | 阻止压缩请求 | AnimSequence.h 第 788 行 |
| PerBoneCustomAttributeData | TArray<FCustomAttributePerBoneData> | 每骨骼自定义属性数据 (UE5.0 废弃) | AnimSequence.h 第 793 行 |

### EditorOnly 异步压缩缓存字段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| CurrentPlatformData | FCompressedAnimSequence* | 当前平台压缩数据指针 | AnimSequence.h 第 809 行 |
| DataByPlatformKeyHash | TMap<FIoHash, TUniquePtr<FCompressedAnimSequence>> | 按平台哈希索引的压缩数据 | AnimSequence.h 第 810 行 |
| CacheTasksByKeyHash | TMap<FIoHash, TPimplPtr<FAnimationSequenceAsyncCacheTask>> | 异步缓存任务 | AnimSequence.h 第 811 行 |
| SharedCompressedDataMutex | FSharedRecursiveMutex | 压缩数据共享互斥锁 | AnimSequence.h 第 812 行 |
| PlatformHashToKeyHash | TMap<uint32, FIoHash> | 平台哈希到数据哈希的映射缓存 | AnimSequence.h 第 815 行 |
| bShouldClearCompressedData | TAtomic<bool> | 是否应在驻留释放时清除压缩数据 | AnimSequence.h 第 818 行 |
| ResidencyReferencerHashes | TMultiMap<uint32, FIoHash> | 驻留引用哈希映射 | AnimSequence.h 第 821 行 |
| PlatformHashToReferencers | TMultiMap<FIoHash, uint32> | 平台哈希到引用者映射 | AnimSequence.h 第 822 行 |

说明：
- AdditiveAnimType 定义叠加动画类型：AAT_None (无)、AAT_Additive (叠加)、AAT_BasePose (基础姿态)
- RefPoseSeq 用于叠加动画的基础姿态参考
- RetargetSource 用于骨骼重定向时指定基础姿态来源
- Interpolation 定义关键帧间插值方式：线性或步进
- CompressedData 在 UE5.6 废弃公共访问，应使用 GetCompressedData() 或 FScopedCompressedAnimSequence
- RetargetSourceAsset 在 UE5.5 废弃，应使用 GetRetargetSourceAsset/SetRetargetSourceAsset
- UE5 使用 TObjectPtr 智能指针包装裸指针，序列化格式与裸指针兼容
- StripAnimDataOnDedicatedServer 控制专用服务器上的动画数据剥离策略
- AttributeCurves 用于驱动自定义动画属性 (UE5 新增)

## FRawAnimSequenceTrack 原始轨道数据

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| PosKeys | TArray<FVector3f> | 位置关键帧数组 | AnimTypes.h 第 858 行 |
| RotKeys | TArray<FQuat4f> | 旋转关键帧数组 | AnimTypes.h 第 862 行 |
| ScaleKeys | TArray<FVector3f> | 缩放关键帧数组 | AnimTypes.h 第 866 行 |

说明：
- 每个关键帧数组长度相等或与时间数组配合使用
- 数据存储骨骼相对于父骨骼的局部变换
- UE4 早期版本使用 FVector/FQuat (双精度)，UE4.23+ 和 UE5 使用 FVector3f/FQuat4f (单精度)

## 废弃字段历史

| 字段 | 废弃版本 | 替代方案 | 源码位置 |
|------|----------|----------|----------|
| SequenceLength | UE5.0 | GetPlayLength() 或 UAnimDataController::SetPlayLength | AnimSequenceBase.h 第 49 行 |
| RawCurveData | UE5.0 | UAnimDataModel 或 GetCurveData() | AnimSequenceBase.h 第 56 行 |
| NumFrames | UE5.0 | UAnimDataModel::GetNumberOfFrames | AnimSequence.h 第 219 行 |
| NumberOfKeys | UE5.0 | UAnimDataModel::GetNumberOfKeys | AnimSequence.h 第 224 行 |
| SamplingFrameRate | UE5.0 | UAnimDataModel::GetFrameRate 或 GetSamplingFrameRate | AnimSequence.h 第 229 行 |
| RawAnimationData | UE5.0 | FBoneAnimationTrack::InternalTrackData | AnimSequence.h 第 232 行 |
| AnimationTrackNames | UE5.0 | FBoneAnimationTrack::Name | AnimSequence.h 第 244 行 |
| RawDataGuid | UE5.1 | GenerateGuidFromModel | AnimSequence.h 第 237 行 |
| SourceRawAnimationData_DEPRECATED | UE5.0 | 无替代 (内部使用) | AnimSequence.h 第 249 行 |
| PerBoneCustomAttributeData | UE5.0 | UAnimDataModel::AnimatedBoneAttributes | AnimSequence.h 第 793 行 |
| RetargetSourceAsset | UE5.5 | GetRetargetSourceAsset/SetRetargetSourceAsset | AnimSequence.h 第 307 行 |
| CompressedData (公共访问) | UE5.6 | GetCompressedData() 或 FScopedCompressedAnimSequence | AnimSequence.h 第 278 行 |
| TargetFrameRate | UE5.6 | PlatformTargetFrameRate.Default | AnimSequence.h 第 780 行 |

## UE5 新增特性

| 特性 | 说明 |
|------|------|
| FScopedCompressedAnimSequence | 嵌套结构，提供线程安全的压缩数据访问作用域 (AnimSequence.h 第 896 行) |
| DataByPlatformKeyHash | 多平台异步压缩缓存，通过 FIoHash 管理 |
| FSharedRecursiveMutex | 压缩数据访问的共享互斥锁，支持并发读取 |
| VariableFrameStrippingSettings | 可变帧剥离优化设置 |
| StripAnimDataOnDedicatedServer | 专用服务器动画数据剥离策略 |
| AttributeCurves | 自定义属性曲线系统 |
| bForceRootLock / bUseNormalizedRootMotionScale | 根运动扩展控制 |
| PlatformTargetFrameRate | 多平台差异化目标帧率 |
| UAnimDataModel | 数据模型分离，原始数据通过 DataModelInterface 管理 |