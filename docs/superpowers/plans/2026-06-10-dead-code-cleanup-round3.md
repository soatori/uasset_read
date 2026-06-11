# Dead Code Cleanup Round 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清理第三轮死代码：统一重复 IR 数据结构、删除未使用常量、处理未集成的 cpp_function_body_extractor 模块

**Architecture:** 分三个独立任务执行：(1) 将 blueprint/*_extractor.py 中的 IR dataclass 统一导入 models/ir.py，删除 ir_builder.py 中的冗余转换逻辑；(2) 删除 8 个零引用常量；(3) 评估并处理 cpp_function_body_extractor 模块（保留或删除）

**Tech Stack:** Python 3.10+, pytest, dataclasses

---

## 文件结构总览

### 修改的文件（IR 去重）

| 路径 | 修改内容 |
|------|---------|
| `src/uasset_read/blueprint/interface_extractor.py` | 删除 InterfaceIR 定义，添加 import |
| `src/uasset_read/blueprint/enum_extractor.py` | 删除 EnumValueIR/EnumIR 定义，添加 import |
| `src/uasset_read/blueprint/struct_extractor.py` | 删除 StructFieldIR/StructIR 定义，添加 import |
| `src/uasset_read/blueprint/delegate_extractor.py` | 删除 DelegateIR 定义，添加 import |
| `src/uasset_read/blueprint/replication_extractor.py` | 删除 ReplicatedVarIR/ReplicationIR 定义，添加 import |
| `src/uasset_read/ir_builder.py` | 简化 _build_blueprint_ir() 中的转换逻辑 |

### 修改的文件（常量清理）

| 路径 | 删除内容 |
|------|---------|
| `src/uasset_read/constants.py` | MAX_FTEXT_UTF16_LEN, MAX_RECURSION_DEPTH |
| `src/uasset_read/cpp_gen/extract_cpp_skeleton.py` | FUNC_PRIVATE, FUNC_PROTECTED, FUNC_PUBLIC, MAX_INHERITANCE_DEPTH |
| `src/uasset_read/graph/chain_builder.py` | MAX_CHAIN_DEPTH |
| `src/uasset_read/pak/constants.py` | PAK_ENTRY_FLAGS |

### 待决策的文件

| 路径 | 状态 |
|------|------|
| `src/uasset_read/cpp_gen/extractors/cpp_function_body_extractor.py` | WIP 模块，有测试覆盖，无生产引用 |
| `tests/cpp_gen/test_macro_body_extraction.py` | 对应测试文件 |

---

## Task 1: IR 数据结构去重

**Files:**
- Modify: `src/uasset_read/blueprint/interface_extractor.py:16-27`
- Modify: `src/uasset_read/blueprint/enum_extractor.py:17-44`
- Modify: `src/uasset_read/blueprint/struct_extractor.py:17-44`
- Modify: `src/uasset_read/blueprint/delegate_extractor.py:16-31`
- Modify: `src/uasset_read/blueprint/replication_extractor.py:17-42`
- Modify: `src/uasset_read/ir_builder.py:594-649`

**背景：**
`blueprint/*_extractor.py` 中定义了 8 个 IR dataclass，与 `models/ir.py` 中的定义完全重复。`ir_builder.py` 中存在约 50 行无意义的逐字段复制转换代码。

- [ ] **Step 1: 修改 interface_extractor.py**

删除 `InterfaceIR` dataclass 定义（约 lines 16-27），在文件顶部添加 import：

```python
from uasset_read.models.ir import InterfaceIR
```

- [ ] **Step 2: 修改 enum_extractor.py**

删除 `EnumValueIR` 和 `EnumIR` dataclass 定义（约 lines 17-44），在文件顶部添加 import：

```python
from uasset_read.models.ir import EnumValueIR, EnumIR
```

- [ ] **Step 3: 修改 struct_extractor.py**

删除 `StructFieldIR` 和 `StructIR` dataclass 定义（约 lines 17-44），在文件顶部添加 import：

```python
from uasset_read.models.ir import StructFieldIR, StructIR
```

- [ ] **Step 4: 修改 delegate_extractor.py**

删除 `DelegateIR` dataclass 定义（约 lines 16-31），在文件顶部添加 import：

```python
from uasset_read.models.ir import DelegateIR
```

- [ ] **Step 5: 修改 replication_extractor.py**

删除 `ReplicatedVarIR` 和 `ReplicationIR` dataclass 定义（约 lines 17-42），在文件顶部添加 import：

```python
from uasset_read.models.ir import ReplicatedVarIR, ReplicationIR
```

- [ ] **Step 6: 简化 ir_builder.py 中的转换逻辑**

在 `_build_blueprint_ir()` 函数中（约 lines 594-649），将逐字段复制转换为直接使用 extractor 返回值：

**替换前：**
```python
interfaces_raw = extract_interfaces(bp)
interfaces = [InterfaceIR(
    name=i.name,
    cpp_type=i.cpp_type,
    ue_path=i.ue_path,
) for i in interfaces_raw]
```

**替换后：**
```python
interfaces = extract_interfaces(bp)
```

对 enums、structs、delegates、replication 做相同简化。

- [ ] **Step 7: 运行测试验证**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -10
```

Expected: 所有测试通过（除预存失败）

- [ ] **Step 8: 提交**

```bash
git add -A
git commit -m "refactor: 统一 IR 数据结构定义，删除 8 个重复 dataclass"
```

---

## Task 2: 删除未使用常量

**Files:**
- Modify: `src/uasset_read/constants.py:44,84`
- Modify: `src/uasset_read/cpp_gen/extract_cpp_skeleton.py:58,1018-1020`
- Modify: `src/uasset_read/graph/chain_builder.py:12`
- Modify: `src/uasset_read/pak/constants.py:109-112`

**背景：**
8 个常量在代码中零引用，部分有冗余（MAX_FTEXT_UTF16_LEN vs MAX_FTEXT_CONSUMPTION），部分明确标注为"占位符"。

- [ ] **Step 1: 删除 constants.py 中的常量**

删除以下两行（约 lines 44, 84）：
```python
MAX_RECURSION_DEPTH = 50           # 属性嵌套最大递归深度（防止恶意/畸形资产栈溢出）
MAX_FTEXT_UTF16_LEN = 20_000       # 20 KB — FText/FString UTF-16 字节长度上限（UTF-16 码元对齐）
```

- [ ] **Step 2: 删除 extract_cpp_skeleton.py 中的常量**

删除以下四行（约 lines 58, 1018-1020）：
```python
MAX_INHERITANCE_DEPTH = 50  # 防止无限循环
FUNC_PUBLIC = 0x00000001  # 占位符，实际访问修饰符需要从其他信息推断
FUNC_PROTECTED = 0x00000002  # 占位符
FUNC_PRIVATE = 0x00000004  # 占位符
```

- [ ] **Step 3: 删除 chain_builder.py 中的常量**

删除以下一行（约 line 12）：
```python
MAX_CHAIN_DEPTH = 1000
```

- [ ] **Step 4: 删除 pak/constants.py 中的常量**

删除以下字典定义（约 lines 109-112）：
```python
PAK_ENTRY_FLAGS = {
    "Flag_Encrypted": 0x01,
    "Flag_Deleted": 0x02,
}
```

- [ ] **Step 5: 运行测试验证**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -10
```

Expected: 所有测试通过（除预存失败）

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -m "refactor: 删除 8 个零引用常量"
```

---

## Task 3: 处理 cpp_function_body_extractor 模块

**Files:**
- Delete: `src/uasset_read/cpp_gen/extractors/cpp_function_body_extractor.py`
- Delete: `tests/cpp_gen/test_macro_body_extraction.py`

**背景：**
该模块（540 行）完全未被生产代码引用，但有测试覆盖（test_macro_body_extraction.py）。根据审计，这是一个 WIP 功能，当前代码库中无集成计划。

**决策依据：**
- 项目约束：无向后兼容要求
- 模块状态：WIP，无生产引用
- 测试状态：有测试但测试的是未使用功能
- 代码量：540 行 + 测试文件

**建议：** 删除该模块及其测试，减少维护负担。如果未来需要，可从 git 历史恢复。

- [ ] **Step 1: 删除模块文件**

```bash
rm src/uasset_read/cpp_gen/extractors/cpp_function_body_extractor.py
```

- [ ] **Step 2: 删除测试文件**

```bash
rm tests/cpp_gen/test_macro_body_extraction.py
```

- [ ] **Step 3: 运行测试验证**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -10
```

Expected: 所有测试通过（除预存失败），测试数量减少

- [ ] **Step 4: 提交**

```bash
git add -A
git commit -m "refactor: 删除未集成的 cpp_function_body_extractor 模块（540行 WIP 代码）"
```

---

## Task 4: 最终验证

- [ ] **Step 1: 运行完整测试矩阵**

```bash
python scripts/test_matrix.py unit
```

Expected: 所有测试通过（除预存失败）

- [ ] **Step 2: 运行质量门禁**

```bash
python scripts/test_matrix.py quality
```

Expected: 与基线一致

- [ ] **Step 3: 确认模块导入正常**

```bash
python -c "import uasset_read; print(uasset_read.__version__)"
python -c "from uasset_read.models.ir import InterfaceIR, EnumIR; print('OK')"
python -c "from uasset_read.blueprint.interface_extractor import extract_interfaces; print('OK')"
```

- [ ] **Step 4: 统计清理成果**

```bash
git diff --stat HEAD~3..HEAD
```

Expected: 约 -700 行（IR 去重 ~100 行 + 常量 ~50 行 + cpp_function_body_extractor ~540 行）

---

## 执行顺序建议

1. **Task 2（常量清理）** — 最简单，风险最低，快速完成
2. **Task 1（IR 去重）** — 中等复杂度，需要修改多个文件
3. **Task 3（cpp_function_body_extractor）** — 需要决策，放在最后
4. **Task 4（最终验证）** — 确认所有变更正确

---

## 风险评估

| Task | 风险等级 | 说明 |
|------|---------|------|
| Task 1 | 低 | 字段完全相同，转换是无意义复制 |
| Task 2 | 无 | 零引用常量，删除不影响功能 |
| Task 3 | 低 | WIP 模块，无生产引用，可从 git 历史恢复 |
| Task 4 | 无 | 仅验证，无代码变更 |

---

## 预期成果

- **代码行数减少**：约 700 行
- **重复代码消除**：8 个 IR dataclass 统一
- **维护负担降低**：删除 WIP 模块，减少代码审查范围
- **代码质量提升**：消除冗余，提高代码一致性
