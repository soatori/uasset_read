---
phase: 62
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/uasset_read/kismet/archive.py
  - src/uasset_read/kismet/bytecode_extractor.py
  - src/uasset_read/kismet/__init__.py
autonomous: true
requirements:
  - BYTECODE-01
  - BYTECODE-02
  - BYTECODE-03
must_haves:
  truths:
    - "FKismetArchive 支持容错模式构造参数（D-05）"
    - "能从 UFunction/K2Node_FunctionEntry 等 UStruct 导出中提取原始字节码字节"
    - "字节码字节流能被解析为 KismetExpression 列表"
    - "容错模式下遇到未知 token 不崩溃，继续解析"
  artifacts:
    - path: "src/uasset_read/kismet/archive.py"
      provides: "FKismetArchive 容错模式支持"
      contains: "def __init__(self, data, name, name_map, tolerant=False)"
    - path: "src/uasset_read/kismet/bytecode_extractor.py"
      provides: "字节码提取和解析入口"
      exports:
        - "extract_bytecode_bytes"
        - "parse_bytecode_stream"
        - "extract_and_parse"
    - path: "src/uasset_read/kismet/__init__.py"
      provides: "模块导出更新"
      contains: "bytecode_extractor 导出"
  key_links:
    - from: "src/uasset_read/kismet/bytecode_extractor.py"
      to: "src/uasset_read/kismet/archive.py"
      via: "FKismetArchive 构造和 read_expression"
      pattern: "FKismetArchive\\("
    - from: "src/uasset_read/kismet/bytecode_extractor.py"
      to: "src/uasset_read/serializers/object_resources.py"
      via: "ObjectExport, resolve_class_name 定位 UStruct 导出"
      pattern: "resolve_class_name|ObjectExport"
---

<objective>
实现 ScriptBytecode 字节流的提取和解析入口。增强 FKismetArchive 支持容错模式（D-05），新增 bytecode_extractor 模块提供从 UStruct 导出中提取字节码并解析为 KismetExpression 列表的完整链路。

Purpose: 填补 Phase 61 表达式系统与 Phase 63 AST 翻译之间的关键缺口——"如何从 .uasset 中拿到字节码字节并转为表达式树"。
Output: bytecode_extractor 模块（extract_bytecode_bytes + parse_bytecode_stream + extract_and_parse），FKismetArchive 容错模式增强，模块导出更新。
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/phase-62/62-CONTEXT.md
@.planning/phases/phase-62/62-DISCUSSION-LOG.md
@.planning/phases/phase-62/RESEARCH.md

# CUE4Parse 参考
@E:\Develop\lib\CUE4Parse\CUE4Parse\UE4\Objects\UObject\UStruct.cs

# Phase 61 已实现代码
@src/uasset_read/kismet/archive.py
@src/uasset_read/kismet/__init__.py
@src/uasset_read/kismet/tokens.py
@src/uasset_read/kismet/expressions/__init__.py
@src/uasset_read/kismet/property_pointer.py

# 序列化基础设施（字节码提取依赖）
@src/uasset_read/serializers/object_resources.py
@src/uasset_read/serializers/package_summary.py
@src/uasset_read/archive.py
@src/uasset_read/parsers/property_parser.py
@src/uasset_read/exceptions.py

# 已有导出识别逻辑
@src/uasset_read/blueprint/core.py
</context>

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->

From src/uasset_read/kismet/archive.py:
```python
class FKismetArchive(FArchive):
    def __init__(self, data: bytes, name: str, name_map: list[str]):
        # 当前 _tolerant 硬编码为 False — Task 1 需改为构造参数
        ...
    def read_expression(self) -> KismetExpression:
        # 当前：未知 token 抛 ParseError — Task 1 需在 tolerant=True 时跳过
        ...
    def read_expression_array(self, end_token: EExprToken) -> list[KismetExpression]:
        ...
    def skip(self, n: int) -> None:
        ...
    def remaining(self) -> int:
        ...
```

From src/uasset_read/serializers/object_resources.py:
```python
@dataclass
class ObjectExport:
    class_index: PackageIndex    # 用于识别 UStruct/UFunction
    super_index: PackageIndex
    outer_index: PackageIndex
    object_name: str
    serial_size: int
    serial_offset: int
    script_serial_size: int = 0  # 脚本数据区大小
    script_serial_offset: int = 0  # 脚本数据区偏移（相对于 serial_offset）
    properties: List[Any] = field(default_factory=list)
```

From src/uasset_read/archive.py:
```python
class FArchive:
    def __init__(self, path: str, tolerant: bool = False):
        ...
    def tell(self) -> int:
        ...
    def seek(self, pos: int) -> None:
        ...
    def read_i32(self) -> int:
        ...
    def read_bytes(self, n: int) -> bytes:
        ...
    def skip(self, n: int) -> None:
        ...
```

From src/uasset_read/serializers/object_resources.py:
```python
def resolve_class_name(
    class_index: PackageIndex,
    import_map: List[ObjectImport],
    export_map: List[ObjectExport]
) -> Optional[str]:
    """从 PackageIndex 解析类名。"""
    ...
```

From src/uasset_read/exceptions.py:
```python
class ParseError(Exception):
    """解析错误。"""
    ...
```

From src/uasset_read/kismet/expressions/base.py:
```python
class KismetExpression(ABC):
    @property
    def Token(self) -> EExprToken: ...
    @property
    def StatementIndex(self) -> int: ...
    @StatementIndex.setter
    def StatementIndex(self, value: int): ...
    def to_dict(self) -> dict: ...
```

From src/uasset_read/kismet/tokens.py:
```python
class EExprToken(enum.IntEnum):
    EX_EndOfScript = 0x53
    # ... 所有 token 0x00-0xFF
```
</interfaces>

<tasks>

<task type="auto">
  <name>Wave 0: 创建测试脚手架</name>
  <files>tests/test_kismet.py</files>
  <action>
创建 tests/test_kismet.py 文件，包含所有后续任务所需的测试函数骨架：

```python
import pytest

# Task 1: FKismetArchive tolerant mode
def test_fkismet_archive_tolerant_mode():
    """Test FKismetArchive tolerant parameter and unknown token handling."""
    pass

# Task 2: bytecode extractor
def test_bytecode_extractor():
    """Test extract_bytecode_bytes and parse_bytecode_stream."""
    pass

# Task 4: output formats
def test_expression_output_formats():
    """Test expressions_to_flat_list and expressions_to_tree."""
    pass

# Task 5: integration tests
def test_extract_bytecode_from_uasset():
    """End-to-end: extract bytecode from real .uasset file."""
    pass

def test_parse_bytecode_to_expressions():
    """End-to-end: parse bytecode to expression list."""
    pass

def test_tolerant_mode_vs_strict_mode():
    """Compare tolerant vs strict mode on malformed bytecode."""
    pass
```

所有测试暂时标记为 `@pytest.mark.skip(reason="Not implemented yet")`。
  </action>
  <verify>
    <automated>python -m pytest tests/test_kismet.py --collect-only</automated>
  </verify>
  <done>tests/test_kismet.py 存在且包含所有计划的测试函数骨架</done>
</task>

<task type="auto" tdd="true">
  <name>Task 1: 增强 FKismetArchive 容错模式（D-05）</name>
  <wave>2</wave>
  <depends_on>["Wave 0"]</depends_on>
  <files>src/uasset_read/kismet/archive.py</files>
  <behavior>
    - FKismetArchive(data, name, name_map, tolerant=False) 接受 tolerant 参数
    - tolerant=False（默认）：未知 token 抛 ParseError，行为与当前一致
    - tolerant=True：未知 token 时记录 warning 日志，跳过 1 字节，尝试重新读取下一个 token
    - tolerant=True 时若连续 10 次遇到未知 token（无法恢复），抛 ParseError 避免无限循环
    - 现有 read_expression()、read_expression_array() 等方法的 tolerant=False 行为完全不变
  </behavior>
  <action>
修改 src/uasset_read/kismet/archive.py 中 FKismetArchive 的 __init__ 和 read_expression：

1. __init__ 签名改为 `def __init__(self, data: bytes, name: str, name_map: list[str], tolerant: bool = False)`
2. 存储 `self._tolerant = tolerant`（替代当前硬编码的 `self._tolerant = False`）
3. read_expression() 中，当 `expr_class is None` 时：
   - 如果 `self._tolerant is False`：保持现有行为，抛出 ParseError
   - 如果 `self._tolerant is True`：
     - `self._logger.warning(f"Unknown EExprToken 0x{token_byte:02X} at offset {stmt_index}, skipping in tolerant mode")`
     - 向前回退 1 字节（`self.seek(stmt_index + 1)`），然后重试读取下一个 token
     - 添加计数器：连续 10 次未知 token 时抛 ParseError("Too many consecutive unknown tokens in tolerant mode")
     - 重试成功（读到已知 token）时重置计数器

不修改 read_expression_array()、xfer_string()、xfer_unicode_string()、read_fname_kismet()、skip()、remaining()。
  </action>
  <verify>
    <automated>python -m pytest tests/test_kismet.py::test_fkismet_archive_tolerant_mode -xvs</automated>
  </verify>
  <done>FKismetArchive 构造函数接受 tolerant 参数；严格模式未知 token 抛 ParseError；容错模式跳过未知字节并继续解析；现有非容错行为完全不变</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: 创建 bytecode_extractor 模块 — 字节码提取和解析（BYTECODE-01, BYTECODE-02）</name>
  <wave>2</wave>
  <depends_on>["Task 1"]</depends_on>
  <files>src/uasset_read/kismet/bytecode_extractor.py</files>
  <behavior>
    - extract_bytecode_bytes(archive, export, summary): 定位并返回 ScriptBytecode 原始字节
    - extract_bytecode_bytes 对不含字节码的导出返回 None（script_serial_size <= 0）
    - extract_bytecode_bytes 对非 UStruct 导出跳过（class_name 不在 UStruct_TYPES 中）
    - parse_bytecode_stream(bytecode_bytes, name_map, tolerant=False): 返回 list[KismetExpression]
    - parse_bytecode_stream 空字节输入返回空列表
    - parse_bytecode_stream 在字节流耗尽时停止（archive.tell() >= len(bytecode_bytes)）
    - extract_and_parse: 组合以上两步，返回 (expressions, error) 元组
    - UStruct 类型识别：UFunction, Function, K2Node_FunctionEntry 等类名匹配
  </behavior>
  <action>
新建 src/uasset_read/kismet/bytecode_extractor.py，包含三个核心函数：

**UStruct 类型白名单（per D-01）：**
```python
USTRUCT_TYPES = frozenset([
    "Function", "UFunction",
    "K2Node_FunctionEntry", "K2Node_FunctionResult",
])
```

**字节码提取策略说明：**
CUE4Parse UStruct.cs 中，字节码是 UStruct 的第一类字段，不是 PropertyTag。UStruct 的序列化顺序为：
1. SuperStruct (PackageIndex)
2. Children (PackageIndex)
3. ChildProperties (variable-length array of FProperty)
4. bytecodeBufferSize (int32)
5. serializedScriptSize (int32)
6. byte[serializedScriptSize] — 实际的字节码数据

**实现路径：** 使用 FArchive 二进制导航而非 PropertyTag 解析。定位到 UStruct 的 serial_offset 后，按顺序跳过已知字段（SuperStruct、Children、ChildProperties），然后读取 bytecodeBufferSize + serializedScriptSize header，最后读取字节码数据。ChildProperties 的跳过方式与现有 serializers/ 中的 UStruct 反序列化一致。

**1. extract_bytecode_bytes(archive, export, summary) → bytes | None**
参数：archive: FArchive, export: ObjectExport, summary: PackageFileSummary
逻辑：
- 如果 export.script_serial_size <= 0，返回 None（无脚本数据）
- 计算 script_start = export.serial_offset + export.script_serial_offset
- archive.seek(script_start)
- 跳过 SerializationControlExtensions（与 parse_properties_from_export 一致）：
  ```python
  if summary.file_version_ue5 >= 1011:  # UE5_PROPERTY_TAG_EXTENSION 类似
      ctrl = archive.read_u8()
      if ctrl & 0x02:
          archive.read_u8()  # skip overridden operation
  ```
- 读取 PropertyTag 循环直到 "None"（复用 read_property_tag，但不解析属性值）：
  ```python
  from uasset_read.parsers.property_parser import read_property_tag
  while True:
      tag = read_property_tag(archive, summary.name_map, tolerant=...)
      if tag.name == "None":
          break
      archive.skip(tag.size)  # 跳过属性值
  ```
- "None" 之后读取 bytecodeBufferSize (int32) 和 serializedScriptSize (int32)
- 如果 serializedScriptSize <= 0，返回 None
- 返回 archive.read_bytes(serializedScriptSize)

**2. parse_bytecode_stream(bytecode_bytes, name_map, tolerant=False) → list[KismetExpression]**
参数：bytecode_bytes: bytes, name_map: list[str], tolerant: bool = False
逻辑：
- 如果 not bytecode_bytes，返回 []
- 创建 `archive = FKismetArchive(bytecode_bytes, "ScriptBytecode", name_map, tolerant=tolerant)`（per D-05）
- 循环 `while archive.tell() < len(bytecode_bytes)`：
  - `expr = archive.read_expression()`
  - `expressions.append(expr)`
- 返回 expressions list

**3. extract_and_parse(archive, export, summary, name_map, tolerant=False) → tuple[list[KismetExpression], str | None]**
参数：archive: FArchive, export: ObjectExport, summary: PackageFileSummary, name_map: list[str], tolerant: bool = False
逻辑：
- 先用 resolve_class_name(export.class_index, import_map, export_map) 检查是否为 UStruct 类型
- 如果不是，返回 ([], None)
- 调用 extract_bytecode_bytes 获取字节
- 如果字节为 None，返回 ([], None)
- 调用 parse_bytecode_stream 解析
- 返回 (expressions, None)；如果捕获 ParseError，返回 ([], str(error))

注意：extract_bytecode_bytes 中 read_property_tag 需要 summary.name_map。summary 是 PackageFileSummary 实例，name_map 需要额外传入或使用 summary 上的引用。参考 property_parser.py 的调用方式，name_map 是独立参数。
  </action>
  <verify>
    <automated>python -m pytest tests/test_kismet.py::test_bytecode_extractor -xvs</automated>
  </verify>
  <done>extract_bytecode_bytes 能从 UStruct 导出提取字节数组；parse_bytecode_stream 将字节数组转为 KismetExpression 列表；extract_and_parse 组合链路正常工作；非 UStruct 导出安全跳过</done>
</task>

<task type="auto">
  <name>Task 3: 更新 kismet 模块导出</name>
  <wave>3</wave>
  <depends_on>["Task 2"]</depends_on>
  <files>src/uasset_read/kismet/__init__.py</files>
  <action>
在 src/uasset_read/kismet/__init__.py 中添加 bytecode_extractor 模块的导出：

1. 添加导入：`from uasset_read.kismet.bytecode_extractor import extract_bytecode_bytes, parse_bytecode_stream, extract_and_parse`
2. 在 __all__ 列表中添加："extract_bytecode_bytes", "parse_bytecode_stream", "extract_and_parse"
3. 验证 `python -c "from uasset_read.kismet import extract_bytecode_bytes, parse_bytecode_stream, extract_and_parse"` 无错误
  </action>
  <verify>
    <automated>python -c "from uasset_read.kismet import extract_bytecode_bytes, parse_bytecode_stream, extract_and_parse; print('OK')"</automated>
  </verify>
  <done>bytecode_extractor 三个函数可从 uasset_read.kismet 导入</done>
</task>

<task type="auto">
  <name>Task 4: 表达式列表输出 API（BYTECODE-03）</name>
  <wave>3</wave>
  <depends_on>["Task 2"]</depends_on>
  <files>src/uasset_read/kismet/bytecode_extractor.py</files>
  <action>
在 bytecode_extractor.py 中添加两个输出格式化函数：

**1. expressions_to_flat_list(expressions) → list[dict]**
- 将 list[KismetExpression] 转换为扁平的 dict 列表
- 每个 dict 包含：StatementIndex, Token (name), type (class name)
- 使用表达式的 to_dict() 方法获取完整数据
- 不递归嵌套子表达式（flat）

**2. expressions_to_tree(expressions) → list[dict]**
- 将 list[KismetExpression] 转换为带层级关系的树结构
- 每个 dict 包含：StatementIndex, Token, type, children (嵌套子表达式的 tree)
- 递归处理：如果表达式有子表达式（如 EX_Context 的 ObjectExpression/ContextExpression，EX_JumpIfNot 的 BooleanExpression），递归调用 expressions_to_tree 生成 children
- 子表达式检测：通过 to_dict() 输出中的嵌套 KismetExpression 对象判断
  - 遍历 to_dict() 的值，如果值是 KismetExpression 实例，递归处理
  - 如果值是 list[KismetExpression]，递归处理每个元素
  - 其他值原样保留

这两个函数作为 BYTECODE-03 要求的 "flat list 和层级树两种视图" 的 API 实现。
  </action>
  <verify>
    <automated>python -m pytest tests/test_kismet.py::test_expression_output_formats -xvs</automated>
  </verify>
  <done>expressions_to_flat_list 返回扁平 dict 列表；expressions_to_tree 返回带 children 的层级树结构；两种视图可正确序列化到 JSON</done>
</task>

<task type="auto">
  <name>Task 5: 端到端集成测试</name>
  <wave>5</wave>
  <depends_on>["Task 3", "Task 4"]</depends_on>
  <files>tests/test_kismet.py</files>
  <action>
在 tests/test_kismet.py 中编写集成测试，使用现有测试资产验证完整链路：

**测试用例 1：test_extract_bytecode_from_uasset**
- 使用 parse_uasset_with_linker 解析一个已知含字节码的 .uasset
- 遍历 export_map，找到 UFunction/Function 类型的导出
- 对每个含字节码的导出调用 extract_bytecode_bytes
- 断言：字节数组非空，长度 > 0

**测试用例 2：test_parse_bytecode_to_expressions**
- 使用 extract_and_parse 解析一个已知函数的字节码
- 断言：返回的表达式列表非空
- 断言：第一个表达式通常是 EX_Return 或 EX_LocalVariable
- 断言：最后一个表达式（在 EX_EndOfScript 之前）有意义

**测试用例 3：test_tolerant_mode_vs_strict_mode**
- 构造包含未知 token 的伪造字节流
- 严格模式：应抛 ParseError
- 容错模式：应跳过未知字节，继续解析已知 token

**测试用例 4：test_output_formats**
- 对已解析的表达式列表调用 expressions_to_flat_list 和 expressions_to_tree
- 断言：两种格式输出结构正确，可 JSON 序列化

测试资产路径：使用项目现有测试文件（tests/ 目录下已有的 .uasset）。如果无含字节码的文件，使用 E:\Develop\lib\UnrealEngine\Samples\FirstPerson 中的蓝图文件。
  </action>
  <verify>
    <automated>python -m pytest tests/test_kismet.py -xvs -k "test_extract_bytecode or test_parse_bytecode or test_tolerant or test_output_formats"</automated>
  </verify>
  <done>4 个集成测试全部通过：字节码提取、表达式解析、容错模式、输出格式化</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| .uasset 文件 → FKismetArchive | 恶意构造的字节流可能导致无限循环或内存耗尽 |
| bytecodeBufferSize/serializedScriptSize | 负数或超大值可能导致 OOB 读取 |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-62-01 | Spoofing | extract_bytecode_bytes | mitigate | 验证 class_name 在 USTRUCT_TYPES 白名单中，拒绝未知类型 |
| T-62-02 | Tampering | serializedScriptSize | mitigate | 解析前检查 serializedScriptSize > 0 且 < export.script_serial_size，拒绝异常值 |
| T-62-03 | Repudiation | tolerant mode | accept | 容错模式的 warning 日志提供审计追踪，无需额外机制 |
| T-62-04 | Information Disclosure | parse_bytecode_stream | accept | 仅读取已提供的 bytes，不泄露外部数据 |
| T-62-05 | Denial of Service | tolerant mode loop | mitigate | 连续 10 次未知 token 时终止循环，防止无限循环 |
| T-62-06 | Elevation of Privilege | bytecode injection | mitigate | 字节码解析不执行代码，仅构建数据结构，无提权风险 |
| T-62-SC | Tampering | pip install | mitigate | slopcheck + blocking human checkpoint for [ASSUMED]/[SUS] |
</threat_model>

<verification>
## Phase 62 验证检查

1. **BYTECODE-01 (ScriptBytecode 提取)**：
   - [ ] extract_bytecode_bytes 能从 UFunction/Function 导出中提取字节数组
   - [ ] 非 UStruct 导出返回 None
   - [ ] script_serial_size=0 时返回 None

2. **BYTECODE-02 (FKismetArchive 增强)**：
   - [ ] FKismetArchive tolerant 参数工作正常
   - [ ] parse_bytecode_stream 返回完整的 KismetExpression 列表
   - [ ] 容错模式跳过未知 token，严格模式抛 ParseError

3. **BYTECODE-03 (表达式列表输出)**：
   - [ ] expressions_to_flat_list 返回扁平 dict 列表
   - [ ] expressions_to_tree 返回带 children 的层级树
   - [ ] 两种输出可 JSON 序列化

4. **集成验证**：
   - [ ] 端到端测试通过：.uasset → extract_and_parse → expressions → output
   - [ ] 所有测试：python -m pytest tests/test_kismet.py -x
</verification>

<success_criteria>
- `from uasset_read.kismet import extract_bytecode_bytes, parse_bytecode_stream, extract_and_parse` 可用
- `FKismetArchive(data, name, name_map, tolerant=True)` 构造函数接受容错模式参数
- 对含字节码的 .uasset 文件调用 extract_and_parse 返回非空表达式列表
- 容错模式下遇到未知 token 不崩溃，继续解析
- expressions_to_flat_list 和 expressions_to_tree 输出正确且可 JSON 序列化
- 所有测试通过：`python -m pytest tests/test_kismet.py -x`
- 不修改已有模块核心逻辑（仅增强 archive.py 的 tolerant 参数，新增 bytecode_extractor.py）
</success_criteria>

<output>
Create `.planning/phases/phase-62/62-01-SUMMARY.md` when done
</output>
