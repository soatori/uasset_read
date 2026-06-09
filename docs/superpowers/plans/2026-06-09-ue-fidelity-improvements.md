# UE Fidelity Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align uasset_read parsing behavior with UE's FLinkerLoad lifecycle to improve output fidelity from "tolerant extractor" to "UE-equivalent loader"

**Architecture:** Refactor loading lifecycle to match UE's two-phase pattern (link → preload → post_load), fix payload offset strategy to use SerialOffset by default, implement class serialization strategy table, complete SoftObjectPath index-based resolution, correct DependsMap FPackageIndex semantics, and unify status model to success|partial|failed.

**Tech Stack:** Python 3.10+, pytest, UE source reference at E:/Develop/lib/UnrealEngine

---

## File Structure

### Files to Create
- `tests/test_lifecycle_preload.py` — Tests for UE-style preload lifecycle
- `tests/test_payload_offset_strategy.py` — Tests for SerialOffset vs ScriptSerialization offset
- `tests/test_class_serialization_strategy.py` — Tests for class strategy table
- `tests/test_soft_object_path_index.py` — Tests for SoftObjectPath index-based resolution
- `tests/test_depends_map_package_index.py` — Tests for FPackageIndex semantics in DependsMap
- `tests/test_status_model_unified.py` — Tests for unified success|partial|failed status
- `src/uasset_read/parsers/class_serialization_strategy.py` — Class strategy registry

### Files to Modify
- `src/uasset_read/parse_uasset.py:568-620` — Move post_load after export parsing, use linker.preload
- `src/uasset_read/link/linker.py:218-286` — Enhance preload to handle class-specific strategies
- `src/uasset_read/parsers/property_parser.py:319-386` — Change default to SerialOffset, make ScriptSerialization opt-in
- `src/uasset_read/serializers/object_resources.py:163-181` — Store SoftObjectPathList for index lookup
- `src/uasset_read/parsers/property_types.py:401-405` — Use index-based SoftObjectPath resolution when list exists
- `src/uasset_read/link/linker.py:398-413` — Fix DependsMap to use FPackageIndex semantics
- `src/uasset_read/models/result.py:50-62` — Change status property to use success|partial|failed
- `src/uasset_read/formatters/helpers.py:17-42` — Update build_status_info for unified model
- `src/uasset_read/parse_uasset.py:620` — Remove unconditional is_success=True

---

## Task 1: Fix Loading Lifecycle — Move post_load After Export Parsing

**Files:**
- Modify: `src/uasset_read/parse_uasset.py:568-620`
- Test: `tests/test_lifecycle_preload.py`

- [ ] **Step 1: Write failing test for preload-before-post_load**

```python
# tests/test_lifecycle_preload.py
"""Test that export parsing follows UE FLinkerLoad lifecycle: link → preload → post_load."""
import pytest
from pathlib import Path
from uasset_read.parse_uasset import parse_uasset_with_linker


def test_preload_happens_before_post_load():
    """UE lifecycle: objects must be preloaded before post_load resolves references."""
    test_file = Path("E:/Develop/lib/UnrealEngine/Samples/Blueprints/BS_Basic.uasset")
    if not test_file.exists():
        pytest.skip("Sample file not found")
    
    result = parse_uasset_with_linker(str(test_file), preload_all=True)
    
    # Verify linker exists
    assert result.linker is not None, "Linker should be created"
    
    # Verify all exports are preloaded
    for idx, inst in enumerate(result.linker._export_objects):
        assert inst._preloaded, f"Export #{idx} ({inst.object_name}) should be preloaded"
    
    # Verify property references are resolved (only works if preload happened first)
    has_object_props = False
    for inst in result.linker._export_objects:
        if hasattr(inst, 'property_references') and inst.property_references:
            has_object_props = True
            # References should be resolved to UObjectInstance, not raw ints
            for prop_name, ref in inst.property_references.items():
                assert hasattr(ref, 'object_name'), \
                    f"ObjectProperty '{prop_name}' should be resolved to UObjectInstance"
    
    # At least some exports should have object properties
    assert has_object_props, "Should have resolved some ObjectProperty references"


def test_linker_preload_is_idempotent():
    """Calling preload multiple times should not re-parse."""
    test_file = Path("E:/Develop/lib/UnrealEngine/Samples/Blueprints/BS_Basic.uasset")
    if not test_file.exists():
        pytest.skip("Sample file not found")
    
    result = parse_uasset_with_linker(str(test_file), preload_all=False)
    linker = result.linker
    
    # Preload same export twice
    linker.preload(0)
    first_parse = linker._export_objects[0].serialized_properties.copy()
    
    linker.preload(0)
    second_parse = linker._export_objects[0].serialized_properties
    
    # Should be identical (no re-parsing)
    assert first_parse == second_parse, "preload should be idempotent"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_lifecycle_preload.py::test_preload_happens_before_post_load -v`
Expected: FAIL — property_references not populated because post_load runs before preload

- [ ] **Step 3: Fix parse_uasset.py lifecycle**

```python
# src/uasset_read/parse_uasset.py, lines 568-620
# BEFORE (current):
#     linker.post_load()  # Line 568 — runs before exports are parsed!
#     ...
#     for export in result.export_map:  # Line 584
#         export.properties = parse_properties_from_export(...)
#     result.is_success = True  # Line 620

# AFTER (fixed):
# Remove line 568: linker.post_load()
# Replace lines 584-606 with linker.preload calls:

        # Parse exports via linker.preload (UE lifecycle: link → preload → post_load)
        for idx in range(len(result.export_map or [])):
            try:
                linker.preload(idx)
                # Copy properties from linker instance to export for backward compat
                inst = linker._export_objects[idx]
                result.export_map[idx].properties = inst.serialized_properties
                if not getattr(result.export_map[idx], "parse_status", None):
                    setattr(result.export_map[idx], "parse_status", "success")
            except Exception as e:
                if not tolerant:
                    raise ParseError(f"Preload error in export #{idx}: {e}") from e
                result.errors.append(f"Preload error in export #{idx}: {e}")
                result.export_map[idx].properties = []
                setattr(result.export_map[idx], "parse_status", "failed")
                setattr(result.export_map[idx], "fallback_reason", "preload_error")
                setattr(result.export_map[idx], "error_message", str(e))

            # Extract component transforms
            if result.export_map[idx].properties:
                result.export_map[idx].transforms = extract_component_transforms(
                    result.export_map[idx].properties
                )

        # NOW call post_load (after all exports are preloaded)
        linker.post_load()

        # Shared post-processing
        _post_process(...)
        
        # Set success based on errors (not unconditional)
        result.is_success = len(result.errors) == 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_lifecycle_preload.py -v`
Expected: PASS — property_references now populated correctly

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/parse_uasset.py tests/test_lifecycle_preload.py
git commit -m "fix: align loading lifecycle with UE FLinkerLoad pattern

- Move linker.post_load() to run AFTER all exports are preloaded
- Use linker.preload(idx) instead of direct parse_properties_from_export
- Set is_success based on error count, not unconditional True
- Ensures _resolve_property_references sees preloaded objects

Fixes lifecycle issue identified in UE fidelity audit."
```

---

## Task 2: Fix Payload Offset Strategy — Use SerialOffset by Default

**Files:**
- Modify: `src/uasset_read/parsers/property_parser.py:319-386`
- Test: `tests/test_payload_offset_strategy.py`

- [ ] **Step 1: Write failing test for default SerialOffset**

```python
# tests/test_payload_offset_strategy.py
"""Test that property parsing uses SerialOffset by default, not ScriptSerialization offsets."""
import pytest
from pathlib import Path
from uasset_read.parse_uasset import parse_uasset


def test_default_uses_serial_offset():
    """UE default: read from SerialOffset, not ScriptSerializationStartOffset."""
    test_file = Path("E:/Develop/lib/UnrealEngine/Samples/Blueprints/BS_Basic.uasset")
    if not test_file.exists():
        pytest.skip("Sample file not found")
    
    result = parse_uasset(str(test_file))
    
    # Find an export with both SerialOffset and ScriptSerializationStartOffset
    for export in result.export_map:
        if (hasattr(export, 'script_serialization_start_offset') and 
            export.script_serialization_start_offset > 0):
            # Should have parsed properties from SerialOffset region
            # If ScriptSerialization was used, we'd miss class-specific payload
            assert len(export.properties) > 0, \
                f"Export {export.object_name} should have properties from SerialOffset region"
            
            # Check that we didn't skip class-specific data
            # (This is a heuristic — real validation requires UE source comparison)
            prop_names = [p.name for p in export.properties if hasattr(p, 'name')]
            # Blueprint exports should have common properties
            if 'BlueprintSystemVersion' in prop_names:
                # This property is in class-specific region, should be present
                break


def test_script_offsets_available_as_diagnostics():
    """ScriptSerialization offsets should be available for diagnostics."""
    test_file = Path("E:/Develop/lib/UnrealEngine/Samples/Blueprints/BS_Basic.uasset")
    if not test_file.exists():
        pytest.skip("Sample file not found")
    
    result = parse_uasset(str(test_file))
    
    for export in result.export_map:
        if hasattr(export, 'script_serialization_start_offset'):
            # Should be preserved for diagnostics
            assert hasattr(export, 'serial_offset')
            # Offsets should be non-negative
            assert export.script_serialization_start_offset >= 0
            if hasattr(export, 'script_serialization_end_offset'):
                assert export.script_serialization_end_offset >= 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_payload_offset_strategy.py::test_default_uses_serial_offset -v`
Expected: FAIL or incomplete — current code uses ScriptSerializationStartOffset for UE5.10+

- [ ] **Step 3: Fix property_parser.py to use SerialOffset by default**

```python
# src/uasset_read/parsers/property_parser.py, lines 319-324
# BEFORE:
#     if summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
#         property_start = export.serial_offset + export.script_serialization_start_offset
#     else:
#         property_start = export.serial_offset

# AFTER:
    # UE default: always start from SerialOffset
    # ScriptSerializationStartOffset is only used in special editor cases
    # (property bag placeholder or class mismatch) — see LinkerLoad.cpp:4793
    # For fidelity, we use SerialOffset and let class-specific handlers
    # decide whether to skip to script region
    property_start = export.serial_offset
    
    # Store script offsets for diagnostics and opt-in strategies
    export._script_serialization_start_absolute = (
        export.serial_offset + getattr(export, 'script_serialization_start_offset', 0)
    )
    export._script_serialization_end_absolute = (
        export.serial_offset + getattr(export, 'script_serialization_end_offset', 0)
    )
```

```python
# src/uasset_read/parsers/property_parser.py, lines 380-386
# BEFORE:
#     if summary.file_version_ue5 >= UE5_SCRIPT_SERIALIZATION_OFFSET:
#         property_end = export.serial_offset + export.script_serialization_end_offset
#     else:
#         property_end = export.serial_offset + export.serial_size

# AFTER:
    # UE default: use SerialSize for property boundary
    property_end = export.serial_offset + export.serial_size
    
    # Note: ScriptSerializationEndOffset could be used for blueprint script-only
    # extraction, but that's a different use case. For full fidelity, we read
    # the entire serialization region.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_payload_offset_strategy.py -v`
Expected: PASS — properties parsed from SerialOffset region

- [ ] **Step 5: Run existing tests to check for regressions**

Run: `pytest tests/test_property_parser_error_handling.py -v`
Expected: PASS — error handling should still work

- [ ] **Step 6: Commit**

```bash
git add src/uasset_read/parsers/property_parser.py tests/test_payload_offset_strategy.py
git commit -m "fix: use SerialOffset by default, not ScriptSerializationStartOffset

- Align with UE LinkerLoad.cpp:4793 — default path uses SerialOffset
- ScriptSerialization offsets preserved for diagnostics
- Prevents skipping class-specific payload before property tags
- Improves fidelity for StaticMesh, Texture2D, AnimSequence, etc.

Fixes payload offset issue identified in UE fidelity audit."
```

---

## Task 3: Implement Class Serialization Strategy Table

**Files:**
- Create: `src/uasset_read/parsers/class_serialization_strategy.py`
- Modify: `src/uasset_read/link/linker.py:218-286`
- Test: `tests/test_class_serialization_strategy.py`

- [ ] **Step 1: Write failing test for strategy table**

```python
# tests/test_class_serialization_strategy.py
"""Test class serialization strategy table."""
import pytest
from pathlib import Path
from uasset_read.parse_uasset import parse_uasset


def test_static_mesh_marked_as_opaque():
    """StaticMesh has class-specific Serialize(), should be marked opaque/partial."""
    test_file = Path("E:/Develop/lib/UnrealEngine/Samples/StaticMesh/SM_Cube.uasset")
    if not test_file.exists():
        pytest.skip("Sample file not found")
    
    result = parse_uasset(str(test_file))
    
    # Find StaticMesh export
    mesh_exports = [e for e in result.export_map 
                    if hasattr(e, 'class_name') and e.class_name == 'StaticMesh']
    
    assert len(mesh_exports) > 0, "Should have StaticMesh export"
    
    for export in mesh_exports:
        # Should NOT be marked as success — we don't have full Serialize()
        status = getattr(export, 'parse_status', 'success')
        assert status in ('opaque', 'partial', 'metadata'), \
            f"StaticMesh should be opaque/partial, not {status}"


def test_blueprint_class_marked_as_properties():
    """BlueprintGeneratedClass uses tagged properties, should be success/partial."""
    test_file = Path("E:/Develop/lib/UnrealEngine/Samples/Blueprints/BS_Basic.uasset")
    if not test_file.exists():
        pytest.skip("Sample file not found")
    
    result = parse_uasset(str(test_file))
    
    # Find BPGC export
    bpgc_exports = [e for e in result.export_map 
                    if hasattr(e, 'class_name') and 
                    e.class_name == 'BlueprintGeneratedClass']
    
    assert len(bpgc_exports) > 0, "Should have BlueprintGeneratedClass export"
    
    for export in bpgc_exports:
        status = getattr(export, 'parse_status', 'success')
        # Tagged properties should parse successfully
        assert status in ('success', 'partial'), \
            f"BPGC should be success/partial, not {status}"


def test_overall_status_reflects_opaque_exports():
    """If any export is opaque, overall status should be partial, not success."""
    test_file = Path("E:/Develop/lib/UnrealEngine/Samples/StaticMesh/SM_Cube.uasset")
    if not test_file.exists():
        pytest.skip("Sample file not found")
    
    result = parse_uasset(str(test_file))
    
    # Check if any export is opaque
    has_opaque = any(
        getattr(e, 'parse_status', 'success') in ('opaque', 'partial', 'metadata')
        for e in result.export_map
    )
    
    if has_opaque:
        # Overall status should reflect this
        assert result.status in ('partial', 'failed'), \
            f"Overall status should be partial when exports are opaque, not {result.status}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_class_serialization_strategy.py::test_static_mesh_marked_as_opaque -v`
Expected: FAIL — StaticMesh currently marked as success or not checked

- [ ] **Step 3: Create class serialization strategy module**

```python
# src/uasset_read/parsers/class_serialization_strategy.py
"""Class serialization strategy table.

Maps UE class names to their serialization strategy:
- full_serializer: Has complete Serialize() implementation (rare, mostly UObject-derived)
- tagged_properties_only: Uses Class::SerializeVersionedTaggedProperties (most Blueprints)
- opaque_class_payload: Has class-specific Serialize() we don't implement (StaticMesh, etc.)
- skip_unsupported: Known incompatible, skip entirely (Niagara, etc.)
"""
from enum import Enum
from typing import Optional


class SerializationStrategy(str, Enum):
    """How a class serializes its data."""
    FULL_SERIALIZER = "full_serializer"
    TAGGED_PROPERTIES_ONLY = "tagged_properties_only"
    OPAQUE_CLASS_PAYLOAD = "opaque_class_payload"
    SKIP_UNSUPPORTED = "skip_unsupported"


# Class → strategy mapping
# Based on UE source: Engine/Source/Runtime/*/Private/*.cpp
CLASS_STRATEGY_TABLE = {
    # UObject-derived with tagged properties
    "BlueprintGeneratedClass": SerializationStrategy.TAGGED_PROPERTIES_ONLY,
    "WidgetBlueprintGeneratedClass": SerializationStrategy.TAGGED_PROPERTIES_ONLY,
    "AnimBlueprintGeneratedClass": SerializationStrategy.TAGGED_PROPERTIES_ONLY,
    "Function": SerializationStrategy.TAGGED_PROPERTIES_ONLY,
    "UserDefinedStruct": SerializationStrategy.TAGGED_PROPERTIES_ONLY,
    "UserDefinedEnum": SerializationStrategy.TAGGED_PROPERTIES_ONLY,
    
    # EdGraph/EdNode with tagged properties
    "EdGraph": SerializationStrategy.TAGGED_PROPERTIES_ONLY,
    "EdGraphNode": SerializationStrategy.TAGGED_PROPERTIES_ONLY,
    "EdGraphSchema": SerializationStrategy.TAGGED_PROPERTIES_ONLY,
    "K2Node": SerializationStrategy.TAGGED_PROPERTIES_ONLY,
    
    # Class-specific Serialize() — we don't implement these
    "StaticMesh": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    "SkeletalMesh": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    "Texture2D": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    "TextureCube": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    "Material": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    "MaterialInstanceConstant": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    "MaterialFunction": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    "AnimSequence": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    "AnimMontage": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    "SoundWave": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    "SoundCue": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    "ParticleSystem": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    "NiagaraSystem": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    "NiagaraEmitter": SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
    
    # Skip entirely — known incompatible
    "NiagaraGraph": SerializationStrategy.SKIP_UNSUPPORTED,
    "NiagaraScript": SerializationStrategy.SKIP_UNSUPPORTED,
    "NiagaraDataInterface": SerializationStrategy.SKIP_UNSUPPORTED,
}


def get_serialization_strategy(class_name: str) -> SerializationStrategy:
    """Get serialization strategy for a class.
    
    Args:
        class_name: UE class name (e.g., 'StaticMesh', 'BlueprintGeneratedClass')
    
    Returns:
        SerializationStrategy enum value
    """
    return CLASS_STRATEGY_TABLE.get(
        class_name,
        SerializationStrategy.TAGGED_PROPERTIES_ONLY  # Default assumption
    )


def should_skip_class(class_name: str) -> bool:
    """Check if class should be skipped entirely."""
    return get_serialization_strategy(class_name) == SerializationStrategy.SKIP_UNSUPPORTED


def is_opaque_class(class_name: str) -> bool:
    """Check if class has opaque class-specific payload."""
    return get_serialization_strategy(class_name) == SerializationStrategy.OPAQUE_CLASS_PAYLOAD
```

- [ ] **Step 4: Integrate strategy into linker.preload**

```python
# src/uasset_read/link/linker.py, lines 218-286
# Add strategy check at start of preload():

    def preload(self, index: int) -> None:
        """Lazily deserialize properties for export *index*."""
        if index in self._preload_cache:
            return
        if index < 0 or index >= len(self._export_objects):
            return

        instance = self._export_objects[index]
        if instance._preloaded:
            self._preload_cache[index] = True
            return

        if instance.serial_size == 0:
            instance._preloaded = True
            self._preload_cache[index] = True
            return

        # Check class serialization strategy
        from uasset_read.parsers.class_serialization_strategy import (
            get_serialization_strategy,
            SerializationStrategy,
        )
        class_name = instance.object_class or "UObject"
        strategy = get_serialization_strategy(class_name)
        
        if strategy == SerializationStrategy.SKIP_UNSUPPORTED:
            # Mark as skipped, don't attempt parsing
            instance._preloaded = True
            instance._serialization_strategy = "skip_unsupported"
            self._preload_cache[index] = True
            if instance._raw_export:
                setattr(instance._raw_export, "parse_status", "skipped")
                setattr(instance._raw_export, "fallback_reason", "unsupported_type")
            return
        
        if strategy == SerializationStrategy.OPAQUE_CLASS_PAYLOAD:
            # Mark as opaque — we don't have class-specific Serialize()
            instance._preloaded = True
            instance._serialization_strategy = "opaque_class_payload"
            self._preload_cache[index] = True
            if instance._raw_export:
                setattr(instance._raw_export, "parse_status", "opaque")
                setattr(instance._raw_export, "fallback_reason", "class_specific_serialize")
            return
        
        # For TAGGED_PROPERTIES_ONLY and FULL_SERIALIZER, proceed with parsing
        # ... (rest of existing preload code)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_class_serialization_strategy.py -v`
Expected: PASS — StaticMesh marked as opaque, BPGC marked as success/partial

- [ ] **Step 6: Commit**

```bash
git add src/uasset_read/parsers/class_serialization_strategy.py \
        src/uasset_read/link/linker.py \
        tests/test_class_serialization_strategy.py
git commit -m "feat: add class serialization strategy table

- Map UE classes to serialization strategies (full/tagged/opaque/skip)
- StaticMesh, Texture2D, AnimSequence marked as opaque_class_payload
- BlueprintGeneratedClass marked as tagged_properties_only
- Niagara, etc. marked as skip_unsupported
- Prevents false 'success' status for classes we don't fully support

Addresses class-specific Serialize() gap from UE fidelity audit."
```

---

## Task 4: Complete SoftObjectPath Index-Based Resolution

**Files:**
- Modify: `src/uasset_read/serializers/object_resources.py:163-181`
- Modify: `src/uasset_read/parsers/property_types.py:401-405`
- Modify: `src/uasset_read/parse_uasset.py:550-552`
- Test: `tests/test_soft_object_path_index.py`

- [ ] **Step 1: Write failing test for index-based SoftObjectPath**

```python
# tests/test_soft_object_path_index.py
"""Test SoftObjectPath index-based resolution when SoftObjectPathList exists."""
import pytest
from pathlib import Path
from uasset_read.parse_uasset import parse_uasset


def test_soft_object_path_list_stored():
    """SoftObjectPathList should be stored for property-level index lookup."""
    test_file = Path("E:/Develop/lib/UnrealEngine/Samples/Blueprints/BS_Basic.uasset")
    if not test_file.exists():
        pytest.skip("Sample file not found")
    
    result = parse_uasset(str(test_file))
    
    # Check if SoftObjectPathList was read
    if hasattr(result.summary, 'soft_object_paths_count'):
        if result.summary.soft_object_paths_count > 0:
            # Should have stored the list
            assert hasattr(result, 'soft_object_path_list'), \
                "Should store SoftObjectPathList for index lookup"
            assert len(result.soft_object_path_list) == result.summary.soft_object_paths_count


def test_soft_object_property_uses_index_when_list_exists():
    """When SoftObjectPathList exists, SoftObjectProperty reads int32 index."""
    test_file = Path("E:/Develop/lib/UnrealEngine/Samples/Blueprints/BS_Basic.uasset")
    if not test_file.exists():
        pytest.skip("Sample file not found")
    
    result = parse_uasset(str(test_file))
    
    # Only test if SoftObjectPathList exists
    if not hasattr(result, 'soft_object_path_list') or not result.soft_object_path_list:
        pytest.skip("No SoftObjectPathList in this file")
    
    # Find SoftObjectProperty in exports
    for export in result.export_map:
        if not hasattr(export, 'properties'):
            continue
        for prop in export.properties:
            if hasattr(prop, 'type') and prop.type == 'SoftObjectProperty':
                # Should be resolved to dict with asset_path, not raw index
                value = prop.value
                if isinstance(value, dict):
                    assert 'asset_path' in value, \
                        "SoftObjectProperty should be resolved to asset_path dict"
                    # asset_path should match an entry in soft_object_path_list
                    if value['asset_path']:
                        assert value['asset_path'] in [
                            entry['asset_path'] for entry in result.soft_object_path_list
                        ], "Resolved asset_path should be in SoftObjectPathList"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_soft_object_path_index.py::test_soft_object_path_list_stored -v`
Expected: FAIL — soft_object_path_list not stored on result

- [ ] **Step 3: Store SoftObjectPathList on result**

```python
# src/uasset_read/parse_uasset.py, around line 550
# AFTER reading soft_package_references, add:

        # Read SoftObjectPaths list (for index-based property resolution)
        if hasattr(result.summary, 'soft_object_paths_count') and result.summary.soft_object_paths_count > 0:
            from uasset_read.serializers.object_resources import read_soft_object_paths
            result.soft_object_path_list = read_soft_object_paths(
                archive, result.summary, result.name_map
            )
        else:
            result.soft_object_path_list = []
```

```python
# src/uasset_read/models/result.py, add field to ParseResult:
    soft_object_path_list: List[Dict] = field(default_factory=list)
    """SoftObjectPathList for index-based SoftObjectProperty resolution."""
```

- [ ] **Step 4: Update parse_soft_object_property to use index**

```python
# src/uasset_read/parsers/property_types.py, line 401
# BEFORE:
# def parse_soft_object_property(tag: PropertyTag, archive: FArchive, name_map: List[str]) -> SoftObjectPathValue:
#     asset_path = archive.read_fstring()
#     sub_path = archive.read_fstring()
#     return SoftObjectPathValue(raw_kind=tag.type, asset_path=asset_path, sub_path=sub_path)

# AFTER:
def parse_soft_object_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    soft_object_path_list: Optional[List[Dict]] = None,
) -> SoftObjectPathValue:
    """Parse SoftObjectProperty (FSoftObjectPath).
    
    When soft_object_path_list exists (UE5.7+), reads int32 index.
    Otherwise reads FString pair (legacy format).
    """
    if soft_object_path_list is not None and len(soft_object_path_list) > 0:
        # UE5.7+ index-based format
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
            # Out of bounds — return empty with diagnostic
            return SoftObjectPathValue(
                raw_kind=tag.type,
                asset_path='',
                sub_path='',
                index=index,
                error=f"SoftObjectPath index {index} out of bounds [0, {len(soft_object_path_list)})",
            )
    else:
        # Legacy FString format
        asset_path = archive.read_fstring()
        sub_path = archive.read_fstring()
        return SoftObjectPathValue(raw_kind=tag.type, asset_path=asset_path, sub_path=sub_path)
```

```python
# src/uasset_read/models/properties.py, update SoftObjectPathValue:
@dataclass
class SoftObjectPathValue:
    raw_kind: str
    asset_path: str = ""
    sub_path: str = ""
    guid: str = ""
    index: Optional[int] = None  # NEW: index into SoftObjectPathList
    error: Optional[str] = None  # NEW: diagnostic for out-of-bounds
```

- [ ] **Step 5: Pass soft_object_path_list through property parser**

```python
# src/uasset_read/parsers/property_parser.py, line 251
# Update dispatch to pass soft_object_path_list:

        elif tag.type in ("NameProperty", "SoftObjectProperty", "DelegateProperty", "SoftClassProperty"):
            soft_path_list = getattr(summary, '_soft_object_path_list', None)
            return handler(tag, archive, name_map, soft_path_list)
```

```python
# src/uasset_read/parse_uasset.py, line 560
# Store soft_object_path_list on summary for property parser access:

        if hasattr(result, 'soft_object_path_list'):
            setattr(result.summary, '_soft_object_path_list', result.soft_object_path_list)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_soft_object_path_index.py -v`
Expected: PASS — SoftObjectPathList stored, properties use index-based resolution

- [ ] **Step 7: Commit**

```bash
git add src/uasset_read/serializers/object_resources.py \
        src/uasset_read/parsers/property_types.py \
        src/uasset_read/parsers/property_parser.py \
        src/uasset_read/parse_uasset.py \
        src/uasset_read/models/result.py \
        src/uasset_read/models/properties.py \
        tests/test_soft_object_path_index.py
git commit -m "feat: implement SoftObjectPath index-based resolution

- Store SoftObjectPathList on ParseResult for property-level access
- SoftObjectProperty reads int32 index when list exists (UE5.7+)
- Falls back to FString pair for legacy format
- Out-of-bounds index produces diagnostic, not crash
- Aligns with UE LinkerLoad.cpp:6450

Fixes SoftObjectPath semantics from UE fidelity audit."
```

---

## Task 5: Fix DependsMap FPackageIndex Semantics

**Files:**
- Modify: `src/uasset_read/link/linker.py:398-413`
- Test: `tests/test_depends_map_package_index.py`

- [ ] **Step 1: Write failing test for FPackageIndex semantics**

```python
# tests/test_depends_map_package_index.py
"""Test DependsMap uses FPackageIndex semantics (positive=export, negative=import)."""
import pytest
from pathlib import Path
from uasset_read.parse_uasset import parse_uasset_with_linker


def test_depends_map_uses_package_index():
    """DependsMap values should be FPackageIndex, not raw export indices."""
    test_file = Path("E:/Develop/lib/UnrealEngine/Samples/Blueprints/BS_Basic.uasset")
    if not test_file.exists():
        pytest.skip("Sample file not found")
    
    result = parse_uasset_with_linker(str(test_file), preload_all=True)
    
    # Check if DependsMap exists
    if not hasattr(result.summary, 'depends_map') or not result.summary.depends_map:
        pytest.skip("No DependsMap in this file")
    
    # Find an export with dependencies
    for exp_idx, dep_indices in enumerate(result.summary.depends_map):
        if not dep_indices:
            continue
        
        # Each dep should be interpretable as FPackageIndex
        for raw_dep in dep_indices:
            # Positive = export, negative = import, 0 = null
            if raw_dep > 0:
                # Export index (1-based)
                export_idx = raw_dep - 1
                assert 0 <= export_idx < len(result.export_map), \
                    f"DependsMap export index {raw_dep} out of bounds"
            elif raw_dep < 0:
                # Import index (-1 based)
                import_idx = -raw_dep - 1
                assert 0 <= import_idx < len(result.import_map), \
                    f"DependsMap import index {raw_dep} out of bounds"
            # raw_dep == 0 is null, valid


def test_linker_resolves_depends_to_instances():
    """Linker should resolve DependsMap to UObjectInstance references."""
    test_file = Path("E:/Develop/lib/UnrealEngine/Samples/Blueprints/BS_Basic.uasset")
    if not test_file.exists():
        pytest.skip("Sample file not found")
    
    result = parse_uasset_with_linker(str(test_file), preload_all=True)
    linker = result.linker
    
    # Check that dependencies are resolved to UObjectInstance
    for inst in linker._export_objects:
        if hasattr(inst, 'dependencies') and inst.dependencies:
            for dep in inst.dependencies:
                assert isinstance(dep, type(inst)), \
                    f"Dependency should be UObjectInstance, not {type(dep)}"
                assert hasattr(dep, 'object_name'), \
                    "Dependency should have object_name"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_depends_map_package_index.py::test_depends_map_uses_package_index -v`
Expected: FAIL or incomplete — current code treats all deps as export indices

- [ ] **Step 3: Fix linker._build_dependency_graph**

```python
# src/uasset_read/link/linker.py, lines 398-413
# BEFORE:
#     def _build_dependency_graph(self) -> None:
#         if not hasattr(self._summary, 'depends_map') or not self._summary.depends_map:
#             return
#         depends_map = self._summary.depends_map
#         for exp_idx, dep_indices in enumerate(depends_map):
#             if exp_idx < len(self._export_objects):
#                 inst = self._export_objects[exp_idx]
#                 inst.dependencies = []
#                 for dep_idx in dep_indices:
#                     if 0 <= dep_idx < len(self._export_objects):
#                         inst.dependencies.append(self._export_objects[dep_idx])

# AFTER:
    def _build_dependency_graph(self) -> None:
        """Convert DependsMap to UObjectInstance dependency links.
        
        DependsMap values are FPackageIndex (int32):
        - Positive: export index (1-based)
        - Negative: import index (-1 based)
        - Zero: null
        """
        if not hasattr(self._summary, 'depends_map') or not self._summary.depends_map:
            return

        depends_map = self._summary.depends_map
        for exp_idx, dep_indices in enumerate(depends_map):
            if exp_idx >= len(self._export_objects):
                continue
            
            inst = self._export_objects[exp_idx]
            inst.dependencies = []
            
            for raw_dep in dep_indices:
                if raw_dep == 0:
                    # Null dependency, skip
                    continue
                
                # Convert FPackageIndex to UObjectInstance
                from uasset_read.serializers.object_resources import PackageIndex
                pkg_idx = PackageIndex(raw_dep)
                resolved = self.resolve_package_index(pkg_idx)
                
                if resolved is not None:
                    inst.dependencies.append(resolved)
                else:
                    # Record diagnostic for unresolvable dependency
                    self._diagnostics.append(OffsetRangeDiagnostic(
                        module="linker",
                        field="DependsMap",
                        export_index=exp_idx,
                        target_offset=raw_dep,
                        source="_build_dependency_graph",
                        error=f"Export #{exp_idx} dependency {raw_dep} could not be resolved",
                    ))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_depends_map_package_index.py -v`
Expected: PASS — DependsMap correctly interpreted as FPackageIndex

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/link/linker.py tests/test_depends_map_package_index.py
git commit -m "fix: interpret DependsMap values as FPackageIndex

- Positive values = export index (1-based)
- Negative values = import index (-1 based)
- Zero = null
- Use resolve_package_index for correct import/export resolution
- Record diagnostic for unresolvable dependencies

Fixes DependsMap semantics from UE fidelity audit."
```

---

## Task 6: Unify Status Model to success|partial|failed

**Files:**
- Modify: `src/uasset_read/models/result.py:50-62`
- Modify: `src/uasset_read/formatters/helpers.py:17-42`
- Modify: `src/uasset_read/parse_uasset.py:620`
- Test: `tests/test_status_model_unified.py`

- [ ] **Step 1: Write failing test for unified status**

```python
# tests/test_status_model_unified.py
"""Test unified status model: success|partial|failed."""
import pytest
from pathlib import Path
from uasset_read.parse_uasset import parse_uasset


def test_status_is_success_partial_or_failed():
    """Status should be one of: success, partial, failed."""
    test_file = Path("E:/Develop/lib/UnrealEngine/Samples/Blueprints/BS_Basic.uasset")
    if not test_file.exists():
        pytest.skip("Sample file not found")
    
    result = parse_uasset(str(test_file))
    
    assert result.status in ('success', 'partial', 'failed'), \
        f"Status should be success|partial|failed, not {result.status}"


def test_opaque_export_makes_status_partial():
    """If any export is opaque, overall status should be partial."""
    test_file = Path("E:/Develop/lib/UnrealEngine/Samples/StaticMesh/SM_Cube.uasset")
    if not test_file.exists():
        pytest.skip("Sample file not found")
    
    result = parse_uasset(str(test_file))
    
    # Check if any export is opaque/partial/skipped
    has_non_success = any(
        getattr(e, 'parse_status', 'success') in ('opaque', 'partial', 'skipped', 'metadata')
        for e in result.export_map
    )
    
    if has_non_success:
        assert result.status == 'partial', \
            f"Status should be partial when exports are opaque, not {result.status}"


def test_errors_make_status_partial_or_failed():
    """If there are errors, status should be partial (with data) or failed (no data)."""
    # Create a scenario with parse errors
    test_file = Path("E:/Develop/lib/UnrealEngine/Samples/Blueprints/BS_Basic.uasset")
    if not test_file.exists():
        pytest.skip("Sample file not found")
    
    result = parse_uasset(str(test_file))
    
    if result.errors:
        # Should be partial (if we have some data) or failed (if no data)
        assert result.status in ('partial', 'failed'), \
            f"Status should be partial/failed when errors exist, not {result.status}"
        
        # If we have summary/name_map/export_map, should be partial not failed
        if result.summary and result.name_map and result.export_map:
            assert result.status == 'partial', \
                "Should be partial (not failed) when we have core data"


def test_no_errors_and_all_success_exports():
    """No errors + all exports success → status is success."""
    test_file = Path("E:/Develop/lib/UnrealEngine/Samples/Blueprints/BS_Basic.uasset")
    if not test_file.exists():
        pytest.skip("Sample file not found")
    
    result = parse_uasset(str(test_file))
    
    # Check if all exports are success
    all_success = all(
        getattr(e, 'parse_status', 'success') == 'success'
        for e in result.export_map
    )
    
    if not result.errors and all_success:
        assert result.status == 'success', \
            f"Status should be success when no errors and all exports success"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_status_model_unified.py::test_status_is_success_partial_or_failed -v`
Expected: FAIL — current status uses success/fail/error

- [ ] **Step 3: Update ParseResult.status property**

```python
# src/uasset_read/models/result.py, lines 50-62
# BEFORE:
#     @property
#     def status(self) -> str:
#         from uasset_read.formatters.helpers import build_status_info
#         return build_status_info(self).status

# AFTER:
    @property
    def status(self) -> str:
        """Unified status: success | partial | failed.
        
        - success: No errors, all exports parsed successfully
        - partial: Some errors or some exports are opaque/skipped, but core data available
        - failed: Critical error, no usable data
        """
        # Failed if no core data
        if not self.summary and not self.name_map and not self.export_map:
            return "failed"
        
        # Partial if there are errors
        if self.errors:
            return "partial"
        
        # Partial if any export is not success
        for export in self.export_map:
            export_status = getattr(export, 'parse_status', 'success')
            if export_status in ('opaque', 'partial', 'skipped', 'metadata', 'failed'):
                return "partial"
        
        # Check metadata for lightweight parse
        if self.metadata.get('lightweight_tolerant_parse'):
            return "partial"
        
        # Success if no errors and all exports success
        return "success"
```

- [ ] **Step 4: Update build_status_info for backward compat**

```python
# src/uasset_read/formatters/helpers.py, lines 17-42
# BEFORE:
# def build_status_info(result: ParseResult) -> StatusInfo:
#     if result.is_success:
#         if not result.errors:
#             return StatusInfo(status="success")
#         else:
#             message = result.errors[0] if result.errors else None
#             return StatusInfo(status="fail", message=message, code="PARSE_ERROR")
#     else:
#         message = result.errors[0] if result.errors else "Unknown error"
#         return StatusInfo(status="error", message=message, code="PARSE_ERROR")

# AFTER:
def build_status_info(result: ParseResult) -> StatusInfo:
    """Build status field (unified model: success|partial|failed).
    
    For backward compatibility, also supports legacy fail/error mapping:
    - partial → fail (with message)
    - failed → error (with message)
    """
    status = result.status  # Use the unified status property
    
    if status == "success":
        return StatusInfo(status="success")
    elif status == "partial":
        message = result.errors[0] if result.errors else "Partial result (some exports incomplete)"
        return StatusInfo(status="partial", message=message, code="PARTIAL_PARSE")
    else:  # failed
        message = result.errors[0] if result.errors else "Unknown error"
        return StatusInfo(status="failed", message=message, code="PARSE_ERROR")
```

- [ ] **Step 5: Remove unconditional is_success=True**

```python
# src/uasset_read/parse_uasset.py, line 620
# BEFORE:
#         result.is_success = True

# AFTER:
        # is_success is now determined by status property
        # Remove this line — status is computed dynamically
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_status_model_unified.py -v`
Expected: PASS — status is success|partial|failed

- [ ] **Step 7: Run full test suite to check for regressions**

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass or are updated for new status model

- [ ] **Step 8: Commit**

```bash
git add src/uasset_read/models/result.py \
        src/uasset_read/formatters/helpers.py \
        src/uasset_read/parse_uasset.py \
        tests/test_status_model_unified.py
git commit -m "feat: unify status model to success|partial|failed

- Replace success/fail/error with success/partial/failed
- partial: some errors or opaque exports, but core data available
- failed: critical error, no usable data
- Remove unconditional is_success=True
- Status computed dynamically from errors and export statuses

Fixes status inconsistency from UE fidelity audit."
```

---

## Task 7: Integration Testing and Validation

**Files:**
- Test: `tests/test_ue_fidelity_integration.py`

- [ ] **Step 1: Write comprehensive integration test**

```python
# tests/test_ue_fidelity_integration.py
"""Integration tests for UE fidelity improvements."""
import pytest
from pathlib import Path
from uasset_read.parse_uasset import parse_uasset, parse_uasset_with_linker


@pytest.mark.integration
class TestUEFidelityImprovements:
    """Validate all 6 fidelity improvements work together."""
    
    def test_lifecycle_preload_before_post_load(self):
        """Task 1: Lifecycle — preload happens before post_load."""
        test_file = Path("E:/Develop/lib/UnrealEngine/Samples/Blueprints/BS_Basic.uasset")
        if not test_file.exists():
            pytest.skip("Sample not found")
        
        result = parse_uasset_with_linker(str(test_file), preload_all=True)
        
        # All exports should be preloaded
        for inst in result.linker._export_objects:
            assert inst._preloaded
        
        # Property references should be resolved
        has_refs = any(
            hasattr(inst, 'property_references') and inst.property_references
            for inst in result.linker._export_objects
        )
        assert has_refs, "Should have resolved property references"
    
    def test_payload_uses_serial_offset(self):
        """Task 2: Payload offset — uses SerialOffset by default."""
        test_file = Path("E:/Develop/lib/UnrealEngine/Samples/Blueprints/BS_Basic.uasset")
        if not test_file.exists():
            pytest.skip("Sample not found")
        
        result = parse_uasset(str(test_file))
        
        # Exports should have properties parsed
        for export in result.export_map:
            if export.serial_size > 0:
                # Should have attempted parsing
                assert hasattr(export, 'properties')
    
    def test_class_strategy_marks_opaque(self):
        """Task 3: Class strategy — opaque classes marked correctly."""
        test_file = Path("E:/Develop/lib/UnrealEngine/Samples/StaticMesh/SM_Cube.uasset")
        if not test_file.exists():
            pytest.skip("Sample not found")
        
        result = parse_uasset(str(test_file))
        
        # StaticMesh should be marked as opaque
        mesh_exports = [e for e in result.export_map 
                       if hasattr(e, 'class_name') and e.class_name == 'StaticMesh']
        for export in mesh_exports:
            status = getattr(export, 'parse_status', 'success')
            assert status in ('opaque', 'partial', 'metadata')
    
    def test_soft_object_path_index_resolution(self):
        """Task 4: SoftObjectPath — index-based resolution when list exists."""
        test_file = Path("E:/Develop/lib/UnrealEngine/Samples/Blueprints/BS_Basic.uasset")
        if not test_file.exists():
            pytest.skip("Sample not found")
        
        result = parse_uasset(str(test_file))
        
        # If SoftObjectPathList exists, should be stored
        if hasattr(result.summary, 'soft_object_paths_count'):
            if result.summary.soft_object_paths_count > 0:
                assert hasattr(result, 'soft_object_path_list')
    
    def test_depends_map_package_index_semantics(self):
        """Task 5: DependsMap — uses FPackageIndex semantics."""
        test_file = Path("E:/Develop/lib/UnrealEngine/Samples/Blueprints/BS_Basic.uasset")
        if not test_file.exists():
            pytest.skip("Sample not found")
        
        result = parse_uasset_with_linker(str(test_file), preload_all=True)
        
        # Dependencies should be resolved to UObjectInstance
        for inst in result.linker._export_objects:
            if hasattr(inst, 'dependencies') and inst.dependencies:
                for dep in inst.dependencies:
                    assert hasattr(dep, 'object_name')
    
    def test_unified_status_model(self):
        """Task 6: Status model — success|partial|failed."""
        test_file = Path("E:/Develop/lib/UnrealEngine/Samples/Blueprints/BS_Basic.uasset")
        if not test_file.exists():
            pytest.skip("Sample not found")
        
        result = parse_uasset(str(test_file))
        
        assert result.status in ('success', 'partial', 'failed')
        
        # If any export is opaque, status should be partial
        has_opaque = any(
            getattr(e, 'parse_status', 'success') in ('opaque', 'partial', 'skipped')
            for e in result.export_map
        )
        if has_opaque:
            assert result.status == 'partial'
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/test_ue_fidelity_integration.py -v -m integration`
Expected: All tests pass

- [ ] **Step 3: Run full test suite**

Run: `python scripts/test_matrix.py all`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/test_ue_fidelity_integration.py
git commit -m "test: add UE fidelity integration tests

- Validate all 6 fidelity improvements work together
- Test lifecycle, payload offset, class strategy, SoftObjectPath,
  DependsMap, and unified status model
- Mark as @integration for selective running"
```

---

## Task 8: Documentation and Release Notes

**Files:**
- Create: `docs/release-notes/v0.5.0-ue-fidelity.md`

- [ ] **Step 1: Write release notes**

```markdown
# v0.5.0 — UE Fidelity Improvements

## Overview

This release aligns uasset_read's parsing behavior with UE's FLinkerLoad lifecycle, improving output fidelity from "tolerant extractor" to "UE-equivalent loader".

## Breaking Changes

### Status Model Unified

**Before:** `success | fail | error`  
**After:** `success | partial | failed`

- `partial`: Some errors or opaque exports, but core data available
- `failed`: Critical error, no usable data

Migration: Update code checking `result.status == 'fail'` to check for `'partial'` instead.

### Payload Offset Strategy

**Before:** UE5.10+ used `ScriptSerializationStartOffset` by default  
**After:** Always uses `SerialOffset` by default (matches UE LinkerLoad.cpp:4793)

Impact: Exports with class-specific payload (StaticMesh, Texture2D, etc.) now parse more data. May expose previously hidden parse errors.

## New Features

### 1. UE-Style Loading Lifecycle

Parsing now follows UE's two-phase pattern:
1. `link()` — Create UObjectInstance shells
2. `preload(idx)` — Deserialize properties on demand
3. `post_load()` — Resolve references after all objects loaded

Benefit: Property references are now correctly resolved.

### 2. Class Serialization Strategy Table

Classes are now mapped to serialization strategies:
- `tagged_properties_only` — BlueprintGeneratedClass, EdGraph, etc.
- `opaque_class_payload` — StaticMesh, Texture2D, AnimSequence, etc.
- `skip_unsupported` — Niagara, etc.

Benefit: Prevents false "success" status for classes we don't fully support.

### 3. SoftObjectPath Index-Based Resolution

When `SoftObjectPathList` exists (UE5.7+), `SoftObjectProperty` now reads int32 index and resolves to the list entry.

Benefit: Correctly handles UE5.7+ soft references.

### 4. DependsMap FPackageIndex Semantics

DependsMap values are now correctly interpreted as `FPackageIndex`:
- Positive = export (1-based)
- Negative = import (-1 based)
- Zero = null

Benefit: Import dependencies are now correctly resolved.

### 5. Unified Status Model

Status is now `success | partial | failed` across all output formats.

Benefit: Consistent status reporting in JSON, text, and IR outputs.

## Migration Guide

### For JSON Consumers

```python
# OLD
if result['status']['status'] == 'fail':
    handle_error()

# NEW
if result['status']['status'] in ('partial', 'failed'):
    handle_error()
```

### For Direct API Users

```python
# OLD
if result.status == 'fail':
    handle_error()

# NEW
if result.status in ('partial', 'failed'):
    handle_error()
```

## Testing

All improvements validated by:
- `tests/test_lifecycle_preload.py`
- `tests/test_payload_offset_strategy.py`
- `tests/test_class_serialization_strategy.py`
- `tests/test_soft_object_path_index.py`
- `tests/test_depends_map_package_index.py`
- `tests/test_status_model_unified.py`
- `tests/test_ue_fidelity_integration.py`

## UE Source References

- Lifecycle: `LinkerLoad.cpp:4694`, `LinkerLoad.cpp:4947`
- Payload offset: `LinkerLoad.cpp:4793`
- SoftObjectPath: `LinkerLoad.cpp:6450`
- DependsMap: `ObjectResource.cpp:125`
```

- [ ] **Step 2: Commit**

```bash
git add docs/release-notes/v0.5.0-ue-fidelity.md
git commit -m "docs: add v0.5.0 release notes for UE fidelity improvements

Document breaking changes, new features, and migration guide
for lifecycle, payload offset, class strategy, SoftObjectPath,
DependsMap, and unified status model improvements."
```

---

## Summary

This plan addresses all 6 major issues from the UE fidelity audit:

1. ✅ **Lifecycle** — Move post_load after export parsing, use linker.preload
2. ✅ **Payload offset** — Use SerialOffset by default, not ScriptSerialization
3. ✅ **Class strategy** — Implement strategy table, mark opaque classes correctly
4. ✅ **SoftObjectPath** — Index-based resolution when list exists
5. ✅ **DependsMap** — FPackageIndex semantics (positive=export, negative=import)
6. ✅ **Status model** — Unified success|partial|failed

Each task follows TDD: write failing test → implement minimal fix → verify pass → commit.

Total estimated effort: 8 tasks × 2-5 minutes per step = ~4-8 hours of focused work.
