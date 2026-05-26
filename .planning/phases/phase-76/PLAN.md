---
phase: 76
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/uasset_read/versioning.py
  - src/uasset_read/serializers/package_summary.py
  - src/uasset_read/parsers/property_parser.py
  - src/uasset_read/serializers/graph.py
  - src/uasset_read/kismet/bytecode_extractor.py
  - src/uasset_read/kismet/bpgc_bytecode.py
  - src/uasset_read/parsers/property_types.py
  - src/uasset_read/parse_uasset.py
  - tests/test_versioning.py
  - tests/test_struct_property.py
  - tests/test_phase75_event_node_field_alignment.py
  - tests/n2c/test_full_regression.py
  - .planning/STATE.md
  - .planning/ROADMAP.md
  - README.md
  - README.zh-CN.md
  - .planning/phases/phase-76/PLAN.md
autonomous: true
requirements: [COR-01, COR-02]

must_haves:
  truths:
    - "4 个关键路径（property_parser.py / graph.py / bytecode_extractor.py / bpgc_bytecode.py）不再直接访问 summary.file_version_ue5 做版本判断，改为通过 VersionContainer"
    - "所有 StructProperty fast-path 在 tag.size 不匹配预期时回退到 PropertyTag 循环，不产生静默误读"
    - "BodyInstance 使用通用 PropertyTag 回退路径，无专用 fast-path"
    - "graph.py L165 的 release_version 死代码已被清理"
    - "parse_uasset.py 在 build_version_container() 后将 version_container 注入到 summary.version_container"
    - "全量测试绿灯（或剩余失败已明确证明与 Phase 76 无关并单独记录）"
    - ".planning/STATE.md 和 README 准确反映 Phase 76 状态"
  artifacts:
    - path: src/uasset_read/serializers/package_summary.py
      provides: PackageFileSummary 新增 version_container 字段
      contains: "version_container: Optional[VersionContainer]"
    - path: src/uasset_read/parse_uasset.py
      provides: version_container 注入到 summary
      contains: "result.summary.version_container = result.version_container"
    - path: src/uasset_read/parsers/property_parser.py
      provides: 3 处版本判断迁移至 VersionContainer
      exports: []
    - path: src/uasset_read/serializers/graph.py
      provides: L165 死代码清理 + L1688 版本判断迁移
      exports: []
    - path: src/uasset_read/kismet/bytecode_extractor.py
      provides: 2 处版本判断迁移至 VersionContainer
      exports: []
    - path: src/uasset_read/kismet/bpgc_bytecode.py
      provides: 2 处版本判断迁移至 VersionContainer
      exports: []
    - path: src/uasset_read/parsers/property_types.py
      provides: StructProperty fast-path 的 tag.size 校验
      contains: _EXPECTED_STRUCT_SIZES
    - path: tests/test_versioning.py
      provides: VersionContainer 集成测试
      exports: []
    - path: tests/test_struct_property.py
      provides: tag.size 不匹配回退测试
      exports: []
  key_links:
    - from: parse_uasset.py
      to: package_summary.py
      via: version_container 注入到 PackageFileSummary
      pattern: "result\\.summary\\.version_container = result\\.version_container"
    - from: property_parser.py
      to: versioning.py
      via: summary.version_container.is_at_least()
      pattern: "version_container\\.is_at_least"
    - from: property_types.py
      to: property_types.py
      via: fast-path 内 tag.size 校验 -> 回退 PropertyTag loop
      pattern: _EXPECTED_STRUCT_SIZES
---

# Phase 76-01 执行计划 — FArchive COR 修复收口

**Milestone:** v14.0 — CUE4Parse 核心对齐
**Phase:** 76
**Scope:** COR-01 (StructProperty 边界) + COR-02 (VersionContainer 收口)
**Status:** Ready for execution (Blockers fixed)
**Date:** 2026-05-27

---

## 背景

Phase 76 不是"未开始"，而是"部分实现、未收口"。

已落地部分：
- `VersionContainer`、`build_version_container()`、`EUEVersion` 已在 `versioning.py` 实现。
- `parse_uasset()` / `parse_uasset_with_linker()` 已挂接 `version_container` 构建。
- `StructProperty` 已扩展 19 类 fast-path（Vector / Rotator / Transform 等）。
- `tests/test_versioning.py` + `tests/test_struct_property.py` 共 38 个测试通过。

未收口问题（经研究确认）：
1. `VersionContainer` 尚未成为关键读取路径的版本判断入口 — 4 个关键文件仍直接访问 `summary.file_version_ue5`。
2. `version_container` 挂在 `ParseResult` 上而非 `PackageFileSummary` 上 — 下游函数收到的 `summary.version_container` 始终为 `None`。
3. 所有 19 个 StructProperty fast-path **零 tag.size 校验** — 若 tag.size 不匹配预期，快径会读取错误字节并导致后续数据错位。
4. `serializers/graph.py` L165 `release_version = summary.get_custom_version(...)` 是死代码 — 赋值后从未使用。
5. 文档状态与代码脱节（STATE.md 仍标记 Next，PLAN.md 把已存在文件写成待新建）。

本计划只处理剩余未收口项，不重复已落地部分。

---

## 目标

1. **COR-02 收口** — 4 个关键路径的硬编码版本判断收敛到 `VersionContainer`，并修复 version_container 注入链路。
2. **COR-01 收口** — StructProperty fast-path 增加 `tag.size` 校验 + BodyInstance 明确走回退路径。
3. **阶段完成门槛** — 全量测试绿灯，文档反映真实进度。

---

## 非目标

- Phase 78 的 UObject 继承树重构
- Phase 79 的 IoStore 支持
- 大规模 EGame / 游戏特化 VersionContainer 设计
- 全仓库所有 `file_version_ue5` 判断的一次性替换（仅收敛 4 个关键路径）
- formatters / package_summary.py 的版本访问迁移（display-only 或赋值处，不迁移）

---

## 执行 Waves（4 waves，顺序不可颠倒）

### Wave 1: VersionContainer 基础设施 + 关键路径收敛

目标：解决架构分叉，让 VersionContainer 从"结果对象附带字段"升级为"实际参与序列化决策的基础设施"。

#### 任务 1.1：PackageFileSummary 增加 version_container 字段 + 注入链路修复

**文件:** `src/uasset_read/serializers/package_summary.py`, `src/uasset_read/parse_uasset.py`

**行动 — package_summary.py:**
- 在 `PackageFileSummary` dataclass 中增加可选字段：`version_container: Optional["VersionContainer"] = None`
- 使用 `TYPE_CHECKING` 导入避免循环依赖：
  ```python
  from typing import TYPE_CHECKING
  if TYPE_CHECKING:
      from uasset_read.versioning import VersionContainer
  ```

**行动 — parse_uasset.py（Blocker #1 修复）:**
- 在两处 `build_version_container()` 调用后添加注入代码：
  ```python
  # Line ~234 (parse_uasset 函数)
  result.version_container = build_version_container(result.summary)
  result.summary.version_container = result.version_container  # 新增：注入到 Summary

  # Line ~320 (parse_uasset_with_linker 函数)
  result.version_container = build_version_container(result.summary)
  result.summary.version_container = result.version_container  # 新增：注入到 Summary
  ```

**验收:**
- `PackageFileSummary` 可接受 `version_container=None` 参数
- `parse_uasset()` 和 `parse_uasset_with_linker()` 在两处构建后注入 `summary.version_container`
- 下游函数可通过 `summary.version_container` 访问 VersionContainer
- 现有所有测试不受影响

---

#### 任务 1.2：关键路径版本判断迁移（property_parser.py + graph.py）

**文件:** `src/uasset_read/parsers/property_parser.py`, `src/uasset_read/serializers/graph.py`

**行动 — property_parser.py（3 处替换）：**

使用统一的 conditional 模式：
```python
summary.version_container.is_at_least(UE5_SCRIPT_SERIALIZATION_OFFSET) if summary.version_container else summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET
```

L133: `summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET` → 替换为上述模式
L140: `summary.file_version_ue5 >= UE5_PROPERTY_TAG_EXTENSION` → 替换为上述模式
L148: `summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET` → 替换为上述模式

**行动 — graph.py（2 处处理）：**

L165-166: `release_version = summary.get_custom_version(FRELEASE_OBJECT_VERSION_GUID, 0)` — **死代码**，直接删除该行及变量。`release_version` 在 `read_ed_graph_pin_type()` 函数体内从未被使用。

L1688: `summary.file_version_ue5 >= 1011` — 改为使用已有常量 `UE5_PROPERTY_TAG_EXTENSION`（值 = 1011）：
```python
summary.version_container.is_at_least(UE5_PROPERTY_TAG_EXTENSION) if summary.version_container else summary.file_version_ue5 >= UE5_PROPERTY_TAG_EXTENSION
```
**注意（Warning #3 修复）：** 不新增 `UE5_1011` 常量，直接使用已有的 `UE5_PROPERTY_TAG_EXTENSION`。

**验收:**
- property_parser.py 中 3 处 `summary.file_version_ue5 >=` 改为 conditional VersionContainer 优先模式
- graph.py L165 死代码删除，L1688 改为 VersionContainer 模式
- `python -m pytest tests/test_versioning.py -q` 通过

---

#### 任务 1.3：关键路径版本判断迁移（bytecode_extractor.py + bpgc_bytecode.py）

**文件:** `src/uasset_read/kismet/bytecode_extractor.py`, `src/uasset_read/kismet/bpgc_bytecode.py`

**行动：**

bytecode_extractor.py（2 处）：
- L96: `summary.file_version_ue5 >= UE5_PROPERTY_TAG_EXTENSION` → 同任务 1.2 的 conditional 模式
- L104: 同上模式

bpgc_bytecode.py（2 处）：
- L132: `summary.file_version_ue5 >= UE5_PROPERTY_TAG_EXTENSION` → 同上
- L140: 同上

**验收:**
- 4 处替换完成
- 所有关键路径（共 9 处：property_parser 3 + graph 2 + bytecode_extractor 2 + bpgc_bytecode 2）全部收敛
- `python -m pytest tests/ -q --tb=short -k "kismet"` 通过（如有相关测试）

---

#### 任务 1.4：VersionContainer 集成测试

**文件:** `tests/test_versioning.py`

**行动:**
- 新增测试验证 `VersionContainer.is_at_least()` 在不同阈值下的行为（覆盖等于/大于/小于阈值三种情况）
- 新增测试验证 `version_container=None` 时的旧行为兼容性回退
- 新增测试验证 `summary.version_container` 在 parse_uasset 后被正确注入（可通过 mock summary 验证）

**验收:**
- `tests/test_versioning.py` 至少新增 3 个测试用例
- 所有测试通过

---

**Wave 1 验收标准:**
- [ ] PackageFileSummary 可接收 version_container 字段
- [ ] parse_uasset.py 在两处注入 summary.version_container
- [ ] 4 个关键文件共 9 处版本判断改为 VersionContainer 优先模式
- [ ] graph.py L165 死代码已删除
- [ ] test_versioning.py 新增 ≥3 个集成测试
- [ ] `pytest tests/test_versioning.py -q` 通过

---

### Wave 2: StructProperty 快径 tag.size 校验 + BodyInstance 策略

目标：让 fast-path 与 fallback 的边界明确、可验证。

研究确认：CUE4Parse 自身 **不验证** tag.size，但我们的项目已有 `struct_end` 跟踪和 `value_end_offset` 对齐恢复（Phase 73 Wave 4）。缺口在于 fast-path structs 在 raw read 前不校验 tag.size。

#### 任务 2.1：19 个 fast-path struct 增加 tag.size 校验（Blocker #2 修复）

**文件:** `src/uasset_read/parsers/property_types.py`

**行动:**

在 `parse_struct_property()` 函数中增加预期大小映射和**统一预检**逻辑：

```python
# 在文件顶部常量区域新增
_EXPECTED_STRUCT_SIZES: dict[str, int] = {
    "Vector": 12, "Rotator": 12, "Vector2D": 8, "Vector4": 16,
    "LinearColor": 16, "Color": 4, "Quat": 16, "Plane": 16,
    "Guid": 16, "IntPoint": 8, "IntVector": 12,
    "Box2D": 20, "Box": 28, "Sphere": 16, "BoxSphereBounds": 40,
    "Matrix": 64, "TwoVectors": 24, "OrientedBox": 60,
    "Transform": 48,
}
```

**控制流策略（修复 Blocker #2）：** 在函数顶部、所有 fast-path 分支之前做统一预检：

```python
# 在 parse_struct_property() 函数开始、fast-path 分发之前
expected_size = _EXPECTED_STRUCT_SIZES.get(struct_type)
if expected_size is not None and tag.size != expected_size:
    logger.warning(
        "StructProperty '%s': tag.size=%d != expected=%d, using fallback",
        struct_type, tag.size, expected_size,
    )
    # 跳过所有 fast-path 分支，直接走下方 PropertyTag loop
    # 将 struct_type 设为 None 或设置一个标志，让后续 fast-path if 分支全部不匹配
    struct_type = None  # 或设置 _use_fallback = True
```

**关键实现细节:**
- 预检在所有 fast-path `if struct_type == "X":` 分支**之前**
- tag.size 不匹配时通过修改 `struct_type` 变量（或设置标志），让后续所有 fast-path if 条件不成立
- 自然落到底部的 PropertyTag loop 通用解析路径
- 使用 `logger.warning` 而非 `logger.error`，因为这是版本差异而非错误

**验收:**
- 19 个 fast-path struct 都有 tag.size 校验
- tag.size 不匹配时走 PropertyTag loop 而非 fast-path
- `pytest tests/test_struct_property.py -q` 通过

---

#### 任务 2.2：BodyInstance 明确使用回退路径

**文件:** `src/uasset_read/parsers/property_types.py`

**行动:**
- 研究确认：CUE4Parse 仅在 ConanExilesEnhanced 游戏特化中有 BodyInstance 处理，通用情况全部走 `FStructFallback`（PropertyTag loop）。
- 确保 `parse_struct_property()` 中没有 BodyInstance 专用 fast-path（如有则删除）。
- 如果 BodyInstance 尚未被任何 fast-path 覆盖，则不需要额外处理 — 它已自然走 PropertyTag loop。
- 在代码注释中明确标注：`# BodyInstance: 复杂结构，版本差异大，使用通用 PropertyTag loop — 与 CUE4Parse FStructFallback 一致`

**验收:**
- BodyInstance 无专用 fast-path
- 代码注释说明策略选择及依据

---

#### 任务 2.3：StructProperty 边界测试扩充

**文件:** `tests/test_struct_property.py`

**行动:** 新增至少 4 个测试用例：

1. **正常 fast-path** — 现有测试已覆盖，确认不变。
2. **tag.size 异常 → 回退** — 构造一个 tag.size 不等于预期值的 StructProperty，验证它走 PropertyTag loop 而非 fast-path（可通过 mock archive 实现）。
3. **fallback 成功解析** — 验证 tag.size 不匹配时 PropertyTag loop 能正确解析 struct 内容。
4. **fallback 失败时位置恢复** — 构造一个无法解析的 struct，验证 archive 位置不会损坏后续读取。

**验收:**
- `pytest tests/test_struct_property.py -q` 通过
- 新增 ≥4 个边界测试用例

---

**Wave 2 验收标准:**
- [ ] 19 个 fast-path struct 均有 tag.size 校验（统一预检模式）
- [ ] BodyInstance 无专用 fast-path，使用 PropertyTag loop
- [ ] test_struct_property.py 新增 ≥4 个边界测试
- [ ] `pytest tests/test_struct_property.py -q` 通过

---

### Wave 3: 清理阻断 Phase 完成的测试红灯

目标：不让 Phase 76 在回归失败状态下"完成"。

#### 任务 3.1：诊断并修复 Phase 75 事件节点对齐测试

**文件:** `tests/test_phase75_event_node_field_alignment.py`

**行动:**
1. 先运行测试，获取具体失败信息：
   ```powershell
   python -m pytest tests/test_phase75_event_node_field_alignment.py -v --tb=long
   ```
2. 分析失败原因：
   - 如果是**代码回归**（Phase 75 修改引入的 bug）→ 修复代码
   - 如果是**测试假设过强**（测试期望与真实 UE 语义不符）→ 修正测试，但必须在测试注释中写清依据（引用 UE 源码 / CUE4Parse / 现有模型）
3. 关注点：
   - `graph.py` L1844-1846 `b_override_function` 的 PropertyTag 读取
   - `read_k2node_event()` 中 legacy fallback 的 b_override_function 读取位置
   - EventReference 和相关字段的解析一致性

**"无关失败"判定规则（Warning #5 修复）：** 任何被标记为"无关"的失败必须附带一行说明，格式为：
```
# UNRELATED: <失败描述> — 涉及文件/函数 <X> 不在 Phase 76 变更范围内（变更文件：property_parser.py, graph.py, bytecode_extractor.py, bpgc_bytecode.py, property_types.py, package_summary.py, parse_uasset.py）
```

**验收:**
- `pytest tests/test_phase75_event_node_field_alignment.py -q` 通过
- 如有测试修正，注释中写明依据

---

#### 任务 3.2：验证 N2C 全量回归门禁

**文件:** `tests/n2c/test_full_regression.py`

**行动:**
1. 运行全量测试确认当前状态：
   ```powershell
   python -m pytest tests/ -q --tb=no
   ```
2. 如果仍有失败：
   - 确认是否与 Phase 76 的修改相关
   - 如果相关 → 在 Wave 3 内修复
   - 如果不相关 → 应用任务 3.1 的"无关失败"判定规则，在 STATE.md 中记录

**验收:**
- 全量测试通过，或
- 剩余失败已明确证明与 Phase 76 无关，并单独记录在 STATE.md 中（附带无关判定说明）

---

**Wave 3 验收标准:**
- [ ] Phase 75 事件节点对齐测试通过
- [ ] N2C 全量回归门禁通过（或无关失败已记录并附带判定说明）
- [ ] `pytest tests/ -q` 全量绿灯（或剩余失败已单独记录且明确无关）

---

### Wave 4: 文档与状态收口

目标：文档反映事实。

#### 任务 4.1：更新规划文档

**文件:** `.planning/STATE.md`, `.planning/ROADMAP.md`, `.planning/phases/phase-76/PLAN.md`

**行动:**

STATE.md:
- Phase 76 状态从 `Next` 更新为实际状态（`Complete` 如果 Wave 1-3 全部通过，否则 `In Progress`）
- 补充已完成项列表

ROADMAP.md:
- Phase 76 条目更新 Plans 数量和描述
- 计划列表更新为实际存在的 PLAN 文件

PLAN.md（本文件）:
- 执行完成后在文件头部添加 `**Completed:** 2026-05-27` 时间戳
- 如有未完成项，在文件末尾标注

**验收:**
- 三个文档中 Phase 76 状态一致

---

#### 任务 4.2：更新 README 状态

**文件:** `README.md`, `README.zh-CN.md`

**行动:**
- Phase 76 从 `76⬜` 更新为 `76✅`（如完成）或保持 `76⬜`（如部分完成，在注释中说明进度）
- 测试数量更新为最新实际值（Wave 3 运行后的实际通过数）
- 版本号和阶段描述与实际进度一致

**验收:**
- 两个 README 中 Phase 76 状态一致
- 测试数量为最新实际值

---

**Wave 4 验收标准:**
- [ ] STATE.md / ROADMAP.md / PLAN.md 状态一致
- [ ] README.md / README.zh-CN.md 状态一致
- [ ] 测试数量为最新实际值

---

## 依赖图

```
Wave 1: 任务 1.1 → 任务 1.2 + 任务 1.3 → 任务 1.4
         (Summary字段+注入) (关键路径迁移)    (集成测试)
                      ↑ 任务 1.2 和 1.3 可并行

Wave 2: 任务 2.1 + 任务 2.2 → 任务 2.3
        (tag.size 校验)  (BodyInstance)  (边界测试)

Wave 3: 任务 3.1 + 任务 3.2
        (Phase 75 红灯) (N2C 回归)

Wave 4: 任务 4.1 + 任务 4.2
        (规划文档)     (README)
```

Wave 依赖关系：
- Wave 2 不依赖 Wave 1（StructProperty tag.size 校验是独立变更）
- Wave 3 依赖 Wave 1 + Wave 2（需要前两个 wave 的变更都已合入后才能准确诊断红灯）
- Wave 4 依赖 Wave 1-3 全部完成

---

## 文件所有权（并行执行）

| 文件 | Wave 1 | Wave 2 | Wave 3 |
|------|--------|--------|--------|
| package_summary.py | 任务 1.1 | — | — |
| parse_uasset.py | 任务 1.1（注入修复） | — | — |
| property_parser.py | 任务 1.2 | — | — |
| graph.py | 任务 1.2 | — | — |
| bytecode_extractor.py | 任务 1.3 | — | — |
| bpgc_bytecode.py | 任务 1.3 | — | — |
| property_types.py | — | 任务 2.1, 2.2 | — |
| test_versioning.py | 任务 1.4 | — | — |
| test_struct_property.py | — | 任务 2.3 | — |
| test_phase75_event_node_field_alignment.py | — | — | 任务 3.1 |
| test_full_regression.py | — | — | 任务 3.2 |

Wave 1 内部：任务 1.2 和 1.3 可并行（修改不同文件）。
Wave 2 内部：任务 2.1 和 2.2 可并行（同一文件不同区域）。

---

## 测试计划

### Wave 1 完成后

```powershell
python -m pytest tests/test_versioning.py -q
```

### Wave 2 完成后

```powershell
python -m pytest tests/test_struct_property.py -q
```

### Wave 3 完成后（全量回归）

```powershell
python -m pytest tests/ -q --tb=short
```

---

## 完成定义

Phase 76 只有在满足以下条件时才可标记 `Complete`：

1. `PackageFileSummary` 有 `version_container` 字段，且 `parse_uasset.py` 在两处正确注入
2. `VersionContainer` 已真实参与 4 个关键读取路径的版本判断（9 处替换完成）
3. 所有 StructProperty fast-path（19 个）有 `tag.size` 校验（统一预检模式），不匹配时回退 PropertyTag loop
4. BodyInstance 使用通用 PropertyTag loop，无专用 fast-path
5. graph.py L165 死代码已清理
6. 全量测试为绿灯（或剩余失败已明确证明与 Phase 76 无关并单独记录，附带无关判定说明）
7. `.planning` 与 README 状态已更新为一致

---

## 风险与对策

### 风险 A: VersionContainer 为 None 时回退路径未覆盖

**对策:** 任务 1.2/1.3 中所有替换使用 conditional 模式（`if summary.version_container else ...`），确保旧行为兼容性。

### 风险 B: tag.size 校验误杀合法变体

**对策:** 使用 `logger.warning` 而非 error，回退路径使用已有的 PropertyTag loop，不会跳过 struct。统一预检模式确保控制流清晰。

### 风险 C: Phase 75 红灯与 Phase 76 修改无关但阻塞完成

**对策:** Wave 3 先运行测试获取具体失败信息，判断是代码回归还是测试假设过强。无关失败按"无关判定规则"记录在 STATE.md 中，不阻塞 Phase 76 标记完成。

### 风险 D: 文档状态提前宣布完成

**对策:** 文档更新在 Wave 4（最后），以 Wave 3 全量测试结果决定 `Complete` 或 `In Progress`。

### 风险 E: `is_at_least()` 语义混淆

**对策（Warning #6）：** `VersionContainer.is_at_least(threshold, stream)` 通过 GUID 查 custom version stream 比较。对于 `file_version_ue5` 阈值（如 1011 = `UE5_PROPERTY_TAG_EXTENSION`），应使用 `summary.version_container.is_at_least(threshold)`（stream 参数使用默认 "framework" 即可，因为 `is_at_least` 内部会通过 stream GUID 查版本号比较）。如果 `is_at_least` 的内部实现是直接比较 `file_version_ue5` 而非 custom version，则需要确认实现语义。当前 `versioning.py` 的 `is_at_least()` 查的是 custom version stream，所以对于 `file_version_ue5` 阈值，应该直接使用 `summary.version_container.file_version_ue5 >= threshold`。

**修正:** 经过检查，`versioning.py` 的 `is_at_least()` 方法是通过 GUID 查 custom version，不是比较 `file_version_ue5`。所以对于 L133/L148 的 `UE5_SCRIPT_SERIALIZATION_OFFSET` 和 L1688 的 `1011` 这些 `file_version_ue5` 阈值，应该用：
```python
summary.version_container.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET if summary.version_container else summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET
```

任务 1.2 和 1.3 中使用此修正模式。

---

## 推荐执行命令

```powershell
# Wave 1
python -m pytest tests/test_versioning.py -q

# Wave 2
python -m pytest tests/test_struct_property.py -q

# Wave 3
python -m pytest tests/test_phase75_event_node_field_alignment.py -q
python -m pytest tests/ -q --tb=short

# Wave 4
# 手动更新文档（任务 4.1 + 4.2）
```

---

*Created: 2026-05-27*
*Research incorporated: 76-RESEARCH.md (CUE4Parse source verified, 9 HIGH/MEDIUM locations, 19 fast-path structs, BodyInstance Option 2, graph.py L165 dead code)*
*Plan verification: 2 Blockers fixed (version_container injection, tag.size control flow), 3 Warnings addressed (constant reuse, scope, unrelated-failure criteria), 1 additional Warning fixed (is_at_least semantics for file_version_ue5 thresholds)*
