# 蓝图图解析研究摘要

**项目：** uasset_read v2.0
**日期：** 2026-05-02
**模式：** Ecosystem (技术栈研究)

## 执行摘要

本研究为 v2.0 蓝图图解析里程碑确定了技术栈。目标是解析 Unreal Engine 蓝图的图结构（UEdGraph, K2Node, UEdGraphPin），以便 AI agent 能理解蓝图逻辑。

**核心发现：** 现有技术栈（Python 标准库 + dataclasses）已**完整足够**，无需新增运行时依赖。

## 关键发现

### 1. 数据结构清晰

| UE 类型 | Python dataclass | 说明 |
|---------|-----------------|------|
| UEdGraphPin | `UEdGraphPin` | 节点引脚，含类型、默认值、连接 |
| K2Node | `K2Node` | 蓝图节点基类 |
| UEdGraph | `UEdGraph` | 图容器（节点列表） |

### 2. 序列化格式确定

**UEdGraphPin:**
```
PinName (FString)
PinType (FEdGraphPinType - Phase 3 已实现)
AutoGenDefaultValue (FString)
LinkedTo 数组 (int32 count + FString names)
SerializedFlags (uint8 bitfield)
```

**LinkedTo 策略：** 使用 **FString 名称索引**（而非指针），通过 pin_name 查找目标引脚。

### 3. 零新增依赖

现有技术栈已覆盖所有需求：
- `struct` → 二进制解析（u32/i32/i64/f32/f64）
- `read_fstring()` → FString → str
- `read_name()` → FName 解析
- `dataclasses` → 模型定义
- `json` → JSON 输出

**无需添加：** construct, pydantic, numpy, C++ 扩展

### 4. 版本分叉中等复杂度

| UE 版本 | 差异 | 影响 |
|---------|------|------|
| UE4 vs UE5 | 序列化标志位 | `bIsDisconnected` (UE5+) |
| 早期 vs 现代 | LinkedTo 格式 | 建议统一用 FString name |

## 推荐实施路线

### 阶段 1: 核心模型（优先级最高）
1. 定义 `UEdGraphPin`, `K2Node`, `UEdGraph` dataclasses
2. 复用 Phase 3 的 `FEdGraphPinType`
3. 实现 `UEdGraphPinRef` 用于链接

### 阶段 2: 序列化解析
1. `read_ue_graph_pin()` - 引脚读取
2. `read_k2_node()` - 节点读取（基类 + 子类）
3. `read_ue_graph()` - 图容器读取

### 阶段 3: 集成与输出
1. 修改 `ObjectExport` 添加 `graph_data` 字段
2. 修改 `BlueprintMetadata` 添加 `graphs` 字段
3. `parse_uasset()` 中集成图解析

## 研究置信度

| 区域 | 置信度 | 说明 |
|------|--------|------|
| 数据结构 | 高 | UE 文档明确 |
| 序列化格式 | 高 | 源码模式清晰 |
| LinkedTo 格式 | 中 | 需真实文件验证 |
| 零依赖 | 高 | 现有 stack 足够 |

## 实施风险

| 风险 | 严重性 | 缓解 |
|------|--------|------|
| LinkedTo 格式不匹配 | 中 | 随机选择真实 .uasset 验证 |
| UE5+ 新标志位 | 低 | 可选字段，向后兼容 |
| 大蓝图性能 | 低 | <100MB 文件内存足够 |

## 验证步骤

**优先执行：** 随机选取 2-3 个真实 .uasset 文件

1. 检查图数据结构
2. 验证 LinkedTo 格式（名称 vs 索引）
3. 确认 K2Node 大小和布局

**推荐测试文件：**
- LyraStarterGame/BP_Character.uasset
- 完整蓝图项目导出的 .uasset

## 文件输出

研究 outputs:
| 文件 | status |
|------|--------|
| `.planning/research/STACK.md` | ✓ 已写入 |

## 总结

蓝图图解析是**适度复杂度**的扩展：
- 数据结构清晰明确
- 序列化模式标准（数组、FString、bitfield）
- 现有技术栈覆盖 100%
- 风险可控，可增量实施

**建议：** 按上述路线图实施，优先验证 LinkedTo 格式。
