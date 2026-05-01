# GameFeature 系统

## 概述

GameFeature 是 UE5 的插件级动态内容加载系统，允许将游戏功能拆分为独立的插件，在运行时按需加载/卸载。Lyra 实现了 ULyraGameFeaturePolicy 作为项目级加载策略，并通过多个 GameFeatureAction 子类定义加载时的具体行为。

## GameFeature 基础概念

### 插件结构

GameFeature 插件是标准的 UE 插件，位于 `Plugins/GameFeatures/` 目录。每个插件包含：

- `.uplugin` 插件描述文件
- `Content/` 资产目录  
- `Source/` 源码目录

### 分块与内容打包

GameFeature 插件支持：
- **Chunking**：将插件资产分配到独立的 Patch/Chunk，实现按需下载
- **ContentBundle**：内容包机制，管理插件资产的加载/卸载
- **DataRegistry**：数据注册表，管理插件中的表格数据
- **InputConfig**：输入配置，注册插件特有的输入映射
- **GameplayCueManager**：GameplayCue 路径注册
- **CommonUILayout**：通用 UI 布局激活

### 内容包（ContentBundle）

UContentBundleEngineSubsystem 是内容包引擎子系统，管理 GameFeature 插件中 ContentBundle 的生命周期：

```
ContentBundle 注册 → 插件安装时注册 Bundle
  → Bundle 激活 → Experience 加载时激活
    → 资产加载 → Bundle 关联的资产加载到内存
  → Bundle 停用 → 插件卸载时停用
```

## ULyraGameFeaturePolicy

继承自 `UDefaultGameFeaturesProjectPolicies`，Lyra 项目的 GameFeature 加载策略单例。

### 关键方法

| 方法 | 用途 |
|------|------|
| InitGameFeatureManager() | 初始化 GameFeature 管理器 |
| ShutdownGameFeatureManager() | 关闭 GameFeature 管理器 |
| GetPreloadAssetListForGameFeature() | 获取 GameFeature 插件需要预加载的资产列表 |
| IsPluginAllowed() | 判断指定插件是否允许加载 |
| GetPreloadBundleStateForGameFeature() | 获取预加载的 Bundle 状态 |
| GetGameFeatureLoadingMode() | 获取加载模式（客户端/服务器） |

### Observer 机制

ULyraGameFeaturePolicy 管理一组 Observer，监听 GameFeature 插件的状态变化：

| Observer 类 | 用途 |
|-------------|------|
| ULyraGameFeature_HotfixManager | GameFeature 加载时执行热修复 |
| ULyraGameFeature_AddGameplayCuePaths | GameFeature 注册/注销时添加/移除 GameplayCue 路径 |

## GameFeatureAction

GameFeatureAction 定义 GameFeature 插件加载/激活时的具体行为。

### 位于主项目的 GameFeatureAction

| 类 | 继承自 | 用途 |
|------|--------|------|
| GameFeatureAction_WorldActionBase | UGameFeatureAction | 世界动作基类 |
| GameFeatureAction_AddAbilities | UGameFeatureAction | 添加 GameplayAbility、效果、属性集 |
| GameFeatureAction_AddInputBinding | UGameFeatureAction | 添加输入绑定映射 |
| GameFeatureAction_AddInputContextMapping | UGameFeatureAction | 添加输入上下文映射 |
| GameFeatureAction_AddWidget | UGameFeatureAction | 添加 UI 控件 |
| GameFeatureAction_AddGameplayCuePath | UGameFeatureAction | 添加 GameplayCue 路径 |
| GameFeatureAction_SplitscreenConfig | UGameFeatureAction | 分屏配置 |

### GameFeatureAction 生命周期

```
插件注册 → OnGameFeatureRegistering
  → 插件加载 → OnGameFeatureLoading
    → 插件激活 → OnGameFeatureActivating
      → GameFeatureAction 执行 (AddAbilities/AddWidget 等)
    → 插件停用 → OnGameFeatureDeactivating
      → GameFeatureAction 回滚
  → 插件卸载 → OnGameFeatureUnload
→ 插件注销 → OnGameFeatureUnregistering
```

## UGameFeatureAction_AddGameplayCuePath

用于向 GameplayCue 管理器注册额外的 GameplayCue 搜索路径：

```cpp
UPROPERTY(EditAnywhere, Category = "Game Feature | Gameplay Cues", meta = (RelativeToGameContentDir, LongPackageName))
TArray<FDirectoryPath> DirectoryPathsToAdd;
```

路径相对于游戏内容目录，使用长包名格式。

## AI ActorFactory

GameFeature 插件可通过 ActorFactory 机制创建自定义的 AI 角色，将角色定义和生成逻辑封装在插件内部。

## 插件实例：TopDownArena

位于 `Plugins/GameFeatures/TopDownArena/`，演示 GameFeature 插件的完整实现：

| 类 | 用途 |
|------|------|
| TopDownArenaRuntimeModule | 插件模块 |
| ALyraCameraMode_TopDownArenaCamera | 俯视角相机模式 |
| ATopDownArenaMovementComponent | 俯视角移动组件 |
| UTopDownArenaAttributeSet | 俯视角属性集 |
| UTopDownArenaPickupUIData | 拾取物 UI 数据 |
