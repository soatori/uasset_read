# Actor 序列化机制

## 概述

Actor 序列化机制描述 AActor、UActorComponent、USceneComponent 的属性标签序列化字段。Actor 通过 Export 表层次追踪，UE5 External Actors 机制将 Actor 存储为独立 .uasset 文件。组件层次：AActor → UActorComponent → USceneComponent。

本文档描述 Actor 序列化概述、AActor/UActorComponent/USceneComponent 序列化字段、内嵌 Actor vs 外部 Actor 差异、Export 表 Actor 层次追踪。

## Part A: Actor 序列化概述

### 组件层次

```
AActor → UObject
UActorComponent → UObject
USceneComponent → UActorComponent
```

### Export 表层次

.umap 文件的 Export 表 Actor 层次结构：

| Export Index | 对象类型 | 说明 |
|--------------|----------|------|
| Export[0] | UWorld | 世界容器对象 |
| Export[1] | ULevel | 主关卡（PersistentLevel） |
| Export[2] | AActor | Root Actor |
| Export[3..N] | UActorComponent | Actor 内嵌组件 |
| Export[N+1] | AActor | Child Actor（内嵌） |
| Export[N+2..] | UActorComponent | Child Actor 内嵌组件 |

### 内嵌对象序列化

Actor 和组件通过 Instanced 属性（UPROPERTY Instanced）内嵌序列化：

- AActor::RootComponent — Instanced 属性，内嵌序列化
- AActor::Components — TArray<TObjectPtr<UActorComponent>>，内嵌序列化
- USceneComponent::AttachChildren — TArray<TObjectPtr<USceneComponent>>，内嵌序列化

### 源码引用

- Runtime/Engine/Classes/GameFramework/Actor.h — AActor 定义
- Runtime/Engine/Classes/Components/ActorComponent.h — UActorComponent 定义
- Runtime/Engine/Classes/Components/SceneComponent.h — USceneComponent 定义

## Part B: AActor 序列化字段

### 继承关系

```
AActor → UObject
```

### 核心字段表

| 字段 | 类型 | 说明 |
|------|------|------|
| PrimaryActorTick | FActorTickFunction | 主 Tick 函数 |
| Owner | AActor* | 所有者 Actor |
| RootComponent | USceneComponent* | 根组件（Instanced） |
| Components | TArray<UActorComponent*> | 组件数组（Instanced） |
| Children | TArray<AActor*> | 子 Actor 数组（EditorOnly） |
| Layer | FName | 层名称（EditorOnly） |
| Tags | TArray<FName> | 标签数组 |
| ActorLabel | FString | Actor 标签（EditorOnly） |
| FolderPath | FName | 文件夹路径（EditorOnly） |

### 网络复制字段表

| 字段 | 类型 | 说明 |
|------|------|------|
| bNetTemporary | uint8 | 网络临时标记 |
| bNetStartup | uint8 | 网络启动标记 |
| bOnlyRelevantToOwner | uint8 | 仅所有者相关 |
| bAlwaysRelevant | uint8 | 永远相关 |
| bReplicates | uint8 | 复制标记 |
| bReplicateMovement | uint8 | 复制移动 |
| RemoteRole | ENetRole | 远程角色 |
| bNetLoadOnClient | uint8 | 网络客户端加载 |
| bNetUseOwnerRelevancy | uint8 | 使用所有者相关性 |
| bRelevantForNetworkReplays | uint8 | 网络录像相关 |

### 可见性字段表

| 字段 | 类型 | 说明 |
|------|------|------|
| bHidden | uint8 | 隐藏标记 |
| bIsEditorOnlyActor | uint8 | 仅编辑器 Actor（EditorOnly） |
| bRelevantForLevelBounds | uint8 | 关卡边界相关 |
| bGenerateOverlapEventsDuringLevelStreaming | uint8 | 流送时生成重叠事件 |

### 碰撞字段表

| 字段 | 类型 | 说明 |
|------|------|------|
| bActorEnableCollision | uint8 | Actor 碰撞启用 |
| bCollideWhenPlacing | uint8 | 放置时碰撞 |

### Level Instance 字段表（EditorOnly）

| 字段 | 类型 | 说明 |
|------|------|------|
| LevelInstanceType | ELevelInstanceType | Level Instance 类型 |
| LevelInstanceFlags | ELevelInstanceFlags | Level Instance 标记 |
| bIsMainWorldOnly | uint8 | 仅主世界 |
| bIgnoreInPIE | uint8 | PIE 忽略 |

### 初始化状态字段表（Transient）

| 字段 | 类型 | 说明 |
|------|------|------|
| bActorInitialized | uint8 | Actor 已初始化 |
| bHasFinishedSpawning | uint8 | 完成生成 |
| bActorHasBegunPlay | EActorBeginPlayState | BeginPlay 状态 |
| bHasRegisteredAllComponents | uint8 | 已注册所有组件 |

### 源码引用

- Runtime/Engine/Classes/GameFramework/Actor.h — AActor 字段定义
- Runtime/Engine/Private/GameFramework/Actor.cpp — AActor 序列化实现

## Part C: UActorComponent 序列化字段

### 继承关系

```
UActorComponent → UObject
```

### 核心字段表

| 字段 | 类型 | 说明 |
|------|------|------|
| PrimaryComponentTick | FActorComponentTickFunction | 主 Tick 函数 |
| ComponentTags | TArray<FName> | 组件标签数组 |
| AssetUserData | TArray<TObjectPtr<UAssetUserData>> | 用户数据（Instanced） |
| AssetUserDataEditorOnly | TArray<TObjectPtr<UAssetUserData>> | 编辑器用户数据（EditorOnly） |

### 状态标记字段表

| 字段 | 类型 | 说明 |
|------|------|------|
| bNetActive | uint8 | 网络活跃标记（Transient） |
| bReplicates | uint8 | 复制标记 |
| bAutoActivate | uint8 | 自动激活 |
| bIsActive | uint8 | 活跃状态 |
| bHiddenInGame | uint8 | 游戏中隐藏 |
| bRenderStateDirty | uint8 | 渲染状态脏标记（Transient） |

### 注册状态字段表（Transient）

| 字段 | 类型 | 说明 |
|------|------|------|
| bHasRegisteredAllComponents | uint8 | 已注册所有组件 |
| bTickFunctionsRegistered | uint8 | Tick 函数已注册 |
| bRenderStateUpdating | uint8 | 渲染状态正在更新 |

### 源码引用

- Runtime/Engine/Classes/Components/ActorComponent.h — UActorComponent 定义
- Runtime/Engine/Private/Components/ActorComponent.cpp — UActorComponent 序列化

## Part D: USceneComponent 序列化字段

### 继承关系

```
USceneComponent → UActorComponent
```

### Transform 字段表

| 字段 | 类型 | 说明 |
|------|------|------|
| RelativeLocation | FVector | 相对位置 |
| RelativeRotation | FRotator | 相对旋转 |
| RelativeScale3D | FVector | 相对缩放 |
| ComponentVelocity | FVector | 组件速度 |
| Bounds | FBoxSphereBounds | 组件边界 |

### 附着字段表

| 字段 | 类型 | 说明 |
|------|------|------|
| AttachParent | TObjectPtr<USceneComponent> | 附着父组件 |
| AttachChildren | TArray<TObjectPtr<USceneComponent>> | 附着子组件数组 |
| AttachSocketName | FName | 附着 Socket 名称 |
| ClientAttachedChildren | TArray<TObjectPtr<USceneComponent>> | 客户端附着子组件（Transient） |

### 绝对变换标记字段表

| 字段 | 类型 | 说明 |
|------|------|------|
| bAbsoluteLocation | uint8 | 绝对位置标记 |
| bAbsoluteRotation | uint8 | 绝对旋转标记 |
| bAbsoluteScale | uint8 | 绝对缩放标记 |
| bVisible | uint8 | 可见标记 |

### 附着行为字段表

| 字段 | 类型 | 说明 |
|------|------|------|
| bShouldBeAttached | uint8 | 应附着标记 |
| bShouldSnapLocationWhenAttached | uint8 | 附着时位置对齐 |
| bShouldSnapRotationWhenAttached | uint8 | 附着时旋转对齐 |
| bShouldSnapScaleWhenAttached | uint8 | 附着时缩放对齐 |

### Physics Volume 字段表

| 字段 | 类型 | 说明 |
|------|------|------|
| PhysicsVolume | TWeakObjectPtr<APhysicsVolume> | 物理 Volume（Transient） |

### Editor Only 字段表

| 字段 | 类型 | 说明 |
|------|------|------|
| bHiddenEdTemporary | uint8 | 编辑器临时隐藏 |
| DetailMode | EDetailMode | 细节模式 |

### ERelativeTransformSpace 枚举

| 值 | 说明 |
|-----|------|
| RTS_World | 世界空间变换 |
| RTS_Actor | Actor 空间变换 |
| RTS_Component | 组件空间变换 |
| RTS_ParentBoneSpace | 父骨骼空间变换 |

### EDetailMode 枚举

| 值 | 说明 |
|-----|------|
| DM_Low | 低细节 |
| DM_Medium | 中细节 |
| DM_High | 高细节 |
| DM_Epic | Epic 细节 |

### 源码引用

- Runtime/Engine/Classes/Components/SceneComponent.h — USceneComponent 定义
- Runtime/Engine/Private/Components/SceneComponent.cpp — USceneComponent 序列化

## Part E: 内嵌 Actor vs 外部 Actor

### UE4 行为：内嵌 Actor

UE4 所有 Actor 内嵌在 .umap Export 表中：

- Export 表中 Actor 对象完整序列化
- Export 表层次：Root Actor → Child Actor → Component
- Actor GUID 不独立存储（通过 Export Index 追踪）

### UE5 行为：External Actors

UE5 引入 External Actors 机制（bUseExternalActors = true）：

- Actor 存储为独立 .uasset 文件
- .umap 通过 Import 表引用外部 Actor 包
- Actor GUID 独立存储，用于追踪

### bUseExternalActors 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| bUseExternalActors | bool (EditorOnly) | UE5 External Actors 标记 |

### EActorPackagingScheme 枚举

Level.h 定义的 Actor 打包方案：

| 值 | 说明 |
|-----|------|
| Original | 原始方案：ZZ/ZZ/...（最多 1679616 个文件夹） |
| Reduced | 简化方案：Z/ZZ/...（最多 46656 个文件夹） |

### ActorPackagingScheme 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| ActorPackagingScheme | EActorPackagingScheme (EditorOnly) | Actor 打包方案 |

### 目录结构

外部 Actor 目录结构：

```
__ExternalActors__/XX/YY/GUID.uasset
```

- XX、YY 为路径编码（基于 EActorPackagingScheme）
- GUID 为 Actor GUID

### GUID 追踪机制

| 字段 | 类型 | 说明 |
|------|------|------|
| ActorGuid | FGuid | Actor GUID（External Actor） |
| ActorPackageGuid | FGuid | Actor 包 GUID |

### Import 表引用

外部 Actor 通过 Import 表引用：

- Import 条目结构：ClassPackage, ClassName, Outer, ObjectName
- Import Index 为负数：-N 表示 Import[N-1]

### 源码引用

- Runtime/Engine/Classes/Engine/Level.h — bUseExternalActors, EActorPackagingScheme 定义
- Runtime/Engine/Private/Engine/Level.cpp — External Actor 实现

## Part F: Export 表 Actor 层次追踪

### 内嵌 Actor 追踪

Export 表 Index 偏移追踪：

- Export[0] = UWorld
- Export[1] = ULevel（PersistentLevel）
- Export[2..N] = Actor 层次（Root → Child → Component）

### FObjectExport 结构

Export 条目关键字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| ObjectName | FName | 对象名称 |
| ClassIndex | FPackageIndex | 类引用（正数=Export，负数=Import） |
| OuterIndex | FPackageIndex | Outer 引用 |
| SerialSize | int64 | 序列化数据大小 |
| SerialOffset | int64 | 序列化数据偏移 |

### 外部 Actor 追踪

Import 表引用追踪（负数 Index）：

- Import[0..N] = 外部对象引用
- Import 条目记录 Actor 包名和类名

### Depends Map

Actor 依赖关系追踪：

- FObjectExport::SerializationBeforeSerializationDependencies
- FObjectExport::CreateBeforeSerializationDependencies
- 依赖关系用于加载顺序优化

### 交叉引用

- [../import-export-tables.md](../import-export-tables.md) — Import/Export 表结构

## Part G: 交叉引用

### StaticMesh Actor

| 文档 | 内容 | Actor 引用 |
|------|------|-----------|
| [static-mesh.md](static-mesh.md) | StaticMesh 结构 | UStaticMeshComponent 引用 |
| [static-mesh-structure.md](static-mesh-structure.md) | UStaticMesh 字段 | StaticMesh Actor RootComponent |

### 序列化机制

| 文档 | 内容 | Actor 引用 |
|------|------|-----------|
| [../serialization/property-tag.md](../serialization/property-tag.md) | PropertyTag 结构 | Actor 属性标签解析 |
| [../serialization/linker-load.md](../serialization/linker-load.md) | LinkerLoad 序列化 | Actor 子对象加载 |

### Import/Export 表

| 文档 | 内容 | Actor 引用 |
|------|------|-----------|
| [../import-export-tables.md](../import-export-tables.md) | Import/Export 表 | Actor 层次追踪 |

## 源码引用汇总

| 文件 | 路径 | 说明 |
|------|------|------|
| Actor.h | Runtime/Engine/Classes/GameFramework/ | AActor 定义 |
| Actor.cpp | Runtime/Engine/Private/GameFramework/ | AActor 序列化 |
| ActorComponent.h | Runtime/Engine/Classes/Components/ | UActorComponent 定义 |
| SceneComponent.h | Runtime/Engine/Classes/Components/ | USceneComponent 定义 |
| Level.h | Runtime/Engine/Classes/Engine/ | bUseExternalActors, EActorPackagingScheme |

## 版本差异

详见 [../version/asset-level.md](../version/asset-level.md)

UE4 与 UE5 Actor 序列化主要差异：

- **Actor 存储：** UE4 内嵌 Actor；UE5 External Actors
- **GUID 追踪：** UE5 Actor GUID 独立存储
- **目录结构：** UE5 __ExternalActors__/ 目录