---
phase: 72g
plan: 01
type: execute
wave: 4
depends_on: []
files_modified:
  - src/uasset_read/serializers/graph.py
  - src/uasset_read/graph/flow_builder.py
  - src/uasset_read/parsers/property_types.py
  - src/uasset_read/blueprint/variable_extractor.py
  - tests/test_phase72g_connections.py
  - tests/test_phase72g_struct_parsing.py
autonomous: true
requirements:
  - M-01
  - M-02
  - M-03
  - M-04
user_setup: []

must_haves:
  truths:
    - "RelativeLocation/RelativeRotation extracted as structured {X,Y,Z}/{Pitch,Yaw,Roll}"
    - "EventGraph connections array non-empty (connections > 0)"
    - "Blueprint.functions contains Move/Aim/JumpStart/JumpEnd"
    - "Each function output includes parameters list (name + type)"
  artifacts:
    - path: "src/uasset_read/parsers/property_types.py"
      provides: "Vector/Rotator fast-path parsing"
      contains: "struct_type == 'Vector' / 'Rotator' direct float reads"
    - path: "src/uasset_read/graph/flow_builder.py"
      provides: "connections output with linked_to_raw validation"
      contains: "linked_to_count check, build_connections_map output"
    - path: "src/uasset_read/blueprint/variable_extractor.py"
      provides: "BPGC property extraction path for functions"
      contains: "UbergraphFunction/FunctionList extraction"
    - path: "tests/test_phase72g_connections.py"
      provides: "Regression test for connections output"
      exports: ["test_linked_to_validation", "test_connections_non_empty"]
  key_links:
    - from: "graph/flow_builder.py::build_connections_map"
      to: "serializers/graph.py::read_pin_array"
      via: "linked_to_raw data from UEdGraphPin"
      pattern: "linked_to_raw"
    - from: "parsers/property_types.py::parse_struct_property"
      to: "archive.py::read_f32"
      via: "Vector/Rotator direct reads"
      pattern: "read_f32()"
---

<objective>
Fix 4 recurring parsing failures in BP_FirstPersonCharacter.uasset parsing (M-01 through M-04), verified through CUE4Parse source analysis and UE C++ verification. Increase coverage from ~56% to >90%.

Purpose: Complex StructProperty (Vector/Rotator) parsing fails, EventGraph connections output is empty, Blueprint.functions list is empty, and function parameters are missing. All issues have root causes verified via CUE4Parse FScriptStruct.cs, UEdGraphPin.cs, and UE BodyInstance.cpp source code comparison.

Output: 4 waves of fixes with regression tests, targeting connections non-empty, struct extraction, functions list, and parameters.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/phase-72g/RESEARCH.md
@.planning/PROJECT.md
@.planning/ROADMAP.md

<interfaces>
From CUE4Parse FScriptStruct.cs (Line 174-178):
```csharp
"Vector" => type == ReadType.ZERO ? new FVector() : new FVector(Ar),
"Rotator" => type == ReadType.ZERO ? new FRotator() : new FRotator(Ar),
```

From CUE4Parse FVector.cs (Line 54-59):
```csharp
public FVector(FArchive Ar)
{
    X = Ar.ReadFReal();  // float
    Y = Ar.ReadFReal();
    Z = Ar.ReadFReal();
}
```

From CUE4Parse UEdGraphPin.cs (Line 86):
```csharp
SerializePinArray(Ar, ref LinkedTo, this, EPinResolveType.LinkedTo);
```

From src/uasset_read/serializers/graph.py (Line 461-468):
```python
linkedto_start = archive.tell()
try:
    linked_to = read_pin_array(archive, name_map, export_map, import_map, linker)
except Exception:
    linked_to = []  # ⚠️ Silent failure
```

From src/uasset_read/graph/flow_builder.py (Line 657):
```python
for linked_pin_ref in (pin.linked_to_raw or []):  # ⚠️ No validation
```

From src/uasset_read/blueprint/variable_extractor.py (Line 489):
```python
functions = _extract_functions_from_graphs(graphs) if graphs else []  # ⚠️ Fallback only
```
</interfaces>
</context>

<tasks>

<task type="auto" wave="1">
  <name>Wave 1: M-02 LinkedTo Validation + Non-empty Check</name>
  <files>
    - src/uasset_read/serializers/graph.py
    - src/uasset_read/graph/flow_builder.py
    - tests/test_phase72g_connections.py
  </files>
  <behavior>
    - Add validation logging in read_pin_array() when LinkedTo read fails
    - Add linked_to_count non-empty check warning in build_connections_map()
    - Create test verifying linked_to_raw is populated for BP_FirstPersonCharacter
  </behavior>
  <action>
    1. In src/uasset_read/serializers/graph.py (Line 461-468):
       - Add `import logging` at file top
       - Change exception handling to log error before returning empty array:
         ```python
         except Exception as e:
             logger.error(f"LinkedTo read failed at pos {linkedto_start}: {e}")
             linked_to = []
         ```
       - Add debug log after successful read:
         ```python
         logger.debug(f"LinkedTo: {len(linked_to)} refs at pos {linkedto_start}")
         ```

    2. In src/uasset_read/graph/flow_builder.py (build_connections_map entry):
       - Add linked_to_count validation:
         ```python
         linked_to_count = sum(len(pin.linked_to_raw or []) for node in graph.nodes for pin in node.pins)
         if linked_to_count == 0:
             warnings.append("WARNING: No LinkedTo data found — connections will be empty")
         ```

    3. Create tests/test_phase72g_connections.py:
       - test_linked_to_validation_logs_error(): mock read_pin_array to raise exception, verify logger.error called
       - test_connections_warning_on_empty_linked_to(): graph with empty linked_to_raw, verify warning added
       - test_linked_to_populated_for_sample_asset(): parse BP_FirstPersonCharacter.uasset, verify linked_to_count > 0
  </action>
  <verify>
    <automated>python -m pytest tests/test_phase72g_connections.py -xvs --tb=short</automated>
  </verify>
  <done>LinkedTo read failures are logged, empty linked_to_raw produces warning, tests verify behavior.</done>
</task>

<task type="auto" wave="2" depends_on="1">
  <name>Wave 2: M-01 Vector/Rotator Fast-path Parsing</name>
  <files>
    - src/uasset_read/parsers/property_types.py
    - tests/test_phase72g_struct_parsing.py
  </files>
  <behavior>
    - Add Vector/Rotator direct float read fast-paths in parse_struct_property()
    - Skip PropertyTags loop for known simple structs (Vector, Rotator, Vector2D)
    - Verify with unit tests that RelativeLocation/RelativeRotation extract correctly
  </behavior>
  <action>
    1. In src/uasset_read/parsers/property_types.py (parse_struct_property() after struct_type extraction):
       Add fast-path before PropertyTags loop:
       ```python
       # Fast-path: Direct float reads for common simple structs
       if struct_type == "Vector":
           x = archive.read_f32()
           y = archive.read_f32()
           z = archive.read_f32()
           return StructValue(struct_type="Vector", fields={"X": x, "Y": y, "Z": z})

       if struct_type == "Rotator":
           pitch = archive.read_f32()
           yaw = archive.read_f32()
           roll = archive.read_f32()
           return StructValue(struct_type="Rotator", fields={"Pitch": pitch, "Yaw": yaw, "Roll": roll})

       if struct_type == "Vector2D":
           x = archive.read_f32()
           y = archive.read_f32()
           return StructValue(struct_type="Vector2D", fields={"X": x, "Y": y})
       ```

    2. Create tests/test_phase72g_struct_parsing.py:
       - test_vector_fast_path(): mock archive with 3 floats, verify StructValue fields
       - test_rotator_fast_path(): mock archive with 3 floats, verify StructValue fields
       - test_relative_location_extraction(): parse SCS_Node from BP_FirstPersonCharacter, verify RelativeLocation fields
       - test_relative_rotation_extraction(): parse SCS_Node, verify RelativeRotation fields
  </action>
  <verify>
    <automated>python -m pytest tests/test_phase72g_struct_parsing.py -xvs --tb=short</automated>
    <automated>python -m pytest tests/test_property_parsing.py -x --tb=short</automated>
  </verify>
  <done>Vector/Rotator use direct float reads, PropertyTags loop skipped. RelativeLocation/RelativeRotation extraction verified.</done>
</task>

<task type="auto" wave="3" depends_on="1">
  <name>Wave 3: M-03 BPGC Property Extraction for Functions</name>
  <files>
    - src/uasset_read/blueprint/variable_extractor.py
    - tests/test_phase72g_functions.py
  </files>
  <behavior>
    - Add BPGC export property extraction path (primary path, not Fallback)
    - Extract UbergraphFunction and FunctionList from BPGC properties
    - Merge with existing _extract_functions_from_graphs() Fallback results
  </behavior>
  <action>
    1. In src/uasset_read/blueprint/variable_extractor.py:
       Add new function _extract_functions_from_bpgc_properties():
       ```python
       def _extract_functions_from_bpgc_properties(properties: List[Any]) -> List[BlueprintFunction]:
           """Primary path: Extract functions from BPGC export properties."""
           functions: List[BlueprintFunction] = []
           for prop in properties:
               if prop.name == "UbergraphFunction":
                   # FPackageIndex reference — resolve to function name
                   if hasattr(prop.value, 'resolve'):
                       func_ref = prop.value.resolve()
                       if func_ref:
                           functions.append(BlueprintFunction(
                               name=func_ref.object_name or "UbergraphGraph",
                               ...
                           ))
               elif prop.name == "FunctionList":
                   # TArray<FPackageIndex> — resolve each
                   for func_idx in (prop.value or []):
                       if hasattr(func_idx, 'resolve'):
                           func_ref = func_idx.resolve()
                           if func_ref:
                               functions.append(BlueprintFunction(
                                   name=func_ref.object_name or "UnknownFunction",
                                   ...
                               ))
           return functions
       ```

    2. In extract_blueprint_metadata() (Line 489):
       Change:
         ```python
         functions = _extract_functions_from_graphs(graphs) if graphs else []
         ```
       To:
         ```python
         functions_bpgc = _extract_functions_from_bpgc_properties(properties) if properties else []
         functions_graph = _extract_functions_from_graphs(graphs) if graphs else []
         functions = functions_bpgc + functions_graph  # Merge primary + fallback
         ```

    3. Create tests/test_phase72g_functions.py:
       - test_bpgc_ubergraph_function_extraction(): mock BPGC properties with UbergraphFunction, verify extraction
       - test_bpgc_function_list_extraction(): mock BPGC properties with FunctionList, verify extraction
       - test_functions_merged_from_bpgc_and_graph(): both paths return data, verify merge
  </action>
  <verify>
    <automated>python -m pytest tests/test_phase72g_functions.py -xvs --tb=short</automated>
  </verify>
  <done>BPGC property extraction path added. UbergraphFunction/FunctionList extracted. Primary + Fallback merged.</done>
</task>

<task type="auto" wave="4" depends_on="1,2,3">
  <name>Wave 4: M-04 Parameter Extraction Verification</name>
  <files>
    - tests/test_phase72g_parameters.py
  </files>
  <behavior>
    - Verify Pin data integrity from Wave 1-3 fixes enables parameter extraction
    - Test that function parameters (name + type) are correctly extracted from K2Node_FunctionEntry pins
  </behavior>
  <action>
    1. Create tests/test_phase72g_parameters.py:
       - test_function_entry_pin_direction_parsed(): K2Node_FunctionEntry mock, verify EGPD_Input/EGPD_Output pins
       - test_parameter_name_and_type_extracted(): function with float params, verify FunctionParameter list
       - test_sample_asset_function_parameters(): parse BP_FirstPersonCharacter, verify DoMove/DoAim have parameters

    2. Run regression:
       ```bash
       python -m pytest tests/test_blueprint_extraction.py -x --tb=short
       ```
  </action>
  <verify>
    <automated>python -m pytest tests/test_phase72g_parameters.py -xvs --tb=short</automated>
    <automated>python -m pytest tests/ -x --tb=short -k "phase72g or blueprint" --maxfail=5</automated>
  </verify>
  <done>Parameter extraction verified working with Wave 1-3 fixes. Sample asset functions have parameters.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| PropertyTag serialization → StructValue output | Struct parsing directly reads binary, offset errors propagate |
| LinkedTo binary → connections array | Pin reference resolution crosses module boundaries |
| BPGC export properties → functions list | PackageLinker dependency for FPackageIndex resolution |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-72G-01 | Integrity | Vector/Rotator fast-path | mitigate | Unit tests verify exact 3-float reads, no offset drift |
| T-72G-02 | Tampering | linked_to_raw empty | mitigate | Validation logging + non-empty warning alerts silent failures |
| T-72G-03 | Information Disclosure | FPackageIndex resolution | accept | Resolved object names may be None — handled by fallback |
| T-72G-04 | Denial of Service | StructProperty loop | mitigate | MAX_DEPTH=5 / MAX_PROPERTY_COUNT limits recursion |
</threat_model>

<verification>
1. python -m pytest tests/test_phase72g_connections.py -xvs — LinkedTo validation verified
2. python -m pytest tests/test_phase72g_struct_parsing.py -xvs — Vector/Rotator fast-path verified
3. python -m pytest tests/test_phase72g_functions.py -xvs — BPGC extraction verified
4. python -m pytest tests/test_phase72g_parameters.py -xvs — Parameter extraction verified
5. python -m pytest tests/ --co -q — total test count unchanged (no deletions)
6. Parse BP_FirstPersonCharacter.uasset and verify:
   - connections array length > 0
   - Blueprint.functions contains "Move", "Aim"
   - RelativeLocation/RelativeRotation fields populated
</verification>

<success_criteria>
- RelativeLocation extracted as {X: float, Y: float, Z: float}
- RelativeRotation extracted as {Pitch: float, Yaw: float, Roll: float}
- EventGraph connections array > 0 (non-empty)
- Blueprint.functions contains Move/Aim/JumpStart/JumpEnd
- Each function output includes parameters list (name + type)
- No regressions: existing test suite passes
</success_criteria>

<output>
Create `.planning/phases/phase-72g/72g-01-SUMMARY.md` when done
</output>