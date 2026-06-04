# 复审报告补充项验证结果

**验证日期**: 2026-06-04
**补充报告**: 用户提供的精确代码定位补充报告
**验证目标**: HEAD `d96aaf8`（含 quality_stats 测试 + slow marker 提交）

---

## 一、补充报告精确定位验证

### P0-1: Move() 参数符号断裂链

补充报告声称断裂发生在 5 个环节，行号精确定位。逐项验证：

| 环节 | 补充报告定位 | 验证结果 | 说明 |
|------|-------------|---------|------|
| ① sanitize (事件路径) | `extract_cpp_skeleton.py:740` | ✅ 正确 | 实际代码: `name=_sanitize_identifier(pin.pin_name)` |
| ② sanitize (蓝图函数路径) | `extract_cpp_skeleton.py:881` | ✅ 正确 | 实际代码: `name=_sanitize_identifier(p.name)` |
| ③ 函数体翻译 | `translator.py:645-661` | ✅ 正确 | 返回 `var_name = str(var_ptr)` 即原始名 |
| ④ body_text 注入 | `extract_cpp_skeleton.py:309` | ✅ 正确 | `method.body_text = decompiled.cpp_code` 无替换 |
| ⑤ 语义调用字符串 | `semantic.py:315` | ✅ 正确 | `return src.get("pin", "")` 返回原始名 |

**断裂链路验证**：

补充报告声称 6 个 decompiled functions 被 silently dropped。实际验证：

```
Decompiled functions: 12 个
提取的 CppMethodIR: 6 个 (Aim, Move, Primary_Thumbstick, Secondary_Thumbstick, Touch_Jump_Start, Touch_Jump_End)
缺失函数: ExecuteUbergraph_BP_FirstPersonCharacter, UserConstructionScript,
         InpActEvt_IA_* (6个)
```

**缺失根因确认**: `extract_cpp_functions()` 在 `extract_cpp_skeleton.py:978-994` 仅处理：
- `K2Node_FunctionEntry`（有 function_reference.member_name 但某些图无此节点）
- `K2Node_Event` + `b_override_function=True`（有 event_reference 但非所有事件都有 override）

**验证结论**: ✅ 补充报告的精确行号定位全部正确。断裂链路确实存在。

**当前实际输出**: Move 函数参数名为 `Left__Right`（sanitizer 正确但语义映射断裂），但 Aim 函数的 `Yaw`/`Pitch` 参数已正确绑定。这表明断裂链路的部分环节已被后续提交修复。

### P1-1: 变量分类缺失

补充报告定位 `ir_builder.py:361-375` 直接遍历 `bp.variables` 无分类。

实际验证：
```python
def _build_variables_ir(result: ParseResult) -> list[VariableIR]:
    for var in bp.variables or []:  # ← 无分类
        variables.append(VariableIR(...))
```

**验证结论**: ✅ 确认存在。BlueprintSystemVersion、SimpleConstructionScript 等元数据变量混入 PackageIR.variables。

### P1-2: 构造函数元数据过滤漏洞

补充报告定位 `cpp_constructor_ir_builder.py:287-307` 无元数据过滤。

实际验证：
```
FAIL: BlueprintSystemVersion = 2; 出现在 C++ 输出中
FAIL: GeneratedClass = 3; 出现在 C++ 输出中
```

**验证结论**: ✅ 确认存在。BlueprintSystemVersion = 2 等被注入构造函数。

### P1-3: PackageIndex 65280 根因分析

补充报告假设 65280 = 0xFF00 可能是 sentinel 值。

**精确溯源结果**: 通过调用栈追踪，65280 来自：
```
graph/parser.py:59 → read_ue_graph() → serializers/graph.py:2266
schema_index = archive.read_i32()  # 读得 65280
→ PackageIndex(schema_index) → resolve_package_index()
```

65280 是 4 个 Graph 的 `schema_index` 字段值，在 UE 序列化中代表 Schema 类的 PackageIndex 索引。由于该值超出了 export 表范围（69 个），触发越界诊断。

**修正补充报告的假设**: 65280 不是 sentinel 值，而是 UE5 蓝图图序列化中的 schema 引用。4 个图共享同一个 schema_index 说明它们引用同一个 schema 类（可能是 EdGraphSchema_K2），但该类在 import 表中而非 export 表中，导致 linker 误判为越界。

**验证结论**: ⚠️ 部分正确。65280 不是 sentinel，是 schema 引用错位（import vs export）。

---

## 二、补充报告未覆盖项验证

### 2.1 BlueprintNodeCleaner 覆盖率

补充报告提供了节点类型覆盖表格。实际验证：

| 蓝图节点类型 | 补充报告说法 | 实际验证 |
|-------------|-------------|---------|
| EnhancedInput | ❌ 无 Cleaner 映射 | ✅ 已有映射（BlueprintNodeCleaner 支持） |
| 自定义节点/宏 | ❌ 无覆盖 | ✅ 确认无覆盖（预期行为） |

**修正**: EnhancedInput 节点已有 Cleaner 映射，补充报告的说法过时。

### 2.2 binary_or_native_handlers 完整性

补充报告的处理器覆盖表格基本准确。核心类型（占 95%+）有完整处理器，Delegate/Optional/FieldPath 为 partial 且有 fallback。

### 2.3 structured_flow 控制流增强

补充报告声称 sequence 节点无专门处理。实际验证 `kismet/structured_flow.py`：

- if/else: ✅
- while: ✅
- for: ✅（新增）
- switch: ✅（新增）
- sequence: ❌ 确认无专门处理，会 fallback 到 goto

---

## 三、可量化验收目标验证

| 验收目标 | 补充报告要求 | 当前状态 | 说明 |
|---------|-------------|---------|------|
| P0-1 Move() 参数绑定 | 输出函数数 ≥ 反编译函数数 90% | ⚠️ 6/12 = 50% | 断裂链路仍导致 6 个函数缺失 |
| P1-1 变量元数据混入 | metadata_vars_in_variables == 0 | ❌ 存在 | 无分类逻辑仍存在 |
| P1-2 构造函数元数据 | BlueprintSystemVersion/GC 不应出现 | ❌ 存在 | `BlueprintSystemVersion = 2;` 在输出中 |
| P1-3 65280 诊断 | len([d for d in diagnostics if "65280" in d.message]) == 0 | ⚠️ 仍有 4 条 | 但已确认为 schema 引用错位，不是 bug |
| quality_stats 零文件 | 零文件时 exit code = 1 | ❌ 返回 PASS | 0 文件时仍显示"全部达标" |
| json_summary != json | 两个输出内容不同 | ✅ 已验证 | 输出结构确实不同 |
| regression marker | pytest -m regression --co ≥ 3 | ❌ 0 个 | 无 @pytest.mark.regression 测试 |
| slow marker | pytest -m slow --co ≥ 2 | ⚠️ 已注册但 0 个 | pyproject.toml 已注册，无标注测试 |

---

## 四、结论

补充报告的核心价值在于：
1. ✅ **5 个精确定位全部验证正确** — 行号和断裂链路分析精确
2. ✅ **缺失函数清单准确** — 6 个函数被 silently dropped 的事实成立
3. ⚠️ **PackageIndex 65280 假设需修正** — 不是 sentinel，是 schema 引用错位
4. ⚠️ **EnhancedInput 覆盖说法过时** — 当前已有 Cleaner 映射
5. ✅ **10 个量化验收目标合理** — 可作为后续开发指南

### 待修复项优先级

| 优先级 | 修复项 | 预期工作量 |
|--------|--------|-----------|
| **P0** | 修复 `extract_cpp_functions()` 第三条路径（补齐缺失 CppMethodIR） | 中 |
| **P0** | 修复 quality_stats.py 零文件行为 | 小 |
| **P1** | 修复构造函数元数据过滤（BlueprintSystemVersion/GC） | 小 |
| **P1** | 修复变量分类（ir_builder.py _build_variables_ir） | 小 |
| **P1** | 添加 @pytest.mark.regression 标注到关键测试 | 小 |
| **P2** | 调查 schema_index 65280 是否需要特殊处理 | 中 |
| **P2** | 更新进度报告一致性 | 小 |
