<!-- generated-by: gsd-doc-writer -->
# Testing Guide

Unreal Engine .uasset 文件解析器的测试指南。

## Test Philosophy

The project follows a **zero-dependency testing strategy**: since the parser has no runtime dependencies on Unreal Engine, all tests can run on any machine with Python 3.10+.

### Test Pyramid

```
        /\
       /  \   Integration / Equivalence   (~5%)
      /----\   Real .uasset files, end-to-end parsing
     /      \
    /--------\  Unit Tests                  (~90%)
   /          \   Synthetic binary data, dataclass structure,
  /            \   parser logic, formatter output
 /--------------\
/                \ Stubs / TODO              (~5%)
                    Wave 0 stubs, skipped tests awaiting real assets
```

**What gets tested:**
- **Binary parsing** -- byte swapping, mmap threshold, FArchive boundary validation
- **Serializer correctness** -- PackageSummary, ImportMap, ExportMap, PropertyTag
- **Property parsers** -- 14 property type parsers (Int, Float, Bool, Name, String, Struct, Map, Set, Enum, Text, Delegate, etc.)
- **Blueprint extraction** -- variable extraction, transform parsing, metadata, component detection
- **Graph parsing** -- UEdGraph/Node/Pin dataclasses, K2Node type readers (CallFunction, Event, Knot, Comment, EnhancedInput)
- **PackageLinker** -- two-stage object graph reconstruction, UObjectInstance creation, outer tree resolution
- **Formatters** -- JSON (full/summary), Text, Markdown, Mermaid output
- **Equivalence** -- modular vs. legacy output parity on real assets

**What is NOT tested in CI:**
- Real `.uasset` files from external UE projects (tests are skipped with `pytest.skip`)
- Performance benchmarks on multi-GB assets
- Platform-specific mmap behavior on all OS combinations

## Running Tests

### Prerequisites

```bash
pip install -e ".[dev]"
```

This installs `pytest>=7.0` and `pytest-cov>=4.0` as development dependencies.

### Basic Commands

```bash
# Run the full test suite
python -m pytest tests/ -v

# Run with shorter output
python -m pytest tests/ --tb=short

# Run a single test file
python -m pytest tests/test_uasset_read.py -v

# Run a single test
python -m pytest tests/test_uasset_read.py::test_package_summary_valid -v

# Run tests matching a keyword
python -m pytest tests/ -k "byte_swap" -v

# Run tests for a specific module
python -m pytest tests/test_link_linker.py tests/test_link_object_instance.py -v

# Show skipped tests
python -m pytest tests/ -v --tb=no -rs
```

### Coverage

```bash
# Run with coverage report
python -m pytest tests/ --cov=uasset_read --cov-report=term-missing

# Run with HTML coverage report
python -m pytest tests/ --cov=uasset_read --cov-report=html
# Open htmlcov/index.html in browser

# Run with minimum coverage threshold (if configured)
python -m pytest tests/ --cov=uasset_read --cov-fail-under=80
```

### Watch Mode

The project does not currently include `pytest-watch` or `pytest-xdist`. Run tests manually after each change.

## Test Organization

### Directory Structure

```
tests/
├── __init__.py
├── test_uasset_read.py              # Core parsing: summary, name/import/export maps, byte swapping
├── test_advanced_properties.py      # 6 advanced property parsers (Struct, Map, Set, Enum, Text, Delegate)
├── test_blueprint_extraction.py     # Blueprint detection, parent class resolution, variable extraction
├── test_graph_parsing.py            # UEdGraph/Node/Pin + K2Node type readers + dispatch
├── test_output_formatting.py        # JSON/Text formatters, CLI, connections, execution flows
├── test_phase14_output_formats.py   # Output format enhancements (status, schema, version)
├── test_link_linker.py              # PackageLinker: link, resolve, outer tree, preload
├── test_link_object_instance.py     # UObjectInstance: creation, null check, full name, repr
├── test_link_result.py              # LinkerParseResult structure
├── test_phase44_linker_objects.py   # PackageLinker with real object scenarios
├── test_phase45_from_archive_with_linker.py  # parse_uasset_with_linker integration
├── test_phase47_pin_linkedto.py     # Pin LinkedTo resolution
├── test_phase48_component_extraction.py      # Component property extraction
├── test_phase12_blueprint_variables.py       # Blueprint variable extraction
├── test_phase13_transform.py               # Transform value parsing (Vector, Rotator, Scale)
├── test_phase21_verification.py            # Phase 21 verification tests
├── test_phase26_blueprint_metadata_enhancement.py  # Metadata enhancement
├── test_phase35d_*.py                      # Phase 35D fix verification (formatter, model, variable)
├── test_ue5_*.py                           # UE5-specific: bool, FText, pin bitfield, serialization
├── test_equivalence.py                     # Modular vs. legacy output parity (real assets)
├── test_dependency_analysis.py             # Import dependency analysis, circular dep detection
├── test_exportmap_properties.py            # ExportMap property parsing
├── test_skill_integration.py               # Skill/integration tests
├── test_mmap_behavior.py                   # mmap threshold and fallback (stubs)
├── test_boundary_validation.py             # FArchive offset/size validation (stubs)
├── test_loop_limits.py                     # Loop limit enforcement (stubs)
└── test_partial_results.py                 # Partial result handling on parse errors
```

### Naming Conventions

| Pattern | Example | Description |
|---------|---------|-------------|
| Test files | `test_*.py` | Matches `python_files` in `pyproject.toml` |
| Test classes | `TestCamelCase` | Groups related tests (e.g., `TestPackageLinkerLink`) |
| Test functions | `test_snake_case` | Individual test cases |
| Requirement IDs | `CORE-01`, `GRAPH-05`, `BLUE-03` | Trace tests to planning requirements |
| Phase prefixes | `test_phase12_*`, `test_phase44_*` | Tests created during specific phases |

### Test Categories by Module

#### Binary Parsing (FArchive)

**File:** `tests/test_uasset_read.py`

Tests the low-level binary reader:
- Magic tag detection (`PACKAGE_FILE_TAG`, `PACKAGE_FILE_TAG_SWAPPED`)
- Byte swapping for big-endian files (`test_byte_swapping_detection`)
- String content integrity under byte swapping (`test_byte_swapping_string_content`)
- Type-specific reads: `read_i32`, `read_u32`, `read_i64`, `read_u64`, `read_f32`
- Boundary validation: seek/read exceeding file size raises `ParseError`
- Raw byte reads must NOT be reversed (only numeric types swap)
- UTF-16/UTF-8 length overflow protection (>10M bytes rejected)
- Name count bounds validation

**Approach:** Synthetic `.uasset` files built with `struct.pack` in `create_test_uasset()`. Each test creates a temp file, parses it, then cleans up.

#### Serializer Tests (PackageSummary, Import/Export Maps, PropertyTag)

**Files:** `tests/test_uasset_read.py`, `tests/test_advanced_properties.py`

Tests the header and table parsers:
- `PackageFileSummary` field reading (UE5.7 format with all conditional fields)
- NameMap extraction with hash fields
- ImportMap parsing including UE5 conditional fields (`PackageName`, `bImportOptional`)
- ExportMap parsing with UE5 fields (TemplateIndex, bool flags, ScriptSerialOffset)
- `PackageIndex` properties: `is_import`, `is_export`, `is_null`, conversion methods
- Custom version table reading
- Version validation (UE5-only, legacy version rejection)
- Six advanced property parsers: Struct, Map, Set, Enum, Text, Delegate

**Approach:** `create_test_uasset()` helper builds complete synthetic headers with configurable names/imports/exports. `MockArchive` class (wrapping `BytesIO`) tests property parsers without files.

#### Parser Tests (14 Property Type Parsers)

**File:** `tests/test_advanced_properties.py`

Tests the property parsing system:
- `parse_struct_property` -- StructProperty with type extraction from tag
- `parse_map_property` -- MapProperty with key/value type extraction
- `parse_set_property` -- SetProperty with element type extraction
- `parse_enum_property` -- EnumProperty with enum name/variant extraction
- `parse_text_property` -- TextProperty with FText history types
- `parse_delegate_property` -- DelegateProperty with function reference

**Approach:** `MockArchive` class wraps `BytesIO` to feed raw bytes to property parsers. Type extraction helper functions (`_extract_struct_type_from_tag`, etc.) are tested separately.

#### Blueprint Tests (Variable Extraction, Transform, Metadata)

**Files:** `tests/test_blueprint_extraction.py`, `tests/test_phase12_blueprint_variables.py`, `tests/test_phase13_transform.py`, `tests/test_phase26_blueprint_metadata_enhancement.py`, `tests/test_phase48_component_extraction.py`

Tests blueprint-specific extraction:
- Blueprint detection via class name (`detect_blueprint`)
- Parent class resolution (`resolve_parent_class`)
- Blueprint variable extraction (name, type, default value, tooltips)
- Transform value parsing: `VectorValue`, `RotatorValue`, `ScaleValue`, `format_transform_value`
- Blueprint metadata enhancement (display name, category, keywords)
- Component property extraction (scene component, static mesh, etc.)

**Status:** Many tests in `test_blueprint_extraction.py` are stubs (`pass`) awaiting full implementation. Phase-numbered tests (`test_phase12_*`, etc.) are the active test suite.

#### Graph Tests (Execution Flow, Data Flow, Connections)

**File:** `tests/test_graph_parsing.py`

Tests the graph parsing system:
- `UEdGraph`, `UEdGraphNode`, `UEdGraphPin` dataclass structure validation
- `FEdGraphPinType` with pin category and subcategory
- `resolve_class_name` from PackageIndex (export/import/null)
- K2Node dataclasses: `K2NodeCallFunction`, `K2NodeEvent`, `K2NodeKnot`, `EdGraphNodeComment`, `K2NodeEnhancedInputAction`
- `FMemberReference` parsing (function/event references)
- Node type dispatch and unknown type handling
- Safety boundary constants: `MAX_PINS_PER_NODE` (1000), `MAX_NODES_PER_GRAPH` (5000), `MAX_LINKEDTO_PER_PIN` (100)
- Import verification for all graph-related exports

**Status:** Dataclass structure tests are complete. Binary parser tests for node/pin reading are skipped awaiting synthetic binary data generators.

#### Linker Tests (PackageLinker, UObjectInstance)

**Files:** `tests/test_link_linker.py`, `tests/test_link_object_instance.py`, `tests/test_link_result.py`, `tests/test_phase44_linker_objects.py`, `tests/test_phase45_from_archive_with_linker.py`

Tests the two-stage object graph reconstruction (v7.0):
- **Stage 1 -- `link()`:** Creates `UObjectInstance` shells from ExportMap/ImportMap, sets linker reference and serial info
- **Stage 2 -- `preload()`:** Deserializes properties on demand with caching and idempotent behavior
- `resolve_package_index()` -- positive (export), negative (import), zero (null), out-of-bounds
- Outer tree resolution -- parent/child relationships via `OuterIndex`
- `get_children()` -- returns correct child list or empty
- `UObjectInstance` -- creation, `is_import`/`is_export`/`is_null` properties, `get_full_name()`, `__repr__`
- Integration with `parse_uasset_with_linker()` pipeline
- Pin LinkedTo resolution (Phase 47)

**Approach:** `_make_linker()` helper creates `PackageLinker` with `MagicMock` archive and configurable import/export entries. Property parsing is patched with `unittest.mock.patch`.

#### Formatter Tests (JSON, Text, Markdown, Mermaid)

**Files:** `tests/test_output_formatting.py`, `tests/test_phase14_output_formats.py`

Tests output formatters:
- `format_json_full()` -- complete JSON output with all data
- `format_json_summary()` -- summarized JSON (70%+ token reduction)
- `format_text_full()` -- human-readable text output
- `format_markdown()` -- Markdown output
- `build_status_info()` -- JSend-style status field (success/fail)
- `build_graphs_summary()` -- graph summary extraction
- `build_connections_map()` -- node connection mapping
- `build_execution_flows()` -- execution flow extraction
- `build_schema_info()` -- semantic schema annotations
- Output version and API freezing (OUT-06)
- CLI argument parsing and output format selection

**Approach:** `@pytest.fixture` creates mock `ParseResult` objects with configurable summary, exports, metadata, and graphs. Tests verify JSON structure, field presence, and output size.

#### Integration / Equivalence Tests

**Files:** `tests/test_equivalence.py`, `tests/test_skill_integration.py`

- **Equivalence tests:** Compare modular vs. legacy output on real `.uasset` files. Uses `DiffRecorder` to collect differences without stopping (per D-04 "record and continue").
- **Skill integration tests:** Verify end-to-end parsing workflows.

**Test assets:** Real `.uasset` files referenced from `E:\Develop\lib\UnrealEngine\Samples\FirstPerson`. Tests that require real assets are marked with `pytest.skip` and a reason.

## Adding New Tests

### Creating Synthetic Binary Data

The primary approach is the `create_test_uasset()` helper in `test_uasset_read.py`. It builds a complete UE5.7-format `.uasset` file with configurable parameters:

```python
path = create_test_uasset(
    tag=PACKAGE_FILE_TAG,           # Magic tag (normal or swapped)
    legacy_version=-8,              # Legacy file version
    ue5_version=1018,               # UE5 version
    names=["MyClass", "MyProperty"], # Name table entries
    imports=[(4, 3, 0, 1)],         # Import table entries
    exports=[(-1, 0, 0, 1, 0, 100, 200)],  # Export table entries
    use_big_endian=False,           # Byte order
)
```

Always clean up temp files:

```python
try:
    result = parse_uasset(path)
    assert result.is_success
finally:
    cleanup_test_file(path)
```

### MockArchive Pattern

For property-level tests that do not need a full file header, use the `MockArchive` pattern:

```python
class MockArchive(FArchive):
    def __init__(self, data: bytes):
        self._file = BytesIO(data)
        self._byte_swapping = False
        self._file_size = len(data)
        self._path = "mock"
        self._mmap = None
        self._use_mmap = False

    def close(self):
        self._file.close()
```

Feed raw bytes directly:

```python
data = struct.pack('<i', 42)  # An IntProperty value
archive = MockArchive(data)
value = archive.read_i32()
assert value == 42
archive.close()
```

### Using Fixtures

The project uses `@pytest.fixture` for reusable test data. Define fixtures in the test file that needs them:

```python
@pytest.fixture
def single_import():
    return [ObjectImport(
        class_package="/Script/Engine",
        class_name="Class",
        outer_index=PackageIndex(0),
        object_name="Blueprint"
    )]
```

### Parameterized Tests

Use `@pytest.mark.parametrize` when testing multiple inputs:

```python
@pytest.mark.parametrize("type_name", [
    "K2Node_CallFunction",
    "K2Node_Event",
    "K2Node_Knot",
    "EdGraphNode_Comment",
    "K2Node_EnhancedInputAction",
])
def test_known_node_types_dispatch(type_name):
    node = UEdGraphNode(node_guid="test", class_name=type_name)
    assert node.class_name == type_name
```

### Mocking with unittest.mock

For linker tests that need to isolate stages:

```python
from unittest.mock import MagicMock, patch

with patch("uasset_read.parsers.property_parser.parse_properties_from_export", return_value=[MagicMock()]):
    linker.preload(0)
```

### Skipping Tests

Use `pytest.skip()` for tests that require resources not available in CI:

```python
def test_full_graph_parsing_integration():
    """Complete Graph->Node->Pin three-layer parsing"""
    pytest.skip("Requires real .uasset files")
```

Use `@pytest.mark.skip` for permanently disabled tests:

```python
@pytest.mark.skip(reason="Phase 34: error message format changed -- functional fix")
def test_export_count_bounds_validation():
    ...
```

### Test ID Conventions

Include requirement IDs in docstrings for traceability:

```python
def test_package_summary_valid():
    """Valid UE5 uasset file header parsing (CORE-01).

    Validates: magic tag, version numbers read correctly.
    """
```

## Integration Tests

### End-to-End Parsing

The primary integration test path:

```python
from uasset_read import parse_uasset

result = parse_uasset("path/to/file.uasset")
assert result.is_success
assert result.summary is not None
assert len(result.name_map) > 0
```

### With Linker

For full two-stage parsing with object graph reconstruction:

```python
from uasset_read import parse_uasset_with_linker

result = parse_uasset_with_linker("path/to/file.uasset")
assert result.linker is not None
linker = result.linker
linker.link()       # Stage 1: create object shells
linker.preload(0)   # Stage 2: deserialize properties
```

### Equivalence Testing

The `test_equivalence.py` module compares outputs between the modular and legacy codebases:

```python
from tests.test_equivalence import DiffRecorder, verify_equivalence

recorder = DiffRecorder()
verify_equivalence("file.uasset", "json_full", recorder)
assert len(recorder.diffs) == 0, f"Found {len(recorder.diffs)} differences"
```

### Real Asset Tests

Tests requiring real `.uasset` files are skipped in CI. To run them locally:

1. Ensure test assets exist at `E:\Develop\lib\UnrealEngine\Samples\FirstPerson`
2. Remove the `pytest.skip()` line from the relevant test
3. Run with `python -m pytest tests/test_equivalence.py -v`

## Debugging Test Failures

### Common Failure Modes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `ParseError: exceeds file size` | Synthetic file too small for declared offsets | Increase padding in `create_test_uasset()` or fix offset calculations |
| `AssertionError: "None" != expected` | Name table missing leading "None" entry | `create_test_uasset()` auto-prepends "None" -- check index offsets |
| `AttributeError: no field 'package_name'` | UE5 version too low for conditional field | Use `ue5_version >= 518` for PackageName field |
| `struct.error: unpack requires` | Binary data too short for format | Check `struct.pack` size matches expected field width |
| Tests pass locally but fail in CI | Real asset path not available | Mark with `pytest.skip` or add fixture |

### Debugging Techniques

```bash
# Show full traceback (not shortened)
python -m pytest tests/test_uasset_read.py::test_name_table_extraction -v --tb=long

# Print during test execution (not captured)
python -m pytest tests/ -s  # disables output capture

# Stop on first failure
python -m pytest tests/ -x

# Run last failed tests only
python -m pytest tests/ --lf

# Show local variables in traceback
python -m pytest tests/ --tb=long --showlocals

# Verbose import resolution
python -m pytest tests/ --import-mode=importlib
```

### Inspecting Synthetic Files

When a test fails, write the synthetic file to disk and inspect it:

```python
def test_debug_header():
    path = create_test_uasset(names=["Test"])
    # Do NOT clean up -- inspect manually
    # Then: python -c "from uasset_read import parse_uasset; print(parse_uasset('path'))"
    ...
```

### Byte Swapping Debug

For endianness issues, verify raw bytes:

```python
import struct
data = struct.pack('>i', -7)  # Big-endian
print(data.hex())  # Should be: fffffff9
```

## Test Configuration

Configuration is in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

No `conftest.py` currently exists -- all fixtures are defined within individual test files. If shared fixtures become necessary, create `tests/conftest.py`.
