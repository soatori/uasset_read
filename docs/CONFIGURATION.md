<!-- generated-by: gsd-doc-writer -->
# Configuration

This project uses **code and CLI arguments** for all configuration. No external config files, environment variables, or external services are required.

## Python and Platform Requirements

| Requirement | Value |
|-------------|-------|
| Python version | >= 3.10 (tested on 3.10, 3.11, 3.12) |
| Platform | Windows, Linux, macOS (any platform with Python 3.10+) |
| Runtime dependencies | None (zero external dependencies) |
| Build system | setuptools >= 61.0 |
| Package layout | src layout (`src/uasset_read/`) |

## Installation Configuration

The project is configured via `pyproject.toml`. It uses the standard setuptools build backend.

### Dependencies

- **Runtime**: `[]` (zero dependencies)
- **Dev**: `pytest>=7.0`, `pytest-cov>=4.0` (installed via `.[dev]` extras)

### Install Commands

```bash
# Production install (no dev tools)
pip install -e .

# Development install (includes pytest)
pip install -e ".[dev]"
```

### Project Metadata

| Field | Value |
|-------|-------|
| Package name | `uasset_read` |
| Version | `6.0.0` |
| CLI entry point | `uasset-read = uasset_read.cli:main` |

## CLI Configuration

All user-facing configuration is controlled through CLI arguments. The command syntax is:

```bash
uasset-read file.uasset [options]
```

### Output Format Flags (mutually exclusive)

| Flag | Description |
|------|-------------|
| `--json` | Output full JSON structure |
| `--text` | Output YAML-style text format (default when no flag is given) |
| `--summary` | Output compact JSON summary |
| `--markdown` | Output Markdown format |

Only one output format flag may be used at a time. If none is specified, `--text` is the default.

### Analysis and Data Flags

| Flag | Description |
|------|-------------|
| `--graph` | Include blueprint graph data in output. Alone: JSON graphs only. Combined with `--json`/`--verbose`: full JSON with graphs. Combined with `--text`: text output with Graphs section. |
| `--schema` | Include field semantic annotations (`_schema` field) |
| `--verbose` | Include extra detail fields (also enables `_schema` annotations) |
| `--export INDEX` | Output only a specific export by index (integer) |

### Error Handling Mode

| Flag | Description |
|------|-------------|
| `--tolerant` | Enable tolerant mode for UE5 serialization (default: ON) |
| `--strict` | Disable tolerant mode: throw `ParseError` on serialization issues |

These two flags are mutually exclusive. `--tolerant` is the default behavior. Using `--strict` overrides it.

### I/O Configuration

| Flag | Description |
|------|-------------|
| `--output FILE` | Write output to the specified file instead of stdout (UTF-8 encoding) |

### Exit Codes

| Code | Meaning |
|------|--------|
| `0` | Success |
| `1` | Parse error |
| `2` | File not found (or path is a directory) |
| `3` | Argument error |

## Python API Configuration

### Main Parse Functions

```python
from uasset_read import parse_uasset, parse_uasset_with_linker
```

#### `parse_uasset(path, tolerant=True)`

Standard parser using the single-archive approach.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | (required) | Path to the `.uasset` file |
| `tolerant` | `bool` | `True` | When `True`, serialization issues are recorded as warnings. When `False`, they raise `ParseError`. |

Returns a `ParseResult` instance with fields: `summary`, `name_map`, `import_map`, `export_map`, `blueprint`, `graphs`, `imports`, `soft_references`, `circular_deps`, `is_success`, `errors`, `mmap_used`, `mmap_warning`.

#### `parse_uasset_with_linker(path, tolerant=True, preload_all=False)`

Advanced parser using the two-stage `PackageLinker` object graph reconstruction (v7.0+).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | (required) | Path to the `.uasset` file |
| `tolerant` | `bool` | `True` | Same as `parse_uasset` |
| `preload_all` | `bool` | `False` | When `True`, preloads all export objects eagerly. When `False`, uses lazy loading on demand. |

Returns a `LinkerParseResult` instance, which includes all `ParseResult` fields plus `linker` (the `PackageLinker` instance) and `all_objects` / `root_objects` (object graph roots).

### FArchive Configuration

```python
from uasset_read import FArchive

archive = FArchive(path, tolerant=False)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str` | (required) | Path to the file |
| `tolerant` | `bool` | `False` | Instance default for tolerant mode (used by `validate_size()` and other validation methods) |

Methods:
- `set_byte_swapping(enabled: bool)` — Enable or disable byte swapping for little/big-endian detection
- `get_mmap_info()` — Returns `{"used": bool, "warning": str | None}` showing mmap status

### Format Configuration

Output formatting is controlled by the `FORMAT_CONFIG` dictionary in `constants.py`:

```python
FORMAT_CONFIG = {
    "pin_reference_mode": "name",  # Use pin names for references
}
```

To change the pin reference mode globally, modify this dict before calling any format functions.

### Exception Configuration

All exceptions inherit from `UAssetError`. The hierarchy is:

```
UAssetError
  |-- VersionError   # Unsupported UE version
  |-- ParseError     # Parsing failure (may carry partial_result)
```

`ParseError` has an optional `partial_result` attribute containing any data recovered before the error occurred.

## Constants and Tunable Thresholds

All constants are defined in `uasset_read.constants` and re-exported via `uasset_read.__init__`. They can be imported and, in some cases, overridden before parsing to tune behavior.

### Memory and Performance

| Constant | Value | Description |
|----------|-------|-------------|
| `MMAP_THRESHOLD` | `50 * 1024 * 1024` (50 MB) | Files at or above this size are read using `mmap` for memory efficiency. Below this threshold, standard file I/O is used. |

To use mmap for smaller files, override before creating `FArchive`:

```python
import uasset_read.constants
uasset_read.constants.MMAP_THRESHOLD = 10 * 1024 * 1024  # 10 MB
```

### Boundary Validation Limits

These constants defend against malformed or malicious `.uasset` files by capping iteration counts.

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_NAME_COUNT` | `10,000,000` | Maximum number of name table entries |
| `MAX_IMPORT_COUNT` | `1,000,000` | Maximum number of import table entries |
| `MAX_EXPORT_COUNT` | `1,000,000` | Maximum number of export table entries |
| `MAX_CUSTOM_VERSIONS` | `10,000` | Maximum number of custom version entries |
| `MAX_PROPERTY_COUNT` | `10,000` | Property loop iteration limit |
| `MAX_ARRAY_COUNT` | `1,000,000` | Maximum ArrayProperty elements |
| `MAX_FSTRING_LENGTH` | `10,000,000` (10 MB) | Maximum FString length (UTF-8 or UTF-16) |

### Blueprint Graph Parsing Limits

| Constant | Value | Description |
|----------|-------|-------------|
| `MAX_PINS_PER_NODE` | `1,000` | Maximum pins per graph node |
| `MAX_NODES_PER_GRAPH` | `5,000` | Maximum nodes per graph |
| `MAX_LINKEDTO_PER_PIN` | `100` | Maximum connections per pin |

### Version Thresholds

| Constant | Value | Description |
|----------|-------|-------------|
| `UE5_VERSION_MIN` | `0` | Minimum UE5 object version |
| `UE5_LEGACY_VERSION` | `-9` | Fixed `LegacyFileVersion` for UE5.6+ files |
| `PROPERTY_TAG_COMPLETE_TYPE_NAME` | `1012` | UE5 format switch threshold for complete type names |

### Package Flags

| Constant | Value | Description |
|----------|-------|-------------|
| `PKG_Cooked` | `0x200` | Package is cooked |
| `PKG_UnversionedProperties` | `0x2000` | Uses unversioned property serialization |
| `PKG_FilterEditorOnly` | `0x00000080` | Filter editor-only objects |

### PropertyTag Flags

| Constant | Value | Description |
|----------|-------|-------------|
| `PROP_TAG_NONE` | `0x00` | No flags |
| `PROP_TAG_HAS_ARRAY_INDEX` | `0x01` | ArrayIndex field present |
| `PROP_TAG_HAS_PROPERTY_GUID` | `0x02` | PropertyGuid field present |
| `PROP_TAG_HAS_EXTENSIONS` | `0x04` | Extension data present |
| `PROP_TAG_HAS_BINARY_OR_NATIVE` | `0x08` | Binary/native serialize |
| `PROP_TAG_BOOL_TRUE` | `0x10` | Bool value is true |
| `PROP_TAG_SKIPPED_SERIALIZE` | `0x20` | Skipped serialize |

### CPF_* Property Flags (Class Property Flags)

Key flags used for blueprint variable visibility and editability:

| Constant | Value | Description |
|----------|-------|-------------|
| `CPF_Edit` | `0x0000000000000001` | Property is editable |
| `CPF_BlueprintVisible` | `0x0000000000000004` | Visible in blueprint |
| `CPF_BlueprintReadWrite` | `0x00000100` | Read/write from blueprint |
| `CPF_BlueprintReadOnly` | `0x0000000000000010` | Read-only from blueprint |
| `CPF_EditAnywhere` | `0x02000000` | Editable anywhere |
| `CPF_EditInstanceOnly` | `0x04000000` | Editable on instance only |
| `CPF_InstancedReference` | `0x0000000000080000` | Instanced sub-object reference |
| `CPF_ExposeOnSpawn` | `0x0001000000000000` | Exposed on spawn/constructor |
| `CPF_Transient` | `0x0000000000002000` | Not saved to disk |
| `CPF_BlueprintAssignable` | `0x80000000` | Assignable as event dispatcher |

For the full list, see `src/uasset_read/constants.py`.

## No Config File Required

This project does **not** use configuration files (`.env`, `config.yaml`, `settings.json`, etc.). All behavior is controlled through:

1. **CLI arguments** (`uasset-read file.uasset --json --strict`)
2. **Python API parameters** (`parse_uasset(path, tolerant=False)`)
3. **Constant overrides** (import and modify `constants.MMAP_THRESHOLD` before parsing)

No environment variables are read at runtime.

## Environment Considerations

### Python Version

The project requires **Python >= 3.10** (uses `match`/`case`, `|` union type syntax, and `struct` module). Verify your version:

```bash
python --version
```

### Platform Support

- **Windows**: Fully supported. mmap works on Windows with `ACCESS_READ`.
- **Linux**: Fully supported. mmap is native and performant.
- **macOS**: Fully supported. mmap works as expected.

### Memory

- Small files (< 50 MB): Standard file I/O, minimal memory overhead.
- Large files (>= 50 MB): Automatically uses `mmap` for read-only memory mapping. If mmap fails (e.g., permissions), falls back to standard I/O with a warning in `ParseResult.mmap_warning`.

### Encoding

- All output is UTF-8 encoded (stdout and file output via `--output`).
- FString decoding uses `errors='replace'` for malformed bytes.
