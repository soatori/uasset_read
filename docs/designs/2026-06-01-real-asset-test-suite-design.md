# 真实案例测试套件设计

**日期**: 2026-06-01
**作者**: Claude Code
**状态**: 待实现

## 概述

使用 `E:\Develop\lib` 目录下 41,000+ 个真实 `.uasset` 文件，为 uasset_read 项目创建一套完整的集成测试套件，覆盖：解析核心结构、Engine 内容兼容性、已知失败回归、格式化器输出、资产类型深度字段验证。

## 目标

1. 扩展现有资产类型覆盖度（从 8 种到 15+ 种）
2. 覆盖边界情况和异常情况（大文件、特殊引擎内容）
3. 覆盖已知失败案例并建立回归测试
4. 验证所有格式化器输出正确性
5. 对核心资产类型做深度字段验证

## 方案设计

**方案 B：多文件拆分** — 按功能职责拆分为 5 个独立测试文件。

## 测试文件清单

### 1. `test_real_asset_coverage.py` — 核心解析覆盖

20 个资产，15+ 种资产类型，验证 `parse_uasset_with_linker` 核心结构返回。

| # | 类型 | 文件 | 来源 |
|---|---|---|---|
| 1-10 | 现有稳定资产 | BP/ SkeletalMesh/Material/StaticMesh/Texture/InputAction/Niagara 等 | 扩展 STABLE_ASSETS |
| 11 | AnimSequence | Lyra `MM_Pistol_TurnRight_90.uasset` | 新增 |
| 14 | NiagaraSystem | ThirtPerson `NS_Jump_Trail.uasset` | 新增 |
| 15-17 | SoundCue/DataTable/Curve | Engine 目录选取 | 新增 |
| 18 | WidgetBlueprint | Lyra `W_UserLoginButton.uasset` | 新增 |
| 19 | MaterialFunction | Lyra `MF_AnimatedSquareTexture.uasset` | 新增 |

验证项：`is_success`、`summary`、`linker`、`name_map`、`export_map`、`blueprint`（如有）、`graphs`（如有）。

### 2. `test_engine_content.py` — Engine 内容兼容性

12 个资产，来自 `Engine/Content` 目录，验证引擎内置资产解析兼容性。

- DefaultPhysicalMaterial / M_Default (Material)
- DefaultTexture (Texture2D)
- Roboto (Font)
- Slate 资源
- 编辑器材质/模型
- 动画序列
- 音效
- 缓冲区可视化材质
- 基础形状 StaticMesh
- 天空材质/贴图

### 3. `test_known_failures.py` — 已知失败回归

8 类已知失败，每类 2-3 个真实文件，基于 `tests/fixtures/real_asset_failures_*.txt`。

| 类别 | 文件 | 涉及类型 |
|---|---|---|
| animation_data_model | Lyra AnimSequence ×3 | AnimSequence/Montage |
| cube_builder | __ExternalActors__ ×3 | 外部 Actor |
| k2_nodes | WidgetBlueprint ×3 | K2Node 相关 |
| material_expression | Material/MaterialFunction ×3 | 材质表达式 |
| metasound | MetaSound ×2 | 音频 MetaSound |
| movie_scene | MovieScene/LevelSequence ×3 | 过场动画 |
| niagara | NiagaraSystem ×2 | Niagara 粒子 |
| payload_offsets | GameplayCue ×3 | 特殊偏移 |

每个文件：tolerant 模式下不崩溃，strict 模式下报预期错误。已修复的自动转绿。

### 4. `test_formatter_outputs.py` — 格式化器输出验证

6 个资产 × 7 种格式化器：

| 资产 | 类型 |
|---|---|
| BP_FirstPersonCharacter | Blueprint（含图） |
| SKM_Manny_Simple | SkeletalMesh |
| M_Mannequin | Material |
| SM_Cube | StaticMesh |
| T_GridChecker_A | Texture2D |
| MI_Manny_01_New | MaterialInstance |

| 格式化器 | 验证项 |
|---|---|
| JSON | 输出可反序列化 |
| Text | 非空，有可读内容 |
| Markdown | 有 `#` 标题 |
| Mermaid | 有 `graph` 语法 |
| BlueprintText | 有节点描述 |
| UEText | UE 格式特征 |
| CppSkeleton | 有 `UCLASS`/`UPROPERTY` 等 |

### 5. `test_asset_type_depth.py` — 资产类型深度字段

| 类型 | 验证项 |
|---|---|
| Texture2D | `imported_size_x/y > 0`、`b_cooked`、2 的幂检查 |
| Material | 表达式数量 > 0、MaterialDomain、BlendMode |
| MaterialInstance | parent 存在、scalar/vector 参数数量 |
| SkeletalMesh | 骨骼数量 > 0、Section 数量 > 0、RefSkeleton |
| StaticMesh | LOD 数量 ≥ 1、Section 数量 ≥ 1 |
| Blueprint | 变量 ≥ 1（有 GUID）、EventGraph 节点 ≥ 1（有连接） |

## 运行方式

```bash
# 全部真实资产测试
pytest tests/test_real_asset_coverage.py tests/test_engine_content.py tests/test_known_failures.py tests/test_formatter_outputs.py tests/test_asset_type_depth.py -v -m integration

# 单独运行
pytest tests/test_known_failures.py -v
pytest tests/test_formatter_outputs.py -v
```

## 失败处理

| 场景 | 处理 |
|---|---|
| 文件不存在 | `pytest.skip` + 警告 |
| 已知未修复缺陷 | `xfail(strict=False)` |
| 意外新失败 | 正常断言失败 |
| 已修复的已知失败 | 自动转绿，移除 xfail |

## 环境变量

- `UE_SAMPLE_ROOT` — Samples 根目录（默认 `E:\Develop\lib\UnrealEngine\Samples`）
- `UE_ENGINE_CONTENT_ROOT` — Engine 内容根目录（默认 `E:\Develop\lib\UnrealEngine\Engine\Content`）

## 文件位置

```
tests/
├── test_real_asset_coverage.py
├── test_engine_content.py
├── test_known_failures.py
├── test_formatter_outputs.py
├── test_asset_type_depth.py
└── fixtures/ (复用现有)
```
