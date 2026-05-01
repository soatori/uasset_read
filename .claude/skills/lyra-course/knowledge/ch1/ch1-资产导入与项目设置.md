# 资产导入与项目设置

## 打包检验

创建空白关卡后首次打包可能遇到的错误及修复：

### 错误 1：GameFeatureData 资产类型未注册

```
Asset manager settings do not include a rule for assets of type GameFeatureData
```

**修复**：在 Game → AssetManager 的 `PrimaryAssetTypesToScan` 中添加：

```ini
(PrimaryAssetType="GameFeatureData",
 AssetBaseClass="/Script/GameFeatures.GameFeatureData",
 bHasBlueprintClasses=False,
 bIsEditorOnly=False,
 Directories=((Path="/Game/Unused")),
 Rules=(Priority=-1, ChunkId=-1, bApplyRecursively=True, CookRule=AlwaysCook))
```

### 错误 2：水体碰撞预设缺失

```
Collision Profile settings do not include an entry for the Water Body Collision profile
```

**修复**：在 `DefaultEngine.ini` 的 `[/Script/Engine.CollisionProfile]` 中添加 `WaterBodyCollision` 碰撞预设。

## 碰撞配置

Lyra 定义了 5 个自定义射线检测通道：

| 通道名 | 用途 |
|--------|------|
| `Lyra_TraceChannel_Interaction` | 交互系统射线检测 |
| `Lyra_TraceChannel_Weapon` | 武器射线检测 |
| `Lyra_TraceChannel_Weapon_Capsule` | 武器胶囊体检测 |
| `Lyra_TraceChannel_Weapon_Multi` | 多段武器检测 |
| `Lyra_TraceChannel_AimAssist` | 辅助瞄准检测 |

以及多个自定义碰撞预设（Collision Profile）：

| 预设名 | 用途 |
|--------|------|
| `LyraPawnMesh` | 角色网格体碰撞 |
| `LyraPawnCapsule` | 角色胶囊体碰撞 |
| `Interactable_OverlapDynamic` | 可交互物重叠检测 |
| `Interactable_BlockDynamic` | 可交互物物理阻挡 |
| `AimAssist_OverlapDynamic` | 辅助瞄准区域检测 |

## 资产导入

直接复制 Lyra 示例工程的 Content 目录到当前工程。

导入后状态说明：
- 所有涉及 C++ 类的蓝图会损坏（C++ 类尚未编写）
- 部分资产可正常使用：
  - 音频资产（MetaSound、SoundWave）
  - 部分动画资产（AnimSequence）
  - 所有材质、纹理、网格体

## 音频设置

项目音频主要通过两个类管理：

| 类 | 继承自 | 用途 |
|----|--------|------|
| `ULyraAudioSettings` | `UDeveloperSettings` | 音频配置，定义默认声音类、并发机制、子混音通道 |
| `ULyraAudioMixEffectsSubsystem` | `UWorldSubsystem` | 运行时音频混音覆写 |

关键音频设置属性（来自 `AudioSettings.h`）：
- `DefaultSoundClass` — 新创建声音的音效类
- `DefaultSoundConcurrencyName` — 默认音效并发机制
- `DefaultBaseSoundMix` — 基础音效混音方案
- `MasterSubmix` — 默认子混音通道（声音输出至音频硬件的根子混音）
- `ReverbSubmix` — 混响效果音效的子混音通道
