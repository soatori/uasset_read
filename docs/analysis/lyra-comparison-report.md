# Lyra 对比分析报告（Issue #177）

## 测试概述

- **测试项目**: LyraStarterGame
- **测试时间**: 2026-06-25
- **测试环境**: UE 5.8 + Python 解析器 v0.5.1

## 解析统计

| 指标 | 数值 |
|------|------|
| 总文件数 | 2840 |
| 成功解析 | 2699 (95.0%) |
| 总解析时间 | 30.82 秒 |
| 峰值内存 | 85.48 MB |

## 差异详情

### B_Weapon 蓝图

| 维度 | 解析器 | MCP | 一致性 |
|------|--------|-----|--------|
| Export 数 | 2 | 2 | ✅ 一致 |
| 函数图数 | 5 | ~5 | ✅ 基本一致 |
| 节点详情 | 有限 | 完整 | ⚠️ 有限 |

### ABP_Mannequin_Base 蓝图

| 维度 | 解析器 (轻量模式) | MCP | 差异 |
|------|-------------------|-----|------|
| Export 数 | 783 | 783 | ✅ 一致 |
| 函数图数 | 64 | 79 | ⚠️ 差异 |
| 变量数 | 0 | 53 | ❌ 缺失 |
| 图结构 | 无 | 完整 | ❌ 缺失 |

## 根因分析

1. **轻量模式限制**: export_count > 300 时自动启用
   - 文件: `src/uasset_read/parse_uasset.py:402-414`
   - 影响: ABP_Mannequin_Base (783 exports) 自动进入轻量模式

2. **图结构解析限制**: 仅提取函数入口节点
   - 文件: `src/uasset_read/graph/flow_builder.py`
   - 影响: 未解析嵌套子图和复杂控制流

3. **变量提取未启用**: 轻量模式跳过变量提取
   - 文件: `src/uasset_read/blueprint/variable_extractor.py`
   - 影响: 53 个变量未提取

## 改进建议

### 短期（v0.4.6）
1. 增加详细模式开关（`--full-parse`）
2. 添加变量提取功能到轻量模式
3. 优化大资产的图结构解析

### 长期（v0.5.0）
1. 实现增量解析（仅解析变化部分）
2. 添加动画蓝图专用解析器
3. 与 MCP 数据结构对齐

## 验证资产

- `ABP_Mannequin_Base` — 主要差异来源
- `B_Weapon` — 基本一致

## 相关文件

- `src/uasset_read/parse_uasset.py:402-414` — 轻量模式判断
- `src/uasset_read/graph/flow_builder.py` — 图结构解析
- `src/uasset_read/blueprint/variable_extractor.py` — 变量提取
