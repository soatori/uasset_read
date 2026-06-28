# 游戏特定序列化变体分析

## 背景

CUE4Parse 对 150+ 游戏有专门的序列化变体处理，uasset_read 目前不支持。本文档分析这些变体的影响范围和设计决策。

## 影响程度评估

### PAK 层变体（~20 个游戏，占 13%）

| 变体类型 | 游戏示例 | 影响 |
|----------|----------|------|
| 自定义魔数 | GameForPeace、CrystalOfAtlan、KartRiderDrift | PAK 文件头解析 |
| 自定义字段顺序 | ArenaBreakoutInfinite | PAK 版本检测 |
| XOR/位运算混淆 | 部分中国游戏 | 数据解密 |

### 资产序列化层变体（~30 个游戏，占 20%）

| 变体类型 | 游戏示例 | 影响 |
|----------|----------|------|
| 自定义字段跳过/插入 | WorldofJadeDynasty、StateOfDecay2、DaysGone | AActor/UScriptSet/UEnum 序列化 |
| 自定义结构体类型 | GTATheTrilogyDefinitiveEdition、MarvelRivals、Borderlands4 | 参数类型/蓝图指令 |
| 自定义序列化逻辑 | WutheringWaves、DeltaForce、PlayerUnknownsBattlegrounds | 蓝图指令/FNameEntry |

### 关键发现

1. **绝大多数游戏不需要特殊处理** — 使用标准 UE5 序列化
2. **变体相互独立** — 每个游戏的变体仅影响特定资产类型的特定字段
3. **不具有普遍性** — 仅影响特定游戏的特定资产类型

## 当前设计合理性

uasset_read 依赖文件头中的 CustomVersions 驱动版本判断，不包含游戏特定分支。这是合理的设计选择：

- UE5 资产的 CustomVersions 始终存储在包头中
- 版本信息是自描述的
- 不需要游戏特定的回退逻辑

## 何时需要支持

仅在以下情况才需要扩展：

1. **用户明确报告** — 特定游戏资产解析失败
2. **PAK 文件解析** — 需要支持非标准 PAK 格式
3. **游戏特定功能** — 需要提取游戏特有的元数据

## 参考资源

- CUE4Parse EGame 定义：`external/CUE4Parse/CUE4Parse/UE4/Versions/EGame.cs`
- CUE4Parse PAK 魔数：`external/CUE4Parse/CUE4Parse/UE4/Pak/Objects/FPakInfo.cs`
- 当前实现：`src/uasset_read/pak/game_versions.py`
- UE 源码：`Engine/Source/Runtime/Core/Private/UObject/DevObjectVersion.cpp`
