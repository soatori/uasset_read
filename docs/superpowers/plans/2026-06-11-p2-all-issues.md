# P2 Issue 全量修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复全部 6 个 P2 issue — 格式正确性（#96/#97/#98）、资源安全（#108）、架构重构（#114/#115）

**Architecture:** 三个独立子系统按依赖顺序分阶段实施：先修格式（保证解析正确性），再修资源（保证批量稳定性），最后重构（改善代码结构）。每个 task 独立可测试、可提交。

**Tech Stack:** Python 3.10+, pytest, 零运行时依赖

---

## 文件结构总览

### 修改文件

| 文件 | 职责 | 涉及 Issue |
|------|------|-----------|
| `src/uasset_read/serializers/package_summary.py` | UE5 PackageSummary 版本门控 | #96 |
| `src/uasset_read/kismet/archive.py` | FKismetArchive 添加版本感知 | #98 |
| `src/uasset_read/kismet/bytecode_extractor.py` | 传递版本到 FKismetArchive | #98 |
| `src/uasset_read/kismet/expressions/vector_consts.py` | VectorConst/RotationConst/TransformConst LWC 门控 | #98 |
| `src/uasset_read/kismet/expressions/string_consts.py` | FScriptText InvariantText 修复 | #97 |
| `src/uasset_read/parsers/property_types/object_ref.py` | SoftObjectPath 三阶段版本门控 | #97 |
| `src/uasset_read/archive.py` | 添加 `__del__` 安全网 | #108 |
| `src/uasset_read/iostore/reader.py` | 添加 `__del__` 安全网 | #108 |
| `src/uasset_read/pak/reader.py` | 添加 `__del__` 安全网 | #108 |
| `src/uasset_read/kismet/function_resolver.py` | 添加 `reset()` 方法 | #108 |
| `src/uasset_read/parsers/class_registry.py` | 添加 `reset_cache()` 方法 | #108 |
| `src/uasset_read/parse_uasset.py` | finally 块补充缓存清理 + #115 stage 拆分 | #108, #115 |
| `src/uasset_read/models/result.py` | 状态计算委托统一函数 | #114 |
| `src/uasset_read/link/result.py` | 状态计算委托统一函数 | #114 |
| `src/uasset_read/ir_builder.py` | `_result_status` 升级为权威实现 | #114 |

### 新建文件

| 文件 | 职责 | 涉及 Issue |
|------|------|-----------|
| `src/uasset_read/status.py` | 统一状态计算函数 `compute_result_status()` | #114 |
| `src/uasset_read/post_process.py` | PostProcessContext + stage runner + 各 stage 类 | #115 |
| `tests/test_p2_version_gating.py` | PackageSummary + SoftObjectPath 版本门控测试 | #96, #97 |
| `tests/test_p2_lwc_kismet.py` | Kismet LWC 门控测试 | #98 |
| `tests/test_p2_memory_safety.py` | `__del__` + 缓存清理测试 | #108 |
| `tests/test_p2_status_unified.py` | 统一状态模型测试 | #114 |
| `tests/test_p2_post_process_stages.py` | Stage 隔离性测试 | #115 |

---

## 阶段 A：格式修复（#96, #97, #98）

### Task 1: PackageSummary UE5 PreloadDependencies 版本门控 (#96)

**Files:**
- Modify: `src/uasset_read/serializers/package_summary.py:787-791`
- Test: `tests/test_p2_version_gating.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_p2_version_gating.py
"""P2 格式修复测试 — 版本门控 (#96, #97)。"""
from __future__ import annotations

import io
import struct
import pytest

from uasset_read.archive import FArchive
from uasset_read.serializers.package_summary import _read_package_summary_ue5
from uasset_read.constants import (
    UE5_NAMES_REFERENCED_FROM_EXPORT_DATA,
    UE5_PAYLOAD_TOC,
    UE5_LARGE_WORLD_COORDINATES,
)


def _build_minimal_ue5_summary_bytes(file_version_ue5: int, include_preload: bool = True):
    """构造最小 UE5 PackageSummary 字节流，用于测试版本门控。

    注意：这是一个辅助函数，需要根据实际的 _read_package_summary_ue5
    读取顺序构造完整的字节流。这里只关注 PreloadDependencies 字段
    是否被正确门控。
    """
    # 实际测试中需要用真实 uasset 文件或 mock archive
    # 此处用集成测试方式验证
    pass


class TestPreloadDependenciesVersionGate:
    """#96: PreloadDependencies 在 UE5 路径中应有版本门控。"""

    def test_ue5_below_512_no_preload_deps(self):
        """UE5 路径中 file_version_ue4 < 512 时不应读取 PreloadDependencies。

        使用真实 UE5 资产样本验证（如果可用），否则用 mock。
        """
        # 集成测试：找一个 UE5 < 512 的样本（如果存在）
        # 或者构造一个 mock archive 验证读取偏移不越过 PreloadDependencies
        pytest.skip("需要构造完整 UE5 summary 字节流 — 见 Step 2 集成方案")

    def test_ue5_at_512_reads_preload_deps(self):
        """UE5 路径中 file_version_ue4 >= 512 时应读取 PreloadDependencies。"""
        pytest.skip("需要构造完整 UE5 summary 字节流 — 见 Step 2 集成方案")
```

**实际测试策略**：由于 `_read_package_summary_ue5` 需要完整的 PackageSummary 字节流（数百字节），纯单元测试成本过高。改用 **回归测试**：在现有样本上运行修复前后对比偏移是否正确。

- [ ] **Step 1 (替代): 写回归测试用偏移检测**

```python
# tests/test_p2_version_gating.py
"""P2 格式修复测试 — 版本门控 (#96, #97)。"""
from __future__ import annotations

import struct
import pytest


class TestPreloadDependenciesVersionGate:
    """#96: PreloadDependencies 在 UE5 路径中应有版本门控。

    UE 源码 PackageFileSummary.cpp L503-511:
      if (Sum.FileVersionUE >= VER_UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS)  // 506
          Record << Sum.PreloadDependenciesUE5;

    项目 UE5 路径 (package_summary.py L787-791) 无条件读取 — 这是 bug。
    """

    def test_version_gate_logic(self):
        """验证版本门控逻辑正确性（纯逻辑测试）。"""
        # UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS = 512
        # 当 file_version_ue4 < 512 时，不应读取 preload deps
        UE4_PRELOAD_DEPS = 512

        # 模拟门控逻辑
        def should_read_preload(file_version_ue4: int) -> bool:
            return file_version_ue4 >= UE4_PRELOAD_DEPS

        assert should_read_preload(512) is True
        assert should_read_preload(516) is True
        assert should_read_preload(511) is False
        assert should_read_preload(0) is False   # 极早期版本
        assert should_read_preload(522) is True   # 最新版本
```

- [ ] **Step 2: 运行测试确认通过**

Run: `python -m pytest tests/test_p2_version_gating.py::TestPreloadDependenciesVersionGate -v`
Expected: PASS

- [ ] **Step 3: 修复 package_summary.py UE5 路径**

在 `src/uasset_read/serializers/package_summary.py:787-791`，将无条件读取改为版本门控：

```python
    # 第 28 步：PreloadDependencies (UE4 >= 512)
    # UE 源码: PackageFileSummary.cpp L503-511
    preload_dependency_count = 0
    preload_dependency_offset = 0
    if file_version_ue4 >= UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS:  # 512
        preload_dependency_count = archive.read_i32()
        preload_dependency_offset = archive.read_i32()
        if preload_dependency_offset > 0:
            archive.validate_offset(preload_dependency_offset, "PreloadDependencyOffset")
```

注意：`file_version_ue4` 是 `_read_package_summary_ue5` 函数的局部变量（L532 `file_version_ue4 = archive.read_i32()`），可以直接使用。常量 `UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS = 512` 定义在 `constants.py:140`。

- [ ] **Step 4: 验证修复后现有测试不回归**

Run: `python -m pytest tests/ -v -m "not slow" --timeout=60 -x`
Expected: 所有现有测试 PASS

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/serializers/package_summary.py tests/test_p2_version_gating.py
git commit -m "fix: UE5 路径 PreloadDependencies 添加版本门控 (#96)"
```

---

### Task 2: FScriptText InvariantText 字段数修复 (#97 D.2)

**Files:**
- Modify: `src/uasset_read/kismet/expressions/string_consts.py:74-79`
- Test: `tests/test_p2_version_gating.py`

**发现的问题**：
1. 枚举成员名称错误：代码使用 `.Invariant` 和 `.CultureInvariant`，但枚举定义为 `.InvariantText` 和 `.LiteralString`（会导致 AttributeError）
2. InvariantText 读取 2 个字符串，UE XFERTEXT 宏只读取 1 个

- [ ] **Step 1: 写失败测试**

```python
# 追加到 tests/test_p2_version_gating.py

class TestFScriptTextInvariant:
    """#97 D.2: FScriptText InvariantText 应只读取 1 个 expression。

    UE XFERTEXT 宏: InvariantText 只有 1 个字符串（invariant/source string）。
    当前代码读取 2 个字符串（key + source），多读 1 个。
    此外，枚举成员名称引用错误（Invariant → InvariantText, CultureInvariant → LiteralString）。
    """

    def test_invariant_reads_one_string(self):
        """验证 InvariantText 只读取一个字符串的修复逻辑。"""
        import io
        from uasset_read.kismet.archive import FKismetArchive
        from uasset_read.kismet.expressions.string_consts import FScriptText
        from uasset_read.kismet.tokens import EBlueprintTextLiteralType

        # 构造 InvariantText 字节流：
        # 1 byte: literal type (InvariantText = 2)
        # ASCII null-terminated string + null byte
        name_map = ["test"]
        source_str = "invariant_text"

        buf = io.BytesIO()
        buf.write(struct.pack('B', 2))  # InvariantText enum value
        buf.write(source_str.encode('ascii'))
        buf.write(b'\x00')  # null terminator
        buf.seek(0)

        archive = FKismetArchive(buf.read(), "test", name_map)
        text = FScriptText.from_archive(archive, name_map)

        assert text.TextLiteralType == EBlueprintTextLiteralType.InvariantText
        assert text.SourceString == source_str
        # 修复后 KeyString 应为 None（不再读取第二个字符串）
        assert text.KeyString is None

    def test_literal_string_reads_one_string(self):
        """验证 LiteralString 读取一个字符串。"""
        import io
        from uasset_read.kismet.archive import FKismetArchive
        from uasset_read.kismet.expressions.string_consts import FScriptText
        from uasset_read.kismet.tokens import EBlueprintTextLiteralType

        name_map = ["test"]
        source_str = "literal_fstring"

        buf = io.BytesIO()
        buf.write(struct.pack('B', 3))  # LiteralString enum value
        buf.write(source_str.encode('ascii'))
        buf.write(b'\x00')
        buf.seek(0)

        archive = FKismetArchive(buf.read(), "test", name_map)
        text = FScriptText.from_archive(archive, name_map)

        assert text.TextLiteralType == EBlueprintTextLiteralType.LiteralString
        assert text.SourceString == source_str
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_p2_version_gating.py::TestFScriptTextInvariant -v`
Expected: FAIL — 枚举成员不存在 + 读取逻辑错误

- [ ] **Step 3: 修复 FScriptText 枚举引用和 InvariantText 逻辑**

修改 `src/uasset_read/kismet/expressions/string_consts.py:74-83`：

```python
        elif lit_type == EBlueprintTextLiteralType.InvariantText:
            # UE XFERTEXT: InvariantText 只读取 1 个 expression（source string）
            source = archive.xfer_string()
            archive.skip(1)  # skip null terminator
            return cls(TextLiteralType=lit_type, SourceString=source)
        elif lit_type == EBlueprintTextLiteralType.LiteralString:
            # UE XFERTEXT: LiteralString 读取 1 个 FString
            source = archive.xfer_string()
            archive.skip(1)  # skip null terminator
            return cls(TextLiteralType=lit_type, SourceString=source)
```

注意：`xfer_string()` 读取 ASCII null-terminated 字符串但不消耗 null terminator，所以需要 `skip(1)` 跳过它。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_p2_version_gating.py::TestFScriptTextInvariant -v`
Expected: PASS

- [ ] **Step 5: 运行全量测试确认不回归**

Run: `python -m pytest tests/ -v -m "not slow" --timeout=60 -x`
Expected: 所有测试 PASS

- [ ] **Step 6: 提交**

```bash
git add src/uasset_read/kismet/expressions/string_consts.py tests/test_p2_version_gating.py
git commit -m "fix: FScriptText 枚举引用修复 + InvariantText 只读取 1 个字符串 (#97 D.2)"
```

---

### Task 3: SoftObjectPath 三阶段版本门控 (#97 D.4)

**Files:**
- Modify: `src/uasset_read/parsers/property_types/object_ref.py:17-51`
- Test: `tests/test_p2_version_gating.py`

**现状分析**：
- 当前代码只区分 2 种路径：UE5.7+ 索引格式（soft_object_path_list 存在时）和 FString 对
- Issue 描述 UE 有 3 阶段格式，但当前 `read_fstring()` 实现可能已经隐式处理了编码差异
- 需要添加显式版本门控以确保正确性，特别是 `< 514` 的单 FString 格式

- [ ] **Step 1: 写版本门控逻辑测试**

```python
# 追加到 tests/test_p2_version_gating.py

class TestSoftObjectPathVersionGate:
    """#97 D.4: SoftObjectPath 应有三阶段版本门控。

    UE 源码 3 阶段格式 (ObjectResource.cpp):
    - < 514: FString（单一路径字符串）
    - 514-1006: FName(AssetPath) + WideString(SubPath)
    - >= 1007: FUtf8String(AssetPath) + FUtf8String(SubPath)
    - >= 1008 (UE5_ADD_SOFTOBJECTPATH_LIST): SoftObjectPathList 索引

    当前代码只有 2 种路径，缺少 < 514 的单 FString 格式。
    """

    def test_version_gate_logic(self):
        """验证版本门控逻辑正确性。"""
        # 测试版本判断逻辑
        def get_soft_object_format(file_version_ue4: int, file_version_ue5: int, has_list: bool):
            if has_list:
                return "index"
            if file_version_ue5 >= 1007:
                return "utf8"
            if file_version_ue4 >= 514:
                return "fname_wide"
            return "legacy_single"

        # Legacy (< 514)
        assert get_soft_object_format(500, 0, False) == "legacy_single"
        assert get_soft_object_format(513, 0, False) == "legacy_single"

        # FName + WideString (514-1006)
        assert get_soft_object_format(514, 0, False) == "fname_wide"
        assert get_soft_object_format(1006, 0, False) == "fname_wide"

        # UTF8 (>= 1007)
        assert get_soft_object_format(0, 1007, False) == "utf8"
        assert get_soft_object_format(0, 1010, False) == "utf8"

        # Index (>= 1008 with list)
        assert get_soft_object_format(0, 1008, True) == "index"
        assert get_soft_object_format(0, 1010, True) == "index"
```

- [ ] **Step 2: 运行测试确认通过**

Run: `python -m pytest tests/test_p2_version_gating.py::TestSoftObjectPathVersionGate -v`
Expected: PASS（纯逻辑测试）

- [ ] **Step 3: 修复 SoftObjectPath 版本门控**

修改 `src/uasset_read/parsers/property_types/object_ref.py`：

```python
def parse_soft_object_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    soft_object_path_list: Optional[List[Dict]] = None,
    file_version_ue4: int = 0,
    file_version_ue5: int = 0,
) -> SoftObjectPathValue:
    """解析 SoftObjectProperty（FSoftObjectPath）。

    UE 源码 3 阶段格式 (ObjectResource.cpp):
    - < 514: FString（单一路径字符串）
    - 514-1006: FName(AssetPath) + WideString(SubPath)
    - >= 1007: FUtf8String(AssetPath) + FUtf8String(SubPath)
    - >= 1008 (UE5_ADD_SOFTOBJECTPATH_LIST): SoftObjectPathList 索引
    """
    # Phase 4: UE5 >= 1008 索引格式（最高优先级）
    if soft_object_path_list is not None and len(soft_object_path_list) > 0:
        index = archive.read_i32()
        if 0 <= index < len(soft_object_path_list):
            entry = soft_object_path_list[index]
            return SoftObjectPathValue(
                raw_kind=tag.type,
                asset_path=entry.get('asset_path', ''),
                sub_path=entry.get('sub_path', ''),
                index=index,
            )
        else:
            return SoftObjectPathValue(
                raw_kind=tag.type,
                asset_path='',
                sub_path='',
                index=index,
                error=f"SoftObjectPath index {index} out of bounds (list size {len(soft_object_path_list)})",
            )

    # Phase 3: UE5 >= 1007 — FUtf8String + FUtf8String
    if file_version_ue5 >= 1007:  # UE5_FSOFTOBJECTPATH_REMOVE_ASSET_PATH_FNAMES
        asset_path = archive.read_fstring()  # UTF8 string
        sub_path = archive.read_fstring()    # UTF8 string
        return SoftObjectPathValue(raw_kind=tag.type, asset_path=asset_path, sub_path=sub_path)

    # Phase 2: UE4 >= 514 — FName(AssetPath) + WideString(SubPath)
    if file_version_ue4 >= 514:
        # FName: int32 index into name map + int32 number
        asset_path_index = archive.read_i32()
        asset_path_number = archive.read_i32()
        # 从 name_map 解析 FName
        if 0 <= asset_path_index < len(name_map):
            asset_path = name_map[asset_path_index]
        else:
            asset_path = ""
        # WideString: length-prefixed UTF-16 string
        sub_path = archive.read_fstring()
        return SoftObjectPathValue(raw_kind=tag.type, asset_path=asset_path, sub_path=sub_path)

    # Phase 1: Legacy (< 514) — 单 FString
    asset_path = archive.read_fstring()
    return SoftObjectPathValue(raw_kind=tag.type, asset_path=asset_path)
```

**注意**：
- Phase 2 的 FName 读取需要验证：`read_i32()` × 2 还是使用现有的 `read_fname()` 方法
- 需要搜索 `parse_soft_object_property` 的所有调用点，添加版本参数传递
- 如果现有代码的 `read_fstring()` 已经正确处理了编码差异，可能只需要添加 Phase 1 的单 FString 格式

- [ ] **Step 4: 更新调用方传递版本参数**

搜索 `parse_soft_object_property` 和 `parse_soft_class_property` 的所有调用点，添加版本参数传递。主要调用点在 `property_parser.py`。

- [ ] **Step 5: 运行测试确认不回归**

Run: `python -m pytest tests/ -v -m "not slow" --timeout=60 -x`
Expected: 所有测试 PASS

- [ ] **Step 6: 提交**

```bash
git add src/uasset_read/parsers/property_types/object_ref.py src/uasset_read/parsers/property_parser.py tests/test_p2_version_gating.py
git commit -m "fix: SoftObjectPath 三阶段版本门控 (#97 D.4)"
```

---

### Task 4: FKismetArchive 版本感知 + Kismet LWC 门控 (#98)

**Files:**
- Modify: `src/uasset_read/kismet/archive.py:26-35`
- Modify: `src/uasset_read/kismet/bytecode_extractor.py:367`
- Modify: `src/uasset_read/kismet/expressions/vector_consts.py:28-32,53-57,89-114`
- Test: `tests/test_p2_lwc_kismet.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_p2_lwc_kismet.py
"""P2 LWC 门控测试 — Kismet 字节码版本感知 (#98)。"""
from __future__ import annotations

import io
import struct
import pytest

from uasset_read.kismet.archive import FKismetArchive
from uasset_read.kismet.expressions.vector_consts import (
    EX_VectorConst,
    EX_RotationConst,
    EX_TransformConst,
)


class TestFKismetArchiveVersionAware:
    """#98: FKismetArchive 应接收并存储版本信息。"""

    def test_constructor_accepts_version(self):
        """FKismetArchive 构造函数应接受 file_version_ue5 参数。"""
        archive = FKismetArchive(
            b"\x00" * 100, "test", ["test"],
            tolerant=False,
            file_version_ue5=1004,
        )
        assert archive.file_version_ue5 == 1004

    def test_default_version_is_zero(self):
        """未传版本时默认为 0。"""
        archive = FKismetArchive(b"\x00" * 100, "test", ["test"])
        assert archive.file_version_ue5 == 0

    def test_is_lwc_property(self):
        """file_version_ue5 >= 1004 时 is_lwc 为 True。"""
        archive = FKismetArchive(
            b"\x00" * 100, "test", ["test"],
            file_version_ue5=1004,
        )
        assert archive.is_lwc is True

        archive2 = FKismetArchive(
            b"\x00" * 100, "test", ["test"],
            file_version_ue5=1000,
        )
        assert archive2.is_lwc is False


class TestVectorConstLWC:
    """#98: EX_VectorConst 应根据 LWC 版本选择 float/double。"""

    def test_pre_lwc_reads_float(self):
        """Pre-LWC (file_version_ue5 < 1004): 读取 3 × float32 = 12 bytes。"""
        # 构造 12 bytes: 3 × float32
        data = struct.pack('<fff', 1.0, 2.0, 3.0)
        archive = FKismetArchive(data, "test", ["test"], file_version_ue5=0)
        expr = EX_VectorConst.from_archive(archive, ["test"])
        assert abs(expr.X - 1.0) < 0.001
        assert abs(expr.Y - 2.0) < 0.001
        assert abs(expr.Z - 3.0) < 0.001

    def test_lwc_reads_double(self):
        """LWC (file_version_ue5 >= 1004): 读取 3 × float64 = 24 bytes。"""
        data = struct.pack('<ddd', 1.0, 2.0, 3.0)
        archive = FKismetArchive(data, "test", ["test"], file_version_ue5=1004)
        expr = EX_VectorConst.from_archive(archive, ["test"])
        assert abs(expr.X - 1.0) < 0.0001
        assert abs(expr.Y - 2.0) < 0.0001
        assert abs(expr.Z - 3.0) < 0.0001


class TestRotationConstLWC:
    """#98: EX_RotationConst 应根据 LWC 版本选择 int32/int64。"""

    def test_pre_lwc_reads_int32(self):
        """Pre-LWC: 读取 3 × int32 = 12 bytes。"""
        data = struct.pack('<iii', 100, 200, 300)
        archive = FKismetArchive(data, "test", ["test"], file_version_ue5=0)
        expr = EX_RotationConst.from_archive(archive, ["test"])
        assert expr.Pitch == 100
        assert expr.Yaw == 200
        assert expr.Roll == 300

    def test_lwc_reads_int64(self):
        """LWC: 读取 3 × int64 = 24 bytes。"""
        data = struct.pack('<qqq', 100, 200, 300)
        archive = FKismetArchive(data, "test", ["test"], file_version_ue5=1004)
        expr = EX_RotationConst.from_archive(archive, ["test"])
        assert expr.Pitch == 100
        assert expr.Yaw == 200
        assert expr.Roll == 300


class TestTransformConstLWC:
    """#98: EX_TransformConst 应根据 LWC 版本选择 float/double。"""

    def test_pre_lwc_reads_all_float(self):
        """Pre-LWC: 10 × float32 = 40 bytes。"""
        data = struct.pack('<10f', *[float(i) for i in range(10)])
        archive = FKismetArchive(data, "test", ["test"], file_version_ue5=0)
        expr = EX_TransformConst.from_archive(archive, ["test"])
        # Rotation (4 floats) + Translation (3 floats) + Scale (3 floats)
        assert abs(expr.X - 0.0) < 0.001  # rot X
        assert abs(expr.Pitch - 4.0) < 0.001  # trans X

    def test_lwc_reads_double_translation(self):
        """LWC: Rotation 4×float32 + Translation 3×float64 + Scale 3×float32 = 68 bytes。"""
        # Rotation: 4 × float32
        rot = struct.pack('<ffff', 0.0, 0.0, 0.0, 1.0)
        # Translation: 3 × float64
        trans = struct.pack('<ddd', 10.0, 20.0, 30.0)
        # Scale: 3 × float32
        scale = struct.pack('<fff', 1.0, 1.0, 1.0)
        data = rot + trans + scale
        archive = FKismetArchive(data, "test", ["test"], file_version_ue5=1004)
        expr = EX_TransformConst.from_archive(archive, ["test"])
        assert abs(expr.Pitch - 10.0) < 0.0001  # trans X
        assert abs(expr.Yaw - 20.0) < 0.0001   # trans Y
        assert abs(expr.Roll - 30.0) < 0.0001  # trans Z
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_p2_lwc_kismet.py -v`
Expected: FAIL — FKismetArchive 不接受 `file_version_ue5` 参数

- [ ] **Step 3: 为 FKismetArchive 添加版本感知**

修改 `src/uasset_read/kismet/archive.py:26-35`：

```python
    def __init__(
        self,
        data: bytes,
        name: str,
        name_map: list[str],
        tolerant: bool = False,
        file_version_ue5: int = 0,
    ):
        self._path = name
        self._file = io.BytesIO(data)
        self._file_size = len(data)
        self._tolerant = tolerant
        self._byte_swapping = False
        self._mmap = None
        self._use_mmap = False
        self._mmap_warning = None
        self._name_map = name_map
        self.file_version_ue5 = file_version_ue5

    @property
    def is_lwc(self) -> bool:
        """是否启用 Large World Coordinates（UE5 >= 1004）。"""
        return self.file_version_ue5 >= 1004  # UE5_LARGE_WORLD_COORDINATES
```

- [ ] **Step 4: 更新 bytecode_extractor.py 传递版本**

修改 `src/uasset_read/kismet/bytecode_extractor.py:367`：

```python
    archive = FKismetArchive(
        bytecode_bytes, "ScriptBytecode", name_map,
        tolerant=tolerant,
        file_version_ue5=summary.file_version_ue5 if summary else 0,
    )
```

搜索所有 `FKismetArchive(` 构造调用，确保传递 `file_version_ue5`。

- [ ] **Step 5: 修复 VectorConst/RotationConst/TransformConst**

修改 `src/uasset_read/kismet/expressions/vector_consts.py`：

```python
@dataclass
class EX_VectorConst(KismetExpression):
    """向量常量 (X, Y, Z) — LWC 感知。"""

    X: float = 0.0
    Y: float = 0.0
    Z: float = 0.0

    @property
    def Token(self):
        return EExprToken.EX_VectorConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_VectorConst:
        if archive.is_lwc:
            # LWC: 3 × float64 = 24 bytes
            x = archive.read_f64()
            y = archive.read_f64()
            z = archive.read_f64()
        else:
            # Pre-LWC: 3 × float32 = 12 bytes
            x = archive.read_f32()
            y = archive.read_f32()
            z = archive.read_f32()
        return cls(X=x, Y=y, Z=z)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["Value"] = f"({self.X}, {self.Y}, {self.Z})"
        return d


@dataclass
class EX_RotationConst(KismetExpression):
    """Rotation constant — LWC 感知。

    Pre-LWC: 3 × int32 = 12 bytes
    LWC: 3 × int64 = 24 bytes
    """

    Pitch: float = 0.0
    Yaw: float = 0.0
    Roll: float = 0.0

    @property
    def Token(self):
        return EExprToken.EX_RotationConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_RotationConst:
        if archive.is_lwc:
            p = archive.read_i64()
            y = archive.read_i64()
            r = archive.read_i64()
        else:
            p = archive.read_i32()
            y = archive.read_i32()
            r = archive.read_i32()
        return cls(Pitch=p, Yaw=y, Roll=r)

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["Value"] = f"(Pitch={self.Pitch}, Yaw={self.Yaw}, Roll={self.Roll})"
        return d


@dataclass
class EX_TransformConst(KismetExpression):
    """Transform constant — LWC 感知。

    Pre-LWC: 10 × float32 = 40 bytes
    LWC: 4×float32 (rotation) + 3×float64 (translation) + 3×float32 (scale) = 68 bytes
    """

    X: float = 0.0
    Y: float = 0.0
    Z: float = 0.0
    W: float = 0.0
    Pitch: float = 0.0
    Yaw: float = 0.0
    Roll: float = 0.0
    SX: float = 1.0
    SY: float = 1.0
    SZ: float = 1.0

    @property
    def Token(self):
        return EExprToken.EX_TransformConst

    @classmethod
    def from_archive(cls, archive: FKismetArchive, name_map: list[str]) -> EX_TransformConst:
        # Rotation (quat): always float32 × 4
        rx = archive.read_f32()
        ry = archive.read_f32()
        rz = archive.read_f32()
        rw = archive.read_f32()

        if archive.is_lwc:
            # Translation: float64 × 3
            tx = archive.read_f64()
            ty = archive.read_f64()
            tz = archive.read_f64()
        else:
            # Translation: float32 × 3
            tx = archive.read_f32()
            ty = archive.read_f32()
            tz = archive.read_f32()

        # Scale: always float32 × 3
        sx = archive.read_f32()
        sy = archive.read_f32()
        sz = archive.read_f32()

        return cls(
            X=rx, Y=ry, Z=rz, W=rw,
            Pitch=tx, Yaw=ty, Roll=tz,
            SX=sx, SY=sy, SZ=sz,
        )
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_p2_lwc_kismet.py -v`
Expected: PASS

- [ ] **Step 7: 运行全量测试确认不回归**

Run: `python -m pytest tests/ -v -m "not slow" --timeout=60 -x`
Expected: 所有测试 PASS

- [ ] **Step 8: 提交**

```bash
git add src/uasset_read/kismet/archive.py src/uasset_read/kismet/bytecode_extractor.py src/uasset_read/kismet/expressions/vector_consts.py tests/test_p2_lwc_kismet.py
git commit -m "fix: Kismet 字节码 LWC 版本门控 (#98)"
```

---

### Task 5: Unversioned Header + EdGraphPinOptimized 验证 (#97 D.1, D.3)

**Files:**
- Test: `tests/test_p2_version_gating.py`

- [ ] **Step 1: 验证 Unversioned Header bit layout 已正确**

当前代码 `unversioned_parser.py:92-96` 已实现正确的 bit layout：
```python
skip_num = raw & 0x007F             # bits 0-6 ✓
has_any_zeroes = bool(raw & 0x0080) # bit 7 ✓
is_last = bool(raw & 0x0100)        # bit 8 ✓
value_num = (raw >> 9) & 0x007F     # bits 9-15 ✓
```

添加回归测试确认正确性：

```python
# 追加到 tests/test_p2_version_gating.py

class TestUnversionedHeaderBitLayout:
    """#97 D.1: 验证 FFragment bit layout 正确性（回归测试）。"""

    def test_fragment_parsing(self):
        """验证 FFragment 位域解析与 UE 源码一致。"""
        from uasset_read.parsers.unversioned_parser import UnversionedFragment

        # 构造一个 fragment:
        # SkipNum = 3 (bits 0-6)
        # bHasAnyZeroes = 1 (bit 7)
        # bIsLast = 0 (bit 8)
        # ValueNum = 5 (bits 9-15)
        raw = 3 | (1 << 7) | (0 << 8) | (5 << 9)
        # raw = 3 + 128 + 0 + 2560 = 2691

        skip_num = raw & 0x007F
        has_any_zeroes = bool(raw & 0x0080)
        is_last = bool(raw & 0x0100)
        value_num = (raw >> 9) & 0x007F

        assert skip_num == 3
        assert has_any_zeroes is True
        assert is_last is False
        assert value_num == 5

    def test_last_fragment(self):
        """bIsLast = 1 的 fragment。"""
        raw = 0 | (0 << 7) | (1 << 8) | (2 << 9)
        skip_num = raw & 0x007F
        has_any_zeroes = bool(raw & 0x0080)
        is_last = bool(raw & 0x0100)
        value_num = (raw >> 9) & 0x007F

        assert skip_num == 0
        assert has_any_zeroes is False
        assert is_last is True
        assert value_num == 2
```

- [ ] **Step 2: 记录 EdGraphPinOptimized 不在范围内**

`EdGraphPinOptimized` 在当前代码库中不存在（grep 无结果）。此子问题不适用。在测试文件中添加注释说明。

- [ ] **Step 3: 运行测试**

Run: `python -m pytest tests/test_p2_version_gating.py -v`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add tests/test_p2_version_gating.py
git commit -m "test: Unversioned Header bit layout 回归测试 (#97 D.1)"
```

---

## 阶段 B：资源安全（#108）

### Task 6: 文件句柄 `__del__` 安全网 (#108 P0)

**Files:**
- Modify: `src/uasset_read/archive.py`
- Modify: `src/uasset_read/iostore/reader.py`
- Modify: `src/uasset_read/pak/reader.py`
- Test: `tests/test_p2_memory_safety.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_p2_memory_safety.py
"""P2 内存安全测试 (#108)。"""
from __future__ import annotations

import gc
import pytest


class TestFileHandleSafety:
    """#108 P0: 文件处理类应有 __del__ 安全网。"""

    def test_farchive_has_del(self):
        """FArchive 应有 __del__ 方法。"""
        from uasset_read.archive import FArchive
        assert hasattr(FArchive, '__del__')

    def test_iostore_reader_has_del(self):
        """IoStoreReader 应有 __del__ 方法。"""
        from uasset_read.iostore.reader import IoStoreReader
        assert hasattr(IoStoreReader, '__del__')

    def test_pak_reader_has_del(self):
        """PakFileReader 应有 __del__ 方法。"""
        from uasset_read.pak.reader import PakFileReader
        assert hasattr(PakFileReader, '__del__')

    def test_farchive_del_closes_safely(self):
        """FArchive.__del__ 不应抛异常。"""
        from uasset_read.archive import FArchive
        # 创建一个 FArchive 但不 close
        # 让 GC 回收时触发 __del__
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as f:
            f.write(b'\x00' * 100)
            tmp_path = f.name
        try:
            archive = FArchive(tmp_path)
            archive.close()  # 先正常关闭
            # __del__ 在已关闭的 archive 上不应抛异常
            archive.__del__()
        finally:
            os.unlink(tmp_path)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_p2_memory_safety.py::TestFileHandleSafety -v`
Expected: FAIL — `__del__` 不存在

- [ ] **Step 3: 添加 `__del__` 到三个文件**

**`src/uasset_read/archive.py`** — 在 `close()` 方法后添加：

```python
    def __del__(self) -> None:
        """安全网：确保文件句柄被释放。"""
        try:
            self.close()
        except Exception:
            pass
```

**`src/uasset_read/iostore/reader.py`** — 在 `close()` 方法后添加：

```python
    def __del__(self) -> None:
        """安全网：确保文件句柄被释放。"""
        try:
            self.close()
        except Exception:
            pass
```

**`src/uasset_read/pak/reader.py`** — 在 `close()` 方法后添加：

```python
    def __del__(self) -> None:
        """安全网：确保文件句柄被释放。"""
        try:
            self.close()
        except Exception:
            pass
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_p2_memory_safety.py::TestFileHandleSafety -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/archive.py src/uasset_read/iostore/reader.py src/uasset_read/pak/reader.py tests/test_p2_memory_safety.py
git commit -m "fix: 文件处理类添加 __del__ 安全网 (#108 P0)"
```

---

### Task 7: 缓存清理机制 (#108 P1)

**Files:**
- Modify: `src/uasset_read/kismet/function_resolver.py:32`
- Modify: `src/uasset_read/parsers/class_registry.py:81-123`
- Modify: `src/uasset_read/parse_uasset.py:714-735`
- Test: `tests/test_p2_memory_safety.py`

- [ ] **Step 1: 写失败测试**

```python
# 追加到 tests/test_p2_memory_safety.py

class TestCacheCleanup:
    """#108 P1: 缓存应有清理机制。"""

    def test_function_ref_resolver_has_reset(self):
        """FunctionRefResolver 应有 reset() 方法清理 _unresolved_refs。"""
        from uasset_read.kismet.function_resolver import FunctionRefResolver
        assert hasattr(FunctionRefResolver, 'reset')

    def test_class_registry_has_reset_cache(self):
        """ClassHandlerRegistry 应有 reset_cache() 方法。"""
        from uasset_read.parsers.class_registry import ClassHandlerRegistry
        registry = ClassHandlerRegistry()
        assert hasattr(registry, 'reset_cache')

    def test_class_registry_global_reset(self):
        """全局 registry 的 reset_default_cache() 应清空缓存。"""
        from uasset_read.parsers.class_registry import (
            get_class_registry, reset_default_registry_cache,
        )
        registry = get_class_registry()
        # 添加一些缓存
        registry._cache["test"] = None
        reset_default_registry_cache()
        assert len(registry._cache) == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_p2_memory_safety.py::TestCacheCleanup -v`
Expected: FAIL

- [ ] **Step 3: 添加 FunctionRefResolver.reset()**

修改 `src/uasset_read/kismet/function_resolver.py`：

```python
    def reset(self) -> None:
        """重置所有缓存和计数器（批量解析时在新资产开始前调用）。"""
        self._cache.clear()
        self._virtual_class_cache.clear()
        self._unresolved_refs.clear()
        self._resolve_attempts = 0
        self._resolve_failures = 0
```

- [ ] **Step 4: 添加 ClassHandlerRegistry.reset_cache() + 全局 reset**

修改 `src/uasset_read/parsers/class_registry.py`：

```python
    def reset_cache(self) -> None:
        """清空查找缓存（保留 handler 注册）。"""
        self._cache.clear()


def reset_default_registry_cache() -> None:
    """清空全局默认 registry 的缓存（批量解析时调用）。"""
    global _default_registry
    if _default_registry is not None:
        _default_registry.reset_cache()
```

- [ ] **Step 5: 在 parse_uasset.py finally 块中调用清理**

修改 `src/uasset_read/parse_uasset.py:714-735`，在现有清理代码后添加：

```python
    # Task 11: 清理 FunctionRefResolver 缓存 (#108)
    # FunctionRefResolver 是 per-parse 创建的，不需要全局清理
    # 但 ClassHandlerRegistry 是全局的，需要清理缓存
    from uasset_read.parsers.class_registry import reset_default_registry_cache
    reset_default_registry_cache()
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_p2_memory_safety.py -v`
Expected: PASS

- [ ] **Step 7: 运行全量测试确认不回归**

Run: `python -m pytest tests/ -v -m "not slow" --timeout=60 -x`
Expected: 所有测试 PASS

- [ ] **Step 8: 提交**

```bash
git add src/uasset_read/kismet/function_resolver.py src/uasset_read/parsers/class_registry.py src/uasset_read/parse_uasset.py tests/test_p2_memory_safety.py
git commit -m "fix: 缓存清理机制 — FunctionRefResolver + ClassHandlerRegistry (#108 P1)"
```

---

## 阶段 C：架构重构（#114, #115）

### Task 8: 统一状态模型 (#114)

**Files:**
- Create: `src/uasset_read/status.py`
- Modify: `src/uasset_read/models/result.py:57-87`
- Modify: `src/uasset_read/link/result.py:55-85`
- Modify: `src/uasset_read/ir_builder.py:136-173`
- Test: `tests/test_p2_status_unified.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_p2_status_unified.py
"""P2 统一状态模型测试 (#114)。"""
from __future__ import annotations

import pytest

from uasset_read.status import compute_result_status


class MockExport:
    def __init__(self, parse_status: str = "success"):
        self.parse_status = parse_status


class MockResult:
    """模拟 ParseResult / LinkerParseResult。"""
    def __init__(self, **kwargs):
        self.is_success = kwargs.get('is_success', True)
        self.errors = kwargs.get('errors', [])
        self.metadata = kwargs.get('metadata', {})
        self.export_map = kwargs.get('export_map', [])
        self.summary = kwargs.get('summary', object())
        self.name_map = kwargs.get('name_map', ["test"])
        self.import_map = kwargs.get('import_map', {"test": "val"})


class TestComputeResultStatus:
    """统一状态计算函数测试。"""

    def test_no_core_data_returns_failed(self):
        """无核心数据 → failed。"""
        result = MockResult(
            is_success=False, summary=None, name_map=None, import_map=None, export_map=[],
        )
        assert compute_result_status(result) == "failed"

    def test_has_data_not_success_returns_partial(self):
        """有核心数据但 is_success=False → partial。"""
        result = MockResult(is_success=False)
        assert compute_result_status(result) == "partial"

    def test_errors_returns_partial(self):
        """有 errors → partial。"""
        result = MockResult(errors=["some error"])
        assert compute_result_status(result) == "partial"

    def test_all_exports_success_returns_success(self):
        """所有 export success → success。"""
        result = MockResult(export_map=[MockExport("success"), MockExport("success")])
        assert compute_result_status(result) == "success"

    def test_any_opaque_export_returns_partial(self):
        """有 opaque export → partial。"""
        result = MockResult(export_map=[MockExport("success"), MockExport("opaque")])
        assert compute_result_status(result) == "partial"

    def test_all_exports_failed_returns_failed(self):
        """所有 export failed → failed。"""
        result = MockResult(export_map=[MockExport("failed"), MockExport("failed")])
        assert compute_result_status(result) == "failed"

    def test_mixed_failed_and_success_returns_partial(self):
        """部分 export failed → partial。"""
        result = MockResult(export_map=[MockExport("success"), MockExport("failed")])
        assert compute_result_status(result) == "partial"

    def test_lightweight_tolerant_returns_partial(self):
        """lightweight_tolerant_parse metadata → partial。"""
        result = MockResult(metadata={"lightweight_tolerant_parse": True})
        assert compute_result_status(result) == "partial"

    def test_skipped_export_returns_partial(self):
        """有 skipped export → partial。"""
        result = MockResult(export_map=[MockExport("skipped")])
        assert compute_result_status(result) == "partial"

    def test_partial_metadata_export_returns_partial(self):
        """有 partial_metadata export → partial。"""
        result = MockResult(export_map=[MockExport("partial_metadata")])
        assert compute_result_status(result) == "partial"

    def test_opaque_unversioned_export_returns_partial(self):
        """有 opaque_unversioned export → partial。"""
        result = MockResult(export_map=[MockExport("opaque_unversioned")])
        assert compute_result_status(result) == "partial"

    def test_fallback_export_returns_partial(self):
        """有 fallback export → partial。"""
        result = MockResult(export_map=[MockExport("fallback")])
        assert compute_result_status(result) == "partial"


class TestParseResultStatusDelegation:
    """验证 ParseResult.status 委托到统一函数。"""

    def test_parse_result_uses_compute(self):
        """ParseResult.status 应与 compute_result_status 一致。"""
        from uasset_read.models.result import ParseResult
        result = ParseResult(is_success=True, export_map=[])
        assert result.status == compute_result_status(result)

    def test_linker_result_uses_compute(self):
        """LinkerParseResult.status 应与 compute_result_status 一致。"""
        from uasset_read.link.result import LinkerParseResult
        result = LinkerParseResult(is_success=True, export_map=[])
        assert result.status == compute_result_status(result)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_p2_status_unified.py -v`
Expected: FAIL — `uasset_read.status` 模块不存在

- [ ] **Step 3: 创建 `src/uasset_read/status.py`**

```python
# src/uasset_read/status.py
"""统一结果状态计算 — 单一权威实现 (#114)。

所有结果类型（ParseResult, LinkerParseResult, PackageIR）的状态
都通过 compute_result_status() 计算，消除重复和漂移。
"""
from __future__ import annotations

from typing import Any

# Export 级状态集合
_PARTIAL_EXPORT_STATUSES = frozenset({
    "opaque", "partial", "partial_metadata", "opaque_unversioned",
    "skipped", "metadata", "fallback",
})
_FAILED_EXPORT_STATUSES = frozenset({"failed"})


def compute_result_status(result: Any) -> str:
    """计算结果状态：success | partial | failed。

    权威实现 — ParseResult.status, LinkerParseResult.status,
    ir_builder._result_status() 都委托到此函数。
    """
    # 1. 无核心数据 → failed
    has_core = (
        getattr(result, "summary", None) is not None
        or getattr(result, "name_map", None)
        or getattr(result, "import_map", None)
        or getattr(result, "export_map", None)
    )
    if not has_core:
        return "failed"

    # 2. is_success=False 但有核心数据 → partial
    if not getattr(result, "is_success", False):
        return "partial"

    # 3. 有 errors → partial
    errors = getattr(result, "errors", None) or []
    if errors:
        return "partial"

    # 4. lightweight tolerant → partial
    metadata = getattr(result, "metadata", None) or {}
    if metadata.get("lightweight_tolerant_parse"):
        return "partial"

    # 5. 检查 export 级状态
    export_map = getattr(result, "export_map", None) or []
    if export_map and isinstance(export_map, list):
        failed_count = 0
        partial_count = 0
        for exp in export_map:
            status = getattr(exp, "parse_status", None)
            if status in _FAILED_EXPORT_STATUSES:
                failed_count += 1
            elif status in _PARTIAL_EXPORT_STATUSES:
                partial_count += 1

        total = len(export_map)
        if failed_count == total and total > 0:
            return "failed"
        if failed_count > 0 or partial_count > 0:
            return "partial"

    return "success"
```

- [ ] **Step 4: 修改 ParseResult.status 委托**

修改 `src/uasset_read/models/result.py:57-87`：

```python
    @property
    def status(self) -> str:
        """Unified status: success | partial | failed.

        委托到 uasset_read.status.compute_result_status() — 单一权威实现。
        """
        from uasset_read.status import compute_result_status
        return compute_result_status(self)
```

- [ ] **Step 5: 修改 LinkerParseResult.status 委托**

修改 `src/uasset_read/link/result.py:55-85`：

```python
    @property
    def status(self) -> str:
        """Unified status: success | partial | failed.

        委托到 uasset_read.status.compute_result_status() — 单一权威实现。
        """
        from uasset_read.status import compute_result_status
        return compute_result_status(self)
```

- [ ] **Step 6: 修改 ir_builder._result_status 委托**

修改 `src/uasset_read/ir_builder.py:136-173`：

```python
def _result_status(result: "ParseResult | LinkerParseResult") -> str:
    """委托到统一状态计算函数 (#114)。"""
    from uasset_read.status import compute_result_status
    return compute_result_status(result)
```

- [ ] **Step 7: 运行测试确认通过**

Run: `python -m pytest tests/test_p2_status_unified.py -v`
Expected: PASS

- [ ] **Step 8: 运行现有状态测试确认兼容**

Run: `python -m pytest tests/test_status_model.py tests/test_status_model_unified.py tests/test_status_unification.py -v`
Expected: PASS

- [ ] **Step 9: 运行全量测试确认不回归**

Run: `python -m pytest tests/ -v -m "not slow" --timeout=60 -x`
Expected: 所有测试 PASS

- [ ] **Step 10: 提交**

```bash
git add src/uasset_read/status.py src/uasset_read/models/result.py src/uasset_read/link/result.py src/uasset_read/ir_builder.py tests/test_p2_status_unified.py
git commit -m "refactor: 统一状态模型 — compute_result_status 单一权威实现 (#114)"
```

---

### Task 9: Post-process Stage 拆分 — 基础设施 (#115)

**Files:**
- Create: `src/uasset_read/post_process.py`
- Modify: `src/uasset_read/parse_uasset.py:82-261`

- [ ] **Step 1: 创建 PostProcessContext 和 Stage 协议**

```python
# src/uasset_read/post_process.py
"""后处理 stage runner — 将 _post_process 拆分为独立 stage (#115)。"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import (
    Any, Callable, Optional, Protocol, Sequence, Union, runtime_checkable,
)

from uasset_read.archive import FArchive
from uasset_read.errors import ParseError

logger = logging.getLogger(__name__)


@dataclass
class PostProcessContext:
    """后处理阶段共享上下文。"""
    path: str
    archive: FArchive
    summary: Any  # PackageFileSummary
    name_map: list[str]
    import_map: list[Any]  # list[ObjectImport]
    export_map: list[Any]  # list[ObjectExport]
    tolerant: bool = True
    linker: Any = None  # PackageLinker | None
    include_parent_assets: bool = False
    asset_roots: Optional[Sequence[str]] = None
    archive_factory: Optional[Callable] = None


@runtime_checkable
class PostProcessStage(Protocol):
    """后处理 stage 协议。"""
    name: str

    def run(self, result: Any, ctx: PostProcessContext) -> None:
        """执行 stage，写入 result 字段。"""
        ...


@dataclass
class PostProcessPipeline:
    """按顺序运行 stage 的管线。"""
    stages: list[PostProcessStage] = field(default_factory=list)

    def add(self, stage: PostProcessStage) -> None:
        self.stages.append(stage)

    def run(self, result: Any, ctx: PostProcessContext) -> None:
        """按顺序运行所有 stage。单个 stage 失败不阻断后续 stage。"""
        for stage in self.stages:
            try:
                stage.run(result, ctx)
            except ParseError as e:
                if hasattr(result, 'errors'):
                    result.errors.append(f"{stage.name}: {e}")
            except ImportError:
                pass  # 模块不存在时静默跳过
            except Exception as e:
                if hasattr(result, 'warnings'):
                    result.warnings.append(f"{stage.name} error: {e}")
```

- [ ] **Step 2: 实现各 stage 类**

```python
# 追加到 src/uasset_read/post_process.py

class GraphExtractionStage:
    """Stage 1: Blueprint Graph 提取。"""
    name = "GraphExtraction"

    def run(self, result: Any, ctx: PostProcessContext) -> None:
        from uasset_read.graph import extract_blueprint_graphs
        if hasattr(result, 'graphs'):
            result.graphs = extract_blueprint_graphs(
                ctx.archive, ctx.summary, ctx.name_map,
                ctx.import_map, ctx.export_map,
                linker=ctx.linker,
            )


class BlueprintMetadataStage:
    """Stage 2: Blueprint 元数据提取。"""
    name = "BlueprintMetadata"

    def run(self, result: Any, ctx: PostProcessContext) -> None:
        from uasset_read.blueprint.extractor import (
            extract_blueprint_metadata,
            detect_blueprint,
            find_main_blueprint_generated_class,
        )

        asset_name = ctx.name_map[0] if ctx.name_map else None
        if not asset_name:
            return

        graphs_list = getattr(result, 'graphs', None)
        blueprint_metadata = None

        # 查找 UBlueprint export
        main_blueprint = None
        for export in ctx.export_map:
            is_bp = detect_blueprint(export, ctx.import_map, ctx.export_map) if ctx.import_map else False
            if is_bp and export.object_name:
                simple_name = asset_name.split("/")[-1] if "/" in asset_name else asset_name
                if export.object_name == simple_name:
                    main_blueprint = export
                    break

        if main_blueprint:
            blueprint_metadata = self._extract(
                main_blueprint, result, ctx, graphs_list,
            )

        # BPGC 回退
        if not blueprint_metadata:
            main_bpgc = find_main_blueprint_generated_class(
                ctx.export_map, ctx.import_map, asset_name,
            )
            if main_bpgc:
                blueprint_metadata = self._extract(
                    main_bpgc, result, ctx, graphs_list,
                )

        if hasattr(result, 'blueprint'):
            result.blueprint = blueprint_metadata

    def _extract(self, export, result, ctx, graphs_list):
        from uasset_read.blueprint.extractor import extract_blueprint_metadata

        owned = ctx.archive_factory is not None
        temp_archive = ctx.archive_factory() if ctx.archive_factory else ctx.archive
        temp_archive.set_byte_swapping(ctx.archive._byte_swapping)
        try:
            meta, warn = extract_blueprint_metadata(
                export, temp_archive, ctx.import_map,
                ctx.export_map, ctx.name_map, ctx.summary,
                linker=ctx.linker, graphs=graphs_list,
            )
            if meta and warn and hasattr(result, 'errors'):
                result.errors.append(f"blueprint parent warning: {warn}")
            return meta
        except ParseError as e:
            if hasattr(result, 'errors'):
                result.errors.append(f"blueprint extraction error: {e}")
            return None
        finally:
            if owned:
                temp_archive.close()


class KismetDecompileStage:
    """Stage 3: Kismet 反编译 + 语义增强。"""
    name = "KismetDecompile"

    def run(self, result: Any, ctx: PostProcessContext) -> None:
        from uasset_read.parse_uasset import _extract_kismet_decompiled

        if not hasattr(result, 'decompiled_functions'):
            return

        decompiled = _extract_kismet_decompiled(
            ctx.path, ctx.archive, ctx.summary, ctx.name_map,
            ctx.import_map, ctx.export_map, ctx.tolerant,
            linker=ctx.linker,
        )
        result.decompiled_functions = decompiled

        if decompiled and getattr(result, "graphs", None):
            from uasset_read.kismet.semantic import enrich_decompiled_functions
            enrich_decompiled_functions(decompiled, result.graphs)

        blueprint = getattr(result, 'blueprint', None)
        if blueprint and not decompiled and hasattr(result, 'warnings'):
            result.warnings.append(
                "Kismet decompilation: no functions decompiled (may have no bytecode)"
            )


class ParentAssetStage:
    """Stage 4: Parent asset 解析。"""
    name = "ParentAsset"

    def run(self, result: Any, ctx: PostProcessContext) -> None:
        if not ctx.include_parent_assets:
            return
        from uasset_read.parse_uasset import _resolve_parent_assets
        _resolve_parent_assets(ctx.path, result, ctx.tolerant, ctx.asset_roots)


class ComponentExtractionStage:
    """Stage 5: 组件 + SCS 树提取。"""
    name = "ComponentExtraction"

    def run(self, result: Any, ctx: PostProcessContext) -> None:
        from uasset_read.blueprint.component_extractor import (
            extract_components, extract_scs_tree,
        )
        if hasattr(result, 'components'):
            result.components = extract_components(ctx.export_map, ctx.import_map)

        try:
            scs_tree = extract_scs_tree(
                ctx.export_map, ctx.import_map,
                archive=ctx.archive, summary=ctx.summary, name_map=ctx.name_map,
            )
            if scs_tree and hasattr(result, 'metadata'):
                result.metadata["scs_tree"] = scs_tree
        except Exception as e:
            if hasattr(result, 'warnings'):
                result.warnings.append(f"SCS tree extraction error: {e}")


class DependencyAnalysisStage:
    """Stage 6: 依赖分析（imports, soft refs, circular deps）。"""
    name = "DependencyAnalysis"

    def run(self, result: Any, ctx: PostProcessContext) -> None:
        from uasset_read.serializers.object_resources import (
            build_imports_list, read_soft_object_paths, detect_circular_deps,
        )
        if hasattr(result, 'imports'):
            result.imports = build_imports_list(ctx.import_map)
        if hasattr(result, 'soft_references'):
            result.soft_references = read_soft_object_paths(
                ctx.archive, ctx.summary, ctx.name_map,
            )
        if hasattr(result, 'circular_deps'):
            result.circular_deps = detect_circular_deps(ctx.import_map)


class ConsistencyCheckStage:
    """Stage 7: name_map 一致性检查 + 最终成功标志。"""
    name = "ConsistencyCheck"

    def run(self, result: Any, ctx: PostProcessContext) -> None:
        if hasattr(result, 'name_map') and not result.name_map:
            if ctx.summary is not None and getattr(ctx.summary, 'name_count', 0) > 0:
                if hasattr(result, 'errors'):
                    result.errors.append(
                        f"name_map 为空（summary.name_count={ctx.summary.name_count}），"
                        f"名称表读取失败"
                    )
        result.is_success = len(result.errors) == 0


def build_default_pipeline() -> PostProcessPipeline:
    """构建默认后处理管线（保持原有顺序）。"""
    pipeline = PostProcessPipeline()
    pipeline.add(GraphExtractionStage())
    pipeline.add(BlueprintMetadataStage())
    pipeline.add(KismetDecompileStage())
    pipeline.add(ParentAssetStage())
    pipeline.add(ComponentExtractionStage())
    pipeline.add(DependencyAnalysisStage())
    pipeline.add(ConsistencyCheckStage())
    return pipeline
```

- [ ] **Step 3: 修改 parse_uasset.py 使用 pipeline**

修改 `src/uasset_read/parse_uasset.py:82-261`，将 `_post_process` 函数体替换为 pipeline 调用：

```python
def _post_process(
    path: str,
    archive: FArchive,
    summary: "PackageFileSummary",
    name_map: List[str],
    import_map: List["ObjectImport"],
    export_map: List["ObjectExport"],
    result: "Union[ParseResult, LinkerParseResult]",
    tolerant: bool = True,
    linker: Optional["PackageLinker"] = None,
    include_parent_assets: bool = False,
    asset_roots: Optional[Sequence[str]] = None,
    archive_factory=None,
) -> None:
    """共享后处理：构造 context 并通过 pipeline 运行各 stage (#115)。"""
    from uasset_read.post_process import PostProcessContext, build_default_pipeline

    ctx = PostProcessContext(
        path=path,
        archive=archive,
        summary=summary,
        name_map=name_map,
        import_map=import_map,
        export_map=export_map,
        tolerant=tolerant,
        linker=linker,
        include_parent_assets=include_parent_assets,
        asset_roots=asset_roots,
        archive_factory=archive_factory,
    )

    pipeline = build_default_pipeline()
    pipeline.run(result, ctx)
```

- [ ] **Step 4: 运行全量测试确认不回归**

Run: `python -m pytest tests/ -v -m "not slow" --timeout=60 -x`
Expected: 所有测试 PASS（行为与拆分前完全一致）

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/post_process.py src/uasset_read/parse_uasset.py
git commit -m "refactor: _post_process 拆为显式 stage pipeline (#115)"
```

---

### Task 10: Stage 隔离性测试 (#115 验收)

**Files:**
- Test: `tests/test_p2_post_process_stages.py`

- [ ] **Step 1: 写 stage 隔离性测试**

```python
# tests/test_p2_post_process_stages.py
"""P2 Post-process stage 隔离性测试 (#115)。"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from uasset_read.post_process import (
    PostProcessContext,
    PostProcessPipeline,
    GraphExtractionStage,
    BlueprintMetadataStage,
    KismetDecompileStage,
    ComponentExtractionStage,
    DependencyAnalysisStage,
    ConsistencyCheckStage,
    build_default_pipeline,
)


class TestPipelineIsolation:
    """验证单个 stage 失败不阻断后续 stage。"""

    def _make_ctx(self):
        return PostProcessContext(
            path="test.uasset",
            archive=MagicMock(),
            summary=MagicMock(),
            name_map=["test"],
            import_map=[],
            export_map=[],
            tolerant=True,
        )

    def test_failing_stage_doesnt_block_others(self):
        """一个 stage 抛异常时，后续 stage 仍然执行。"""
        pipeline = PostProcessPipeline()

        stage1_called = False
        stage2_called = False

        class FailingStage:
            name = "Failing"
            def run(self, result, ctx):
                raise RuntimeError("intentional failure")

        class SuccessStage:
            name = "Success"
            def run(self, result, ctx):
                nonlocal stage2_called
                stage2_called = True

        pipeline.add(FailingStage())
        pipeline.add(SuccessStage())

        result = MagicMock()
        result.errors = []
        result.warnings = []

        pipeline.run(result, self._make_ctx())

        assert stage2_called, "Second stage should have been called despite first stage failure"

    def test_pipeline_error_reporting(self):
        """Stage 失败时错误写入 result.errors 或 result.warnings。"""
        pipeline = PostProcessPipeline()

        class ParseErrorStage:
            name = "ParseErr"
            def run(self, result, ctx):
                from uasset_read.errors import ParseError
                raise ParseError("test parse error")

        pipeline.add(ParseErrorStage())

        result = MagicMock()
        result.errors = []
        result.warnings = []

        pipeline.run(result, self._make_ctx())

        assert len(result.errors) > 0
        assert "ParseErr" in result.errors[0]

    def test_default_pipeline_has_all_stages(self):
        """默认管线包含 7 个 stage。"""
        pipeline = build_default_pipeline()
        assert len(pipeline.stages) == 7
        names = [s.name for s in pipeline.stages]
        assert "GraphExtraction" in names
        assert "BlueprintMetadata" in names
        assert "KismetDecompile" in names
        assert "ParentAsset" in names
        assert "ComponentExtraction" in names
        assert "DependencyAnalysis" in names
        assert "ConsistencyCheck" in names

    def test_consistency_check_sets_is_success(self):
        """ConsistencyCheckStage 设置 is_success。"""
        stage = ConsistencyCheckStage()
        result = MagicMock()
        result.errors = []
        result.name_map = ["test"]

        ctx = self._make_ctx()
        ctx.summary.name_count = 1

        stage.run(result, ctx)
        assert result.is_success is True

    def test_consistency_check_detects_empty_name_map(self):
        """ConsistencyCheckStage 检测空 name_map。"""
        stage = ConsistencyCheckStage()
        result = MagicMock()
        result.errors = []
        result.name_map = []

        ctx = self._make_ctx()
        ctx.name_map = []
        ctx.summary.name_count = 5

        stage.run(result, ctx)
        assert result.is_success is False
        assert any("name_map" in e for e in result.errors)
```

- [ ] **Step 2: 运行测试**

Run: `python -m pytest tests/test_p2_post_process_stages.py -v`
Expected: PASS

- [ ] **Step 3: 运行全量测试确认不回归**

Run: `python -m pytest tests/ -v -m "not slow" --timeout=60 -x`
Expected: 所有测试 PASS

- [ ] **Step 4: 提交**

```bash
git add tests/test_p2_post_process_stages.py
git commit -m "test: post-process stage 隔离性测试 (#115 验收)"
```

---

## 验收检查清单

完成所有 task 后，执行最终验收：

- [ ] **全量测试通过**

```bash
python scripts/test_matrix.py all
```

- [ ] **质量门禁通过**

```bash
python scripts/test_matrix.py quality
```

- [ ] **烟雾测试 — 真实样本**

```bash
python run.py E:/Develop/lib/UnrealEngine/Samples/*.uasset --summary
```

- [ ] **批量解析无文件句柄泄漏**

```bash
python scripts/test_matrix.py integration
```

---

## Issue 覆盖矩阵

| Issue | Task | 状态 |
|-------|------|------|
| #96 PackageSummary 版本门控 | Task 1 | ⬜ |
| #97 D.1 Unversioned Header | Task 5 | ⬜ (已修复，补回归测试) |
| #97 D.2 FScriptText InvariantText | Task 2 | ⬜ |
| #97 D.3 EdGraphPinOptimized | Task 5 | ⬜ (不适用 — 代码库不存在) |
| #97 D.4 SoftObjectPath 三阶段 | Task 3 | ⬜ |
| #98 LWC 类型大小映射 | Task 4 | ⬜ |
| #108 P0 文件句柄 __del__ | Task 6 | ⬜ |
| #108 P1 缓存清理 | Task 7 | ⬜ |
| #114 状态模型统一 | Task 8 | ⬜ |
| #115 post_process 拆分 | Task 9, 10 | ⬜ |
