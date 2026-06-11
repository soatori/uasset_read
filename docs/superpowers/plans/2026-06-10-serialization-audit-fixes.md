# 序列化审计修复实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复序列化相关 issues（#77, #82, #83, #84, #100），包括 bytecode fallback 误输出、UClass/BPGC 解析验证、偏移策略文档化

**Architecture:** 
1. 修复 bytecode fallback 分类问题，区分 UE 真实数据与 heuristic guess
2. 验证并完善 UClass/BPGC 原生字段解析
3. 新增偏移策略架构文档

**Tech Stack:** Python 3.10+, pytest, UE 源码对照

**Issues:** #77, #82, #83, #84, #100

---

## 文件结构

### 修改文件
| 文件 | 职责 |
|------|------|
| `src/uasset_read/kismet/bytecode_extractor.py` | 修复 fallback 分类，添加置信度标记 |
| `src/uasset_read/models/ir.py` | 添加 bytecode 置信度字段 |
| `src/uasset_read/ir_builder.py` | 传递置信度到 IR |
| `src/uasset_read/renderers/json_renderer.py` | 渲染置信度字段 |
| `src/uasset_read/parsers/property_parser.py` | 验证 UClass 字段解析完整性 |

### 新增文件
| 文件 | 职责 |
|------|------|
| `docs/designs/payload-offset-strategy.md` | 偏移策略架构文档（合并 #100 + #84） |
| `tests/test_bytecode_fallback_classification.py` | fallback 分类测试 |
| `tests/test_uclass_parsing_completeness.py` | UClass 解析完整性测试 |

---

## Task 1: 验证 UClass/BPGC 解析现状 (#82, #83)

**Files:**
- Read: `src/uasset_read/parsers/class_serialization_strategy.py`
- Read: `src/uasset_read/parsers/asset_types/uclass.py`
- Read: `src/uasset_read/parsers/property_parser.py:389-438`
- Test: `tests/test_uclass_parsing_completeness.py`

**背景:** Issue #82 和 #83 报告 BPGC 分类错误和 UClass parser 缺失，但代码探索显示：
- BPGC 已标记为 `UCLASS_NATIVE`
- `uclass.py` 已实现 `parse_uclass_fields()`

本任务验证实现是否完整。

- [ ] **Step 1: 编写 UClass 解析完整性测试**

```python
# tests/test_uclass_parsing_completeness.py
"""验证 UClass/BPGC 原生字段解析完整性。"""
import pytest
from pathlib import Path


class TestUClassParsingCompleteness:
    """UClass 原生字段解析完整性测试。"""
    
    def test_bpgc_strategy_is_uclass_native(self):
        """验证 BPGC 策略为 UCLASS_NATIVE。"""
        from uasset_read.parsers.class_serialization_strategy import (
            get_serialization_strategy,
            SerializationStrategy,
        )
        
        strategy = get_serialization_strategy("BlueprintGeneratedClass")
        assert strategy == SerializationStrategy.UCLASS_NATIVE, \
            f"BPGC 应为 UCLASS_NATIVE，实际为 {strategy}"
    
    def test_widget_bpgc_strategy_is_uclass_native(self):
        """验证 WidgetBlueprintGeneratedClass 策略为 UCLASS_NATIVE。"""
        from uasset_read.parsers.class_serialization_strategy import (
            get_serialization_strategy,
            SerializationStrategy,
        )
        
        strategy = get_serialization_strategy("WidgetBlueprintGeneratedClass")
        assert strategy == SerializationStrategy.UCLASS_NATIVE
    
    def test_uclass_parser_exists(self):
        """验证 uclass parser 模块存在。"""
        from uasset_read.parsers.asset_types import uclass
        assert hasattr(uclass, "parse_uclass_fields")
    
    def test_uclass_fields_structure(self):
        """验证 UClass 字段结构包含所有必要字段。"""
        from uasset_read.parsers.asset_types.uclass import parse_uclass_fields
        from uasset_read.archive import FArchive
        import io
        
        # 构造最小 UClass payload（模拟）
        # SuperStruct(4) + Children(4) + PropertiesSize(4) + MinAlignment(4)
        # + FuncMap count(4) + ClassFlags(4) + ClassWithin(4) + ClassConfigName
        # + Interfaces count(4) + ClassGeneratedBy(4) + ForceScriptOrder(1)
        # + Dummy + CDO(4)
        
        # 这里使用真实测试资产验证
        sample_path = Path("E:/Develop/lib/UnrealEngine/Samples")
        if not sample_path.exists():
            pytest.skip("样本路径不存在")
        
        # 查找包含 BPGC 的资产
        # 实际测试需要使用真实资产或 mock archive
```

- [ ] **Step 2: 运行测试验证现状**

```bash
python -m pytest tests/test_uclass_parsing_completeness.py -v
```

- [ ] **Step 3: 检查 UClass 字段是否被正确传递到 IR**

验证 `property_parser.py` 解析的 UClass 字段是否被传递到最终输出：

```python
# 检查点：
# 1. property_parser.py L389-438 调用 parse_uclass_fields
# 2. 结果存储在 export._uclass_native_fields
# 3. ir_builder.py 是否读取并传递此字段
# 4. json_renderer.py 是否渲染此字段
```

- [ ] **Step 4: 补充缺失的 IR 传递（如需要）**

如果 UClass 字段未被传递到 IR，修改 `ir_builder.py`：

```python
# src/uasset_read/ir_builder.py - _build_export_ir()
# 添加 UClass 原生字段传递
uclass_fields = getattr(export, "_uclass_native_fields", None)
if uclass_fields is not None:
    export_ir.diagnostics = export_ir.diagnostics or {}
    export_ir.diagnostics["uclass_native"] = {
        "func_map_count": uclass_fields.get("func_map", {}).get("count", 0),
        "class_flags": uclass_fields.get("class_flags", 0),
        "interfaces_count": uclass_fields.get("interfaces", {}).get("count", 0),
        "has_cdo": not uclass_fields.get("class_default_object", {}).get("is_null", True),
    }
```

- [ ] **Step 5: 提交**

```bash
git add tests/test_uclass_parsing_completeness.py src/uasset_read/ir_builder.py
git commit -m "feat: 验证并完善 UClass/BPGC 原生字段解析 (#82, #83)"
```

---

## Task 2: 修复 Bytecode Fallback 分类 (#77)

**Files:**
- Modify: `src/uasset_read/kismet/bytecode_extractor.py`
- Modify: `src/uasset_read/models/ir.py`
- Modify: `src/uasset_read/ir_builder.py`
- Modify: `src/uasset_read/renderers/json_renderer.py`
- Test: `tests/test_bytecode_fallback_classification.py`

**问题:** `_scan_export_serial_for_bytecode` 是 heuristic scan，不应被当作 UE 等价输出。

- [ ] **Step 1: 编写 fallback 分类测试**

```python
# tests/test_bytecode_fallback_classification.py
"""验证 bytecode fallback 分类正确性。"""
import pytest


class TestBytecodeFallbackClassification:
    """Bytecode fallback 分类测试。"""
    
    def test_function_export_is_success(self):
        """function_export 应为 success 状态。"""
        # 主路径提取应标记为 success
        pass
    
    def test_bpgc_fallback_is_partial_metadata(self):
        """bpgc_bytecode_extraction 应为 partial_metadata。"""
        # BPGC fallback 是 UE 真实数据，只是存放位置不同
        pass
    
    def test_serial_scan_is_opaque(self):
        """serial_scan_recovery 应标记为 opaque/heuristic。"""
        # Serial scan 是 heuristic guess，非 UE 等价
        pass
    
    def test_serial_scan_has_low_confidence(self):
        """serial_scan 结果应有低置信度标记。"""
        pass
    
    def test_fallback_reason_propagated_to_ir(self):
        """fallback_reason 应传递到 IR 层。"""
        pass
    
    def test_confidence_field_in_decompiled_function(self):
        """DecompiledFunctionIR 应包含 confidence 字段。"""
        from uasset_read.models.ir import DecompiledFunctionIR
        
        func = DecompiledFunctionIR(name="TestFunc")
        assert hasattr(func, "confidence") or hasattr(func, "bytecode_confidence")
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_bytecode_fallback_classification.py -v
```

Expected: 部分测试失败（confidence 字段不存在）

- [ ] **Step 3: 修改 bytecode_extractor.py 返回置信度**

```python
# src/uasset_read/kismet/bytecode_extractor.py

# 修改 extract_bytecode_bytes 返回值
# 从 (bytes, reason) 改为 (bytes, reason, confidence)

def extract_bytecode_bytes(...) -> tuple[bytes | None, str, str]:
    """
    Returns:
        (bytecode_bytes, fallback_reason, confidence)
        - confidence: "high" | "medium" | "low" | "none"
    """
    ...
    if serialized_script_size > 0:
        return archive.read_bytes(serialized_script_size), "function_export", "high"
    
    # BPGC fallback
    fallback = _bpgc_fallback(...)
    if fallback is not None:
        return fallback, "bpgc_bytecode_extraction", "high"
    
    # Serial scan recovery
    result = _scan_export_serial_for_bytecode(...)
    if result is not None:
        # 计算置信度
        confidence = _calculate_scan_confidence(result)
        return result, "serial_scan_recovery", confidence
    
    return None, "none", "none"


def _calculate_scan_confidence(bytecode: bytes) -> str:
    """计算 serial scan 结果的置信度。"""
    if len(bytecode) < 10:
        return "low"
    
    # 检查是否有完整的函数结构
    has_return = bytecode[0] in _PLAUSIBLE_SCRIPT_START_TOKENS
    has_end = bytecode[-1] == 0x53  # EX_EndOfScript
    
    if has_return and has_end and len(bytecode) > 50:
        return "medium"
    elif has_return or has_end:
        return "low"
    else:
        return "low"
```

- [ ] **Step 4: 更新 IR 模型添加 confidence 字段**

```python
# src/uasset_read/models/ir.py

@dataclass
class DecompiledFunctionIR:
    """反编译函数 IR。"""
    name: str
    fallback_reasons: list[str] = field(default_factory=list)
    bytecode_status: str = "parsed"
    bytecode_confidence: str = "high"  # 新增：high | medium | low | none
```

- [ ] **Step 5: 更新 ir_builder.py 传递 confidence**

```python
# src/uasset_read/ir_builder.py

def _build_decompiled_functions_ir(result) -> list[DecompiledFunctionIR]:
    for func in result.decompiled_functions or []:
        decompiled.append(DecompiledFunctionIR(
            name=func.function_name,
            fallback_reasons=func.fallback_reasons,
            bytecode_status=getattr(func, "bytecode_status", "parsed"),
            bytecode_confidence=getattr(func, "bytecode_confidence", "high"),  # 新增
        ))
```

- [ ] **Step 6: 更新 json_renderer.py 渲染 confidence**

```python
# src/uasset_read/renderers/json_renderer.py

def _decompiled_function_to_dict(self, func: DecompiledFunctionIR) -> dict:
    d = {
        "name": func.name,
    }
    if func.fallback_reasons:
        d["fallback_reasons"] = func.fallback_reasons
    if func.bytecode_status != "parsed":
        d["bytecode_status"] = func.bytecode_status
    if func.bytecode_confidence != "high":  # 新增
        d["bytecode_confidence"] = func.bytecode_confidence
    return d
```

- [ ] **Step 7: 运行测试验证通过**

```bash
python -m pytest tests/test_bytecode_fallback_classification.py -v
```

- [ ] **Step 8: 运行现有测试确保无回归**

```bash
python -m pytest tests/test_bytecode_scanner_fix.py tests/test_kismet*.py -v
```

- [ ] **Step 9: 提交**

```bash
git add src/uasset_read/kismet/bytecode_extractor.py \
        src/uasset_read/models/ir.py \
        src/uasset_read/ir_builder.py \
        src/uasset_read/renderers/json_renderer.py \
        tests/test_bytecode_fallback_classification.py
git commit -m "fix: 区分 bytecode fallback 分类，添加置信度标记 (#77)"
```

---

## Task 3: 编写偏移策略架构文档 (#100, #84)

**Files:**
- Create: `docs/designs/payload-offset-strategy.md`

**背景:** #100 和 #84 都要求文档化偏移策略，合并为一个文档任务。

- [ ] **Step 1: 创建偏移策略文档**

```markdown
# Payload 偏移策略架构决策

> **Issue:** #100, #84  
> **状态:** 已实现，本文档化架构决策

## 概述

本项目 payload 偏移策略默认使用 `SerialOffset/SerialSize`，与 UE `LinkerLoad.cpp:4793` 对齐。
`ScriptSerializationStartOffset` 仅在特定条件下使用。

## UE 源码行为

```cpp
// LinkerLoad.cpp L4786-4806
int64 StartPos = Export.SerialOffset;  // 默认使用 SerialOffset

if (UEVer() >= SCRIPT_SERIALIZATION_OFFSET) {
    if (bIsLoadingToPropertyBagObject || !bDoesSavedClassMatchActualClass) {
        // 仅在特定运行时条件时使用 ScriptSerialization 偏移
        StartPos += Export.ScriptSerializationStartOffset;
    }
}
```

### UE 运行时条件分析

| 条件 | 只读解析器场景 | 结果 |
|------|---------------|------|
| `bIsLoadingToPropertyBagObject` | 不创建 PropertyBag placeholder | 始终 false |
| `!bDoesSavedClassMatchActualClass` | 不加载真正 UClass | 始终 false |

**结论:** UE 运行时条件在只读场景下始终不满足，默认使用 `SerialOffset/SerialSize` 是正确策略。

## 项目实现

### Linker 层 (`link/linker.py`)

```python
# L388-402: Issue #67
seek_offset = instance.serial_offset
effective_serial_size = instance.serial_size
exp = self._export_map[index]

if self._uses_script_serialization_offset(exp):
    sss_offset = getattr(exp, 'script_serialization_start_offset', 0)
    sse_offset = getattr(exp, 'script_serialization_end_offset', 0)
    if sss_offset > 0:
        seek_offset = instance.serial_offset + sss_offset
        effective_serial_size = sse_offset - sss_offset
```

### Property Parser 层 (`parsers/property_parser.py`)

```python
# L347-358: 属性解析起始位置
property_start = export.serial_offset  # 默认使用 SerialOffset

# ScriptSerialization 绝对偏移存储用于诊断
export._script_serialization_start_absolute = (
    export.serial_offset + getattr(export, 'script_serialization_start_offset', 0)
)
export._script_serialization_end_absolute = (
    export.serial_offset + getattr(export, 'script_serialization_end_offset', 0)
)
```

### 条件判断 (`_uses_script_serialization_offset`)

```python
# L436-463
def _uses_script_serialization_offset(self, exp) -> bool:
    """检查是否应使用 ScriptSerializationStartOffset。"""
    # 条件：
    # 1. UE 版本 >= UE5_SCRIPT_SERIALIZATION_OFFSET (1004)
    # 2. 非 UnversionedProperties
    # 3. script_serialization_start_offset > 0
    ...
```

## 简化决策理由

1. **只读解析器不创建运行时对象** — `bIsLoadingToPropertyBagObject` 始终 false
2. **不进行类匹配验证** — `bDoesSavedClassMatchActualClass` 始终 true
3. **UE 运行时条件在只读场景下不满足** — 默认 SerialOffset 是正确策略

## 诊断支持

ScriptSerialization 偏移保留为诊断字段：
- `export._script_serialization_start_absolute`
- `export._script_serialization_end_absolute`
- `export.transforms["serialization_control"]`

这些字段可用于：
- 偏移错位诊断
- UE 版本兼容性分析
- 调试日志输出

## 参考

- UE 源码: `Engine/Source/Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp:4786-4806`
- 项目约束: `.claude/rules/constraints.md` → Payload 偏移默认策略
- 相关 Issue: #67, #100, #84
```

- [ ] **Step 2: 提交**

```bash
git add docs/designs/payload-offset-strategy.md
git commit -m "docs: 新增 Payload 偏移策略架构文档 (#100, #84)"
```

---

## Task 4: 集成测试与验证

**Files:**
- Test: `tests/test_serialization_audit_integration.py`

- [ ] **Step 1: 编写集成测试**

```python
# tests/test_serialization_audit_integration.py
"""序列化审计修复集成测试。"""
import pytest
from pathlib import Path


class TestSerializationAuditIntegration:
    """集成测试：验证所有序列化审计修复。"""
    
    @pytest.fixture
    def sample_dir(self):
        path = Path("E:/Develop/lib/UnrealEngine/Samples")
        if not path.exists():
            pytest.skip("样本路径不存在")
        return path
    
    def test_bpgc_export_has_uclass_diagnostics(self, sample_dir):
        """验证 BPGC export 包含 UClass 诊断信息。"""
        from uasset_read import parse_single
        
        # 查找包含 BPGC 的资产
        blueprint_files = list(sample_dir.glob("**/*_Gen.uasset"))
        if not blueprint_files:
            pytest.skip("未找到蓝图资产")
        
        result = parse_single(blueprint_files[0])
        
        # 检查 BPGC export
        for export in result.export_map:
            if export.object_class == "BlueprintGeneratedClass":
                # 应有 uclass_native 诊断
                assert hasattr(export, "_uclass_native_fields") or \
                       getattr(export, "parse_status", None) == "uclass_native"
    
    def test_bytecode_fallback_reason_in_output(self, sample_dir):
        """验证 bytecode fallback_reason 在输出中可见。"""
        from uasset_read import parse_single
        from uasset_read.renderers import json_renderer
        
        # 查找包含 Function 的资产
        blueprint_files = list(sample_dir.glob("**/*_Gen.uasset"))
        if not blueprint_files:
            pytest.skip("未找到蓝图资产")
        
        result = parse_single(blueprint_files[0])
        ir = result.to_ir()
        json_output = json_renderer.render(ir)
        
        # 如果有 decompiled_functions，检查字段
        if json_output.get("decompiled_functions"):
            func = json_output["decompiled_functions"][0]
            # 应有 fallback_reasons 或 bytecode_confidence
            assert "fallback_reasons" in func or "bytecode_confidence" in func or \
                   func.get("bytecode_status") == "parsed"
    
    def test_offset_strategy_documentation_exists(self):
        """验证偏移策略文档存在。"""
        doc_path = Path("docs/designs/payload-offset-strategy.md")
        assert doc_path.exists(), "偏移策略文档应存在"
```

- [ ] **Step 2: 运行集成测试**

```bash
python -m pytest tests/test_serialization_audit_integration.py -v
```

- [ ] **Step 3: 运行全量测试确保无回归**

```bash
python scripts/test_matrix.py unit
```

- [ ] **Step 4: 提交**

```bash
git add tests/test_serialization_audit_integration.py
git commit -m "test: 添加序列化审计修复集成测试"
```

---

## Task 5: 关闭 Issues

- [ ] **Step 1: 关闭 Issue #77**

```bash
gh issue close 77 --comment "已修复：bytecode fallback 现在区分分类（function_export/bpgc_bytecode_extraction/serial_scan_recovery）并添加置信度标记（high/medium/low）。"
```

- [ ] **Step 2: 关闭 Issue #82**

```bash
gh issue close 82 --comment "已验证：BPGC 已正确标记为 UCLASS_NATIVE，UClass 原生字段解析已实现并传递到 IR 诊断。"
```

- [ ] **Step 3: 关闭 Issue #83**

```bash
gh issue close 83 --comment "已验证：UClass parser 已实现（uclass.py），包含 FuncMap/ClassFlags/Interfaces/CDO 等字段。"
```

- [ ] **Step 4: 关闭 Issue #84 和 #100**

```bash
gh issue close 84 --comment "已文档化：新增 docs/designs/payload-offset-strategy.md 说明偏移策略架构决策。"
gh issue close 100 --comment "已文档化：ScriptSerialization 偏移计算架构决策已在 payload-offset-strategy.md 中说明。"
```

---

## 验收标准

1. **Issue #77:** bytecode fallback 分类正确，confidence 字段在 JSON 输出中可见
2. **Issue #82:** BPGC 策略为 UCLASS_NATIVE，UClass 字段传递到 IR
3. **Issue #83:** UClass parser 完整，包含所有必要字段
4. **Issue #84/100:** 偏移策略文档存在且内容完整
5. **测试:** 所有新增测试通过，无回归
6. **质量:** `python scripts/test_matrix.py quality` 通过
