# Fix Plan: #522 CubeBuilder & #515 StructProperty

> Generated 2026-08-02 from `dev-0.5.5` (HEAD `7bba5d07`).
> Both issues are partially fixed; this plan covers remaining work to close them.

---

## Issue #522 — CubeBuilder: Geometry, Materials, Collision, LOD

### Current State

| Aspect | Status |
|--------|--------|
| Strategy | `OPAQUE_CLASS_PAYLOAD` in `_OPAQUE_CLASSES` |
| Handler | `PropertyMetadataHandler("CubeBuilder")` |
| Parsed fields | `layer`, `polygon_count`, `vertex_payload_size` |
| Export status | `partial_metadata` |
| Test fixture | `tests/samples/FirstPerson_Lvl_FirstPerson.umap` (contains `CubeBuilder_3`) |

### What Remains

CubeBuilder has a native `UBrush::Serialize()` that writes geometry outside the standard UPROPERTY region. The current metadata handler only extracts tagged UPROPERTY values (Layer, Polys, Vertices as raw bytes). The actual binary payload — vertex positions, polygon topology, material bindings, collision settings, LOD config — is not decoded.

### Implementation Phases

#### Phase 1: Design Document & UE Source Analysis

1. **Create `docs/designs/issue-522-cube-builder-geometry.md`**
   - Document the native `UBrush::Serialize()` binary layout from UE source
   - Reference: `Engine/Source/Runtime/Engine/Classes/Engine/Brush.h` and `Engine/Source/Runtime/Engine/Private/BrushBuilder.cpp`
   - Map the byte layout after the UPROPERTY region:
     - Poly vertices (FVector positions)
     - Polygon normals and texture coordinates
     - Material slot references
     - Collision model data
     - LOD configuration

2. **Capture binary evidence**
   - Extract raw bytes from `CubeBuilder_3` export's `serial_offset + property_end` to `serial_offset + serial_size`
   - Annotate byte ranges against UE source structure

#### Phase 2: Parser Implementation

**Files to modify:**

| File | Change |
|------|--------|
| `src/uasset_read/parsers/asset_types/cube_builder.py` | **New file** — `CubeBuilderHandler(ClassHandler)` |
| `src/uasset_read/parsers/asset_types/__init__.py` | Register `CubeBuilderHandler` (replaces `PropertyMetadataHandler`) |
| `src/uasset_read/parsers/class_serialization_strategy.py` | Move `CubeBuilder` from `_OPAQUE_CLASSES` to `_TAGGED_PROPERTIES_CLASSES` or keep opaque with handler override |

**Parser structure:**

```python
class CubeBuilderHandler(ClassHandler):
    def can_handle(self, class_name: str) -> bool:
        return class_name == "CubeBuilder"

    def parse(self, export, archive, context=None) -> HandlerResult:
        # 1. Read tagged UPROPERTY region (Layer, Polys, Vertices, etc.)
        # 2. Seek to post-property binary payload
        # 3. Decode vertex positions (FVector array)
        # 4. Decode polygon topology (indices, normals, UVs)
        # 5. Decode material assignments
        # 6. Decode collision data (if present)
        # 7. Decode LOD settings (if present)
        # 8. Return structured result with parse_status="partial" or "success"
```

**Key decisions:**
- Keep `OPAQUE_CLASS_PAYLOAD` strategy but let the handler override status to `partial`/`success`
- Raw fallback: if binary decode fails at any point, preserve raw bytes and set `partial` status
- Geometry output: list of polygons with vertex positions, normals, UVs

#### Phase 3: Tests & Verification

1. **Red tests first** (in `tests/temp/test_issue_522_cube_builder_geometry.py`):
   - `test_cube_builder_has_geometry_fields` — expects `polygons` or `vertices_decoded` in custom_data
   - `test_cube_builder_polygon_count_matches_metadata` — geometry polygon count matches `polygon_count`
   - `test_cube_builder_vertex_positions_are_vectors` — each vertex has x/y/z

2. **Verify against fixture**: Run against `FirstPerson_Lvl_FirstPerson.umap` → `CubeBuilder_3`

3. **Move passing tests** to `tests/test_issue_522_cube_builder_geometry.py` (benchmark test, requires confirmation per constraints)

#### Phase 4: Documentation

- Update `docs/formats/uasset/` with CubeBuilder binary format reference
- Update wiki/ with CubeBuilder parsing notes

### Risk & Mitigation

| Risk | Mitigation |
|------|------------|
| UE version differences in brush serialization | Version-gate with `file_version_ue5` checks; raw fallback on unknown versions |
| Incomplete binary evidence from single fixture | Document what's decoded vs raw; mark unknown regions as `opaque_tail` |
| Breaking existing metadata tests | Run existing `test_issue_522_cube_builder_metadata.py` alongside new tests |

### Estimated Scope

- **New files**: 1 handler, 1 design doc, 1 test file
- **Modified files**: `__init__.py` (registration), possibly `class_serialization_strategy.py`
- **Effort**: Medium — binary format analysis is the hard part; the handler follows established patterns

---

## Issue #515 — StructProperty: MovieSceneDoubleChannel & Related

### Current State

| Aspect | Status |
|--------|--------|
| EditedDocumentInfo | ✅ Supported (tagged fallback) |
| MovieSceneDoubleChannel | ❌ Opaque (27 occurrences in Lyra sample) |
| MovieSceneFrameRange | ❌ Opaque (13 occurrences) |
| MovieSceneFloatChannel | ❌ Opaque (11 occurrences) |
| Design doc | `docs/designs/issue-515-moviescene-structs.md` (MovieSceneDoubleChannel binary layout documented) |
| Red test | `tests/temp/test_issue_515_moviescene_double_channel.py` (3 tests, currently failing) |
| Test fixture | `tests/samples/Lyra_SEQ_LobbyScreen_LevelSequence.uasset` |

### Implementation Phases

#### Phase 1: MovieSceneDoubleChannel (Highest Priority)

The design doc already specifies the binary layout. Implementation uses the **tagged fallback** mechanism.

**Files to modify:**

| File | Change |
|------|--------|
| `src/uasset_read/parsers/property_types.py` | Add to `_TAGGED_FALLBACK_STRUCTS` and `_TAGGED_FALLBACK_STRUCT_SCHEMAS` |

**Schema definition** (based on UE source `MovieSceneChannel.h`):

```python
# Add to _TAGGED_FALLBACK_STRUCTS:
"MovieSceneDoubleChannel",

# Add to _TAGGED_FALLBACK_STRUCT_SCHEMAS:
"MovieSceneDoubleChannel": [
    ("Values", "ArrayProperty"),    # TArray<FMovieSceneDoubleValue>
    ("Times", "ArrayProperty"),     # TArray<FFrameNumber>
    ("bHasDefaults", "BoolProperty"),
    ("DefaultValue", "StructProperty"),  # FMovieSceneDoubleValue (if bHasDefaults)
],
```

**Key considerations:**
- `Traits` field may be version-gated (UE5.1+) — handle via tagged PropertyTag size
- `Values` array elements contain `(f64 value, u8 interpolation)` — the tagged parser reads them as StructProperty with inner tags
- `Times` array elements are `FFrameNumber` (i32) — already supported via fast-path
- `TickResolution` is `FFrameRate` — already in tagged fallback set

**Decision needed:** Whether to use tagged fallback (add to schema) or write a custom binary parser. The tagged fallback is simpler but may not handle the `Traits` version-gating cleanly. A custom parser in a dedicated handler gives more control.

**Recommended approach:** Start with tagged fallback (minimal change), validate against fixture, then upgrade to custom parser if tagged approach can't handle version differences.

#### Phase 2: MovieSceneFrameRange & MovieSceneFloatChannel

After MovieSceneDoubleChannel is working, apply the same pattern:

**MovieSceneFrameRange** (UE source: `MovieSceneFrameRange.h`):
```python
"MovieSceneFrameRange": [
    ("LowerBound", "StructProperty"),  # FFrameNumber
    ("UpperBound", "StructProperty"),  # FFrameNumber
],
```

**MovieSceneFloatChannel** (UE source: `MovieSceneChannel.h`):
```python
"MovieSceneFloatChannel": [
    ("Values", "ArrayProperty"),    # TArray<FMovieSceneFloatValue>
    ("Times", "ArrayProperty"),     # TArray<FFrameNumber>
    ("bHasDefaults", "BoolProperty"),
    ("DefaultValue", "StructProperty"),
],
```

#### Phase 3: Tests

1. **Red tests first** (existing `test_issue_515_moviescene_double_channel.py` is already red):
   - `test_moviescene_double_channel_has_fields` — parse_status != "opaque"
   - `test_moviescene_double_channel_keyframe_count` — exposes keyframe count
   - `test_moviescene_double_channel_values` — exposes keyframe values

2. **Add tests for FrameRange and FloatChannel** (in `tests/temp/`)

3. **Verify against Lyra fixture**: `Lyra_SEQ_LobbyScreen_LevelSequence.uasset`

4. **Move to benchmark tests** (requires confirmation per constraints)

#### Phase 4: Documentation

- Update `docs/formats/uasset/serialization/` with MovieScene struct formats
- Update design doc with implementation results

### Risk & Mitigation

| Risk | Mitigation |
|------|------------|
| Tagged fallback can't handle Traits version-gating | Fall back to custom binary parser in a dedicated handler |
| ArrayProperty inner struct parsing fails for complex elements | Validate with fixture; if needed, add inner struct schemas |
| Breaking existing tagged fallback structs | Run full test suite; tagged fallback is additive (new entries only) |

### Estimated Scope

- **Modified files**: `property_types.py` (2-3 schema additions)
- **New files**: 1-2 test files in `tests/temp/`
- **Effort**: Low-Medium — binary layout is documented, mechanism exists, follows established pattern

---

## Execution Order

| Step | Issue | Description | Dependencies |
|------|-------|-------------|--------------|
| 1 | #515 | Add MovieSceneDoubleChannel to tagged fallback schemas | None |
| 2 | #515 | Run red tests → verify green | Step 1 |
| 3 | #515 | Add MovieSceneFrameRange + MovieSceneFloatChannel schemas | Step 2 |
| 4 | #515 | Run all #515 tests → verify green | Step 3 |
| 5 | #515 | Move passing tests to benchmark (requires confirmation) | Step 4 |
| 6 | #522 | Create design doc with UE source binary layout analysis | None |
| 7 | #522 | Implement CubeBuilderHandler with geometry decoding | Step 6 |
| 8 | #522 | Write and verify tests against fixture | Step 7 |
| 9 | #522 | Move passing tests to benchmark (requires confirmation) | Step 8 |
| 10 | Both | Update format documentation | Steps 5, 9 |

**Rationale:** #515 is lower risk (schema additions to existing mechanism) and should be done first to build confidence. #522 requires new binary format analysis and a new handler — higher risk, higher effort.

---

## Acceptance Criteria

### #522 CubeBuilder
- [ ] Geometry fields decoded (vertex positions, polygon topology)
- [ ] Material assignments exposed (at minimum slot count/names)
- [ ] Export `parse_status` upgraded from `partial_metadata` to `partial` or `success`
- [ ] Existing metadata tests still pass
- [ ] New geometry tests pass against `FirstPerson_Lvl_FirstPerson.umap`

### #515 StructProperty
- [ ] MovieSceneDoubleChannel `parse_status` != `opaque`
- [ ] MovieSceneDoubleChannel fields populated (keyframe count, values, times)
- [ ] MovieSceneFrameRange fields populated
- [ ] MovieSceneFloatChannel fields populated
- [ ] All 3 red tests in `test_issue_515_moviescene_double_channel.py` pass
- [ ] Existing struct parsing tests unaffected
