# 路线图 — v7.0 ✅ 完成

**v7.0** ✅ 432 passed, 20 pre-existing (asset -9), 68 skipped

## v7.0 Phase 分解

| Phase | 名称 | 目标 | 状态 |
|-------|------|------|------|
| 41 | link/ 模块 | UObjectInstance, PackageLinker, LinkerParseResult | ✅ 完成 |
| 42 | 集成入口 | parse_uasset_with_linker() | ✅ 完成 |
| 43 | PackageIndex | resolve_with_linker() | ✅ 完成 |
| 44 | 模型增强 | UEdGraphPin linked_to_objects | ✅ 完成 |
| 44a | 移除旧版本兼容代码 | 删除UE4/旧版本条件分支和常量 | ✅ 完成 |
| 44b | 替换直接字节读取 | 消除struct.unpack，统一使用FArchive方法 | ✅ 完成 |
| 44c | 清理测试工具 | 删除废弃测试和调试脚本 | ✅ 完成 |
| 45 | 图序列化 | from_archive_with_linker() 方法 + default_object_ref | ✅ 完成 |
| 46 | 测试验证 | 432 passed, 0 new failures | ✅ 完成 |

**v7.0 完成**: 432 passed, 20 pre-existing (asset version -9), 68 skipped

**核心改变**: PackageIndex → UObjectInstance 实际引用，构建 Outer 对象树

<details>
<summary>v7.0 Phase 详情 (已归档)</summary>

- **Phase 44a**: 移除 UE4 兼容代码 — `constants.py`, `package_summary.py` 等 8 文件
- **Phase 44b**: 替换直接字节读取 — `property_types.py`, `graph.py`, `archive.py`
- **Phase 44c**: 清理测试工具 — 删除 `test_property_parsing.py`, `tools/*`, `temp/*`
- **Phase 45**: 图序列化 linker 变体 — `from_archive_with_linker()` + `default_object_ref`
- **Phase 46**: 最终验证 — UE5.6 资产 12/12 UAT 通过

详见 `.planning/archive/v7.0/phases/`
</details>

---

## v8.0 🔨 BP-to-CPP 翻译能力

> 对比 `BP_FirstPersonCharacter.uasset` 与等价 C++ 实现 (`FirstPersonCCharacter.cpp/h`)，
> 识别出 4 个 gap，分 4 个 phase 解决。详见 `.planning/milestones/v8.0.md`

| Phase | 名称 | 目标 | 状态 |
|-------|------|------|------|
| 47 | Pin LinkedTo 修复 | linked_to_raw 非空，connections > 0 | ✅ 完成 |
| 48 | 组件属性递归解析 | 输出组件数值型属性 | ✅ 完成 |
| 49 | 函数调用引脚解析 | CallFunction 参数引脚完整 | ✅ 完成 |
| 50 | EnhancedInput 语义增强 | TriggerEvent 类型可识别 | ✅ 完成 |
| 51 | 二进制输出清理 | 消除 JSON 中 binary/null 泄漏 | ✅ 完成 |

### 验证标准 — JSON 可翻译性

Phase 47–50 完成后，`BP_FirstPersonCharacter.uasset` 的 JSON 输出需覆盖 C++ 文件中：

| C++ 结构 | JSON 对应 | Phase |
|----------|-----------|-------|
| 组件声明 + 构造函数数值 | `components[]` 含位置/旋转/缩放/标志 | 48 |
| 函数签名（参数名+类型） | `graphs[].nodes[].parameters[]` | 49 |
| 输入绑定（Action→Trigger→函数） | `input_bindings[]` | 50 |
| 执行流（BeginPlay→函数链） | `execution_flows[].nodes[]` | 47 |

*Updated: 2026-05-17*
