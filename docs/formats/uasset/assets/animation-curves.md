# 动画曲线数据

## 概述

动画曲线存储骨骼动画的帧数据，包括位置、旋转、缩放三种变换类型。曲线系统用于驱动 Morph Target 权重、材质参数和骨骼变换，支持在动画播放过程中动态调整这些值。

完整曲线结构 (per D-40)：
- FRawCurveTracks: 曲线数据容器，存储所有类型的曲线
- FAnimCurveBase: 曲线基类，提供名称、类型标志和编辑器元数据
- FFloatCurve: 浮点曲线，用于 Morph Target 和材质参数
- FTransformCurve: 变换曲线，用于骨骼变换 (位置/旋转/缩放)
- FVectorCurve: 向量曲线，用于 EditorOnly 的变换编辑

## FRawCurveTracks 曲线容器结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| FloatCurves | TArray&lt;FFloatCurve&gt; | 浮点曲线数组，用于 Morph Target 和材质参数 | AnimCurveTypes.h 第 1074 行 |
| VectorCurves | TArray&lt;FVectorCurve&gt; (EditorOnly, transient) | 向量曲线数组 (EditorOnly)，用于编辑器中的骨骼变换预览 | AnimCurveTypes.h 第 1082 行 |
| TransformCurves | TArray&lt;FTransformCurve&gt; (EditorOnly) | 变换曲线数组 (EditorOnly)，用于编辑器中的叠加动画编辑 | AnimCurveTypes.h 第 1088 行 |

说明：
- FloatCurves 在运行时和编辑器中都可用，用于驱动 Morph Target 权重和材质参数
- VectorCurves 标记为 transient，不序列化，仅用于编辑器中修改骨骼轨道的临时数据
- TransformCurves 仅在编辑器中使用，用于叠加动画编辑，会序列化保存
- UE5.0 后曲线数据通过 UAnimDataModel 管理，RawCurveData 已废弃

## EAnimAssetCurveFlags 曲线类型标志

| 标志名 | 值 | 用途 | 源码位置 |
|--------|------|------|----------|
| AACF_NONE | 0 | 无标志 | AnimCurveTypes.h 第 43 行 |
| AACF_DriveMorphTarget_DEPRECATED | 0x00000001 | 驱动 Morph Target (已废弃，移至 FAnimCurveType) | AnimCurveTypes.h 第 45 行 |
| AACF_DriveAttribute_DEPRECATED | 0x00000002 | 驱动属性 (已废弃，移至 FAnimCurveType) | AnimCurveTypes.h 第 47 行 |
| AACF_Editable | 0x00000004 | 可在序列编辑器中编辑 | AnimCurveTypes.h 第 49 行 |
| AACF_DriveMaterial_DEPRECATED | 0x00000008 | 驱动材质 (已废弃，移至 FAnimCurveType) | AnimCurveTypes.h 第 51 行 |
| AACF_Metadata | 0x00000010 | 元数据曲线，不参与运行时计算 | AnimCurveTypes.h 第 53 行 |
| AACF_DriveTrack | 0x00000020 | 驱动骨骼轨道 (待移除) | AnimCurveTypes.h 第 55 行 |
| AACF_Disabled | 0x00000040 | 禁用曲线，不参与计算 | AnimCurveTypes.h 第 57 行 |

默认值：AACF_DefaultCurve = AACF_Editable (0x00000004)

## FAnimCurveBase 曲线基类字段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| LastObservedName_DEPRECATED | FName (EditorOnly) | 废弃：最后观察名称 | AnimCurveTypes.h 第 98 行 |
| Name_DEPRECATED | FSmartName (EditorOnly) | 废弃：智能名称 (UE5.3 前使用) | AnimCurveTypes.h 第 101 行 |
| Color | FLinearColor (EditorOnly) | 编辑器中曲线显示颜色 | AnimCurveTypes.h 第 104 行 |
| Comment | FString (EditorOnly) | 曲线注释文本 | AnimCurveTypes.h 第 107 行 |
| CurveName | FName (private) | 曲线名称，用于标识和查找 | AnimCurveTypes.h 第 112 行 |
| CurveTypeFlags | int32 | 曲线类型标志位，控制编辑和元数据属性 | AnimCurveTypes.h 第 120 行 |

说明：
- CurveName 是私有字段，通过 GetName()/SetName() 访问
- UE5.3 前使用 FSmartName (UID + DisplayName) 标识曲线，之后简化为 FName
- 构造函数 FAnimCurveBase(FName InName, int32 InCurveTypeFlags) 为当前推荐方式
- PostSerializeFixup() 用于修复 VER_UE4_SKELETON_ADD_SMARTNAMES 和 FFrameworkObjectVersion::SmartNameRefactor 之间的旧数据

## FFloatCurve 浮点曲线字段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| (继承 FAnimCurveBase) | — | 曲线名称、类型标志、编辑器元数据 | AnimCurveTypes.h 第 92-200 行 |
| FloatCurve | FRichCurve | 曲线数据，存储时间到值的映射 | AnimCurveTypes.h 第 219 行 |

说明：
- 浮点曲线用于驱动 Morph Target 权重和材质参数
- 曲线名称通常与 Morph Target 名称或材质参数名称对应
- FloatCurve 存储关键帧数据，支持多种插值模式

## FTransformCurve 变换曲线字段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| (继承 FAnimCurveBase) | — | 曲线名称、类型标志、编辑器元数据 | AnimCurveTypes.h 第 92-200 行 |
| TranslationCurve | FVectorCurve | 位置曲线，存储 XYZ 三个分量 | AnimCurveTypes.h 第 313 行 |
| RotationCurve | FVectorCurve | 旋转曲线，存储欧拉角 XYZ (非四元数) | AnimCurveTypes.h 第 320 行 |
| ScaleCurve | FVectorCurve | 缩放曲线，存储 XYZ 三个分量 | AnimCurveTypes.h 第 323 行 |

说明：
- TransformCurve 仅在编辑器中使用，用于叠加动画编辑
- RotationCurve 使用欧拉角而非四元数，因为曲线编辑器无法处理四元数插值
- 使用欧拉角可能导致万向节锁，需要添加额外关键帧来修复
- 运行时数据已烘焙到压缩骨骼数据中

## FVectorCurve 向量曲线字段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| (继承 FAnimCurveBase) | — | 曲线名称、类型标志、编辑器元数据 | AnimCurveTypes.h 第 92-200 行 |
| FloatCurves[3] | FRichCurve[3] | 三个浮点曲线，分别对应 X/Y/Z 分量 | AnimCurveTypes.h 第 269 行 |

分量索引 (EIndex)：

| 索引 | 值 | 分量 |
|------|------|------|
| X | 0 | X 分量 |
| Y | 1 | Y 分量 |
| Z | 2 | Z 分量 |
| Max | 3 | — |

## FRichCurve 时间轴曲线

FRichCurve 定义在 Curves/RichCurve.h 中，继承自 FRealCurve。

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Keys | TKeyedIndexedContainer&lt;FKeyHandle, FRichCurveKey&gt; | 关键帧容器，按键句柄索引 | RichCurve.h |
| DefaultValue | float | 默认值，无关键帧时使用 | RichCurve.h |
| PreInfinityExtrap | ERichCurveExtrapolation | 前向外推模式 | RichCurve.h |
| PostInfinityExtrap | ERichCurveExtrapolation | 后向外推模式 | RichCurve.h |

外推模式 (ERichCurveExtrapolation)：

| 模式 | 说明 |
|------|------|
| RCCE_Constant | 常数：使用边界值 |
| RCCE_Linear | 线性：沿边界切线延伸 |
| RCCE_Cycle | 循环：重复曲线范围 |
| RCCE_CycleWithOffset | 循环偏移：重复并累加偏移 |
| RCCE_Oscillate | 振荡：来回重复 |

## FRichCurveKey 关键帧字段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| InterpMode | ERichCurveInterpMode | 插值模式 | RichCurve.h 第 86 行 |
| TangentMode | ERichCurveTangentMode | 切线模式 | RichCurve.h 第 90 行 |
| TangentWeightMode | ERichCurveTangentWeightMode | 切线权重模式 | RichCurve.h 第 94 行 |
| Time | float | 时间点 (秒) | RichCurve.h 第 98 行 |
| Value | float | 曲线值 | RichCurve.h 第 102 行 |
| ArriveTangent | float | 到达切线，用于贝塞尔插值 | RichCurve.h 第 106 行 |
| ArriveTangentWeight | float | 到达切线权重 | RichCurve.h 第 110 行 |
| LeaveTangent | float | 离开切线，用于贝塞尔插值 | RichCurve.h 第 114 行 |
| LeaveTangentWeight | float | 离开切线权重 | RichCurve.h 第 118 行 |

插值模式 (ERichCurveInterpMode)：

| 模式 | 说明 |
|------|------|
| RCIM_Constant | 常数：保持前一帧值直到此帧 |
| RCIM_Linear | 线性：线性插值到此帧 |
| RCIM_Cubic | 曲线：使用切线进行贝塞尔插值 |

切线模式 (ERichCurveTangentMode)：

| 模式 | 说明 |
|------|------|
| RCTM_Auto | 自动：自动计算切线 |
| RCTM_User | 用户：使用用户指定的统一切线 |
| RCTM_Break | 断开：到达和离开切线独立 |
| RCTM_None | 无切线 |
| RCTM_SmartAuto | 智能自动：比 Auto 更平滑的曲线 |

切线权重模式 (ERichCurveTangentWeightMode)：

| 模式 | 说明 |
|------|------|
| RCTWM_WeightedNone | 不考虑切线权重 |
| RCTWM_WeightedArrive | 仅考虑到达切线权重 |
| RCTWM_WeightedLeave | 仅考虑离开切线权重 |
| RCTWM_WeightedBoth | 同时考虑到达和离开切线权重 |

## 骨骼索引机制 (per D-41)

动画曲线通过 CurveName 和骨骼名称关联到骨骼层级。骨骼轨道使用 FTrackToSkeletonMap 结构映射轨道索引到骨骼树索引。

### FTrackToSkeletonMap 结构

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| BoneTreeIndex | int32 | 骨骼树索引，指向 USkeleton.BoneTree 中的骨骼 | AnimTypes.h 第 827 行 |

索引映射关系：

| 概念 | 说明 |
|------|------|
| TrackIndex | 动画轨道数组索引，对应 AnimationTracks[i] |
| BoneTreeIndex | Skeleton.BoneTree 骨骼树索引，用于定位骨骼在层级中的位置 |
| BoneName | 通过 Skeleton.GetBoneName(BoneTreeIndex) 获取骨骼名称 |

映射流程：
1. TrackToSkeletonMapTable[TrackIndex].BoneTreeIndex 获取骨骼树索引
2. 通过骨骼树索引在 Skeleton.BoneTree 中找到对应骨骼
3. AnimationTracks[TrackIndex] 存储该骨骼的位置/旋转/缩放关键帧

压缩数据索引：
- FCompressedAnimSequence::CompressedTrackToSkeletonMapTable 存储压缩数据的轨道到骨骼映射
- 压缩数据运行时使用此表快速定位骨骼变换

## FRawAnimSequenceTrack 原始轨道数据

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| PosKeys | TArray&lt;FVector3f&gt; | 位置关键帧数组 | AnimTypes.h 第 858 行 |
| RotKeys | TArray&lt;FQuat4f&gt; | 旋转关键帧数组 (四元数) | AnimTypes.h 第 862 行 |
| ScaleKeys | TArray&lt;FVector3f&gt; | 缩放关键帧数组 | AnimTypes.h 第 866 行 |

说明：
- 每个关键帧数组长度相同（NumFrames 或 1），1 表示恒定值压缩方案
- 数据存储骨骼相对于父骨骼的局部变换
- UE5 使用 FVector3f/FQuat4f (单精度)，UE4 使用 FVector/FQuat (双精度)
- UE5.0 后此结构已废弃，数据通过 FAnimSequenceTrackContainer::AnimationTracks 管理
- 序列化：UE5.6+ 使用 BulkSerialize，旧版本通过 FUE5ReleaseStreamObjectVersion::RawAnimSequenceTrackSerializer 判断

## FCurveTrack 曲线轨道结构 (压缩前)

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| CurveName | FName | 曲线名称，通常为 Morph Target 名称 | AnimSequence.h 第 143 行 |
| CurveWeights | TArray&lt;float&gt; | 每帧的权重值数组 | AnimSequence.h 第 146 行 |

说明：
- 此结构用于存储压缩前的曲线权重数据
- 每个元素对应一帧的权重值
- CompressCurveWeights() 方法可将相同值压缩为单个关键帧
- IsValidCurveTrack() 检查是否包含有效权重

## 曲线类型分类 (ERawCurveTrackTypes)

| 类型 | 值 | 说明 | 用途 |
|------|------|------|------|
| RCT_Float | 0 | 浮点曲线 | Morph Target 权重、材质参数 |
| RCT_Vector | 1 | 向量曲线 (Hidden) | 编辑器骨骼变换 |
| RCT_Transform | 2 | 变换曲线 | 编辑器叠加动画变换 |
| RCT_MAX | 3 | — | — |

## 源码引用

- Runtime/Engine/Classes/Animation/AnimSequence.h — UAnimSequence 定义，FCurveTrack 结构
- Runtime/Engine/Classes/Animation/AnimSequenceBase.h — UAnimSequenceBase 基类，RawCurveData 字段
- Runtime/Engine/Public/Animation/AnimCurveTypes.h — FRawCurveTracks, FAnimCurveBase, FFloatCurve, FTransformCurve, FVectorCurve 定义 (129 个符号)
- Runtime/Engine/Public/Animation/AnimTypes.h — FTrackToSkeletonMap, FRawAnimSequenceTrack 定义 (155 个符号)
- Runtime/Engine/Classes/Curves/RichCurve.h — FRichCurve, FRichCurveKey 定义
- Runtime/Engine/Private/Animation/AnimSequence.cpp — 曲线序列化实现

## 版本差异

### UE5 特性

| 特性 | 说明 |
|------|------|
| UAnimDataModel | 数据模型分离，曲线数据通过 DataModelInterface 管理 |
| 废弃字段 | RawCurveData 已废弃，使用 GetCurveData() 或 UAnimDataModel |
| FName 标识 | 曲线标识从 FSmartName 改为 FName (UE5.3) |
| 平台压缩 | 支持多平台异步压缩缓存，通过 FIoHash 管理 |
| 属性曲线 | AttributeCurves 用于自定义属性动画 |
| 曲线类型迁移 | DriveMorphTarget/DriveAttribute/DriveMaterial 标志移至 FAnimCurveType (per-skeleton) |

### UE4 特性

| 特性 | 说明 |
|------|------|
| 直接数据访问 | RawCurveData 直接可用 |
| FSmartName 标识 | 曲线使用 FSmartName (UID + Name) 标识 |
| 同步压缩 | 曲线压缩在保存时同步完成 |
| 基础曲线结构 | FloatCurves, VectorCurves, TransformCurves 结构相同 |

### 废弃字段历史

| 字段 | 废弃版本 | 替代方案 |
|------|----------|----------|
| RawCurveData | UE5.0 | GetCurveData() 或 UAnimDataModel |
| LastObservedName_DEPRECATED | UE5.3 | CurveName |
| Name_DEPRECATED | UE5.3 | CurveName (FName) |
| FAnimCurveParam | UE5.3 | 直接使用 FName |
| FSmartName 构造函数 | UE5.3 | FName 构造函数 |
| GetCurveData(UID) | UE5.3 | GetCurveData(FName) |
| AddCurveData(FSmartName) | UE5.3 | AddCurveData(FName) |
| DeleteCurveData(FSmartName) | UE5.3 | DeleteCurveData(FName) |
| GetAnimCurveUID | UE5.3 | 直接使用 CurveName |
| FCurveElement (全局) | UE5.3 | 不再使用 |
