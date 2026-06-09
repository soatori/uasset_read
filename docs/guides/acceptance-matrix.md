# 验收矩阵

## 概述

验收测试证明产品目标达成。运行方式：

```bash
python scripts/test_matrix.py acceptance -q
```

## 维度覆盖

| 维度 | 测试类 | 用例数 | 说明 |
|---|---|---|---|
| 输出内容正确性 | `TestOutputCorrectness` | 6 | JSON 字段与解析结果一致 |
| 跨格式一致性 | `TestCrossFormatConsistency` | 4 | 同一资产不同格式报告相同核心数据 |
| 蓝图语义↔C++ 对应 | `TestBlueprintCppCorrespondence` | 4 | blueprint_text/cpp_skeleton 与 JSON 一致 |
| 资产类型×格式覆盖 | `TestAssetTypeFormatMatrix` | 72 | 9 种类型 × 8 种格式 = 不崩溃且非空 |
| 已知缺口登记 | `TestKnownGapsDocumented` | 3 | xfail/skip 有显式 reason |

**合计**: 89 个验收用例

## 资产类型×格式矩阵

| 资产类型 | json | json_summary | text | text_summary | markdown | blueprint_text | blueprint_ue_text | cpp_skeleton |
|---|---|---|---|---|---|---|---|---|
| Blueprint | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| SkeletalMesh | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| StaticMesh | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Material | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| MaterialInstance | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Texture2D | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| InputAction | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| InputMappingContext | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| AnimBlueprint | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

## 已知缺口

| 缺口 | 状态 | 说明 |
|---|---|---|
| P_Fire.uasset (UE4 legacy) | xfail | UE4 legacy_file_version=-3，当前仅支持 {-9, -8} |
| .usmap 类型映射 | skip | 需要 .usmap 文件基础设施 |
| PAK AES 解密 | skip | 需要 PAK 解密基础设施 |

## 测试分层总览

| 层级 | 套件 | 用例数 | 说明 |
|---|---|---|---|
| L0 | smoke | 97 | 快速冒烟测试 |
| L1 | unit | 1091 | 单元测试（不含 integration/quality/regression/slow/auxiliary/acceptance） |
| L2 | integration | — | 需要外部样本资产 |
| L3 | regression | — | 真实资产回归 |
| L4 | auxiliary | 47 | 辅助/历史回归 |
| L5 | acceptance | 89 | 最终验收 |
| — | all | 1315 | 全量（不含 auxiliary） |
