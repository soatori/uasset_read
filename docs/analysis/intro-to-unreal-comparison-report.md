# Intro_To_Unreal 对比分析报告（Issue #174）

## 测试概述

- **测试项目**: Intro_To_Unreal
- **测试时间**: 2026-06-25
- **测试环境**: UE 5.8 + Python 解析器 v0.5.1

## 测试结果

### 1. 资产发现对比

| 目录 | MCP 数量 | 解析器数量 | 匹配度 |
|------|----------|------------|--------|
| 总资产 | 297 | 265 | 89% |
| Characters | 128 | 128 | 100% |
| DemoTemplate | 94 | 92 | 98% |
| LevelPrototyping | 29 | 29 | 100% |
| Input | 9 | 9 | 100% |
| FirstPerson | 7 | 7 | 100% |

### 2. 蓝图资产对比

**MCP 返回的蓝图资产数**: 33
**解析器测试的蓝图文件数**: 33

#### BP_DoorFrame_Unlockable 详细对比

| 属性 | 解析器 | MCP | 状态 |
|------|--------|-----|------|
| 资产类名 | ✅ BP_DoorFrame_Unlockable_C | ✅ BP_DoorFrame_Unlockable_C | 匹配 |
| 父类 | ✅ BP_DoorFrame_C | ✅ BP_DoorFrame_C | 匹配 |
| 导出数 | 31 | - | - |
| 导入数 | 44 | - | - |
| **图数** | **0** | **2** | ⚠️ 差异 |
| 图列表 | - | UserConstructionScript, EventGraph | MCP 提供 |
| 节点数 | - | 9 (EventGraph) | MCP 提供 |

### 3. 材质资产对比

**MCP 返回的材质资产数**: 5
**解析器测试的材质文件数**: 5

#### M_Mannequin 详细对比

| 属性 | 解析器 | MCP | 状态 |
|------|--------|-----|------|
| 资产类名 | - | Material | MCP 提供 |
| 导出数 | 0 | - | ⚠️ 差异 |
| 导入数 | 45 | - | - |
| 着色模型 | - | MSM_DefaultLit | MCP 提供 |
| 混合模式 | - | BLEND_Masked | MCP 提供 |
| 材质域 | - | MD_Surface | MCP 提供 |

## 关键发现

### ✅ 解析器优势
- 快速解析大量文件 (265文件/7.9秒)
- 提取基本的包信息 (导出、导入、属性)
- 零依赖，可离线使用

### ⚠️ 解析器不足
1. **蓝图图解析为空** (应有图但显示0)
   - 原因: 可能是轻量模式或图提取逻辑问题
   - 影响: BP_DoorFrame_Unlockable 缺少 UserConstructionScript 和 EventGraph

2. **材质资产导出为空** (应有导出但显示0)
   - 原因: 材质资产的 export 解析可能未正确触发
   - 影响: M_Mannequin 缺少材质参数信息

3. **缺少资产类型信息**
   - 原因: 未提取类名或资产类型
   - 影响: 无法区分材质、蓝图、网格等类型

### ✅ MCP 优势
- 提供完整的蓝图图结构和节点信息
- 提供详细的资产属性 (材质参数、着色模型等)
- 实时查询编辑器状态

### ⚠️ MCP 不足
- 需要编辑器运行
- 依赖网络连接
- 无法批量解析离线文件

## 建议

### 短期修复
1. **检查蓝图图解析逻辑**
   - 验证 `extract_blueprint_graphs()` 是否正确调用
   - 检查轻量模式判断是否过于激进

2. **改进材质资产解析**
   - 确保材质 export 正确解析
   - 添加材质参数提取

3. **添加资产类型信息**
   - 从 export 的 class_name 提取资产类型
   - 在 JSON 输出中添加 `asset_type` 字段

### 长期改进
1. 与 MCP 数据结构对齐
2. 添加材质专用解析器
3. 优化大资产的图结构解析

## 验证资产

- `BP_DoorFrame_Unlockable` — 蓝图图解析问题
- `M_Mannequin` — 材质资产解析问题

## 测试文件

- 详细结果: `temp/full_parse_results.json`
- MCP 对比: `temp/mcp_vs_parser_results.json`
