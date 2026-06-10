# 死代码清理 Round 2 — 巨型冗余文件 + 死函数 + 未使用 imports

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除 1494 行冗余 property_types.py 旧文件、26 个零引用死函数、86 个未使用 import。

**Architecture:** 按风险从低到高执行：先清理未使用 import（纯删除），再删除死函数（纯删除），最后删除 property_types.py 巨型冗余文件（需验证 import 路径）。每步 TDD：运行测试确认无回归。

**Tech Stack:** Python 3.10+, pytest

---

## 文件结构总览

### 删除的文件

| 路径 | 原因 |
|---|---|
| `src/uasset_read/parsers/property_types.py` | 1494 行，功能已完全拆分到 `property_types/` 子包 |

### 修改的文件（死函数删除）

| 路径 | 删除内容 |
|---|---|
| `src/uasset_read/archive.py` | `peek_i32`, `serialize_int`, `serialize_bits`, `get_name_map` 方法 |
| `src/uasset_read/blueprint/component_extractor.py` | `_find_scs_property_on_bpgc` 函数 |
| `src/uasset_read/graph/pin_trace.py` | `_classify_node` 函数 |
| `src/uasset_read/iostore/reader.py` | `does_chunk_exist`, `try_resolve` 方法 |
| `src/uasset_read/iostore/structures.py` | `from_hash` 方法 |
| `src/uasset_read/kismet/archive.py` | `read_fname_kismet` 方法 |
| `src/uasset_read/kismet/bytecode_extractor.py` | `expressions_to_flat_list`, `expressions_to_tree` 函数 |
| `src/uasset_read/kismet/result.py` | `to_cpp_string` 方法 |
| `src/uasset_read/kismet/structured_flow.py` | `_Block` 类, `_find_matching_pop` 方法 |
| `src/uasset_read/kismet/translator.py` | `resolve_type`, `populate_from_metadata`, `ue_to_cpp` 方法 |
| `src/uasset_read/link/object_instance.py` | `get_class_object`, `get_template_object`, `ensure_preloaded` 方法 |
| `src/uasset_read/package.py` | `read_payload` 方法 |
| `src/uasset_read/package_version_profile.py` | `needs_legacy_guid_position` 方法 |
| `src/uasset_read/pak/structures.py` | `decode_encoded_pak_entry` 函数 |
| `src/uasset_read/parsers/asset_types/uclass.py` | `parse_uclass_handler` 函数 |

### 修改的文件（未使用 import 清理）

46 个文件，详见 Task 3。

---

### Task 1: 删除冗余 property_types.py（1494 行）

**Files:**
- Delete: `src/uasset_read/parsers/property_types.py`

**背景：**
`property_types.py`（1494 行）的所有功能已拆分到 `property_types/` 子包（scalar.py, containers.py, structs.py, object_ref.py, text_delegate.py, ue5_verse.py, _utils.py, _common.py）。`property_types/__init__.py` 已从子模块 re-export 所有公共 API。

Python import 优先级：当 `property_types.py` 和 `property_types/` 目录同时存在时，**包（目录）优先**。因此 `property_types.py` 实际上从未被 import——它是纯死代码。

- [ ] **Step 1: 验证当前 import 路径**

```bash
cd E:\Develop\uasset_read
python -c "import uasset_read.parsers.property_types; print(uasset_read.parsers.property_types.__file__)"
```

Expected: 输出应指向 `property_types/__init__.py`（目录），而非 `property_types.py`（文件）。

- [ ] **Step 2: 运行基线测试**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -5
```

记录 passed/failed 数量作为基线。

- [ ] **Step 3: 删除 property_types.py**

```bash
rm src/uasset_read/parsers/property_types.py
```

- [ ] **Step 4: 验证 import 仍然正确**

```bash
python -c "import uasset_read.parsers.property_types; print(uasset_read.parsers.property_types.__file__)"
python -c "from uasset_read.parsers.property_types import parse_int_property, get_struct_size, format_variable_type; print('OK')"
```

Expected: 两行都成功，无 ImportError。

- [ ] **Step 5: 运行全量测试确认无回归**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -5
```

Expected: passed/failed 数量与基线完全一致。

- [ ] **Step 6: Commit**

```bash
git add -A src/uasset_read/parsers/property_types.py
git commit -m "refactor: 删除冗余 property_types.py（1494行，已完全拆分到子包）"
```

---

### Task 2: 删除 26 个零引用死函数

**Files:** 见上方"修改的文件（死函数删除）"列表

**背景：** 以下函数/方法在整个项目（src/ + tests/）中从未被调用。它们是重构遗留或从未使用的预留接口。

- [ ] **Step 1: 删除 archive.py 中的 4 个死方法**

在 `src/uasset_read/archive.py` 中删除：

1. `peek_i32` 方法（约 L296-308）：
```python
    def peek_i32(self) -> int:
        """预读 signed 32-bit integer（不移动位置）"""
        import struct
        current_pos = self.tell()
        try:
            fmt = '>' if self._byte_swapping else '<'
            data = self.read(4)
            result = struct.unpack(fmt + 'i', data)[0]
            self.seek(current_pos)
            return result
        except Exception:
            self.seek(current_pos)
            raise
```

2. `serialize_int` 方法（约 L371-379）：
```python
    def serialize_int(self, value: int) -> bytes:
        """序列化 32 位整数（用于 SerializeInt 兼容）。..."""
        import struct
        fmt = '>' if self._byte_swapping else '<'
        return struct.pack(fmt + 'i', value)
```

3. `serialize_bits` 方法（约 L381-395）：
```python
    def serialize_bits(self, value: int, num_bits: int) -> bytes:
        """序列化指定位数的值（用于 SerializeBits 兼容）。..."""
```

4. `get_name_map` 方法（约 L490-496）：
```python
    def get_name_map(self) -> Optional[list]:
        """获取当前缓存的名称表。..."""
        return self._name_map
```

- [ ] **Step 2: 删除其他文件中的死函数**

逐个文件删除（先 Read 确认行号，再 Edit 删除）：

| 文件 | 函数 | 约行号 |
|---|---|---|
| `blueprint/component_extractor.py` | `_find_scs_property_on_bpgc` | L177 |
| `graph/pin_trace.py` | `_classify_node` | L89 |
| `iostore/reader.py` | `does_chunk_exist` | L262 |
| `iostore/reader.py` | `try_resolve` | L267 |
| `iostore/structures.py` | `from_hash` (classmethod) | L94 |
| `kismet/archive.py` | `read_fname_kismet` | L141 |
| `kismet/bytecode_extractor.py` | `expressions_to_flat_list` | L502 |
| `kismet/bytecode_extractor.py` | `expressions_to_tree` | L523 |
| `kismet/result.py` | `to_cpp_string` | L73 |
| `kismet/structured_flow.py` | `_Block` class | L22 |
| `kismet/structured_flow.py` | `_find_matching_pop` | L165 |
| `kismet/translator.py` | `resolve_type` | L80 |
| `kismet/translator.py` | `populate_from_metadata` | L84 |
| `kismet/translator.py` | `ue_to_cpp` | L126 |
| `link/object_instance.py` | `get_class_object` | L121 |
| `link/object_instance.py` | `get_template_object` | L131 |
| `link/object_instance.py` | `ensure_preloaded` | L145 |
| `package.py` | `read_payload` | L166 |
| `package_version_profile.py` | `needs_legacy_guid_position` | L57 |
| `pak/structures.py` | `decode_encoded_pak_entry` | L491 |
| `parsers/asset_types/uclass.py` | `parse_uclass_handler` | L263 |

对每个函数：先 Read 文件确认精确行号和内容，然后用 Edit 删除整个函数体（包括 def 行和 docstring）。

- [ ] **Step 3: 运行全量测试**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -5
```

Expected: passed/failed 数量与 Task 1 基线一致。

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: 删除 26 个零引用死函数（archive/iostore/kismet/link/pak 等）"
```

---

### Task 3: 清理 86 个未使用 import

**Files:** 46 个文件（详见下方列表）

**背景：** 这些 import 语句导入了符号但在文件中从未使用。多数是重构遗留或 typing 残留。

- [ ] **Step 1: 清理 typing 残留（约 15 处）**

从以下文件中移除未使用的 typing import：

| 文件 | 移除 |
|---|---|
| `cpp_gen/cpp_type_mapper.py:19` | `List`, `Optional` |
| `graph/chain_builder.py:9` | `Any`, `Set`, `Tuple` |
| `graph/flow_builder.py:8` | `Iterable` |
| `iostore/structures.py:5` | `Optional` |
| `kismet/bpgc_bytecode.py:15` | `Optional` |
| `kismet/bytecode_extractor.py:15` | `Optional` |
| `kismet/expressions/assignments.py:9` | `Optional` |
| `kismet/expressions/context.py:3` | `Optional` |
| `kismet/expressions/control_flow.py:9` | `Optional` |
| `kismet/translator.py:13` | `Optional` |
| `models/core.py:13` | `Dict` |
| `pak/game_versions.py:7` | `Optional` |
| `parsers/property_types/object_ref.py:4` | `Any` |
| `parsers/property_types.py` | 整个文件已删除（Task 1） |
| `parsers/unversioned_parser.py:10` | `Optional` |

对每个文件：Read → 找到 import 行 → Edit 移除未使用的符号。

- [ ] **Step 2: 清理 dataclasses.field 未使用导入（5 处）**

| 文件 | 行号 |
|---|---|
| `blueprint/delegate_extractor.py:9` |
| `blueprint/interface_extractor.py:9` |
| `cpp_gen/cpp_constructor_ir_builder.py:21` |
| `package_version_profile.py:12` |
| `renderers/base.py:10` |

- [ ] **Step 3: 清理业务模块未使用 import（约 30 处）**

| 文件 | 移除 |
|---|---|
| `archive.py:57` | `import struct as _struct`（注意：此 import 在 read() 方法内部，删除该行） |
| `cpp_gen/cpp_default_value_formatter.py:15` | `ScaleValue`, `VectorValue` |
| `cpp_gen/extract_cpp_skeleton.py:46` | `CPF_InstancedReference` |
| `cpp_gen/extractors/cpp_function_body_extractor.py:8` | `Any` |
| `cpp_gen/formatters/cpp_header_formatter.py:21` | `CppHeaderMeta` |
| `cpp_gen/formatters/cpp_json_ir.py:17` | `asdict` |
| `graph/_execution_trace.py:15,22` | `UEdGraph`, `_derive_node_name`, `_get_start_event_name` |
| `graph/chain_builder.py:8,11,12` | `warnings`, `CONTROL_FLOW_NODES`, `UEdGraphNode` |
| `graph/flow_builder.py:21` | `_sanitize_string`, `_sanitize_pin_dict`, `_sanitize_recursive` |
| `kismet/bpgc_bytecode.py:18` | `EExprToken` |
| `link/linker.py:19` | `PackageIndex as PI` |
| `pak/index.py:13` | `FPakDirectoryEntry` |
| `pak/structures.py:8,21` | `BytesIO`, `get_game_info` |
| `parse_uasset.py:24` | `VersionContainer` |
| `parsers/property_parser.py:130` | `asset_types` |
| `parsers/property_types/containers.py:15` | `FallbackReason` |
| `parsers/property_types/structs.py:16` | `read_validated_count` |
| `parsers/utils.py:5` | `ErrorContext` |
| `serializers/graph/_common.py:4,9,17` | `json`, `Tuple`, `MAX_FTEXT_CONSUMPTION` |
| `serializers/graph/nodes.py:22` | `read_fmember_reference` |
| `serializers/package_summary.py:894` | `ObjectExport` |

- [ ] **Step 4: 处理 `__init__.py` 和 `renderers/__init__.py` 的 re-export**

`src/uasset_read/__init__.py` 中以下导入未在 `__all__` 中列出但被 re-export：
- L216: `VersionContainer`, `build_version_container`, `EUEVersion`
- L219: `PackageLinker`, `UObjectInstance`, `LinkerParseResult`
- L230: `IoStoreReader`, `FIoChunkId`, `FIoOffsetAndSize`
- L245: `VectorValue`, `RotatorValue`, `ScaleValue`, `format_transform_value`
- L258-260: `read_property_tag`, `parse_ctrl_flags`, `parse_ue511_ctrl_flags`, `parse_default_value`, `format_variable_type`, `read_blueprint_variable`, `parse_property_flags_to_labels`

**决策**：这些是子模块 API 的便捷 re-export，保留（它们为外部使用者提供短路径导入）。不删除。

`renderers/__init__.py` 中 6 个 renderer 模块导入：检查是否在 `__all__` 中。如果不在，添加到 `__all__` 或删除。

- [ ] **Step 5: 运行全量测试**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -5
```

Expected: passed/failed 数量与基线一致。

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: 清理 86 个未使用 import（typing 残留 + 重构遗留）"
```

---

### Task 4: 最终验证

- [ ] **Step 1: 运行全量测试矩阵**

```bash
python scripts/test_matrix.py unit
```

Expected: 全部 PASS（除预先存在的失败）

- [ ] **Step 2: 运行质量门禁**

```bash
python scripts/test_matrix.py quality
```

Expected: 与基线一致

- [ ] **Step 3: 确认模块导入正常**

```bash
python -c "import uasset_read; print(uasset_read.__version__)"
python -c "from uasset_read.parsers.property_types import parse_int_property; print('OK')"
python -c "from uasset_read.archive import FArchive; print('OK')"
```

- [ ] **Step 4: 统计清理成果**

```bash
git diff --stat HEAD~4..HEAD
```

Expected: 约 -1700 行（1494 + 150 + 86）
