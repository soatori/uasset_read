# 测试要求规范

> 目标：验证 `uasset_read` 是否真的满足项目主目标。
>
> 核心验收不是“能跑”，而是下面三件事都成立：
> 1. 不打开 UE 编辑器，也能读取 `.uasset` / `.umap`。
> 2. 输出统一的、可供 agent 理解的结构化内容。
> 3. 蓝图输出能和对应的 C++ 类语义、编辑器节点文本对齐。

---

## 一、测试分层

### 1.1 L0: 目标验收烟雾测试

这层必须在日常开发里最快跑完，覆盖最核心链路：

- `parse_single()` 的入口和格式选择
- `parse_uasset_with_linker()` 的容错与诊断传递
- `PackageIR` / `NodeIR` / `GraphIR` 这类 IR 结构契约
- `json` / `json_summary` / `text` / `markdown` / `blueprint_text` / `blueprint_ue_text` / `cpp_skeleton` 的渲染器注册和基础输出
- 截断文件、非法版本、未知属性、容错早期失败

建议保留文件：

- `tests/test_core_api.py`
- `tests/test_renderers.py`
- `tests/test_ir_structures.py`
- `tests/test_truncated_file.py`
- `tests/test_version_compatibility.py`
- `tests/test_unknown_property_fallback.py`
- `tests/test_tolerant_early_parse_diagnostics.py`
- `tests/test_package_summary_fields.py`
- `tests/test_parse_package_core.py`

### 1.2 L1: 解析器与模型单元测试

这层验证内部实现是否稳定，属于核心逻辑保护，不直接依赖真实样本资产：

- 包结构、导入导出表、属性解析
- Kismet 反编译、节点清理、函数解析
- Blueprint 节点文本清理和 C++ 映射
- Pak / IoStore / BulkData / Archive 这类底层容器与读写保护

建议保留文件：

- `tests/test_blueprint_node_cleaner.py`
- `tests/test_function_resolver.py`
- `tests/test_function_resolver_enhanced.py`
- `tests/test_ir_builder.py`
- `tests/test_json_completeness.py`
- `tests/test_kismet_decompilation.py`
- `tests/test_kismet_deprecated_tokens.py`
- `tests/test_pak_handling.py`
- `tests/test_pak_structures.py`
- `tests/test_raw_readers.py`
- `tests/test_archive_diagnostic.py`
- `tests/test_array_count_check.py`
- `tests/test_binary_or_native_handlers.py`
- `tests/test_class_registry.py`
- `tests/test_export_error_context.py`
- `tests/test_linker_offset_check.py`
- `tests/test_property_parser_error_handling.py`
- `tests/test_variable_extractor.py`

### 1.3 L2: 代表性样本资产集成测试

这层验证“真实资产输入 -> 统一输出”是否成立，重点是覆盖主要资产类型和容错模式：

- `tests/test_sample_assets_representative.py`
- `tests/test_tolerant_class_specific.py`
- `tests/test_compat_check.py`
- `tests/test_cpp_quality_gate.py`
- `tests/test_constructor_metadata.py`
- `tests/test_event_execution_fix.py`

这层是最接近项目目标的验证集，应该保持稳定，并持续补样本，不建议频繁删减。

### 1.4 L3: 真实资产回归测试

这层验证“真实蓝图和真实资产”是否满足目标定义，重点看输出是否能对照编辑器和 C++ 语义：

- `tests/test_real_asset_e2e.py`
- `tests/test_sample_assets_representative.py` 中的真实资产项

这层里允许保留已知缺陷的 `xfail`，但必须明确缺陷原因和适用范围。

### 1.5 L4: 辅助与历史回归测试

这类测试不是主目标，但在回归历史问题上仍有价值：

- `tests/test_api_cleanup.py`
- `tests/test_cue4parse_gap_completion.py`
- `tests/test_quality_stats.py`
- `tests/test_diagnostic_output.py`
- `tests/test_fallback_models.py`
- `tests/test_pin_recovery.py`
- `tests/test_jump_analyzer.py`

如果某个测试只是在保护旧接口废弃路径，而且项目已经不再暴露该路径，可以考虑删除或并入更高层的验收测试。

---

## 二、当前仓库里最重要的测试事实

我已经跑过当前全量测试，结果是：

- `1226 passed`
- `2 skipped`
- `2 xfailed`

这说明仓库当前不是“测试不够”，而是“测试很散，缺少分层和归口”。

从目标角度看，真正需要优先守住的是：

1. `parse_single()` 到 renderer 的整条链路
2. `parse_uasset_with_linker()` 的诊断、容错、失败模式
3. 代表性资产是否能输出稳定的 IR / JSON / Blueprint 文本 / C++ skeleton
4. 真实蓝图是否能和节点文本、C++ 语义对齐

---

## 三、建议清理原则

### 3.1 不建议直接删的测试

以下测试虽然看起来像“内部实现测试”，但实际在守核心能力：

- `test_blueprint_node_cleaner.py`
- `test_function_resolver.py`
- `test_function_resolver_enhanced.py`
- `test_kismet_decompilation.py`
- `test_ir_builder.py`
- `test_renderers.py`
- `test_real_asset_e2e.py`
- `test_sample_assets_representative.py`

### 3.2 可以考虑合并或降级的测试

这些测试通常与已有测试存在明显重叠，更适合改成更少但更强的验收点：

- `test_api_cleanup.py`
- `test_quality_stats.py`
- `test_cpp_quality_gate.py`
- `test_cue4parse_gap_completion.py`

### 3.3 需要重点审查是否过期的测试

如果项目已经不再支持相应旧接口或旧路径，这些测试可以考虑删除：

- 仅验证废弃 API 的 warning 测试
- 只保护历史修补点、但没有继续使用场景的测试
- 只验证输出字符串里某个实现细节、但不验证目标契约的测试

这类测试不能靠名字判断，必须结合当前代码路径和产品目标判断。

---

## 四、体系化自动测试脚本建议

建议补一个统一入口脚本，按场景跑不同测试层。推荐命令如下：

```bash
python scripts/test_matrix.py smoke
python scripts/test_matrix.py unit
python scripts/test_matrix.py integration
python scripts/test_matrix.py regression
python scripts/test_matrix.py quality
python scripts/test_matrix.py all
```

建议语义：

- `smoke`：只跑 L0，最快，适合本地提交前
- `unit`：L0 + L1，适合普通 PR
- `integration`：样本资产集成测试
- `regression`：真实资产和已知缺陷回归
- `quality`：C++ 输出质量门禁
- `all`：完整 pytest 套件

脚本的职责不是重新实现测试逻辑，只是把仓库里的 pytest 约定统一起来，避免每个人记不同命令。

---

## 五、提交前检查

- [ ] L0 烟雾测试通过
- [ ] L1 单元测试通过
- [ ] L2 样本资产集成测试通过，或因样本缺失被明确跳过
- [ ] L3 真实资产回归测试通过，或因环境缺失被明确跳过
- [ ] `xfail` 只用于已知、可解释、可追踪的缺陷
- [ ] 新增特性必须补对应层级的测试
