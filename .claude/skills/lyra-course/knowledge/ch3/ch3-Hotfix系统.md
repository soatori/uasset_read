# Hotfix 系统

## 概述

Lyra 的热修复系统通过 ULyraHotfixManager 实现运行时配置修补。继承自 UOnlineHotfixManager，支持从网络服务下载热修复文件并动态更新配置和资产引用。

## ULyraHotfixManager

继承自 `UOnlineHotfixManager`，负责管理在线热修复流程。

### 关键方法

| 方法 | 用途 |
|------|------|
| StartHotfixProcess() | 启动热修复流程 |
| OnHotfixCompleted() | 热修复完成回调 |
| WantsHotfixProcessing() | 判断是否处理指定文件 |
| ApplyHotfixProcessing() | 应用文件的热修复 |
| HotfixIniFile() | 应用 .ini 文件的热修复 |
| PatchAssetsFromIniFiles() | 从 .ini 文件修补资产引用 |
| RequestPatchAssetsFromIniFiles() | 请求从 .ini 修补资产 |
| OnHotfixAvailablityCheck() | 热修复可用性检查回调 |

### 热修复流程

```
StartHotfixProcess()
  → 从在线服务下载热修复文件列表
  → 逐个文件处理：
    → WantsHotfixProcessing() 过滤
    → ApplyHotfixProcessing() 应用
      → .ini 文件 → HotfixIniFile() 更新配置
      → 资产文件 → PatchAssetsFromIniFiles() 更新引用
  → OnHotfixCompleted() 完成回调
    → 广播 OnPendingGameHotfixChanged 事件
```

### 缓存目录

```cpp
virtual FString GetCachedDirectory() override
{
    return FPaths::ProjectPersistentDownloadDir() / TEXT("Hotfix/");
}
```

热修复文件缓存于项目持久下载目录的 `Hotfix/` 子目录。

### 热修复状态追踪

| 属性 | 用途 |
|------|------|
| bHasPendingGameHotfix | 是否有待处理的游戏热修复 |
| bHasPendingDeviceProfileHotfix | 是否有待处理的设备配置热修复 |
| GameHotfixCounter | 游戏热修复计数 |

### ShouldWarnAboutMissing

当从 .ini 修补资产时，`ShouldWarnAboutMissingWhenPatchingFromIni()` 控制是否对缺失资产发出警告。

## LyraTextHotfixConfig

位于 `Hotfix/` 目录，处理文本内容的热修复配置。

## LyraRuntimeOptions

位于 `Hotfix/` 目录，运行时选项的热修复支持。

## 与设置的关联

热修复完成后会触发 ULyraSettingsLocal 的 `OnHotfixDeviceProfileApplied()` 回调，重新应用设备配置和帧率设置：

```
Hotfix 完成
  → OnHotfixCompleted()
    → OnPendingGameHotfixChanged 事件
      → ULyraSettingsLocal::OnHotfixDeviceProfileApplied()
        → ReapplyThingsDueToPossibleDeviceProfileChange()
          → UpdateGameModeDeviceProfileAndFps()
            → 更新设备配置后缀
            → 更新帧率模式
```
