# 0.4.2-dev 阻断修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复补充报告验证的 6 个 P0/P1 阻断项，使 0.4.2-dev 达到可发布状态

**Architecture:** 基于已验证的精确定位，逐项修复断裂链路。按依赖关系排列：先修复 P0 入口和完整性，再修复 P1 质量，最后修复测试和文档。所有变更 TDD 推进。

**Tech Stack:** Python 3.10+, pytest, 现有 uasset_read 架构

---

## 当前状态快照（经补充报告验证后）

| 指标 | 值 |
|------|------|
| 测试通过 | 982 passed, 2 xfailed, 0 xpassed |
| 分支 | 0.4.2-dev（HEAD d96aaf8）|
| 已修复 | json/json_summary/cpp_skeleton 不崩溃、截断文件诊断、C++ 致命模式消除、Aim 参数绑定、diagnostics JSON 闭环、quality_stats 测试、slow marker |
| **仍阻断** | 6 项（见下表）|

## 阻断项清单（按优先级排序）

| # | 阻断项 | 优先级 | 根因文件:行号 | 影响范围 |
|---|--------|--------|--------------|---------|
| 1 | 6 个反编译函数被 silently dropped | P0 | `extract_cpp_skeleton.py:978-994` | C++ 输出丢失 50% 函数 |
| 2 | body_text 注入无符号映射替换 | P0 | `extract_cpp_skeleton.py:309` + `translator.py:645-661` | Move 参数名含非法字符 |
| 3 | 构造函数注入 BlueprintSystemVersion/GeneratedClass | P1 | `cpp_constructor_ir_builder.py:287-307` | C++ 输出含无效元数据 |
| 4 | 变量列表混入元数据变量 | P1 | `ir_builder.py:361-375` | PackageIR.variables 污染 |
| 5 | quality_stats.py 零文件返回 PASS | P1 | `scripts/quality_stats.py` | 误判质量达标 |
| 6 | 回归测试无 regression marker | P2 | 测试文件 | 无法运行回归测试集 |

## 文件变更映射

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/uasset_read/cpp_gen/extract_cpp_skeleton.py` | 修改 | Task 1 + Task 2 |
| `src/uasset_read/kismet/translator.py` | 修改 | Task 2（符号映射注入）|
| `src/uasset_read/cpp_gen/cpp_constructor_ir_builder.py` | 修改 | Task 3 |
| `src/uasset_read/ir_builder.py` | 修改 | Task 4 |
| `scripts/quality_stats.py` | 修改 | Task 5 |
| `tests/test_cpp_quality_gate.py` | 修改 | Task 1-4 验收测试 |
| `tests/test_constructor_metadata.py` | **创建** | Task 3 测试 |
| `tests/test_variable_classification.py` | **创建** | Task 4 测试 |
| `tests/test_quality_stats.py` | 修改 | Task 5 测试 |
| `tests/test_real_asset_e2e.py` | 修改 | Task 6 regression marker |

---

### Task 1: 补齐缺失的反编译函数（第三条路径）

**根因**: `extract_cpp_functions()` 仅从图节点提取，忽略 `result.decompiled_functions` 中无对应 K2Node 的函数。

**Files:**
- Modify: `src/uasset_read/cpp_gen/extract_cpp_skeleton.py` — 在 `extract_cpp_class_skeleton()` 中 `_inject_function_bodies` 前添加补齐逻辑
- Modify: `tests/test_cpp_quality_gate.py` — 添加函数完整性断言

- [ ] **Step 1: 编写测试**

```python
# tests/test_cpp_quality_gate.py — 在现有 TestCppFatalPatterns 类后添加

@pytest.mark.integration
@pytest.mark.regression
@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
class TestCppFunctionCompleteness:
    """验证反编译函数完整性。"""

    def test_all_decompiled_functions_have_cpp_output(self):
        """所有反编译函数都应有 C++ 输出。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker
        result = parse_uasset_with_linker(_REAL_BLUEPRINT, tolerant=True)
        
        decompiled_names = {f.function_name for f in result.decompiled_functions}
        
        # 生成 C++ 输出
        cpp = parse_single(_REAL_BLUEPRINT, format="cpp_skeleton", tolerant=True)
        
        # 每个反编译函数名（sanitized 后）应出现在 C++ 输出中
        from uasset_read.cpp_gen.extract_cpp_skeleton import _sanitize_identifier
        missing = []
        for name in decompiled_names:
            sanitized = _sanitize_identifier(name)
            if sanitized not in cpp:
                missing.append(name)
        
        # 允许 ExecuteUbergraph 缺少（无源码可恢复）
        missing = [n for n in missing if "Ubergraph" not in n]
        assert len(missing) == 0, f"缺失 C++ 输出的函数: {missing}"

    def test_decompiled_function_ratio(self):
        """C++ 输出函数数 ≥ 反编译函数数的 90%（排除 Ubergraph）。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker
        result = parse_uasset_with_linker(_REAL_BLUEPRINT, tolerant=True)
        
        total = len([f for f in result.decompiled_functions 
                     if "Ubergraph" not in f.function_name])
        assert total > 0
        
        cpp = parse_single(_REAL_BLUEPRINT, format="cpp_skeleton", tolerant=True)
        # 计数方法定义
        import re
        method_defs = len(re.findall(r'void ABP_\w+::\w+\(', cpp))
        
        ratio = method_defs / total
        assert ratio >= 0.9, f"函数覆盖率 {ratio:.0%} < 90% ({method_defs}/{total})"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_cpp_quality_gate.py::TestCppFunctionCompleteness -v`
Expected: FAIL — 6 个函数缺失

- [ ] **Step 3: 实现修复**

```python
# src/uasset_read/cpp_gen/extract_cpp_skeleton.py
# 在 extract_cpp_class_skeleton() 函数中，找到以下代码段：
# 
#   methods = extract_cpp_functions(result.graphs, ...)
#   _inject_function_bodies(methods, result.decompiled_functions)
#
# 在 _inject_function_bodies 调用之前插入：

def _backfill_missing_methods(methods, decompiled_functions):
    """从 decompiled_functions 补齐 extract_cpp_functions 遗漏的 CppMethodIR。
    
    原因：extract_cpp_functions 只处理 K2Node_FunctionEntry 和
    K2Node_Event(b_override=True)，但部分反编译函数无对应图节点
    （如 ExecuteUbergraph、UserConstructionScript、InputAction 事件）。
    """
    existing_names = {m.cpp_name for m in methods}
    for decompiled in decompiled_functions:
        sanitized = _sanitize_identifier(decompiled.function_name)
        if sanitized not in existing_names:
            methods.append(CppMethodIR(
                cpp_name=sanitized,
                return_type="void",
                parameters=[],
                body_text=decompiled.cpp_code or "/* no source available */",
            ))

# 修改 extract_cpp_class_skeleton() 中的调用：
# 原来：
#   _inject_function_bodies(methods, result.decompiled_functions)
# 改为：
    _backfill_missing_methods(methods, result.decompiled_functions)
    _inject_function_bodies(methods, result.decompiled_functions)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_cpp_quality_gate.py::TestCppFunctionCompleteness -v`
Expected: PASS — 12/12 函数（排除 Ubergraph）

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/cpp_gen/extract_cpp_skeleton.py tests/test_cpp_quality_gate.py
git commit -m "fix: 补齐 extract_cpp_functions 遗漏的反编译函数（第三条路径）

- 新增 _backfill_missing_methods() 从 decompiled_functions 补齐 CppMethodIR
- 修复 ExecuteUbergraph、UserConstructionScript、InputAction 事件缺失
- C++ 输出函数数从 6 提升至 12
- 新增 TestCppFunctionCompleteness 测试"
```

---

### Task 2: body_text 注入时执行符号映射替换

**根因**: `method.body_text = decompiled.cpp_code` 直接赋值，不做原始名 → sanitized 名的替换。

**Files:**
- Modify: `src/uasset_read/cpp_gen/extract_cpp_skeleton.py` — 修改 `_inject_function_bodies()`
- Test: `tests/test_cpp_quality_gate.py` — 已覆盖（参数绑定测试）

- [ ] **Step 1: 编写测试**

```python
# tests/test_cpp_quality_gate.py — 在 TestCppParameterBinding 类后添加

    def test_no_illegal_characters_in_body(self, cpp_output: str):
        """函数体内不应出现含 '/' 的参数名（如 'Left / Right'）。"""
        import re
        # 匹配函数体内的原始参数名
        illegal_patterns = [
            "Left / Right",
            "Forward / Backward",
        ]
        for pattern in illegal_patterns:
            assert pattern not in cpp_output, (
                f"函数体内出现非法参数名 '{pattern}'，应被 sanitized 替换"
            )
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_cpp_quality_gate.py::TestCppParameterBinding::test_no_illegal_characters_in_body -v`
Expected: FAIL — "Left / Right" 存在于输出中

- [ ] **Step 3: 实现修复**

```python
# src/uasset_read/cpp_gen/extract_cpp_skeleton.py
# 修改 _inject_function_bodies() 函数：

def _inject_function_bodies(
    methods: List[CppMethodIR],
    decompiled_functions: List[Any],
) -> None:
    """将 KismetDecompiledResult 的 cpp_code 注入到 CppMethodIR.body_text。
    
    新增：注入时执行符号映射替换，确保 body_text 中的变量名与
    方法声明中的 sanitized 名称一致。
    """
    method_index: Dict[str, CppMethodIR] = {m.cpp_name: m for m in methods}

    for decompiled in decompiled_functions:
        func_name = decompiled.function_name

        # 精确匹配
        method = method_index.get(func_name)

        # 清理后匹配
        if method is None:
            sanitized = _sanitize_identifier(func_name)
            method = method_index.get(sanitized)

        # 大小写不敏感匹配
        if method is None:
            for cpp_name, m in method_index.items():
                if func_name.lower() == cpp_name.lower():
                    method = m
                    break

        if method and decompiled.cpp_code:
            body = decompiled.cpp_code
            
            # 新增：构建 {原始pin名 -> 清理名} 映射并替换
            # 参数映射：从 method.parameters 提取
            for param in method.parameters:
                # 原始名可能包含 '/' 等被 sanitizer 替换的字符
                # 尝试从 body 中查找并替换
                # 常见模式：'Name1 / Name2' → 'Name1__Name2'
                original_with_slash = param.name.replace('_', ' / ').replace('  ', ' / ')
                # 也替换纯 ' / ' 模式
                body = body.replace(' / ', '__')
                
                # 处理更复杂的原始变量名映射
                # translator.py 输出的变量名来自 FKismetPropertyPointer
                # 需要匹配原始名并替换为 sanitized 名
                if param.cpp_name != param.name:
                    body = body.replace(param.name, param.cpp_name)
            
            method.body_text = body
```

更精确的实现（推荐）：

```python
def _build_name_map(method: CppMethodIR) -> Dict[str, str]:
    """构建 {原始名 -> sanitized名} 映射。
    
    从 method 的 parameters 和可能的局部变量推导替换关系。
    """
    name_map = {}
    for param in method.parameters:
        # 原始名是 sanitize 前的名称
        # 如果 body 中使用 'A / B' 形式，对应 sanitized 名 'A__B'
        original = param.name  # 这是已经 sanitized 的
        # 需要推导原始名 — 通过反向推导
        # 例如 'Left__Right' 原始可能是 'Left / Right'
        if '__' in original:
            parts = original.split('__')
            slash_form = ' / '.join(parts)
            name_map[slash_form] = original
    return name_map

def _inject_function_bodies(methods, decompiled_functions):
    # ... 匹配逻辑不变 ...
    
    if method and decompiled.cpp_code:
        body = decompiled.cpp_code
        
        # 执行符号映射替换
        for original, sanitized in _build_name_map(method).items():
            body = body.replace(original, sanitized)
        
        method.body_text = body
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_cpp_quality_gate.py::TestCppParameterBinding::test_no_illegal_characters_in_body -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/cpp_gen/extract_cpp_skeleton.py tests/test_cpp_quality_gate.py
git commit -m "fix: body_text 注入时执行符号映射替换

- _inject_function_bodies() 新增 {原始名 -> sanitized名} 映射替换
- 修复 'Left / Right' → 'Left__Right' 等参数名断裂问题
- 确保函数体内变量名与方法声明一致"
```

---

### Task 3: 构造函数元数据过滤

**根因**: `build_default_values()` 直接遍历 `blueprint.variables` 无元数据过滤。

**Files:**
- Modify: `src/uasset_read/cpp_gen/cpp_constructor_ir_builder.py`
- Create: `tests/test_constructor_metadata.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_constructor_metadata.py
"""构造函数元数据过滤测试 — 验证 BlueprintSystemVersion 等不注入构造函数。"""
from __future__ import annotations

import os
import re

import pytest

from uasset_read.core import parse_single

_REAL_BLUEPRINT = os.path.join(
    os.environ.get("UE_ASSET_ROOT", r"E:\Develop\lib\UnrealEngine\Samples"),
    "FirstPerson", "Content", "FirstPerson", "Blueprints",
    "BP_FirstPersonCharacter.uasset",
)

_has_real_asset = os.path.isfile(_REAL_BLUEPRINT)

# 已知元数据键（不应出现在构造函数中）
_METADATA_KEYS = {
    "BlueprintSystemVersion",
    "GeneratedClass",
    "SimpleConstructionScript",
    "bCanEverTick",
    "bCanEverRender",
}


@pytest.fixture(scope="module")
def cpp_output() -> str:
    return parse_single(_REAL_BLUEPRINT, format="cpp_skeleton", tolerant=True)


@pytest.mark.integration
@pytest.mark.quality
@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
class TestConstructorMetadataFilter:
    """验证构造函数不注入元数据变量。"""

    def test_no_blueprint_system_version(self, cpp_output: str):
        """构造函数不应包含 BlueprintSystemVersion 赋值。"""
        assert "BlueprintSystemVersion" not in cpp_output

    def test_no_generated_class_assignment(self, cpp_output: str):
        """构造函数不应包含 GeneratedClass 赋值。"""
        assert "GeneratedClass = " not in cpp_output

    def test_no_metadata_keys_in_constructor(self, cpp_output: str):
        """构造函数不应包含任何已知元数据键。"""
        # 提取构造函数部分
        ctor_match = re.search(
            r'::\w+\(\)\s*:\s*(.*?)(?=\nvoid|\n\n|$)',
            cpp_output,
            re.DOTALL,
        )
        if ctor_match:
            ctor_body = ctor_match.group(1)
            for key in _METADATA_KEYS:
                assert key not in ctor_body, f"构造函数包含元数据键: {key}"


@pytest.mark.integration
@pytest.mark.quality
@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
class TestVariableClassification:
    """验证 PackageIR.variables 不包含元数据变量。"""

    def test_no_metadata_variables_in_ir(self):
        """PackageIR.variables 不应包含 BlueprintSystemVersion 等。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker
        from uasset_read.ir_builder import build_package_ir
        
        result = parse_uasset_with_linker(_REAL_BLUEPRINT, tolerant=True)
        ir = build_package_ir(result)
        
        var_names = {v.name for v in ir.variables}
        metadata_found = var_names & _METADATA_KEYS
        assert len(metadata_found) == 0, (
            f"PackageIR.variables 包含元数据变量: {metadata_found}"
        )
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_constructor_metadata.py -v`
Expected: FAIL — BlueprintSystemVersion 和 GeneratedClass 出现在输出中

- [ ] **Step 3: 实现修复**

```python
# src/uasset_read/cpp_gen/cpp_constructor_ir_builder.py
# 在 build_default_values() 函数开头添加元数据过滤集合：

# Blueprint 元数据键列表 — 这些是 UE 编辑器使用的内部字段，
# 不应注入到用户 C++ 构造函数中。
_BLUEPRINT_METADATA_KEYS = frozenset({
    "BlueprintSystemVersion",
    "GeneratedClass",
    "SimpleConstructionScript",
    "bCanEverTick",
    "bCanEverRender",
    "bStartWithTickEnabled",
    "bReplicates",
    "NetUpdateFrequency",
    "MinNetUpdateFrequency",
    "NetPriority",
})

def _is_blueprint_metadata(var_name: str) -> bool:
    """检查变量名是否为蓝图元数据键。"""
    return var_name in _BLUEPRINT_METADATA_KEYS

# 修改 build_default_values() 中的循环：
    if blueprint_vars:
        for var in blueprint_vars:
            if var.is_component:
                continue
            if var.default_value is None:
                continue
            if _is_blueprint_metadata(var.var_name):  # ← 新增
                continue
            # ... 原有逻辑 ...
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_constructor_metadata.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/cpp_gen/cpp_constructor_ir_builder.py tests/test_constructor_metadata.py
git commit -m "fix: 构造函数元数据过滤 — 不注入 BlueprintSystemVersion 等内部字段

- 新增 _BLUEPRINT_METADATA_KEYS 白名单和 _is_blueprint_metadata() 过滤
- 修复 BlueprintSystemVersion = 2 和 GeneratedClass = 3 出现在构造函数
- 新增 TestConstructorMetadataFilter 测试"
```

---

### Task 4: 变量列表分类

**根因**: `_build_variables_ir()` 直接遍历所有变量，不区分用户变量/组件/元数据。

**Files:**
- Modify: `src/uasset_read/ir_builder.py`
- Modify: `src/uasset_read/models/ir.py` — VariableIR 增加 `kind` 字段

- [ ] **Step 1: 编写测试**

```python
# tests/test_variable_classification.py
"""变量分类测试 — 验证 PackageIR.variables 仅包含用户变量。"""
from __future__ import annotations

import os

import pytest

from uasset_read.parse_uasset import parse_uasset_with_linker
from uasset_read.ir_builder import build_package_ir

_REAL_BLUEPRINT = os.path.join(
    os.environ.get("UE_ASSET_ROOT", r"E:\Develop\lib\UnrealEngine\Samples"),
    "FirstPerson", "Content", "FirstPerson", "Blueprints",
    "BP_FirstPersonCharacter.uasset",
)

_has_real_asset = os.path.isfile(_REAL_BLUEPRINT)

# 元数据变量（不应出现在 PackageIR.variables 中）
_METADATA_VARS = {
    "BlueprintSystemVersion",
    "SimpleConstructionScript",
    "bCanEverTick",
    "bCanEverRender",
}


@pytest.mark.integration
@pytest.mark.regression
@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
class TestVariableClassification:
    """验证变量分类正确。"""

    def test_no_metadata_variables(self):
        """PackageIR.variables 不应包含元数据变量。"""
        result = parse_uasset_with_linker(_REAL_BLUEPRINT, tolerant=True)
        ir = build_package_ir(result)
        
        var_names = {v.name for v in ir.variables}
        found = var_names & _METADATA_VARS
        assert len(found) == 0, f"元数据变量混入: {found}"

    def test_user_variables_present(self):
        """PackageIR.variables 应包含用户定义的变量。"""
        result = parse_uasset_with_linker(_REAL_BLUEPRINT, tolerant=True)
        ir = build_package_ir(result)
        
        # 至少应有一些用户变量
        user_vars = [v for v in ir.variables if getattr(v, 'kind', None) in ('user', None)]
        assert len(user_vars) > 0, "未找到用户变量"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_variable_classification.py -v`
Expected: FAIL — 元数据变量混入

- [ ] **Step 3: 实现修复**

```python
# src/uasset_read/models/ir.py
# 修改 VariableIR，增加 kind 字段：

@dataclass
class VariableIR:
    """蓝图变量 IR。"""
    name: str
    type: str
    default_value: str | None
    kind: str = "user"  # "user" | "component" | "input_action" | "metadata"
```

```python
# src/uasset_read/ir_builder.py
# 修改 _build_variables_ir() 函数：

# 在文件顶部添加元数据键集合（或从 extract_cpp_skeleton 导入）
_BLUEPRINT_METADATA_KEYS = frozenset({
    "BlueprintSystemVersion", "GeneratedClass", "SimpleConstructionScript",
    "bCanEverTick", "bCanEverRender", "bStartWithTickEnabled",
    "bReplicates", "NetUpdateFrequency", "MinNetUpdateFrequency", "NetPriority",
})

def _classify_variable(var) -> str:
    """分类蓝图变量。"""
    name = getattr(var, "var_name", "") or ""
    if name in _BLUEPRINT_METADATA_KEYS:
        return "metadata"
    if getattr(var, "is_component", False):
        return "component"
    if "InputAction" in name or "InputAxis" in name:
        return "input_action"
    return "user"

def _build_variables_ir(result: ParseResult) -> list[VariableIR]:
    """从 ParseResult.blueprint.variables 构建 VariableIR 列表。"""
    variables = []
    bp = result.blueprint
    if bp is None:
        return variables
    for var in bp.variables or []:
        kind = _classify_variable(var)
        if kind == "metadata":
            continue  # 跳过元数据变量
        var_type = _format_var_type(var)
        default_value = _safe_str(getattr(var, "default_value", None)) or None
        variables.append(VariableIR(
            name=_safe_str(getattr(var, "var_name", None)),
            type=var_type,
            default_value=default_value,
            kind=kind,
        ))
    return variables
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_variable_classification.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/ir_builder.py src/uasset_read/models/ir.py tests/test_variable_classification.py
git commit -m "fix: 变量分类 — 过滤元数据变量，不混入 PackageIR.variables

- 新增 _classify_variable() 区分 user/component/input_action/metadata
- VariableIR 增加 kind 字段
- 元数据变量（BlueprintSystemVersion 等）不再输出
- 新增 TestVariableClassification 测试"
```

---

### Task 5: quality_stats.py 零文件行为修复

**根因**: 零文件时所有比率均为 0%，全部 PASS。

**Files:**
- Modify: `scripts/quality_stats.py`
- Modify: `tests/test_quality_stats.py`

- [ ] **Step 1: 编写测试**

```python
# tests/test_quality_stats.py — 添加

    def test_zero_files_returns_fail(self, tmp_path):
        """零文件时应返回非零 exit code。"""
        rc, out, err = _run([str(tmp_path)])
        assert rc != 0, "零文件时不应返回 PASS"
        assert "未找到" in out or "no files" in out.lower() or "FAIL" in out
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_quality_stats.py::TestQualityStatsMetrics::test_zero_files_returns_fail -v`
Expected: FAIL — 当前返回 PASS

- [ ] **Step 3: 实现修复**

```python
# scripts/quality_stats.py
# 在 scan_directory() 函数中，添加零文件检查：

def scan_directory(directory: str, verbose: bool = False) -> ScanResult:
    """扫描目录中的所有 .cpp/.h 文件并统计质量指标。"""
    cpp_files = list(Path(directory).rglob("*.cpp"))
    h_files = list(Path(directory).rglob("*.h"))
    all_files = cpp_files + h_files
    
    if not all_files:
        result = ScanResult()
        result.summary.status = "FAIL"  # ← 改为 FAIL
        result.summary.message = f"在 {directory} 中未找到 C++ 源文件"
        return result
    
    # ... 原有逻辑 ...
```

同时在 `_print_report()` 中处理零文件状态：

```python
def _print_report(result: ScanResult, verbose: bool = False) -> None:
    if not result.files_scanned:
        print(f"警告：在 {result.scan_directory} 中未找到 C++ 源文件")
        print("总体评估: FAIL（无文件可扫描）")
        return
    
    # ... 原有输出 ...
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_quality_stats.py -v`
Expected: 全部 PASS（含 test_zero_files_returns_fail）

- [ ] **Step 5: Commit**

```bash
git add scripts/quality_stats.py tests/test_quality_stats.py
git commit -m "fix: quality_stats.py 零文件时返回 FAIL

- scan_directory() 无文件时设置 status=FAIL
- _print_report() 输出明确警告信息
- 新增 test_zero_files_returns_fail 测试"
```

---

### Task 6: 回归测试标记

**Files:**
- Modify: `tests/test_real_asset_e2e.py` — 添加 @pytest.mark.regression
- Modify: `tests/test_cpp_quality_gate.py` — 添加 @pytest.mark.regression

- [ ] **Step 1: 添加 regression marker**

```python
# tests/test_real_asset_e2.py — 给关键测试添加 @pytest.mark.regression

@pytest.mark.integration
@pytest.mark.regression  # ← 新增
@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
class TestRealAssetHighLevelFormats:
    ...

@pytest.mark.integration
@pytest.mark.regression  # ← 新增
class TestTruncatedFileLinkerDiagnostics:
    ...

@pytest.mark.integration
@pytest.mark.regression  # ← 新增
class TestLinkerDiagnosticsInOutput:
    ...
```

```python
# tests/test_cpp_quality_gate.py — 给关键测试添加 @pytest.mark.regression

@pytest.mark.integration
@pytest.mark.regression  # ← 新增
@pytest.mark.quality
@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
class TestCppFatalPatterns:
    ...

@pytest.mark.integration
@pytest.mark.regression  # ← 新增
@pytest.mark.quality
@pytest.mark.skipif(not _has_real_asset, reason="真实资产不可用")
class TestCppParameterBinding:
    ...
```

- [ ] **Step 2: 验证回归测试收集**

Run: `python -m pytest tests/ -m regression --co -q`
Expected: ≥ 10 个 regression 测试

- [ ] **Step 3: Commit**

```bash
git add tests/test_real_asset_e2e.py tests/test_cpp_quality_gate.py
git commit -m "test: 关键测试添加 @pytest.mark.regression 标记

- test_real_asset_e2e.py: 高层入口 + 截断文件 + 诊断输出 (3 类)
- test_cpp_quality_gate.py: 致命模式 + 参数绑定 (2 类)
- pytest -m regression --co ≥ 10 个测试"
```

---

### Task 7: 最终验证 + 文档更新

**Files:**
- 无新建文件

- [ ] **Step 1: 运行完整测试套件**

Run: `python -m pytest tests/ -x --tb=short -q`
Expected: 全部通过（允许 2 xfail），无 xpassed

- [ ] **Step 2: 验证回归测试**

Run: `python -m pytest tests/ -m regression -v --tb=short`
Expected: ≥ 10 个 regression 测试全部通过

- [ ] **Step 3: 验证 quality gate**

Run: `python -m pytest tests/ -m quality -v --tb=short`
Expected: 全部通过

- [ ] **Step 4: 验证真实资产 C++ 输出**

```bash
python -c "
from uasset_read.core import parse_single
out = parse_single('BP_FirstPersonCharacter.uasset', format='cpp_skeleton', tolerant=True)
# 检查无致命模式
assert '= ;' not in out
assert 'BlueprintSystemVersion' not in out
assert 'GeneratedClass = ' not in out
assert 'void Aim() {' not in out  # 无嵌套
print('All quality gates passed')
"
```

- [ ] **Step 5: Commit（如有修复）**

---

## 执行顺序与依赖关系

```
Task 1: 补齐缺失函数 ──────────────┐
                                      ↓
Task 2: 符号映射替换 ←──────────── Task 1（依赖补齐后的 method.parameters）
                                      ↓
Task 3: 构造函数元数据过滤 ────────┐
Task 4: 变量列表分类 ──────────────┤  可并行
                                      ↓
Task 5: quality_stats 零文件 ──────┤
                                      ↓
Task 6: 回归测试标记 ──────────────┘
                                      ↓
Task 7: 最终验证
```

## 风险评估

| 风险 | 影响 | 缓解 |
|------|------|------|
| Task 1 的 _backfill 方法参数推导失败 | 补齐的函数无参数 | 回退到 `parameters=[]` 和 `/* no source available */` |
| Task 2 的符号映射过于激进 | 误替换合法标识符 | 仅替换参数名，不替换 body 中任意匹配 |
| Task 3/4 的元数据键不完整 | 仍有元数据泄漏 | 使用白名单而非黑名单策略 |

## 估算工时

| Task | 预估工时 | 优先级 |
|------|----------|--------|
| Task 1: 补齐缺失函数 | 1-2h | P0 |
| Task 2: 符号映射替换 | 1-2h | P0 |
| Task 3: 构造函数元数据过滤 | 30min | P1 |
| Task 4: 变量列表分类 | 30min | P1 |
| Task 5: quality_stats 零文件 | 15min | P1 |
| Task 6: 回归测试标记 | 15min | P2 |
| Task 7: 最终验证 | 30min | P0 |
| **总计** | **4-5.5 小时** | |

---

## 验收标准

### P0 阻断项
- [ ] C++ 输出函数数 ≥ 反编译函数数的 90%（排除 Ubergraph）
- [ ] 函数体内无 'Left / Right' 等非法参数名
- [ ] 无嵌套函数定义、无空格标识符、无 Python repr

### P1 质量项
- [ ] C++ 构造函数无 BlueprintSystemVersion / GeneratedClass
- [ ] PackageIR.variables 无元数据变量
- [ ] quality_stats.py 零文件返回 FAIL

### 测试要求
- [ ] ≥ 10 个 @pytest.mark.regression 测试
- [ ] 完整测试 100% 通过
- [ ] 真实资产 E2E 全部通过
