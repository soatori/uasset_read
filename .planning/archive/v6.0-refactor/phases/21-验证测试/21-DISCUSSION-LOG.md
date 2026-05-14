# Phase 21: 验证测试 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-04
**Phase:** 21-验证测试
**Areas discussed:** 测试方法, 测试资产, 验证标准, 测试文件组织, Expected数据来源

---

## 测试方法

| Option | Description | Selected |
|--------|-------------|----------|
| 集成测试（真实资产） | 解析真实资产，验证解析结果符合预期模式。适合验证完整流程，但需要UE编辑器对照。 | ✓ |
| 单元测试（mock数据） | 使用mock数据构造测试用例，验证输出函数逻辑。适合验证格式化逻辑，但无法验证解析正确性。 | |
| 二者结合 | 集成测试验证解析正确性 + 单元测试验证输出格式化逻辑。全面覆盖但工作量较大。 | |

**User's choice:** 集成测试（真实资产）
**Notes:** 验证目标是解析正确性，不需要mock数据测试格式化逻辑

---

## 测试资产

| Option | Description | Selected |
|--------|-------------|----------|
| BP_FirstPersonCharacter（推荐） | UE 5.7标准测试资产，已用于现有测试。路径已定义：test_exportmap_properties.py:FIRST_PERSON_CHARACTER_PATH | ✓ |
| 多资产验证 | 添加更多蓝图资产进行多场景验证。可提升覆盖度，但需要定位和配置新资产。 | |

**User's choice:** BP_FirstPersonCharacter（推荐）
**Notes:** 单资产验证即可满足TEST-01~04要求

---

## 验证标准

| Option | Description | Selected |
|--------|-------------|----------|
| 确匹配（推荐） | 节点数量、执行流程、数据流必须完全匹配。严格确保正确性，但可能因资产版本变化而调整。 | ✓ |
| 关键节点匹配 | 关键节点和流程匹配，允许动态节点数量差异。灵活应对资产变化，但可能遗漏问题。 | |

**User's choice:** 精确匹配（推荐）
**Notes:** 严格验证确保解析正确性

---

## 测试文件组织

| Option | Description | Selected |
|--------|-------------|----------|
| 新建专用文件（推荐） | 创建test_phase21_verification.py，集中存放Phase 21测试用例。便于追踪和隔离验证测试。 | ✓ |
| 扩展现有文件 | 添加到test_output_formatting.py或test_graph_parsing.py。减少文件数量，但混合不同阶段测试。 | |

**User's choice:** 新建专用文件（推荐）
**Notes:** 便于追踪和隔离Phase 21验证测试

---

## Expected数据来源

| Option | Description | Selected |
|--------|-------------|----------|
| 手动构造（推荐） | 根据UE编辑器截图/文档手动构造expected数据。确保数据准确，但需要人工对照验证。 | |
| 从解析结果提取 | 从现有解析结果提取expected数据，假设现有解析正确。快速配置，但无法验证解析是否真的正确。 | |

**User's choice:** C++源码对照（FirstPersonCCharacter.h/cpp）
**Notes:** 用户提供了C++源码路径作为expected数据权威参考：
- `E:/Develop/lib/UnrealEngine/Samples/FirstPersonC/Source/FirstPersonC/FirstPersonCCharacter.h`
- `E:/Develop/lib/UnrealEngine/Samples/FirstPersonC/Source/FirstPersonC/FirstPersonCCharacter.cpp`

关键对照函数：
- DoJumpStart() → Jump()
- DoJumpEnd() → StopJumping()
- MoveInput(ActionValue) → DoMove(Right, Forward) → AddMovementInput

---

## Claude's Discretion

- 确切节点数量expected值（需解析确定）
- 执行流程深度（是否追踪到AddMovementInput层级）
- 数据流匹配模式（参数名映射）

---

## Deferred Ideas

None — discussion stayed within phase scope.

---

*Phase: 21-验证测试*
*Discussion completed: 2026-05-04*