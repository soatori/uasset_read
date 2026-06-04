# uasset_read 蓝图实现差距修复计划

> **日期**: 2026-06-04
> **基于**: `docs/superpowers/reports/2026-06-04-uasset-blueprint-implementation-gap-report.md`
> **目标**: 将项目从"结构化读取"提升到"可理解的蓝图功能实现代码输出"

---

## 执行摘要

当前项目已具备基础解析能力，但存在5个核心差距：

1. **测试基线不可信** — 1个失败测试 + xpassed + .gitignore 遗漏测试文件
2. **偏移/范围越界无结构化诊断** — 139个已知错误模式无统一报告
3. **C++ 输出不可编译** — 变量名空格、空默认值、函数壳嵌套
4. **Kismet 反编译语义不足** — 大量 `/* deprecated */` 和 `goto`
5. **全量资产成功率未达 99.5%** — 当前约 96.4%

---

## Phase 0: 修复测试基线 (预计 2-3 小时)

### 目标
恢复可信测试状态，确保 100% 通过率（xfail 除外）。

### Task 0.1: 修复 `test_borderlands4_custom_properties` 回归

**当前状态**: ✅ 已修复（测试已通过）

```bash
python -m pytest tests/test_cue4parse_gap_completion.py::test_borderlands4_custom_properties -v
# 结果: PASSED
```

### Task 0.2: 检查 xpassed 测试

**当前状态**: 1 个 xpassed

**具体测试**: `tests/test_api_cleanup.py::test_format_graphs_json_minimal_graph_does_not_crash`

**问题**: 测试标记为 `@pytest.mark.xfail(reason="format_graphs_json 依赖已删除的 n2c.processors 模块")`，但现在已通过

**修复方案**:
1. 检查 `format_graphs_json` 是否仍有 n2c 依赖
2. 如果已修复，移除 xfail marker
3. 如果是误报，更新 reason 或调整测试

**验收**: 0 个 xpassed

### Task 0.3: 修复 .gitignore 测试文件遗漏

**问题**: 27 个测试文件在磁盘上，但只有 20 个被 Git 跟踪

**被忽略的文件**:
- `tests/test_kismet_decompilation.py`
- `tests/test_unknown_property_fallback.py`
- `tests/test_tolerant_class_specific.py`
- `tests/test_binary_or_native_handlers.py`
- `tests/test_error_recovery.py`
- 等 7 个文件

**修复方案**:
1. 修改 `.gitignore`，移除 `tests/*` 的默认忽略规则
2. 改为显式忽略特定临时文件（如 `tests/temp/*`）
3. 将所有应纳入项目的测试文件加入 Git

**验收**:
```bash
git status tests/  # 确认所有 test_*.py 被跟踪
python -m pytest tests/ --co -q  # 确认收集数量与磁盘一致
```

### Task 0.4: 更新测试统计文档

**操作**:
1. 更新 `docs/release-notes/testing-requirements.md` 中的测试数量
2. 更新 CLAUDE.md 中的测试统计（当前 452 个测试）
3. 确认 integration 测试数量（当前 42 个）

**验收**: 文档数字与 `pytest --co` 输出一致

---

## Phase 1: 建立偏移/范围诊断 (预计 4-6 小时)

### 目标
所有 offset/range 越界都结构化报告，不再静默吞掉。

### Task 1.1: 新增 OffsetRangeDiagnostic 模型

**新增文件**: `src/uasset_read/models/diagnostics.py`

```python
@dataclass
class OffsetRangeDiagnostic:
    """偏移/范围越界诊断信息"""
    kind: str = "offset_range_diagnostic"
    asset_path: str = ""
    asset_type: str = ""
    module: str = ""  # linker|property|graph|pin|kismet|pak|iostore
    object_name: str = ""
    export_index: int | None = None
    import_index: int | None = None
    field: str = ""  # serial_offset|script_serial_offset|ValueEndOffset|CodeOffset|LinkedTo
    current_pos: int = 0
    target_offset: int = 0
    read_size: int = 0
    file_size: int = 0
    range_start: int | None = None
    range_end: int | None = None
    source: str = ""  # 计算来源
    error: str = ""
    fallback_used: bool = False
    fallback_result: str = ""  # failed|partial|success
```

**测试**: `tests/test_offset_range_diagnostic.py`

### Task 1.2: 在关键点接入诊断

**诊断点清单**:

| 位置 | 文件 | 检查内容 |
|------|------|----------|
| archive.seek() | `archive.py` | 目标超出文件大小 |
| archive.read_bytes() | `archive.py` | 请求范围超出剩余文件 |
| export serial range | `serializers/object_resources.py` | `serial_offset + serial_size` 超出文件 |
| script serial range | `serializers/object_resources.py` | `script_serial_offset + script_serial_size` 超出 export 范围 |
| UE5 ValueEndOffset | `parsers/property_parser.py` | 小于当前位置或超出 export |
| Array/Map/Set count | `parsers/` | 负数或超过上限 |
| Pin LinkedTo/SubPins | `serializers/graph.py` | count 异常 |
| Kismet CodeOffset | `kismet/jump_analyzer.py` | 找不到表达式目标 |
| Pak compression block | `pak/` | offset/size 越界 |

**实现策略**:
- 在 `FArchive` 中添加 `seek_safe()` 和 `read_safe()` 方法
- 返回 `Result[T, OffsetRangeDiagnostic]` 或抛出 `OffsetRangeError`（tolerant 模式捕获）
- 在 `ParseResult` 中添加 `diagnostics: list[OffsetRangeDiagnostic]` 字段

### Task 1.3: JSON/Markdown 输出 diagnostics

**修改文件**:
- `src/uasset_read/renderers/json_renderer.py` — 输出 `diagnostics` 数组
- `src/uasset_read/renderers/markdown_renderer.py` — 诊断信息章节

**输出格式**:
```json
{
  "diagnostics": [
    {
      "kind": "offset_range_diagnostic",
      "module": "linker",
      "field": "serial_offset",
      "target_offset": 4294967296,
      "file_size": 2191,
      "error": "Offset exceeds file size",
      "fallback_used": true,
      "fallback_result": "partial"
    }
  ]
}
```

### Task 1.4: 测试覆盖

**测试用例**:
1. 正常偏移不产生诊断
2. 越界偏移产生诊断且包含完整字段
3. tolerant 模式下诊断进入 `result.diagnostics`
4. strict 模式下越界抛出 `OffsetRangeError`
5. 真实资产回归测试（`BP_FirstPersonCharacter`）

**验收**:
- 4294967295/4294967296 这类问题有结构化报告
- tolerant 模式不静默吞掉越界
- 每个诊断包含 offset、size、file_size、source、fallback_result

---

## Phase 2: 修复 C++ 输出基本正确性 (预计 3-4 小时)

### 目标
输出不再出现明显非法 C++。

### Task 2.1: 修复变量名 sanitizer

**问题**: 变量名包含空格（如 `Target Touch UI`）

**修复方案**:
1. 在 `cpp_gen/formatters.py` 或 `cpp_gen/extract_cpp_skeleton.py` 中添加 `sanitize_identifier()` 函数
2. 规则：
   - 空格 → 下划线
   - 移除非法字符（保留 `[a-zA-Z0-9_]`）
   - 数字开头 → 前缀 `_`
   - C++ 保留字 → 后缀 `_`
3. 在所有变量名输出点调用 sanitizer

**测试**:
```python
def test_sanitize_identifier_spaces():
    assert sanitize_identifier("Target Touch UI") == "Target_Touch_UI"

def test_sanitize_identifier_special_chars():
    assert sanitize_identifier("MyVar@#$") == "MyVar"

def test_sanitize_identifier_leading_digit():
    assert sanitize_identifier("123Var") == "_123Var"
```

### Task 2.2: 修复默认值空输出

**问题**: `= ;`（空默认值）

**根因**: `format_cpp_default_value()` 在值为空字符串时仍输出 `= `

**修复方案**:
1. 在 `cpp_gen/cpp_default_value_formatter.py` 中检查值是否为空
2. 空值时不输出赋值部分

```python
def format_cpp_default_value(var_name: str, var_type: str, default_value: str) -> str:
    if not default_value or default_value.strip() == "":
        return f"{var_type} {var_name}"  # 无默认值
    return f"{var_type} {var_name} = {default_value}"
```

### Task 2.3: 修复函数体 wrapper 嵌套

**问题**:
```cpp
void Aim(float Yaw, float Pitch)
{
    Aim() {
    /* deprecated */
    return;
    }
}
```

**根因**: `body_text` 包含完整函数文本（含签名），被直接塞进另一个函数实现

**修复方案**:
1. 明确 `CppMethodIR.body_text` 约定：只存函数体语句，不存完整 wrapper
2. 在 `kismet/body_builder.py` 的 `to_function_body_structured()` 中，只返回 `{` 和 `}` 之间的内容
3. 在 `cpp_gen/formatters.py` 输出方法实现时，使用 `ClassName::MethodName` 格式

### Task 2.4: 修复 .cpp 重复头

**问题**: `.cpp` 文件头部重复

**修复方案**: 检查 `format_cpp_header()` 和 `format_cpp_source()` 的调用逻辑，确保不重复输出 `#include` 和命名空间声明

### Task 2.5: 方法实现加类作用域

**问题**: 方法实现缺少 `ClassName::` 前缀

**修复方案**:
```cpp
// 错误
void Aim(float Yaw, float Pitch) { ... }

// 正确
void AMyCharacter::Aim(float Yaw, float Pitch) { ... }
```

**验收**:
- `BP_FirstPersonCharacter` 输出无 `= ;`
- 输出无带空格变量名
- 函数体无嵌套函数定义
- `cpp_skeleton` 基本格式稳定

---

## Phase 3: 提升 Kismet 反编译语义 (预计 8-12 小时)

### 目标
从 token 伪代码提升为可理解的实现参考。

### Task 3.1: 解析 deprecated / instrumentation token

**问题**: 大量 `/* deprecated */` 输出

**UE 源码参考**:
- `0xFF` = `EX_Instrumentation` — 调试/性能标记，非功能代码
- `0x4A` = `EX_DeprecatedOp4A` — 已废弃操作码

**修复方案**:
1. 在 `kismet/translator.py` 中，将 `EX_Instrumentation` 和 `EX_DeprecatedOp*` 标记为可跳过
2. 不输出 `/* deprecated */`，而是静默跳过或输出 `/* instrumentation: debug only */`
3. 统计 deprecated token 比例，纳入质量报告

### Task 3.2: 完善 StackNode、VirtualFunction、Delegate、Interface 解析

**当前状态**:
- `FunctionRefResolver` 已实现基础解析
- 但 `EX_VirtualFunction` 和 `EX_LocalVirtualFunction` 仍可能输出 `Function_N`

**增强方案**:
1. 对 `EX_VirtualFunction`，从 `linker` 解析函数名
2. 对 `EX_LocalFinalFunction`，检查是否为蓝图本地函数
3. 对 delegate 调用，解析绑定对象和函数名

### Task 3.3: 建立常见蓝图节点到 C++ 语义调用映射

**映射表**:

| 蓝图节点 | UE 类/函数 | C++ 输出 |
|----------|-----------|----------|
| EnhancedInputAction | `UEnhancedInputAction` | `OnActionTriggered(ActionValue)` |
| AddMovementInput | `ACharacter::AddMovementInput` | `AddMovementInput(WorldDirection, ScaleValue)` |
| Jump | `ACharacter::Jump` | `Jump()` |
| StopJumping | `ACharacter::StopJumping` | `StopJumping()` |
| SetTimer | `UKismetSystemLibrary::K2_SetTimer` | `GetWorldTimerManager().SetTimer(...)` |
| Branch | `UKismetNode` | `if (condition) { ... } else { ... }` |
| Sequence | `UKismetNode` | `{ /* Then 0 */ } { /* Then 1 */ }` |

**实现位置**: `kismet/translator.py` 的 `MathFunctionCleaner.clean()` 或新增 `BlueprintNodeCleaner`

### Task 3.4: 完善控制流结构化

**当前状态**: `JumpAnalyzer` 支持基础 if/else、while

**增强方案**:
1. 支持 for 循环模式检测
2. 支持 switch/case 模式检测
3. 支持 sequence 节点（多输出引脚）
4. 降低 goto fallback 比例

**目标**: 控制流结构化率 >= 70%

### Task 3.5: 建立质量统计脚本

**新增文件**: `scripts/quality_stats.py`

**统计指标**:
- `Function_N` 占位符比例（目标 < 10%）
- `goto` fallback 比例（目标 < 30%）
- `/* deprecated */` 比例
- 函数体为空或只有 `return` 的比例

**验收**:
- `Move` 输出应能体现输入参数和移动调用
- FirstPerson/ThirdPerson 样本中主要事件和函数输出不再只是 `return`
- `Function_` 占位符比例可量化并低于目标阈值
- `goto` 比例可量化并低于目标阈值

---

## Phase 4: 全量资产成功率提升 (预计 6-8 小时)

### 目标
从 96.4% 向 99.5% 推进。

### Task 4.1: 修复 linker 偏移越界

**已知问题**: 85 个 `Offset 4294967296 exceeds file size` 错误

**典型值**:
- `4294967295` = `0xFFFFFFFF` — 32 位无符号最大值
- `4294967296` = `0x100000000` — 溢出

**根因分析**:
- `FPackageIndex` 解析错误
- export/import 指向错误对象
- PropertyTag size / ValueEndOffset 错位

**修复方案**:
1. 在 `PackageIndex` 解析时添加边界检查
2. 在 `resolve_package_index()` 中验证 index 范围
3. 越界时返回 `None` 并记录诊断（Phase 1 的 `OffsetRangeDiagnostic`）

### Task 4.2: 修复数组 count 错位

**已知问题**: 33 个 `数组数量超过最大值` 或负数错误

**修复方案**:
1. 在数组/Map/Set 解析前检查 count 范围
2. 负数或超过 `MAX_PROPERTY_COUNT` 时记录诊断并跳过
3. 使用 `struct.unpack` 时检查溢出

### Task 4.3: 完善 UE4 legacy 支持或明确 xfail

**已知问题**: `P_Fire.uasset` (ParticleSystem) 使用 `legacy_file_version=-3`

**当前支持**: 仅 `{-9, -8}`

**方案**:
1. 如果 UE4 legacy 版本差异较小，扩展支持
2. 如果差异较大，在测试中标记 `xfail` 并记录原因
3. 在解析时输出明确诊断信息

### Task 4.4: 对截断/损坏文件输出明确诊断

**方案**:
1. 检测文件大小与预期不匹配的情况
2. 输出 `TruncatedFileDiagnostic` 或复用 `OffsetRangeDiagnostic`
3. 在 tolerant 模式下尽可能解析可用部分

### Task 4.5: unknown class/property fallback 完整落地

**当前状态**: Phase 0 的 unknown-asset-handling 计划已实施部分

**待完成**:
1. 确认 `PropertyFallback` 在所有未知类型路径生效
2. 确认 `ClassHandlerRegistry` 被正确使用
3. 添加更多 custom property handler（如需要）

**验收**:
- 4403 资产全量扫描通过率 >= 99.5%
- 每个失败都有明确分类和 xfail/skip 策略

---

## 执行顺序与依赖关系

```
Phase 0 (测试基线)
    ↓
Phase 1 (偏移诊断) ← 依赖 Phase 0 的可信测试
    ↓
Phase 2 (C++ 正确性) ← 依赖 Phase 1 的诊断能力
    ↓
Phase 3 (Kismet 语义) ← 依赖 Phase 2 的输出框架
    ↓
Phase 4 (全量成功率) ← 依赖 Phase 1-3 的所有修复
```

**并行机会**:
- Phase 1 和 Phase 2 可部分并行（诊断模型 vs C++ sanitizer）
- Phase 3 的 Task 3.1-3.3 可并行

---

## 最终验收标准

### 解析成功率
| 指标 | 目标 |
|------|------|
| 全量资产解析通过率 | >= 99.5% |
| integration 测试通过率 | 100%，xfail 除外 |
| stable 资产 strict/tolerant 双模式 | 全通过 |

### 蓝图功能输出
| 指标 | 目标 |
|------|------|
| 蓝图变量提取 | 名称、类型、默认值、GUID 可用 |
| 蓝图函数提取 | 函数名、参数、返回值可用 |
| 事件链 | Event -> Call chain 可追踪 |
| Kismet 反编译 | 主要函数体不为空、不只是 deprecated/return |
| 函数引用解析率 | >= 80% |
| 控制流结构化率 | >= 70% |

### C++ 输出质量
| 指标 | 目标 |
|------|------|
| 非法变量名 | 0 |
| 空默认值 `= ;` | 0 |
| 嵌套函数壳 | 0 |
| `Function_` 占位符 | 抽样比例 < 10% |
| `goto` fallback | 抽样比例受控且报告原因 |

### 诊断报告
| 指标 | 目标 |
|------|------|
| 偏移越界 | 必须结构化报告 |
| 范围越界 | 必须结构化报告 |
| 数组 count 异常 | 必须报告 count、位置、上限 |
| Kismet CodeOffset 缺失 | 必须报告 |
| fallback 使用 | 必须报告原因和结果 |

---

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| UE 源码理解不足 | Kismet 语义提升受限 | 优先参考 CUE4Parse 实现 |
| 全量资产测试环境不可用 | 无法验证 99.5% 目标 | 使用 CI 自动化测试 |
| 性能回归 | 大资产解析变慢 | 添加性能基准测试 |
| 破坏现有功能 | 测试失败 | 每个 Task 后运行完整测试 |

---

## 估算工时

| Phase | 任务数 | 预估工时 | 优先级 |
|-------|--------|----------|--------|
| Phase 0 | 4 | 2-3 小时 | P0 |
| Phase 1 | 4 | 4-6 小时 | P0 |
| Phase 2 | 5 | 3-4 小时 | P0 |
| Phase 3 | 5 | 8-12 小时 | P1 |
| Phase 4 | 5 | 6-8 小时 | P1 |
| **总计** | **23** | **23-33 小时** | |

---

## 下一步行动

1. **立即执行**: Phase 0 — 修复测试基线
2. **本周完成**: Phase 1 + Phase 2 — 诊断 + C++ 正确性
3. **下周完成**: Phase 3 — Kismet 语义提升
4. **后续**: Phase 4 — 全量资产成功率

选择执行方式：
1. **Subagent-Driven** — 每个 Task 独立子 agent 执行，中间审查
2. **Inline Execution** — 当前会话内批量执行，设置检查点
