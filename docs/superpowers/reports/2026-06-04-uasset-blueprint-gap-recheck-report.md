# uasset_read 蓝图实现目标复审与下一步指导

**复审日期**: 2026-06-04  
**项目目标**: 成功解析 `.uasset`，并输出蓝图函数、变量及具体功能实现代码  
**复审基线**: `docs/superpowers/reports/2026-06-04-uasset-blueprint-implementation-gap-report.md`  
**进度报告**: `docs/superpowers/reports/2026-06-04-blueprint-gap-fix-progress.md`  
**HEAD**: `71b7397 feat: P2-P3 完成...`  
**工作区状态**: 包含未提交的 Kismet 修改和 3 个未跟踪测试文件

---

## 1. 复审结论

当前修改解决了部分基础问题，但**尚未解决项目最终目标**。

底层 `parse_uasset_with_linker()` 已能成功读取真实的
`BP_FirstPersonCharacter.uasset`，并且最新未提交修改能从图拓扑恢复
`Aim`、`Move` 的调用名称。这些属于有效进展。

但是当前仍存在以下阻断问题：

1. `json`、`json_summary`、`cpp_skeleton` 三个高层输出入口对真实资产全部崩溃。
2. 截断文件通过 linker 入口解析时，会在诊断收集阶段抛出 `AttributeError`。
3. 真实蓝图生成的 C++ 仍包含嵌套函数、非法变量名、未定义参数和 Python 对象表示，不能编译。
4. linker 已记录的偏移/范围诊断没有传递到最终解析结果或 JSON/Markdown 输出。
5. 真实 `Aim`、`Move` 虽恢复了调用名称，但没有恢复参数数据流；`ExecuteUbergraph` 仍为空壳。
6. 当前质量统计会把明显不可编译的 C++ 判定为“全部达标”。
7. 本地测试全部通过，但真实高层入口没有被测试覆盖；新增的 3 个测试文件尚未被 Git 跟踪。
8. 进度报告将 Phase 0-4 标记为完成，与实际验收结果矛盾。

**发布判断**: 当前状态不应进入 `0.4.1` 发布准备，应先完成 P0/P1 阻断项。

---

## 2. 当前快照与验证结果

### 2.1 工作区状态

当前 HEAD:

```text
71b73978f92779bfdf674c4b2103693c4a51ea8a
feat: P2-P3 完成 — diagnostics 输出 + 质量统计 + include 去重 +
wrapper 嵌套修复 + ClassName:: 作用域 + 截断文件诊断 + UE4 legacy xfail
```

当前未提交修改:

```text
M  src/uasset_read/kismet/bytecode_extractor.py
M  src/uasset_read/kismet/semantic.py
M  src/uasset_read/kismet/structured_flow.py
M  src/uasset_read/kismet/translator.py
?? tests/test_bytecode_scanner_fix.py
?? tests/test_empty_function_enrichment.py
?? tests/test_goto_label_emission.py
```

因此，本报告同时区分：

- **已提交基线**: HEAD `71b7397`
- **当前本地快照**: HEAD 加上述未提交修改

### 2.2 测试执行结果

完整测试:

```text
947 passed, 2 xfailed in 10.76s
```

集成测试:

```text
40 passed, 907 deselected, 2 xfailed in 5.07s
```

测试收集:

```text
949 tests collected
```

测试文件跟踪:

| 指标 | 当前值 |
|---|---:|
| 磁盘上的 `test_*.py` | 49 |
| Git 跟踪的 `test_*.py` | 46 |
| 未跟踪测试文件 | 3 |

当前两个 `xfail` 均为 UE4 `legacy_file_version=-3` 的已知限制，且使用
`strict=True`，标注本身合理。

### 2.3 真实资产回归

测试资产:

```text
E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\FirstPerson\Blueprints\BP_FirstPersonCharacter.uasset
```

底层 linker 解析:

```text
is_success = True
errors = 0
warnings = 0
decompiled_functions = 12
linker diagnostics = 4
```

高层输出入口:

```text
json         -> AttributeError: LinkerParseResult has no attribute diagnostics
json_summary -> AttributeError: LinkerParseResult has no attribute diagnostics
cpp_skeleton -> AttributeError: LinkerParseResult has no attribute diagnostics
markdown     -> 成功
text         -> 成功
```

截断文件 linker 入口:

```text
parse_uasset_with_linker(truncated_file)
-> AttributeError: LinkerParseResult has no attribute diagnostics
```

---

## 3. 已解决或有明确进展的项目

| 项目 | 状态 | 说明 |
|---|---|---|
| 完整测试无普通失败 | 已解决 | 当前 `947 passed, 2 xfailed` |
| 意外 `xpass` | 已解决 | 当前无 `xpass` |
| 原有测试文件忽略规则 | 基本解决 | 已提交测试文件可被跟踪，但新增 3 个测试仍未跟踪 |
| `OffsetRangeDiagnostic` 模型 | 已实现 | 模型、JSON/Markdown renderer 支持已存在 |
| `= ;` 空默认值 | 已解决 | 真实输出未再出现 |
| 方法 `ClassName::Method` 作用域 | 部分解决 | 外层方法实现已有类作用域 |
| deprecated 注释噪声 | 表面解决 | 输出中不再出现，但当前采用静默跳过 |
| `Aim` / `Move` 调用名称恢复 | 有进展 | 当前未提交图拓扑补充可恢复调用名称 |
| goto label fallback | 有进展 | 新增标签映射修改和测试 |
| UE4 legacy 限制标注 | 已明确 | 使用严格 `xfail` 标注 |

这些改动值得保留，但不能作为最终目标完成的依据。

---

## 4. 阻断问题

## P0-1: linker 结果缺少 `diagnostics`，高层主入口不可用

### 现象

`parse_single()` 对 `json`、`json_summary`、`cpp_skeleton` 使用
`parse_uasset_with_linker()`，随后调用 `build_package_ir()`。

但是：

- `ParseResult` 有 `diagnostics` 字段：
  `src/uasset_read/models/result.py:47`
- `LinkerParseResult` 没有 `diagnostics` 字段：
  `src/uasset_read/link/result.py:23-51`
- `build_package_ir()` 无条件访问 `result.diagnostics`：
  `src/uasset_read/ir_builder.py:56`
- `parse_uasset_with_linker()` 的 `finally` 也会访问
  `result.diagnostics`：
  `src/uasset_read/parse_uasset.py:640-645`

### 影响

1. 真实资产的 JSON 和 C++ 输出全部失败。
2. CLI 的 `--json`、`--json-summary`、`--cpp-skeleton` 路径失败。
3. 截断文件原本应返回结构化诊断，却被 `AttributeError` 覆盖。
4. 当前“诊断输出已完成”的结论不成立。

### 必须修复

1. 为 `LinkerParseResult` 添加与 `ParseResult` 一致的 `diagnostics` 字段。
2. 最好抽取共享结果基类或 Protocol，避免两个结果模型继续漂移。
3. `parse_uasset_with_linker()` 必须合并 archive 和 linker diagnostics。
4. 添加真实入口测试，禁止只 mock `build_package_ir()`。

### 验收

```python
parse_single(real_asset, format="json")
parse_single(real_asset, format="json_summary")
parse_single(real_asset, format="cpp_skeleton")
```

均不抛异常。

截断文件必须返回失败结果及 `truncated_file` 诊断，不能抛
`AttributeError`。

---

## P1-1: 真实 C++ 输出仍不可编译

真实资产输出包含以下片段：

```cpp
StructProperty Target Touch UI;

void ABP_FirstPersonCharacter::Aim(float Yaw, float Pitch)
{
    void Aim() {
    AddControllerYawInput(Val);
    AddControllerPitchInput(Val);
    }
}

UbergraphPages = [9];
ImplementedInterfaces = [StructValue(...)];
```

同时存在两个连续标题：

```cpp
// ABP_FirstPersonCharacter.cpp
// ABP_FirstPersonCharacter.cpp
```

### 根因

1. 蓝图变量名未使用 sanitizer：
   `src/uasset_read/cpp_gen/extract_cpp_skeleton.py:578-585`
2. 反编译结果以完整函数定义注入 `body_text`：
   `src/uasset_read/cpp_gen/extract_cpp_skeleton.py:275-309`
3. wrapper 剥离只支持 `{` 位于独立第二行：
   `src/uasset_read/cpp_gen/formatters/cpp_function_body_formatter.py:181-191`
4. Kismet/图语义输出使用 `Func() {` 同行格式：
   `src/uasset_read/kismet/body_builder.py:404-409`
   和 `src/uasset_read/kismet/semantic.py:176-215`
5. renderer 和 implementation formatter 都输出 `.cpp` 标题：
   `src/uasset_read/renderers/cpp_skeleton_renderer.py:91-94`
   和
   `src/uasset_read/cpp_gen/formatters/cpp_function_body_formatter.py:92-96`
6. 未知/集合默认值最终使用 Python `str(value)`：
   `src/uasset_read/cpp_gen/cpp_constructor_ir_builder.py:275-284`
   和 `src/uasset_read/cpp_gen/cpp_default_value_formatter.py:149-154`

### 影响

- 当前不能声称输出“具体功能实现 C++”。
- 当前输出不能作为 Unreal C++ 工程代码使用。
- wrapper、sanitizer 和默认值修复仅覆盖了单元测试构造的输入形态。

### 必须修复

1. 明确 `body_text` 合约：只允许“函数体语句”，不允许完整函数定义。
2. 在 Kismet/semantic 层输出结构化语句 IR，而不是完整函数壳。
3. 所有变量、方法、参数、赋值目标统一经过 sanitizer。
4. 对数组、结构、opaque fallback 使用类型化格式化；无法表达时输出注释并跳过赋值。
5. 移除重复 `.cpp` 标题。
6. 增加 C++ 语法/编译 smoke test。

### 验收

真实 `BP_FirstPersonCharacter` 输出中必须满足：

- 无嵌套函数定义。
- 无带空格的标识符。
- 无 Python list/dict/dataclass `repr`。
- 无未声明的 `Val`、`WorldDirection`、`ScaleValue`、`bForce`。
- 无重复 `.cpp` 标题。
- 通过 C++ syntax smoke test。

---

## P1-2: 偏移/范围诊断没有形成闭环

### 当前实现

- `FArchive.seek_safe()`、`read_safe()`、`check_remaining()` 可以记录诊断：
  `src/uasset_read/archive.py:131-254`
- linker 可以记录 serial offset、serial size 和 PackageIndex 越界：
  `src/uasset_read/link/linker.py:119-134`
  和 `src/uasset_read/link/linker.py:183-205`
  和 `src/uasset_read/link/linker.py:231-262`
- JSON/Markdown renderer 可以输出 `PackageIR.diagnostics`。

### 未解决问题

1. `seek_safe()`、`read_safe()`、`check_remaining()` 在生产解析路径中没有调用点。
2. 普通 `read()`、`seek()` 越界只抛异常，不记录结构化诊断：
   `src/uasset_read/archive.py:55-95`
3. `parse_uasset_with_linker()` 只尝试收集 archive diagnostics，没有合并
   `linker.diagnostics`：
   `src/uasset_read/parse_uasset.py:640-645`
4. `LinkerParseResult` 缺少 `diagnostics`，导致收集本身崩溃。
5. `validate_export_data_range()` 文档声称验证每个 export 的
   `serial_offset + serial_size`，实际只按固定 `72` 字节估算 export table：
   `src/uasset_read/serializers/package_summary.py:490-528`
6. PackageIndex 越界被复用为 `OffsetRangeDiagnostic`，但
   `target_offset/read_size` 均为 0，字段语义容易误导。

### 真实资产发现

真实 `BP_FirstPersonCharacter` 解析成功，但 linker 内部记录了 4 条：

```text
Export PackageIndex 65280 (idx=65279) 越界，export 数量 69
```

这 4 条诊断没有进入最终结果，也没有出现在 JSON/Markdown 中。

这些诊断可能代表真实引用解析错误，也可能是误报；当前没有闭环可以判断。

### 必须修复

1. 统一诊断收集入口。
2. archive 普通越界路径在抛错前记录诊断。
3. 将 `linker.diagnostics` 合并到结果。
4. 区分 `byte_offset_range`、`index_range`、`truncated_file`。
5. 在读取 ExportMap 后验证每个 export 的实际范围。
6. 对真实资产中的 4 条 PackageIndex 越界逐条定位来源。

### 验收

- 截断文件返回结构化诊断，不抛收集阶段异常。
- linker 诊断在 JSON/Markdown 可见。
- 所有越界包含真实 field、source、target/range、fallback 结果。
- 成功资产中的诊断有明确的 true-positive/false-positive 判定。

---

## P1-3: Kismet 语义恢复仍是部分实现

### 当前进展

最新未提交修改能从函数图恢复：

```cpp
void Aim() {
    AddControllerYawInput(Val);
    AddControllerPitchInput(Val);
}

void Move() {
    AddMovementInput(WorldDirection, ScaleValue, bForce);
    AddMovementInput(WorldDirection, ScaleValue, bForce);
}
```

这比仅输出 `return;` 有明显进步。

### 仍存在的问题

1. `Val` 没有绑定到 `Yaw` 或 `Pitch`。
2. `WorldDirection`、`ScaleValue`、`bForce` 没有恢复实际数据来源。
3. `ExecuteUbergraph_BP_FirstPersonCharacter` 仍只有 `return;`。
4. graph enrichment 输出完整函数壳，和 C++ formatter 的 body 合约冲突。
5. `_EMPTY_BODY_THRESHOLD = 3` 将“表达式数量少”直接视为“空函数”：
   `src/uasset_read/kismet/semantic.py:12-13`
   和 `src/uasset_read/kismet/semantic.py:59-74`
   这可能覆盖合法的短函数。
6. deprecated/instrumentation token 被静默跳过，统计没有进入最终
   `KismetDecompiledResult.warnings`：
   `src/uasset_read/kismet/translator.py:1105-1120`
   和 `src/uasset_read/kismet/pipeline.py:83-114`
7. 函数引用统计将 `0` 次尝试报告为 `100%` 成功率：
   `src/uasset_read/kismet/function_resolver.py:186-199`
   因此真实资产中的“100%”没有质量意义。

### 最新 scanner 修改风险

当前未提交修改从候选起始 token 中删除：

- `EX_IntConst`
- `EX_WireTracepoint`
- `EX_Tracepoint`

位置：

`src/uasset_read/kismet/bytecode_extractor.py:33-42`

scanner 只从候选集合开始尝试，并按表达式数量选择结果：

`src/uasset_read/kismet/bytecode_extractor.py:172-195`

这会降低误选，但也可能漏掉合法地以这些 token 开始的函数。

同时，translator 将部分大整数直接替换为 `/* suspicious */`。合法的
`0x01000000` 等值也会丢失语义。该策略属于症状抑制，不是可靠解析。

### 必须修复

1. 建立 Pin 数据流表达式 IR，解析 linked pin、默认值、函数参数和纯函数结果。
2. 图拓扑补充必须输出 body statements，并保留原始 bytecode 结果和来源。
3. 不使用表达式数量作为唯一“空函数”判断。
4. 不静默丢弃 token 或整数；应输出诊断、置信度和原始值。
5. `0` 次解析尝试的成功率应为 `N/A`，不能是 `100%`。
6. 用真实资产 golden tests 验证参数绑定。

### 验收

至少对真实样本满足：

```cpp
AddControllerYawInput(Yaw);
AddControllerPitchInput(Pitch);
```

`Move` 的方向、缩放值和输入参数必须可追踪，不能只输出未定义 Pin 名。

---

## P2-1: 测试全绿，但没有覆盖产品主路径

### 当前测试缺口

1. `tests/test_core_api.py:42-73` mock 了 `build_package_ir()` 和 renderer，
   因而没有发现 `LinkerParseResult.diagnostics` 缺失。
2. `tests/test_sample_assets_representative.py:170-173` 的真实资产辅助函数只调用
   `parse_uasset_with_linker()`，没有调用 `parse_single()`。
3. C++ 质量测试主要使用手工构造的 mock `CppClassIR`。
4. 最新 `test_empty_function_enrichment.py` 仍是 mock 图测试，没有验证真实资产
   到最终 C++ 输出的完整链路。
5. 当前没有生成 C++ 的 syntax/compile gate。
6. `scripts/quality_stats.py` 没有单元测试。

### 当前标注状态

`pyproject.toml` 只注册：

```toml
integration
```

没有注册或使用：

- `quality`
- `regression`
- `slow`

### 当前跟踪状态

以下测试文件未被 Git 跟踪：

```text
tests/test_bytecode_scanner_fix.py
tests/test_empty_function_enrichment.py
tests/test_goto_label_emission.py
```

它们共贡献 39 个本地通过测试。当前本地 `947 passed` 不能等同于 CI 或提交后的
测试基线。

### 必须修复

1. 增加真实资产高层入口回归。
2. 增加截断文件 linker 结果回归。
3. 增加真实 C++ 输出 fatal-pattern 和 syntax smoke test。
4. 注册并使用 `quality`、`regression`、`slow` marker。
5. 将应进入项目的 3 个新测试纳入 Git。
6. CI 分别执行 unit、integration、quality、slow。

---

## P2-2: 质量统计会产生错误的完成信号

对当前明显不可编译的真实 C++ 输出运行：

```text
python scripts/quality_stats.py <仅包含该输出的目录>
```

结果为：

```text
Function_N 占位符比率  PASS
goto 回退比率          PASS
总体评估               全部达标
```

### 原因

1. 指标只检查 `Function_`、`goto`、deprecated 和空函数体。
2. 不检查嵌套函数、非法标识符、Python repr、未定义参数或语法错误。
3. `scan_file()` 每行使用累计的 `function_placeholder_count` 扣减当前行调用数：
   `scripts/quality_stats.py:147-156`
4. scoped 函数定义不被当前 `RE_FUNCTION_DEF` 正确统计：
   `scripts/quality_stats.py:55-60`
5. `scan_directory()` 对目录递归扫描，没有默认排除 vendor/external：
   `scripts/quality_stats.py:173-181`

### 必须修复

质量指标必须先有“fatal gate”，再计算比例：

- C++ syntax/compile 失败直接失败。
- 非法标识符直接失败。
- 嵌套函数定义直接失败。
- Python repr 直接失败。
- 未定义占位参数直接失败。
- diagnostics 丢失直接失败。

比例指标只能作为后续质量优化，不能替代正确性验收。

---

## 5. 计划和报告偏移审查

## 5.1 目标偏移

当前存在明确目标偏移：

| 偏移 | 说明 |
|---|---|
| 从语义正确转向输出清洁 | 静默删除 deprecated/instrumentation、隐藏可疑整数，会减少坏标记，但不恢复语义 |
| 从真实入口转向 mock 单测 | 单元测试通过，但 JSON/C++ 高层入口仍崩溃 |
| 从可编译 C++ 转向比例指标 | 不可编译输出仍被质量脚本判定全部达标 |
| 从诊断闭环转向诊断模型存在 | 模型和 renderer 已存在，但 linker 诊断没有进入最终结果 |
| 从全量成功率转向局部样本通过 | Phase 4 标记完成，但全量资产通过率仍未测量 |

下一阶段必须以真实入口和可验证输出为中心，不能继续以“无注释噪声”或
“单元测试数量增加”作为主要完成指标。

## 5.2 范围扩张

未发现大规模无关功能扩张。新增的 diagnostics、sanitizer、graph enrichment、
quality stats 均与目标相关。

当前主要问题不是范围过大，而是**相关功能没有沿完整产品链路闭环**。

需要限制的范围扩张风险：

1. 不应继续增加更多 token 特判，先修复 bytecode 候选评分和诊断。
2. 不应继续增加更多 mock quality tests，先建立真实资产 E2E 和 compile gate。
3. quality stats 不应扫描整个仓库或 `external/` 后作为项目输出质量证据。
4. 不应在全量通过率未测量时继续扩展更多资产类型支持并宣称 Phase 4 完成。

## 5.3 进度报告不一致

`docs/superpowers/reports/2026-06-04-blueprint-gap-fix-progress.md` 存在以下问题：

1. Phase 0-4 标题均标记“完成”，但表格中仍有多个 `待实现/待验证/待测试`。
2. Phase 1 标记完成，但 linker 诊断输出路径崩溃。
3. Phase 2 标记完成，但真实 C++ 不可编译。
4. Phase 3 标记完成，但 `Aim`/`Move` 参数数据流和 Ubergraph 未恢复。
5. Phase 4 标记完成，但全量资产解析通过率仍为“待测试”。
6. `~85%` 函数解析率和 `~75%` 控制流结构化率没有可复现测量证据。
7. 测试数字仍是 `824` 和 `40` 个测试文件，当前本地快照为
   `949` 个收集用例、49 个测试文件，其中 3 个未跟踪。
8. “未完成任务（可选）”中包含实际 P0/P1 阻断项，不应标为可选。

建议将该报告改为“阶段进展”，撤销 Phase 1-4 的完成标记。

---

## 6. 下一步实施顺序

## Phase A: 恢复高层主入口和诊断结果契约

**优先级**: P0  
**目标**: JSON/C++ 主入口可用，截断文件诊断不崩溃。

任务：

1. 统一 `ParseResult` 与 `LinkerParseResult` 的共享字段。
2. 添加 `LinkerParseResult.diagnostics`。
3. 合并 archive/linker diagnostics。
4. 添加真实资产 `parse_single()` E2E。
5. 添加截断文件 linker E2E。

完成标准：

- `json`、`json_summary`、`cpp_skeleton` 不抛异常。
- 截断文件返回诊断结果。
- 4 条真实 linker PackageIndex 诊断可在结果中观察。

## Phase B: 建立 C++ 正确性硬门槛

**优先级**: P1  
**目标**: 真实资产输出至少语法有效。

任务：

1. 将 Kismet/semantic 输出合约改为纯 body statements。
2. 统一 sanitizer。
3. 修复集合、结构、opaque 默认值。
4. 修复重复标题和构造函数输出。
5. 添加 fatal-pattern 检查和 syntax smoke test。

完成标准：

- 真实 `BP_FirstPersonCharacter` 输出无本报告列出的非法片段。
- quality gate 对当前旧输出必须失败。

## Phase C: 恢复蓝图参数和数据流语义

**优先级**: P1  
**目标**: 输出可追踪的具体功能实现，而非调用名列表。

任务：

1. 从 graph pins 构建数据流表达式。
2. 绑定函数参数、默认值、纯函数结果和对象上下文。
3. 恢复 EventGraph/Ubergraph 分支和调用链。
4. 保留 bytecode、graph topology、fallback 的来源和置信度。
5. 移除静默丢弃语义的策略。

完成标准：

- `Aim` 使用 `Yaw` 和 `Pitch`。
- `Move` 参数来源可追踪。
- `ExecuteUbergraph` 不再只有 `return;`，或明确报告无法恢复的原因。

## Phase D: 完成偏移/范围诊断闭环

**优先级**: P1  
**目标**: 所有越界都可定位、可输出、可判断 fallback。

任务：

1. 普通 read/seek 越界记录诊断。
2. 验证真实 export data ranges。
3. 区分 byte/index/truncated diagnostics。
4. 输出 source、target/range、fallback。
5. 调查真实样本的 4 条 PackageIndex 越界。

完成标准：

- JSON/Markdown 中可见所有诊断。
- 诊断不被异常覆盖。

## Phase E: 修复测试分层和文档状态

**优先级**: P2  
**目标**: 测试通过可以代表产品目标通过。

任务：

1. 跟踪 3 个新增测试文件。
2. 注册 `quality`、`regression`、`slow` marker。
3. CI 增加真实 E2E 和 C++ syntax gate。
4. 修复 `quality_stats.py` 统计错误和扫描范围。
5. 更新 README、CLAUDE、testing requirements 和进度报告。
6. 测量全量资产解析成功率后再更新 Phase 4。

---

## 7. 建议新增的最小回归测试

```python
@pytest.mark.integration
@pytest.mark.regression
def test_real_asset_high_level_formats_do_not_crash(...):
    for fmt in ("json", "json_summary", "cpp_skeleton"):
        output = parse_single(real_blueprint, format=fmt, tolerant=True)
        assert output
```

```python
@pytest.mark.regression
def test_linker_truncated_file_returns_diagnostics(...):
    result = parse_uasset_with_linker(truncated_asset, tolerant=True)
    assert not result.is_success
    assert any(d.kind == "truncated_file" for d in result.diagnostics)
```

```python
@pytest.mark.integration
@pytest.mark.quality
def test_real_blueprint_cpp_has_no_fatal_patterns(...):
    cpp = parse_single(real_blueprint, format="cpp_skeleton", tolerant=True)
    assert "StructProperty Target Touch UI;" not in cpp
    assert " = [" not in cpp
    assert "StructValue(" not in cpp
    assert cpp.count("// ABP_FirstPersonCharacter.cpp") == 1
    assert "void Aim() {" not in cpp
    assert "void Move() {" not in cpp
```

```python
@pytest.mark.integration
@pytest.mark.quality
def test_real_aim_and_move_bind_parameters(...):
    cpp = parse_single(real_blueprint, format="cpp_skeleton", tolerant=True)
    assert "AddControllerYawInput(Yaw)" in cpp
    assert "AddControllerPitchInput(Pitch)" in cpp
    assert "AddControllerYawInput(Val)" not in cpp
```

这些测试应在修复前失败，在修复后成为发布门槛。

---

## 8. 发布门槛

在以下条件全部满足前，不建议发布：

| 门槛 | 当前状态 |
|---|---|
| `parse_single(..., json/json_summary/cpp_skeleton)` 成功 | 失败 |
| 截断文件 linker 入口返回结构化诊断 | 失败 |
| linker diagnostics 进入最终输出 | 失败 |
| 真实蓝图 C++ syntax gate 通过 | 失败 |
| `Aim` / `Move` 参数数据流恢复 | 失败 |
| 全量资产解析通过率已测量且达到目标 | 未测量 |
| 所有项目测试被 Git 跟踪 | 失败 |
| quality/regression/slow 标注已建立 | 失败 |
| 进度报告与实际一致 | 失败 |

---

## 9. 最终判断

当前项目已经从“只能结构化读取”推进到“可以部分恢复蓝图调用名称”，但还没有达到：

> 成功解析 `.uasset`，并输出蓝图函数、变量及具体功能实现代码。

当前最重要的不是继续增加新特判或扩大资产类型，而是完成以下闭环：

1. 高层主入口可用。
2. 偏移/范围诊断可传递。
3. 真实 C++ 语法有效。
4. Pin 数据流绑定到具体函数参数和表达式。
5. 真实资产 E2E、质量门槛和报告状态一致。

完成 Phase A-D 后，才可以重新评估 Phase 0-4 是否真正完成。
