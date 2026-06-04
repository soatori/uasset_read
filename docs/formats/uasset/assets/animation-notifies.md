# 动画通知结构

## 概述

动画通知 (AnimNotify) 是动画序列中的事件触发机制，用于在特定时间点或时间段执行自定义逻辑。通知系统支持两种类型：

- **AnimNotify**: 单帧触发通知，在特定时间点触发瞬间事件
- **AnimNotifyState**: 持续通知，在时间段内持续触发状态事件

通知存储在 UAnimSequenceBase 的 Notifies 数组中，按触发时间排序 (最早在前)。

继承关系：
- FAnimLinkableElement: 可链接元素基类 (支持时间同步)
- FAnimNotifyEvent: 通知事件结构 (继承 FAnimLinkableElement)
- UAnimNotify: 单帧通知对象
- UAnimNotifyState: 持续通知对象

## FAnimNotifyEvent 通知事件结构

FAnimNotifyEvent 是存储动画通知事件的核心结构，继承自 FAnimLinkableElement，支持蒙太奇片段链接。

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| DisplayTime_DEPRECATED | float (EditorOnly) | 废弃：用户请求的触发时间 | AnimTypes.h 第 283 行 |
| TriggerTimeOffset | float | 触发时间偏移量，用于调整实际触发时间 | AnimTypes.h 第 288 行 |
| EndTriggerTimeOffset | float | 结束触发时间偏移量 (NotifyState 结束时) | AnimTypes.h 第 292 行 |
| TriggerWeightThreshold | float | 触发权重阈值，低于此值不触发 | AnimTypes.h 第 295 行 |
| NotifyName | FName | 通知名称 | AnimTypes.h 第 298 行 |
| Notify | TObjectPtr&lt;UAnimNotify&gt; | 单帧通知对象引用 | AnimTypes.h 第 301 行 |
| NotifyStateClass | TObjectPtr&lt;UAnimNotifyState&gt; | 持续通知对象引用 | AnimTypes.h 第 304 行 |
| Duration | float | 持续时长 (NotifyState 使用) | AnimTypes.h 第 307 行 |
| EndLink | FAnimLinkableElement | 结束时间链接元素 (NotifyState) | AnimTypes.h 第 311 行 |
| bConvertedFromBranchingPoint | bool | 是否从旧 BranchingPoint 转换 | AnimTypes.h 第 315 行 |
| MontageTickType | TEnumAsByte&lt;EMontageNotifyTickType::Type&gt; | 蒙太奇触发类型 | AnimTypes.h 第 318 行 |
| NotifyTriggerChance | float | 触发概率 (0=永不, 1=总是) | AnimTypes.h 第 322 行 |
| NotifyFilterType | TEnumAsByte&lt;ENotifyFilterType::Type&gt; | 过滤类型 | AnimTypes.h 第 326 行 |
| NotifyFilterLOD | int32 | LOD 过滤起始级别 | AnimTypes.h 第 330 行 |
| bCanBeFilteredViaRequest | bool | 是否允许运行时过滤 | AnimTypes.h 第 334 行 |
| bTriggerOnDedicatedServer | bool | 是否在专用服务器触发 | AnimTypes.h 第 338 行 |
| bTriggerOnFollower | bool | 是否在同步组跟随者触发 | AnimTypes.h 第 342 行 |
| NotifyColor | FColor (EditorOnly) | 编辑器中通知颜色 | AnimTypes.h 第 347 行 |
| Guid | FGuid (EditorOnly) | 编辑器唯一标识 | AnimTypes.h 第 351 行 |
| TrackIndex | int32 | 编辑器轨道索引 | AnimTypes.h 第 356 行 |

FAnimLinkableElement 继承字段：

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| LinkedMontage | TObjectPtr&lt;UAnimMontage&gt; | 链接的蒙太奇 | AnimLinkableElement.h 第 147 行 |
| SlotIndex | int32 | 蒙太奇槽索引 | AnimLinkableElement.h 第 151 行 |
| SegmentIndex | int32 | 片段索引 (INDEX_NONE 表示未链接) | AnimLinkableElement.h 第 155 行 |
| LinkMethod | TEnumAsByte&lt;EAnimLinkMethod::Type&gt; | 时间链接方法 | AnimLinkableElement.h 第 159 行 |
| CachedLinkMethod | TEnumAsByte&lt;EAnimLinkMethod::Type&gt; | 缓存的链接方法 | AnimLinkableElement.h 第 163 行 |
| SegmentBeginTime | float | 片段开始时间 | AnimLinkableElement.h 第 167 行 |
| SegmentLength | float | 片段长度 | AnimLinkableElement.h 第 171 行 |
| LinkValue | float | 链接时间值 | AnimLinkableElement.h 第 175 行 |
| LinkedSequence | TObjectPtr&lt;UAnimSequenceBase&gt; | 链接的动画序列 | AnimLinkableElement.h 第 182 行 |

说明：
- Notify 和 NotifyStateClass 互斥，同一事件只能有其一
- Duration 仅当 NotifyStateClass 非空时有效
- TriggerTimeOffset 用于处理无法精确触发的情况
- GetTriggerTime() 返回实际触发时间 = LinkValue + TriggerTimeOffset
- 默认值：TriggerWeightThreshold = ZERO_ANIMWEIGHT_THRESH, NotifyTriggerChance = 1.0, bTriggerOnDedicatedServer = true

## FAnimLinkableElement 链接元素基类

FAnimLinkableElement 提供动画元素与蒙太奇片段的时间同步能力。

### EAnimLinkMethod 链接方法枚举

| 值 | 说明 | 源码位置 |
|----|------|----------|
| Absolute | 元素固定在特定时间，不随片段移动 | AnimLinkableElement.h 第 20 行 |
| Relative | 元素随片段移动，但片段大小变化时不变 | AnimLinkableElement.h 第 22 行 |
| Proportional | 元素保持片段比例位置，片段变化时跟随 | AnimLinkableElement.h 第 24 行 |

说明：
- Absolute 用于固定时间点的通知
- Relative 和 Proportional 用于蒙太奇中的时间同步
- UE5.1 起 Link() 统一替代 LinkMontage()/LinkSequence()

## UAnimNotify 单帧通知对象

UAnimNotify 是单帧通知的基类，在动画播放到触发时间点时执行。

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| NotifyColor | FColor | 编辑器显示颜色 (EditorOnly) | AnimNotify.h 第 67 行 |
| bShouldFireInEditor | bool | 是否在编辑器中触发 (EditorOnly) | AnimNotify.h 第 71 行 |
| bIsNativeBranchingPoint | bool | 是否为原生分支点 | AnimNotify.h 第 125 行 |
| MeshContext | USkeletalMeshComponent* (private) | 当前触发的网格上下文 (私有) | AnimNotify.h 第 132 行 |

### 核心方法

| 方法名 | 说明 | 源码位置 |
|--------|------|----------|
| GetNotifyName() | 获取自定义通知名称 (BlueprintNativeEvent) | AnimNotify.h 第 59 行 |
| Received_Notify(EventReference) | 通知触发回调 (BlueprintImplementableEvent) | AnimNotify.h 第 62 行 |
| Notify(MeshComp, Animation) | 通知触发回调 (UE5.0 废弃) | AnimNotify.h 第 86 行 |
| Notify(MeshComp, Animation, EventReference) | 通知触发回调 (UE5.0+) | AnimNotify.h 第 87 行 |
| BranchingPointNotify(Payload) | 分支点通知回调 | AnimNotify.h 第 88 行 |
| GetDefaultTriggerWeightThreshold() | 获取默认触发权重阈值 (BlueprintNativeEvent) | AnimNotify.h 第 98 行 |

说明：
- bIsNativeBranchingPoint 为 true 时，蒙太奇中总是作为分支点处理
- Notify 方法接收 USkeletalMeshComponent、UAnimSequenceBase 和 FAnimNotifyEventReference 参数
- Received_Notify 为 BlueprintImplementableEvent，可在蓝图中实现

## UAnimNotifyState 持续通知对象

UAnimNotifyState 是持续通知的基类，在时间段内持续触发状态事件。

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| NotifyColor | FColor | 编辑器显示颜色 (EditorOnly) | AnimNotifyState.h 第 46 行 |
| bShouldFireInEditor | bool | 是否在编辑器中触发 (EditorOnly) | AnimNotifyState.h 第 50 行 |
| bIsNativeBranchingPoint | bool | 是否为原生分支点 | AnimNotifyState.h 第 105 行 |

### 核心方法

| 方法名 | 说明 | 源码位置 |
|--------|------|----------|
| GetNotifyName() | 获取自定义通知名称 (BlueprintNativeEvent) | AnimNotifyState.h 第 32 行 |
| Received_NotifyBegin(EventReference) | 状态开始回调 (BlueprintImplementableEvent) | AnimNotifyState.h 第 35 行 |
| Received_NotifyTick(EventReference) | 状态帧回调 (BlueprintImplementableEvent) | AnimNotifyState.h 第 38 行 |
| Received_NotifyEnd(EventReference) | 状态结束回调 (BlueprintImplementableEvent) | AnimNotifyState.h 第 41 行 |
| NotifyBegin(MeshComp, Animation, Duration) | 状态开始回调 (UE5.0 废弃) | AnimNotifyState.h 第 65 行 |
| NotifyTick(MeshComp, Animation, DeltaTime) | 状态帧回调 (UE5.0 废弃) | AnimNotifyState.h 第 67 行 |
| NotifyEnd(MeshComp, Animation) | 状态结束回调 (UE5.0 废弃) | AnimNotifyState.h 第 69 行 |
| NotifyBegin(MeshComp, Animation, Duration, EventReference) | 状态开始回调 (UE5.0+) | AnimNotifyState.h 第 71 行 |
| NotifyTick(MeshComp, Animation, DeltaTime, EventReference) | 状态帧回调 (UE5.0+) | AnimNotifyState.h 第 72 行 |
| NotifyEnd(MeshComp, Animation, EventReference) | 状态结束回调 (UE5.0+) | AnimNotifyState.h 第 73 行 |
| BranchingPointNotifyBegin(Payload) | 分支点开始回调 | AnimNotifyState.h 第 75 行 |
| BranchingPointNotifyTick(Payload, DeltaTime) | 分支点帧回调 | AnimNotifyState.h 第 76 行 |
| BranchingPointNotifyEnd(Payload) | 分支点结束回调 | AnimNotifyState.h 第 77 行 |
| GetDefaultTriggerWeightThreshold() | 获取默认触发权重阈值 (BlueprintNativeEvent) | AnimNotifyState.h 第 87 行 |

说明：
- NotifyBegin 在进入时间段时触发
- NotifyTick 在时间段内每帧触发
- NotifyEnd 在离开时间段时触发

## FAnimNotifyEventReference 通知事件引用

FAnimNotifyEventReference 用于传递通知触发时的上下文信息。

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| ContextData | TSharedPtr&lt;TArray&lt;TUniquePtr&lt;IAnimNotifyEventContextDataInterface&gt;&gt;&gt; (private) | 上下文数据数组 | AnimNotifyQueue.h 第 120 行 |
| Notify | FAnimNotifyEvent* (private) | 通知事件指针 | AnimNotifyQueue.h 第 122 行 |
| MirrorTable | TObjectPtr&lt;const UMirrorDataTable&gt; (transient) | 镜像数据表 | AnimNotifyQueue.h 第 126 行 |
| NotifySource | TObjectPtr&lt;const UObject&gt; (transient) | 通知来源对象 | AnimNotifyQueue.h 第 129 行 |
| CurrentAnimTime | float | 当前动画时间 | AnimNotifyQueue.h 第 132 行 |
| bActiveContext | bool | 是否为活动上下文 | AnimNotifyQueue.h 第 135 行 |

说明：
- NotifySource 是触发通知的动画序列或蒙太奇
- MirrorTable 用于镜像动画中的通知映射
- ContextData 存储额外的上下文信息 (TSharedPtr 包装)
- GetCurrentAnimationTime() 获取触发时的动画时间
- IsActiveContext() 检查上下文是否活跃 (未淡出)

## FAnimNotifyQueue 通知队列

FAnimNotifyQueue 用于收集和过滤动画播放中触发的通知。

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| PredictedLODLevel | int32 | 预测 LOD 级别 | AnimNotifyQueue.h 第 199 行 |
| RandomStream | FRandomStream | 内部随机流 (用于概率触发) | AnimNotifyQueue.h 第 202 行 |
| AnimNotifies | TArray&lt;FAnimNotifyEventReference&gt; (transient) | 已触发的通知列表 | AnimNotifyQueue.h 第 206 行 |
| UnfilteredMontageAnimNotifies | TMap&lt;FName, FAnimNotifyArray&gt; (transient) | 未过滤的蒙太奇通知 | AnimNotifyQueue.h 第 210 行 |
| World | TWeakObjectPtr&lt;UWorld&gt; (Transient) | 世界指针 | AnimNotifyQueue.h 第 222 行 |

说明：
- AnimNotifies 存储当前帧触发的所有通知
- PassesFiltering() 检查通知是否通过 LOD 过滤
- PassesChanceOfTriggering() 检查通知是否通过概率检查

## 触发条件

### AnimNotify 单帧触发

触发时机：
- 动画播放时间越过 GetTriggerTime() 时触发
- 通知存储在 Notifies 数组，按时间排序
- GetAnimNotifies() 方法检测时间区间内的通知

触发条件：
- InstanceWeight >= TriggerWeightThreshold
- NotifyFilterType/NotifyFilterLOD 通过 LOD 过滤
- NotifyTriggerChance 概率检查通过
- bTriggerOnDedicatedServer 在专用服务器上触发

### AnimNotifyState 持续触发

触发时机：
- NotifyBegin: 进入时间段 (CurrentTime >= GetTriggerTime())
- NotifyTick: 在时间段内每帧
- NotifyEnd: 离开时间段 (CurrentTime >= GetEndTriggerTime())

触发条件：
- 同 AnimNotify 的权重、LOD、概率过滤
- Duration 定义时间段长度
- EndLink 存储结束时间点

### EMontageNotifyTickType 蒙太奇触发类型

| 值 | 说明 | 源码位置 |
|----|------|----------|
| Queued | 通知排队到评估阶段结束后触发 (更快)。不适合改变蒙太奇片段或位置 | AnimTypes.h 第 91 行 |
| BranchingPoint | 通知遇到时立即触发 (较慢，适合改变片段) | AnimTypes.h 第 93 行 |

说明：
- Queued 类型不能用于改变蒙太奇片段或位置
- BranchingPoint 类型适合需要立即响应的脚本逻辑

### ENotifyFilterType 过滤类型

| 值 | 说明 | 源码位置 |
|----|------|----------|
| NoFiltering | 无过滤 | AnimTypes.h 第 104 行 |
| LOD | 按 Skeletal Mesh LOD 过滤 | AnimTypes.h 第 107 行 |

说明：
- LOD 过滤在低 LOD 时跳过通知以优化性能
- NotifyFilterLOD 定义开始过滤的 LOD 级别

## 常见通知类型

### 单帧通知类型

| 类名 | 用途 | 源码位置 |
|------|------|----------|
| UAnimNotify_PlaySound | 播放音效 | AnimNotify_PlaySound.h |
| UAnimNotify_PlayParticleEffect | 播放粒子效果 | AnimNotify_PlayParticleEffect.h |
| UAnimNotify_ResetDynamics | 重置动力学模拟 | AnimNotify_ResetDynamics.h |
| UAnimNotify_ResetClothingSimulation | 重置布料模拟 | AnimNotify_ResetClothingSimulation.h |
| UAnimNotify_PauseClothingSimulation | 暂停布料模拟 | AnimNotify_PauseClothingSimulation.h |
| UAnimNotify_ResumeClothingSimulation | 恢复布料模拟 | AnimNotify_ResumeClothingSimulation.h |

### 持续通知类型

| 类名 | 用途 | 源码位置 |
|------|------|----------|
| UAnimNotifyState_TimedParticleEffect | 定时粒子效果 | AnimNotifyState_TimedParticleEffect.h |
| UAnimNotifyState_Trail | 拖尾效果 | AnimNotifyState_Trail.h |
| UAnimNotifyState_DisableRootMotion | 禁用根运动 | AnimNotifyState_DisableRootMotion.h |

### UAnimNotify_PlaySound 字段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| Sound | USoundBase* | 要播放的音效 | AnimNotify_PlaySound.h 第 36 行 |
| VolumeMultiplier | float | 音量倍数 | AnimNotify_PlaySound.h 第 40 行 |
| PitchMultiplier | float | 音调倍数 | AnimNotify_PlaySound.h 第 44 行 |
| bFollow | bool | 音效是否跟随拥有者 | AnimNotify_PlaySound.h 第 48 行 |
| AttachName | FName | 附加的骨骼/插槽名称 | AnimNotify_PlaySound.h 第 57 行 |

### UAnimNotify_PlayParticleEffect 字段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| PSTemplate | UParticleSystem* | 粒子系统模板 | AnimNotify_PlayParticleEffect.h 第 45 行 |
| LocationOffset | FVector | 位置偏移 | AnimNotify_PlayParticleEffect.h 第 49 行 |
| RotationOffset | FRotator | 旋转偏移 | AnimNotify_PlayParticleEffect.h 第 53 行 |
| Scale | FVector | 缩放 | AnimNotify_PlayParticleEffect.h 第 57 行 |
| Attached | bool | 是否附加到骨骼 | AnimNotify_PlayParticleEffect.h 第 71 行 |
| SocketName | FName | 插槽名称 | AnimNotify_PlayParticleEffect.h 第 75 行 |

### UAnimNotifyState_TimedParticleEffect 字段

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| PSTemplate | UParticleSystem* | 粒子系统模板 | AnimNotifyState_TimedParticleEffect.h 第 23 行 |
| SocketName | FName | 附加的插槽名称 | AnimNotifyState_TimedParticleEffect.h 第 27 行 |
| LocationOffset | FVector | 位置偏移 | AnimNotifyState_TimedParticleEffect.h 第 31 行 |
| RotationOffset | FRotator | 旋转偏移 | AnimNotifyState_TimedParticleEffect.h 第 35 行 |
| bDestroyAtEnd | bool | 结束时是否立即销毁 | AnimNotifyState_TimedParticleEffect.h 第 40 行 |

## FBranchingPointNotifyPayload 分支点载荷

FBranchingPointNotifyPayload 用于传递分支点通知的上下文信息。

| 字段名 | 类型 | 用途 | 源码位置 |
|--------|------|------|----------|
| SkelMeshComponent | USkeletalMeshComponent* | 骨骼网格组件 | AnimNotify.h 第 28 行 |
| SequenceAsset | UAnimSequenceBase* | 序列资产 | AnimNotify.h 第 29 行 |
| NotifyEvent | FAnimNotifyEvent* | 通知事件 | AnimNotify.h 第 30 行 |
| MontageInstanceID | int32 | 蒙太奇实例 ID | AnimNotify.h 第 31 行 |
| bReachedEnd | bool | 是否到达结束 | AnimNotify.h 第 32 行 |

说明：
- MontageInstanceID 用于识别蒙太奇播放实例
- bReachedEnd 标记是否到达蒙太奇结束

## 源码引用

- Runtime/Engine/Public/Animation/AnimTypes.h — FAnimNotifyEvent, FAnimSyncMarker, FAnimNotifyTrack 定义 (155 个符号)
- Runtime/Engine/Classes/Animation/AnimLinkableElement.h — FAnimLinkableElement 链接元素基类
- Runtime/Engine/Classes/Animation/AnimSequenceBase.h — UAnimSequenceBase 定义, Notifies 数组 (50 个符号)
- Runtime/Engine/Classes/Animation/AnimNotifies/AnimNotify.h — UAnimNotify 单帧通知基类
- Runtime/Engine/Classes/Animation/AnimNotifies/AnimNotifyState.h — UAnimNotifyState 持续通知基类
- Runtime/Engine/Public/Animation/AnimNotifyQueue.h — FAnimNotifyQueue, FAnimNotifyEventReference 定义
- Runtime/Engine/Classes/Animation/AnimNotifies/AnimNotify_PlaySound.h — 播放音效通知
- Runtime/Engine/Classes/Animation/AnimNotifies/AnimNotify_PlayParticleEffect.h — 播放粒子效果通知
- Runtime/Engine/Classes/Animation/AnimNotifies/AnimNotifyState_TimedParticleEffect.h — 定时粒子效果通知

## 版本差异

### UE5 特性

| 特性 | 说明 |
|------|------|
| FAnimNotifyEventReference | 新增通知引用结构，传递更多上下文 (含 ContextData、NotifySource、CurrentAnimTime) |
| Notify(EventReference) | Notify 方法新增 EventReference 参数 |
| NotifyBegin/Tick/End(EventReference) | NotifyState 方法新增 EventReference 参数 |
| Received_Notify 系列 | BlueprintImplementableEvent 版本的回调 |
| 废弃方法 | Notify(), NotifyBegin(), NotifyTick(), NotifyEnd() (不带 EventReference) |
| bTriggerOnFollower | 支持在同步组跟随者触发 |
| bCanBeFilteredViaRequest | 支持运行时请求过滤 |
| Link() | 统一的链接方法替代 LinkMontage/LinkSequence |
| NotifyColor/Guid | FAnimNotifyEvent 新增 EditorOnly 颜色和指导字段 |

### UE4 特性

| 特性 | 说明 |
|------|------|
| Notify() | 不带 EventReference 的触发方法 |
| LinkMontage() | 专门的蒙太奇链接方法 |
| LinkSequence() | 专门的序列链接方法 |
| DisplayTime_DEPRECATED | 旧版本的用户请求时间字段 |

### 废弃字段历史

| 字段/方法 | 废弃版本 | 替代方案 |
|-----------|----------|----------|
| DisplayTime_DEPRECATED | UE5.0 | GetTriggerTime() 或 LinkValue |
| Notify(MeshComp, Animation) | UE5.0 | Notify(MeshComp, Animation, EventReference) |
| NotifyBegin(MeshComp, Animation, TotalDuration) | UE5.0 | NotifyBegin(MeshComp, Animation, TotalDuration, EventReference) |
| NotifyTick(MeshComp, Animation, FrameDeltaTime) | UE5.0 | NotifyTick(MeshComp, Animation, FrameDeltaTime, EventReference) |
| NotifyEnd(MeshComp, Animation) | UE5.0 | NotifyEnd(MeshComp, Animation, EventReference) |
| LinkMontage() | UE5.1 | Link() |
| LinkSequence() | UE5.1 | Link() |
