# uasset_read 下一步目标审查报告

**日期**: 2026-06-04  
**范围**: 当前工作区磁盘状态  
**目标假设**: 项目目标调整为“能够成功解析 `.uasset` 文件，并输出蓝图函数、变量及其具体功能实现代码”。  

---

## 1. 总结结论

当前项目已经具备 `.uasset` 基础读取、包/linker 解析、蓝图变量提取、图结构提取、Kismet 字节码解析尝试、IR 输出和 C++ skeleton 生成能力。

但如果目标是“成功解析资产，并包含蓝图函数/变量的具体功能实现代码”，当前仍未达标。当前输出更接近：

- 结构化读取结果
- 蓝图图/变量/组件摘要
- Kismet token 级伪代码
- C++ 类骨架和参考输出

主要差距是：反编译结果无法稳定还原真实蓝图行为，C++ 输出目前存在不可编译片段，偏移/范围越界缺少统一诊断，测试标注和测试跟踪状态也存在不一致。

---

## 2. 当前已具备能力

### 2.1 解析管线

已有能力：

- 读取包摘要、名称表、导入表、导出表。
- 支持 linker 解析对象引用。
- 后处理阶段会提取 graph、blueprint metadata、components、imports、soft references。
- 后处理阶段会尝试 Kismet 反编译并写入 `result.decompiled_functions`。

关键文件：

- `src/uasset_read/parse_uasset.py`
- `src/uasset_read/package.py`
- `src/uasset_read/link/`
- `src/uasset_read/serializers/`

### 2.2 蓝图结构提取

已有能力：

- 提取 `BlueprintMetadata`。
- 提取变量、函数、事件、组件。
- 提取 `UEdGraph`、节点、Pin、执行链。
- 对 Pin GUID、LinkedTo 恢复、SubPins 重同步已有部分测试。

关键文件：

- `src/uasset_read/blueprint/variable_extractor.py`
- `src/uasset_read/graph/`
- `src/uasset_read/serializers/graph.py`
- `tests/test_pin_recovery.py`
- `tests/test_pin_guid_filtering.py`

### 2.3 Kismet 与 C++ 输出

已有能力：

- `FunctionRefResolver` 尝试将 StackNode 解析为 `ClassName::FuncName`。
- `JumpAnalyzer` 支持基础跳转目标分析。
- `StructuredControlFlow` 支持部分 if/else、while 模式。
- `decompiled_functions` 已进入 IR。
- JSON renderer 能输出 `decompiled_functions`。
- C++ skeleton renderer 可调用 cpp_gen 管线输出 `.h` 和 `.cpp` 参考。

关键文件：

- `src/uasset_read/kismet/function_resolver.py`
- `src/uasset_read/kismet/jump_analyzer.py`
- `src/uasset_read/kismet/structured_flow.py`
- `src/uasset_read/kismet/pipeline.py`
- `src/uasset_read/ir_builder.py`
- `src/uasset_read/renderers/json_renderer.py`
- `src/uasset_read/renderers/cpp_skeleton_renderer.py`
- `src/uasset_read/cpp_gen/`

---

## 3. 真实资产抽查结果

抽查资产：

`E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\FirstPerson\Blueprints\BP_FirstPersonCharacter.uasset`

当前结果：

| 项目 | 结果 |
|---|---:|
| parse success | true |
| errors | 0 |
| warnings | 0 |
| graphs | 4 |
| components | 6 |
| blueprint variables | 11 |
| blueprint functions | 3 |
| blueprint events | 0 |
| decompiled functions | 12 |

说明：基础解析和结构提取可用。

但函数体质量不足。示例：

```cpp
Move() {
    /* deprecated */
    return;
}
```

这无法表达真实蓝图逻辑，例如方向计算、移动输入、增强输入事件参数传递等。

C++ skeleton 抽查还出现：

```cpp
UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "variable")
StructProperty Target Touch UI = ; // UE type: StructProperty
```

以及函数体嵌套函数壳：

```cpp
void Aim(float Yaw, float Pitch)
{
    Aim() {
    /* deprecated */
    return;
    }
}
```

结论：当前输出不能作为“具体功能实现代码”，只能作为低可信度参考。

---

## 4. 核心缺口

### P0-1: Kismet 反编译语义不足

现象：

- 反编译函数体大量出现 `/* deprecated */`。
- `ExecuteUbergraph_*` 仍可能退化为 `goto Label_N`。
- 函数调用可能解析为低语义形式。
- 事件函数通常没有还原真实参数、输入 action、执行链语义。

影响：

- AI 或人工无法仅凭输出理解蓝图真实功能。
- 不能满足“具体功能实现代码”的目标。

下一步：

1. 明确 `0xFF` / deprecated / instrumentation token 的 UE 源码含义。
2. 完善 `EExprToken` 覆盖。
3. 将 Kismet token 翻译从“单行表达式”提升为“语义语句”。
4. 为常见节点建立语义映射：
   - EnhancedInputAction
   - AddMovementInput
   - Jump / StopJumping
   - SetTimer / Delay
   - Branch / Sequence / Switch
   - Interface / Delegate / Event Dispatch

验收：

- 典型 FirstPerson/ThirdPerson 蓝图输出应包含真实调用名。
- `Move` 这类函数不能只输出 `return`。
- `/* deprecated */` 不应作为主要函数体内容。

### P0-2: C++ 输出不可编译

现象：

- 变量名未完全 sanitize，例如包含空格。
- 默认值为空但仍输出 `= ;`。
- `body_text` 是完整函数文本，被直接塞进另一个函数实现中。
- `.cpp` 头部重复。
- 方法实现缺少类作用域或签名格式不稳定。

影响：

- `cpp_skeleton` 输出无法作为可靠 C++ 代码或接近可编译参考。

下一步：

1. 修复 `CppMethodIR.body_text` 约定：只存函数体语句，不存完整 wrapper。
2. formatter 输出方法实现时使用 `ClassName::MethodName`。
3. 对所有 C++ 标识符统一走 sanitizer。
4. 默认值无法可靠格式化时不输出赋值。
5. 区分 `.h` 声明、`.cpp` 实现、构造函数输出位置。

验收：

- 输出中不得出现 `= ;`。
- 输出中不得出现带空格的变量名。
- 函数体不得嵌套完整函数壳。
- 至少 `BP_FirstPersonCharacter` 输出能通过基本 C++ 文本检查。

### P0-3: 函数引用解析质量未达验收

已有 `FunctionRefResolver`，但仍缺少真实资产级统计。

下一步：

1. 抽样 50 个蓝图统计 `Function_` / `LocalFunction_` 占位符比例。
2. 统计 `ClassName::FuncName` 成功解析率。
3. 输出 unresolved 列表，包含 StackNode、export/import index、所在函数、资产路径。

验收：

- 函数引用解析率 >= 80%。
- 未解析引用必须进入报告，而不是只留在伪代码中。

### P0-4: 控制流结构化率未达验收

已有 `JumpAnalyzer` 和 `StructuredControlFlow`，但仍会 fallback 到 goto。

下一步：

1. 对 Kismet `CodeOffset` 建立统一目标解析报告。
2. 增强 if/else、while、for、switch、sequence 支持。
3. 检测跳转目标缺失、目标越界、目标非表达式边界。

验收：

- 抽样 50 个蓝图，goto 使用率可量化。
- 控制流结构化率 >= 70%。
- 无法结构化时要报告原因。

---

## 5. 偏移目标与读取范围诊断要求

用户明确要求：如果发现偏移目标或范围超出，也需要报告。

这应作为独立诊断类别，而不是混在普通解析失败中。

### 5.1 已知问题

已有全量抽测报告记录：

| 分类 | 数量 | 错误模式 |
|---|---:|---|
| 偏移量越界 | 85 | `Offset 4294967296 exceeds file size N at package seek` |
| 数组数量越界 | 33 | `数组数量超过最大值` 或负数 |
| 文件读取越界 | 21 | `Cannot read 4 bytes at position N, only M bytes remaining` |

偏移越界典型值：

- `4294967295` = `0xFFFFFFFF`
- `4294967296` = `0x100000000`

这通常说明：

- 32 位无符号溢出。
- `FPackageIndex` 解析错误。
- export/import 指向错误对象。
- PropertyTag size / ValueEndOffset 错位。
- serial range 计算错误。

### 5.2 必须报告的字段

建议新增统一结构：`OffsetRangeDiagnostic`。

字段建议：

```json
{
  "kind": "offset_range_diagnostic",
  "asset_path": "...",
  "asset_type": "Blueprint",
  "module": "linker|property|graph|pin|kismet|pak|iostore",
  "object_name": "...",
  "export_index": 12,
  "import_index": null,
  "field": "serial_offset|script_serial_offset|ValueEndOffset|CodeOffset|LinkedTo",
  "current_pos": 115013,
  "target_offset": 4294967296,
  "read_size": 4,
  "file_size": 2191,
  "range_start": 1024,
  "range_end": 2048,
  "source": "export.script_serial_offset + export.serial_offset",
  "error": "Offset exceeds file size",
  "fallback_used": true,
  "fallback_result": "failed|partial|success"
}
```

### 5.3 需要覆盖的诊断点

必须覆盖：

- `archive.seek(pos)` 目标超出文件大小。
- `read_bytes(size)` 请求范围超出剩余文件。
- export `serial_offset + serial_size` 超出文件。
- `script_serial_offset + script_serial_size` 超出 export 范围。
- UE5 `ValueEndOffset` 小于当前位置或超出 export。
- Array/Map/Set count 为负数或超过上限。
- Pin LinkedTo/SubPins count 异常。
- Kismet `CodeOffset` 找不到表达式目标。
- Pak/IoStore compression block offset/size 越界。

验收：

- 所有范围越界都进入 `result.warnings` 或独立 `result.diagnostics`。
- JSON/Markdown 输出可见。
- tolerant fallback 不能静默吞掉越界原因。

---

## 6. Unknown Property / Fallback 状态

当前已有：

- `src/uasset_read/models/fallback.py`
- `tests/test_fallback_models.py`

但仍不完整：

- `src/uasset_read/parsers/class_registry.py` 不存在。
- `tests/test_class_registry.py` 不存在。
- unknown property fallback 与 custom property handler 路径存在回归。

当前完整测试失败：

```text
FAILED tests/test_cue4parse_gap_completion.py::test_borderlands4_custom_properties
```

期望：

```python
{"kind": "GbxDefPtrProperty", "name": "Def", "struct": 42}
```

实际：

```python
PropertyFallback(name='DefPtr', type='CustomProperty_FD', ...)
```

结论：

fallback 改造覆盖了 custom property handler，是 P0 回归。

下一步：

1. 修复 `parse_property_value` 分派顺序。
2. custom property handler 命中时必须优先返回 handler 结果。
3. 只有 handler 不存在或明确失败时才返回 `PropertyFallback`。
4. 增加 regression 测试，确保 Borderlands4 handler 不被 fallback 覆盖。

---

## 7. 测试标注与测试收集问题

### 7.1 当前 marker 配置

`pyproject.toml` 已注册：

```toml
markers = [
    "integration: 需要外部样本资产或较慢路径的集成测试",
]
```

`pytest --markers` 可见 `integration` marker。

### 7.2 当前收集结果

当前测试收集：

| 类型 | 数量 |
|---|---:|
| 总测试 | 452 |
| integration | 42 |
| not integration | 410 |

这和部分旧文档中的 218、374 等统计不一致，需要更新文档。

### 7.3 当前测试运行结果

最新完整测试：

```text
1 failed, 448 passed, 2 xfailed, 1 xpassed
```

最新 integration：

```text
40 passed, 2 xfailed
```

说明：

- integration 标注本身可用。
- 当前主要失败在 fallback/custom property 行为。
- 有 1 个 xpassed，需要检查是否已修复并移除 xfail。

### 7.4 `.gitignore` 与测试跟踪不一致

当前 `.gitignore` 中有：

```gitignore
tests/*
!tests/test_pak_handling.py
!tests/test_variable_extractor.py
...
```

当前磁盘有 27 个 `test_*.py`，但 Git 跟踪只有 20 个。

被 ignore 的测试示例：

- `tests/test_kismet_decompilation.py`
- `tests/test_unknown_property_fallback.py`
- `tests/test_tolerant_class_specific.py`
- `tests/test_binary_or_native_handlers.py`
- `tests/test_error_recovery.py`

风险：

- 本地 pytest 会跑这些文件。
- CI、CodeGraph、提交审查可能漏掉未跟踪测试。
- 测试统计和报告不可信。

下一步：

1. 修改 `.gitignore`，不要默认忽略 `tests/*`。
2. 将所有应进入项目的测试文件纳入 Git。
3. 明确哪些测试是本地实验文件；实验文件放到 `temp/`。
4. 更新测试统计文档。

### 7.5 建议新增 marker

建议增加：

```toml
markers = [
    "integration: 需要外部样本资产或较慢路径的集成测试",
    "quality: 输出质量测试，例如 C++ 可读性、Function_ 占位符、goto 比例",
    "regression: 已修复 bug 的回归测试",
    "slow: 大样本或全量扫描测试",
]
```

---

## 8. 下一步优先级路线

### Phase 0: 修复测试基线

目标：先恢复可信测试状态。

任务：

1. 修复 `test_borderlands4_custom_properties` 回归。
2. 检查 `xpassed` 测试，确认是否移除 xfail。
3. 修复 `.gitignore` 的 `tests/*` 问题。
4. 确认所有应纳入项目的测试已被 Git 跟踪。
5. 更新测试统计文档。

验收：

```bash
python -m pytest tests -q --tb=short
python -m pytest tests -q -m integration --tb=short
```

期望：

- 全部通过，xfail 除外。
- 无 xpassed。
- 测试数量与文档一致。

### Phase 1: 建立偏移/范围诊断

目标：所有 offset/range 越界都结构化报告。

任务：

1. 新增 `OffsetRangeDiagnostic` 模型。
2. 在 archive seek/read、PropertyTag、export range、graph/pin、kismet、pak/iostore 关键点接入。
3. JSON/Markdown 输出 diagnostics。
4. 增加单元测试和真实资产回归测试。

验收：

- 4294967295/4294967296 这类问题有结构化报告。
- tolerant 模式不静默吞掉越界。
- 每个诊断包含 offset、size、file_size、source、fallback_result。

### Phase 2: 修复 C++ 输出基本正确性

目标：输出不再出现明显非法 C++。

任务：

1. 修复变量名 sanitizer。
2. 修复默认值空输出。
3. 修复函数体 wrapper 嵌套。
4. 修复 `.cpp` 重复头。
5. 方法实现加类作用域。

验收：

- `BP_FirstPersonCharacter` 输出无 `= ;`。
- 输出无带空格变量名。
- 函数体无嵌套函数定义。
- `cpp_skeleton` 基本格式稳定。

### Phase 3: 提升 Kismet 反编译语义

目标：从 token 伪代码提升为可理解的实现参考。

任务：

1. 解析 deprecated / instrumentation token。
2. 完善 StackNode、VirtualFunction、Delegate、Interface 解析。
3. 建立常见蓝图节点到 C++ 语义调用映射。
4. 完善控制流结构化。
5. 建立质量统计脚本。

验收：

- `Move` 输出应能体现输入参数和移动调用。
- FirstPerson/ThirdPerson 样本中主要事件和函数输出不再只是 `return`。
- `Function_` 占位符比例可量化并低于目标阈值。
- `goto` 比例可量化并低于目标阈值。

### Phase 4: 全量资产成功率提升

目标：从 96.4% 向 99.5% 推进。

任务：

1. 修复 linker 偏移越界。
2. 修复数组 count 错位。
3. 完善 UE4 legacy 支持或明确 xfail。
4. 对截断/损坏文件输出明确诊断。
5. unknown class/property fallback 完整落地。

验收：

- 4403 资产全量扫描通过率 >= 99.5%，或每个失败都有明确分类和 xfail/skip 策略。

---

## 9. 最终验收标准

### 9.1 解析成功率

| 指标 | 目标 |
|---|---:|
| 全量资产解析通过率 | >= 99.5% |
| integration 测试通过率 | 100%，xfail 除外 |
| stable 资产 strict/tolerant 双模式 | 全通过 |

### 9.2 蓝图功能输出

| 指标 | 目标 |
|---|---:|
| 蓝图变量提取 | 名称、类型、默认值、GUID 可用 |
| 蓝图函数提取 | 函数名、参数、返回值可用 |
| 事件链 | Event -> Call chain 可追踪 |
| Kismet 反编译 | 主要函数体不为空、不只是 deprecated/return |
| 函数引用解析率 | >= 80% |
| 控制流结构化率 | >= 70% |

### 9.3 C++ 输出质量

| 指标 | 目标 |
|---|---|
| 非法变量名 | 0 |
| 空默认值 `= ;` | 0 |
| 嵌套函数壳 | 0 |
| `Function_` 占位符 | 抽样比例 < 10% |
| `goto` fallback | 抽样比例受控且报告原因 |
| 输出文件结构 | `.h` / `.cpp` 清晰，无重复头 |

### 9.4 诊断报告

| 指标 | 目标 |
|---|---|
| 偏移越界 | 必须结构化报告 |
| 范围越界 | 必须结构化报告 |
| 数组 count 异常 | 必须报告 count、位置、上限 |
| Kismet CodeOffset 缺失 | 必须报告 |
| fallback 使用 | 必须报告原因和结果 |

### 9.5 测试体系

| 指标 | 目标 |
|---|---|
| 测试文件跟踪 | 所有项目测试纳入 Git |
| marker 注册 | integration / quality / regression / slow |
| xfail | 必须有明确 reason，修复后移除 |
| xpass | 0 |
| 文档测试数量 | 与 pytest 收集一致 |

---

## 10. 当前建议立即执行的任务清单

1. 修复 `test_borderlands4_custom_properties`，恢复 custom property handler 优先级。
2. 清理 `.gitignore`，确保测试文件不被意外忽略。
3. 将偏移/范围越界诊断建模为正式输出。
4. 修复 C++ 输出的非法语法问题。
5. 为 `BP_FirstPersonCharacter` 建立输出质量回归测试。
6. 添加 `quality` marker，并建立 `Function_` / `goto` 比例统计测试。
7. 更新 `docs/release-notes/testing-requirements.md` 和旧报告中的测试数量。

---

## 11. 风险说明

- 当前工作区有未提交修改，本报告基于当前磁盘状态，不代表干净主分支。
- 部分测试文件被 `.gitignore` 影响，CodeGraph 和 Git 跟踪结果可能与本地 pytest 不一致。
- 真实资产测试依赖 `E:\Develop\lib\UnrealEngine\Samples`，无样本环境会 skip。
- Cooked 资产图数据缺失属于格式限制，但仍应输出明确诊断。

---

## 12. 结论

下一步不应直接继续扩大功能面，而应先建立可信测试基线和诊断闭环。

优先顺序应为：

1. 测试基线修复。
2. 偏移/范围越界结构化报告。
3. C++ 输出合法性修复。
4. Kismet 语义反编译质量提升。
5. 全量资产成功率提升。

完成这些后，项目才接近“成功解析 `.uasset` 并输出蓝图函数/变量具体功能实现代码”的目标。
