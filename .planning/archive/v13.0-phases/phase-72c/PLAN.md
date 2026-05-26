# Phase 72-C: Kismet 字节码导航

**状态:** Completed ✅
**日期:** 2026-05-23
**前置:** Phase 62 (字节码提取), Phase 63 (C++ 翻译), Phase 64 (管线)
**目标:** 从 BlueprintGeneratedClass 中提取 Kismet 字节码，解决当前 `decompile_uasset()` 返回 0 函数的问题。

**完成:** 2026-05-23 — BPGC bytecode extraction module + pipeline fallback integration
---

## 问题诊断

### 现状

`decompile_uasset()` 对 BP_FirstPersonCharacter.uasset 返回 0 个函数。

### 根因

UE5 cooked `.uasset` 文件中，Function 导出的 `script_serial_region` **不包含**实际字节码：

- 12 个 Function 导出全部有 `script_serial_size=9`（仅 "None" 标记 + 元数据）
- `extract_bytecode_bytes()` 读到 PropertyTag "None" 后，`bytecodeBufferSize=0`，`serializedScriptSize=0` → 返回 None
- 实际字节码存储在 **BlueprintGeneratedClass** 的 `script_serial_region` 中
- BPGC（`BP_FirstPersonCharacter_C`，export #2）有 `script_serial_size=217`

### CUE4Parse 参考

- `UStruct.Deserialize()`: SuperStruct → Children → ChildProperties → `bytecodeBufferSize(i32)` → `serializedScriptSize(i32)` → `byte[serializedScriptSize]`
- 这是未烘焙格式。烘焙格式中字节码通过 BPGC 的 ScriptAndPropBuffer 存储。

### BPGC script_serial_region 格式（烘焙格式）— 诊断中

**关键 EExprToken 值（已确认）：**
- `EX_EndOfScript` = 0x53
- `EX_PushExecutionFlow` = 0x4C
- `EX_PopExecutionFlow` = 0x4D
- `EX_FinalFunction` = 0x1C
- `EX_LocalVariable` = 0x00

**诊断发现（2026-05-23）：**
- BPGC 有 4 个 PropertyTag（DynamicBindingObjects, SimpleConstructionScript, UberGraphFunction, PropertyGuids）
- PropertyTag "None" 在 serial 偏移 209 处
- "None" 之后有 600 字节数据（serial_size=817 - 217）
- 标准 UStruct 格式（bytecodeBufferSize + serializedScriptSize）在 cooked 文件中不适用（读得 i32 对 = 0, -23）
- 字节码可能以 `EX_EndOfScript (0x53)` 作为每函数结束标记
- 0xDD 在脚本区域出现 2 次，实际可能是其他 token 值

**待确认:** 字节码的 per-function 分隔方式（size-prefix 还是 sentinel 0x53）

---

## Wave 0: BPGC 字节码格式诊断

**目标:** 确定 BPGC `script_serial_region` 中字节码的精确序列化格式。

**诊断脚本:** 临时脚本（不提交），输出：

1. 扫描 BPGC script_serial_region 中所有 `0x53` (EX_EndOfScript) 位置
2. 对每个 0x53 位置，向后追溯 64 字节，寻找 size 标记模式
3. 尝试按 `i32(size) + byte[size]` 和 `i64(size) + byte[size]` 两种格式解析
4. 对比解析出的函数数量与 ExportMap 中 Function 数量（12 个）

**预期输出:** 确认的字节码分隔格式（size-prefix 或 sentinel-based）

**验收:** 诊断结果能解释 217 字节 script_serial_size 的分配（12 个函数字节码 + header）

---

## 实现方案

### Wave 1: BPGC 字节码提取模块

**文件:** `src/uasset_read/kismet/bpgc_bytecode.py`

**新增 API:**

```python
def extract_bpgc_bytecode(
    archive: FArchive,
    bpgc_export: ObjectExport,
    summary: PackageFileSummary,
    name_map: list[str],
    import_map: list,
    export_map: list,
) -> dict[str, bytes] | None:
    """
    从 BlueprintGeneratedClass 的 script_serial_region 提取所有函数的字节码。

    返回: {function_name: bytecode_bytes} 字典，按 ordinal 映射到 Function 导出。
    """
```

**核心逻辑:**

1. 导航到 BPGC 的 `serial_offset`
2. 跳过 SerializationControlExtensions（如果存在，`file_version_ue5 >= 1011`）
3. 尝试读取 PropertyTag 循环直到 "None"（可能为空）
4. 读取 UStruct 头部：SuperStruct (FPackageIndex, 4 bytes) → Children (TArray, i32 count + 4*N) → ChildProperties (TArray, if FProperties version)
5. 读取字节码缓冲：`bytecodeBufferSize(i32)` → `serializedScriptSize(i32)` → `byte[serializedScriptSize]`
6. 如果步骤 5 的 `serializedScriptSize == 0`，尝试 cooked 格式：按 Wave 0 确认的分隔格式解析
7. 将每个字节码 buffer 映射到对应的 Function 导出名

**缓存策略:**

- `extract_bpgc_bytecode()` 在 `bytecode_extractor.py` 模块级别缓存，以 `(file_path, bpgc_object_name)` 为 key
- 每次调用 `extract_bytecode_bytes()` 时，先检查缓存中是否有该文件的 BPGC bytecode
- 缓存失效：不同文件路径自动使用不同缓存 key，无需显式失效

### Wave 2: 管线集成 + 测试

**修改文件:**
- `src/uasset_read/kismet/bytecode_extractor.py` — 添加 BPGC fallback 路径
- `src/uasset_read/kismet/pipeline.py` — 集成新提取逻辑

**新增文件:**
- `tests/test_kismet_bpgc.py` — BPGC 字节码提取测试

**集成逻辑 (`bytecode_extractor.py`):**

```python
# Module-level cache: file_path -> {function_name: bytecode_bytes}
_BPGC_CACHE: dict[str, dict[str, bytes]] = {}

def extract_bytecode_bytes(archive, export, summary, name_map, import_map, export_map):
    # 现有路径：尝试从 Function export 直接读取
    result = _extract_from_function_export(archive, export, summary, name_map, import_map, export_map)
    if result is not None:
        return result

    # BPGC fallback
    file_path = archive._path
    if file_path not in _BPGC_CACHE:
        bpgc = find_main_blueprint_generated_class(export_map, import_map, Path(file_path).stem)
        if bpgc is None:
            return None
        _BPGC_CACHE[file_path] = extract_bpgc_bytecode(archive, bpgc, summary, name_map, import_map, export_map) or {}

    return _BPGC_CACHE[file_path].get(export.object_name)
```

---

## 任务分解

### Task 0: BPGC 字节码格式诊断 (Wave 0)

- [ ] 编写诊断脚本，扫描 BPGC script_serial_region
- [ ] 确认字节码分隔格式（size-prefix vs EX_EndOfScript sentinel）
- [ ] 验证解析结果能匹配 12 个 Function 导出

**输出:** 确认的字节码序列化格式文档（写入本 PLAN.md 的"BPGC script_serial_region 格式"章节）

**验收:** 诊断脚本能从 BP_FirstPersonCharacter.uasset 中提取出 12 段字节码

### Task 1: bpgc_bytecode.py 核心模块 (Wave 1)

- [ ] `extract_bpgc_bytecode()` — BPGC script_serial_region 解析（使用 Wave 0 确认的格式）
- [ ] `_parse_cooked_bytecode_buffer()` — 烘焙格式解析（纯函数，可独立测试）
- [ ] `_find_function_ordinal()` — Function 在 BPGC children 中的 ordinal 定位

**验收:** 从 BP_FirstPersonCharacter.uasset 提取 ≥ 12 个字节码 buffer，每个能映射到 Function 名

### Task 2: 管线集成 (Wave 2)

- [ ] 修改 `extract_bytecode_bytes()` 添加 BPGC fallback + 模块级缓存
- [ ] 更新 `decompile_single_function()` 使用新路径
- [ ] 更新 `kismet/__init__.py` 导出新符号

**验收:** `decompile_uasset()` 对 BP_FirstPersonCharacter.uasset 返回 ≥ 12 个函数结果

### Task 3: 测试 (Wave 2，可与 Task 2 并行)

- [ ] `test_parse_cooked_bytecode_buffer` — 合成 buffer 单元测试
- [ ] `test_extract_bpgc_bytecode_real_asset` — 真实资产集成测试
- [ ] `test_decompile_uasset_bpgc_functions` — 端到端测试（≥ 12 函数）
- [ ] `test_decompile_execute_ubergraph` — ExecuteUbergraph ≥ 50 表达式
- [ ] Regression: 现有 kismet 测试全部通过

---

## 依赖分析

```
Wave 0: Task 0 (格式诊断)
    ↓
Wave 1: Task 1 (bpgc_bytecode.py — 使用确认的格式)
    ↓
Wave 2: Task 2 (管线集成)  +  Task 3 (测试)  [可并行]
```

Task 0 必须先完成 — Wave 1 的解析逻辑依赖 Wave 0 的格式确认。

## 成功标准

1. `decompile_uasset()` 对 BP_FirstPersonCharacter.uasset 返回 ≥ 12 个函数
2. `ExecuteUbergraph_BP_FirstPersonCharacter` 解析出 ≥ 50 个表达式
3. 所有现有 kismet 测试通过（无回归）
4. 其他 .uasset 解析无影响
5. FArchive 流式解析 STRICT，无裸字节读取

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| BPGC bytecode 格式与预期不同 | 先写诊断脚本验证格式假设，再实现解析 |
| 只适用于特定 UE 版本 | 添加版本检查，对不同 file_version_ue5 使用不同路径 |
| ExecuteUbergraph 字节码在其他位置 | 诊断脚本扫描全文件搜索 EX_PushExecutionFlow (0x4C) 模式 |
