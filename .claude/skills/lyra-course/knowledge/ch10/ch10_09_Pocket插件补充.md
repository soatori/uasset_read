# Pocket 插件补充

## 概述

PocketWorlds 是 Lyra 工程中的一个独立插件（`Plugins/PocketWorlds`），提供两种正交能力：

1. **口袋关卡流送（Pocket Level Streaming）** — 为每个本地客户端独立流式子关卡，用于 UI/菜单场景
2. **口袋截图（Pocket Capture）** — 基于 `USceneCaptureComponent2D` 的场景截图系统，用于生成缩略图

两者各自通过独立的 `UWorldSubsystem` 管理。

## 口袋关卡流送

### 口袋关卡定义

[UPocketLevel](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/PocketWorlds/Source/Public/PocketLevel.h) 继承 `UDataAsset`，作为口袋世界的定义资产：

- `Level`（`TSoftObjectPtr<UWorld>`）：要流式加载的关卡资源
- `Bounds`（`FVector`）：口袋世界的边界大小，用于计算多个实例的垂直偏移避免重叠

### 口袋关卡子系统

[UPocketLevelSubsystem](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/PocketWorlds/Source/Public/PocketLevelSystem.h) 继承 `UWorldSubsystem`，是全局管理器，管理一个 `UPocketLevelInstance` 数组。

`GetOrCreatePocketLevelFor(LocalPlayer, PocketLevel, DesiredSpawnPoint)` 是核心入口：
- 遍历已有实例，匹配 `LocalPlayer + PocketLevel` 则直接复用
- 不匹配时，累加 `Bounds.Z` 计算垂直偏移，创建新实例

### 口袋关卡实例

[UPocketLevelInstance](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/PocketWorlds/Source/Public/PocketLevelInstance.h) 继承 `UObject`（`Within=PocketLevelSubsystem`），负责单个口袋世界的生命周期。

**核心方法：**

| 方法 | 说明 |
|------|------|
| `Initialize` | 调用 `ULevelStreamingDynamic::LoadLevelInstanceBySoftObjectPtr`，绑定 `OnLevelLoaded` / `OnLevelShown` 回调 |
| `StreamIn` / `StreamOut` | 控制流式关卡的可见性和加载状态 |
| `AddReadyCallback` | 关卡就绪时回调；已就绪则直接执行 |
| `BeginDestroy` | 清理流送关卡、移除绑定 |

**`HandlePocketLevelLoaded()` 关键模式：**
- `bClientOnlyVisible = true`：标记为仅客户端可见
- `bExchangedRoles = true`：避免服务器同步预期
- `SetOwner(PlayerController)`：所有 Actor 归属本地玩家控制器

## 口袋截图系统

### 截图子系统

[UPocketCaptureSubsystem](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/PocketWorlds/Source/Public/PocketCaptureSubsystem.h) 继承 `UWorldSubsystem`，管理多个 `UPocketCapture` 实例池。

**核心功能：**
- `CreateThumbnailRenderer(Class)`：创建 `UPocketCapture`，使用 `nullptr` 占位空槽复用
- `DestroyThumbnailRenderer(Renderer)`：置空槽位并反初始化
- `StreamThisFrame(Components)`：标记组件 `bForceMipStreaming = true`，纳入流送队列
- 每帧 Tick 中：清理上一帧的 `bForceMipStreaming`，交换 `StreamNextFrame`

**两帧 Mip 流送策略：** 当前帧标记组件 → 截图 → 下一帧 Tick 清理标记，确保截图帧获得高精度 Mip 纹理。

### 口袋截图渲染器

[UPocketCapture](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/PocketWorlds/Source/Public/PocketCapture.h) 继承 `UObject`（`Abstract, Within=PocketCaptureSubsystem`），负责对目标 Actor 进行场景截图。

**三种渲染目标：**
- `DiffuseRT`（`RTF_RGBA8`）：漫反射颜色截图
- `AlphaMaskRT`（`RTF_R8`）：Alpha 遮罩截图
- `EffectsRT`（`RTF_R8`）：特效截图（TODO 未实现）

**`CaptureScene()` 核心流程：**
1. 获取 `CaptureTarget` 上的 `UCameraComponent`
2. 调用 `GetThumbnailSystem()->StreamThisFrame()` 触发 Mip 流送
3. 若传入 `OverrideMaterial`，临时替换所有 PrimitiveComponent 的材质
4. 关闭大量 ShowFlags（DOF、MotionBlur、TAA、AO、VolumetricFog 等）确保干净截图
5. 设置 `CaptureSource`，调用 `CaptureScene()`
6. 恢复原始材质

## 参考源码

- [PocketWorlds 插件目录](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/PocketWorlds/)
- [UPocketLevel](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/PocketWorlds/Source/Public/PocketLevel.h)
- [UPocketLevelSubsystem](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/PocketWorlds/Source/Public/PocketLevelSystem.h)
- [UPocketLevelInstance](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/PocketWorlds/Source/Public/PocketLevelInstance.h)
- [UPocketCaptureSubsystem](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/PocketWorlds/Source/Public/PocketCaptureSubsystem.h)
- [UPocketCapture](file:///d:/UPS/GitLab/XGUnrealNote/Courses/Lyra-Deep-Dive/code/Lyra/Plugins/PocketWorlds/Source/Public/PocketCapture.h)
