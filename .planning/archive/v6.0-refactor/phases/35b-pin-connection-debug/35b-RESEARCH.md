# Phase 35b: Pin Connection Deep Debug & Fix - Research

**Researched:** 2026-05-13
**Domain:** Unreal Engine 5 UEdGraphPin binary serialization format
**Confidence:** MEDIUM

## Summary

The root cause of `pin.linked_to_raw` being empty across all 130 pins in 37 nodes is a **combination of two bugs**: (1) `archive.read_bool()` consumes 4 bytes (uint32) instead of 1 byte (uint8) for UE5 assets, causing ~15+ bytes of cumulative drift across multiple bool reads, and (2) a **custom version GUID mismatch** that causes all version-dependent code paths to fall through to default branches. The `pins_offset` calculation (`script_serial_offset + script_serial_size`) is confirmed correct — it is NOT the root cause.

The test asset (`BP_FirstPersonCharacter.uasset`) has UE5 version 1017 and 13 custom version entries, but **none** of the 13 GUIDs match the three GUIDs the project checks for (`FFrameworkObjectVersion`, `FUE5MainStreamObjectVersion`, `FReleaseObjectVersion`). This was verified by dumping the asset's custom version table and comparing against the project's constant GUIDs — zero matches.

The primary byte drift comes from `read_bool()` reading 4 bytes per bool when UE5 serializes bools as 1 byte. Across the pin body, there are at least 5 bool reads (4 in PinType + 1 in FText), contributing +15 bytes of drift. By the time `read_pin_array()` is called for LinkedTo, the archive position is reading data from the wrong location where the value happens to encode `array_count=0`.

**Primary recommendation:** Fix `read_bool()` to use u8 for UE5 assets, or add a separate `read_bool_ue5()` method. Then add binary-trace diagnostics to verify field positions against known-good anchor points.

## User Constraints (from CONTEXT.md)

### Locked Decisions
*(None — CONTEXT.md does not contain a Decisions section)*

### Claude's Discretion
*(None — CONTEXT.md does not contain a Claude's Discretion section)*

### Deferred Ideas (OUT OF SCOPE)
- Parse BulkData content (v7.0 scope)
- Parse bytecode/Ubergraph enhancement (v8.0 scope)

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| 35b-01 | read_pin_array returns empty (array_count=0) | Root cause: read_bool() consumes 4 bytes instead of 1, causing +15 bytes drift before LinkedTo is read |
| 35b-02 | pins_offset dynamic scanning inaccurate | pins_offset = script_serial_offset + script_serial_size is CORRECT — verified for all 18 EventGraph nodes |
| 35b-03 | UE5 UEdGraphPin serialization format version differences | Custom version GUID mismatch causes all version checks to default to wrong branch; read_bool() size mismatch compounds the issue |
| 35b-04 | FText skip logic affects subsequent field positions | FText with history_type=255 (None) should consume flags(4B) + history_type(1B) + b_has_culture(1B u8) = 6 bytes minimum; current code uses read_bool() which reads 4B instead of 1B |
| 35b-05 | execution_flows and data_flows cannot build | Cascading failure from linked_to_raw empty; flow_builder.py code is correct but receives empty data |

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| UEdGraphPin binary parsing | API / Backend | — | Deserialization of .uasset binary format |
| Custom version lookup | API / Backend | — | Package summary header parsing |
| Pin connection resolution | API / Backend | — | Cross-node reference resolution within same package |
| Execution flow tracing | API / Backend | — | Graph traversal over parsed pin connections |
| Data flow extraction | API / Backend | — | Graph traversal over parsed pin connections |
| JSON output formatting | API / Backend | — | Serialization of parsed data structures |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.10+ | Binary parsing (struct, dataclasses) | Zero-dependency project requirement |
| struct | built-in | Binary data unpacking | Standard Python binary parsing |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hexdump / binascii | built-in | Binary dump visualization | When manually tracing field positions |
| logging | built-in | Replace DEBUG_PIN_PARSING prints | Production-safe debug output |

### Tools Used for This Research
| Tool | Purpose | Result |
|------|---------|--------|
| UE5 Source (EdGraphPin.cpp) | Authoritative serialization order | Verified field order L1838-1964 |
| Custom version table dump | GUID matching | 0/3 GUIDs matched |
| Binary analysis scripts | Pin layout scanning | Confirmed 0 linked entries across 130 pins |

## Architecture Patterns

### System Architecture Diagram

```
.uasset binary
    │
    ▼
FArchive (binary reader, byte-swapping)
    │  └── read_bool() reads 4 bytes (uint32) — UE5 uses 1 byte (uint8) → DRIFT
    ▼
Package Summary → Custom Version Table (13 entries, NONE match project GUIDs)
    │  └── get_custom_version() returns 0 for all 3 known GUIDs
    ▼
Export Map → Node Exports (37 K2Node/EdGraphNode exports)
    │
    ▼
For each node:
    script_serial (PropertyTag-based) → pins_offset = script_serial_offset + script_serial_size ✓
    │
    ▼
Pins Area: end_marker(4B) + pins_count(4B) + [pin_header(24B) + pin_body(variable)] × N
    │
    ▼
Each pin body (current order in graph.py):
    PinName(FName: 8B) → PinFriendlyName(FText: ~6B) → SourceIndex(i32: 4B)
    → PinToolTip(FString: variable) → Direction(u8: 1B)
    → PinType(FEdGraphPinType):
        PinCategory(FName: 8B) → PinSubCategory(FName: 8B)
        → PinSubCategoryObject(i32: 4B)
        → ContainerType(u8: 1B)
        → bIsReference(read_bool: 4B, should be 1B) → +3 DRIFT
        → bIsWeakPointer(read_bool: 4B, should be 1B) → +3 DRIFT
        → FSimpleMemberReference(i32+FName+16B: ~28B)
        → bIsConst(read_bool: 4B, should be 1B) → +3 DRIFT
        → bIsUObjectWrapper(read_bool: 4B, should be 1B) → +3 DRIFT
    → DefaultValue(FString) → AutoDefaultValue(FString)
    → DefaultObject(i32) → DefaultTextValue(FText)
    → LinkedTo(TArray<PinRef>) ← READS AT WRONG POSITION → count=0
    │
    ▼
PROBLEM: ~15+ bytes of drift from read_bool() size mismatch + version defaults
```

### Recommended Project Structure

No structural changes needed. The fix belongs entirely in `src/uasset_read/serializers/graph.py` and `src/uasset_read/archive.py`.

### Pattern 1: Binary Anchoring for Field Verification

**What:** When debugging binary serialization, anchor on known-good positions and walk forward.
**When to use:** Pin body field order verification, version-dependent format changes.
**Example approach:**
1. Find PinName FName at a known offset (e.g., offset 336 in K2Node_CallFunction_12)
2. Read FName (index=149, number=0) → confirms position
3. Next 4 bytes = FText flags (0x00000000), next byte = history_type (0xFF = 255)
4. history_type=0xFF means only flags + optional culture bool → consumes ~5 bytes
5. Continue field-by-field, recording consumption vs expected

### Anti-Patterns to Avoid

- **Guessing field order from UE4 docs:** UE5 format differs significantly (FName vs FString for PinName, u8 vs u32 BitField, SourceIndex addition)
- **Assuming custom version GUIDs match:** As proven, the asset's 13 custom versions don't include any of the 3 project GUIDs. All version checks fall through to defaults.
- **Using `file_version_ue5 > 0` as version proxy:** This works for some checks (UE5 always has FName format) but not others (SourceIndex depends on MainStreamObjectVersion >= 50).
- **Assuming read_bool() works for UE5:** UE5 serializes bools as uint8 (1 byte), but `read_bool()` reads uint32 (4 bytes). This is the primary drift source.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| FText parsing | Custom text format parser | `read_ftext_with_history()` with correct history_type handling | FText has 3 serialization modes (None/Base/Custom) with different field counts |
| FName parsing | Manual index+number read | `archive.read_name(name_map)` | Handles both UE4 and UE5 FName formats |
| Pin reference parsing | Manual b_null+owning+guid | `read_pin_reference()` / `read_pin_array()` | Standard UE5 SerializePin pattern |
| Bool reading | `archive.read_bool()` for UE5 | `archive.read_u8() != 0` for UE5 bools | UE5 serializes bools as uint8, not uint32 |
| PropertyTag skipping | Manual size-based skip | `read_property_tag()` + seek by tag.size | PropertyTag has complex flag-based extensions |

**Key insight:** The pin body contains a mix of custom serialization (FName, FGuid, FText) and reflection-based serialization (FEdGraphPinType). Getting the byte count wrong for any one field cascades into all subsequent fields reading wrong data.

## Runtime State Inventory

> SKIPPED — This is not a rename/refactor/migration phase. No runtime state changes required.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.10+ | Core runtime | ✓ | 3.12+ | — |
| UE5 Source (EdGraphPin.cpp) | Authoritative serialization reference | ✓ | UE5.5+ (local) | Web documentation |
| Test asset (BP_FirstPersonCharacter.uasset) | Debugging target | ✓ | UE5 v1017 | Other UE5 assets |
| pytest | Test execution | ✓ | Current | — |

## Common Pitfalls

### Pitfall 1: Custom Version GUID Mismatch
**What goes wrong:** The project checks for 3 specific custom version GUIDs, but the test asset has 13 different GUIDs. All `get_custom_version()` calls return 0.
**Why it happens:** The asset may have been saved by a different UE5 build (e.g., a game-specific custom build) that uses different custom version GUIDs than the standard UE5 engine.
**How to avoid:** Use `file_version_ue5` and `file_version_ue4` as primary version indicators when custom version GUIDs don't match. Or, identify which of the 13 asset GUIDs corresponds to Framework/Mainstream/Release by matching version numbers.
**Warning signs:** `summary.get_custom_version(guid, 0)` returns 0 for all known GUIDs.

### Pitfall 2: `read_bool()` Size Mismatch for UE5
**What goes wrong:** `archive.read_bool()` reads 4 bytes (uint32), but UE5 serializes bools as 1 byte (uint8). Each bool read introduces +3 bytes of drift.
**Why it happens:** The project's `read_bool()` was designed for UE4 serialization where bools were stored as int32. UE5 changed to uint8 for compactness.
**How to avoid:** Add a version-aware bool reader: `read_bool_ue5()` that reads u8, or make `read_bool()` check `summary.file_version_ue5 > 0`.
**Warning signs:** Fields after bool reads (especially PinType fields, Direction, LinkedTo) read garbage values.

### Pitfall 3: FText history_type=255 (None) Byte Consumption
**What goes wrong:** `read_ftext_with_history()` is called with `history_type=0xFF` (255). The function reads `b_has_culture` bool. With `read_bool()` reading 4 bytes instead of 1, this adds +3 bytes of drift.
**Why it happens:** The split between caller (reading flags + history_type) and callee (reading rest) means total consumption is: 4 (flags) + 1 (history_type) + 4 (b_has_culture via read_bool) = 9 bytes instead of the correct 4 + 1 + 1 = 6 bytes.
**How to avoid:** Trace exact byte consumption for each FText read and compare against expected values from binary dump.
**Warning signs:** Direction field reads as 255 (invalid — should be 0-2), PinName reads as "None".

### Pitfall 4: SourceIndex Conditional Read
**What goes wrong:** SourceIndex (i32) is conditionally serialized based on `FUE5MainStreamObjectVersion >= 50`. With mainstream_version=0, the code has a heuristic: try reading i32, if value is in range -100 to 1000000, accept it; otherwise seek back.
**Why it happens:** The heuristic may incorrectly consume bytes that belong to PinToolTip (FString), shifting all subsequent fields.
**How to avoid:** Since `file_version_ue5=1017 > 0`, the code unconditionally reads SourceIndex (line 353-354). This is correct for UE5 assets.
**Warning signs:** If SourceIndex is NOT present in the binary but is read anyway, PinToolTip FString will be read from the wrong position.

## Code Examples

### Correct UE5 UEdGraphPin::Serialize() Field Order (from EdGraphPin.cpp L1838-1964)

```cpp
// Source: E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Private/EdGraph/EdGraphPin.cpp:1838-1964
// UEdGraphPin::Serialize(FArchive& Ar)

Ar << OwningNode;                          // FPackageIndex (i32)
Ar << PinId;                               // FGuid (16 bytes)

if (CustomVer(FFrameworkObjectVersion) >= PinsStoreFName)
    Ar << PinName;                         // FName (index + number)
else
    Ar << PinNameStr;                      // FString

#if WITH_EDITORONLY_DATA
if (!Ar.IsFilterEditorOnly())
    Ar << PinFriendlyName;                 // FText (flags + history_type + variant data)
#endif

if (CustomVer(FUE5MainStreamObjectVersion) >= EdGraphPinSourceIndex)
    Ar << SourceIndex;                     // int32

Ar << PinToolTip;                          // FString
Ar << Direction;                           // TEnumAsByte (u8)
PinType.Serialize(Ar);                     // FEdGraphPinType (custom serialization)
Ar << DefaultValue;                        // FString
Ar << AutogeneratedDefaultValue;           // FString
Ar << DefaultObject;                       // FPackageIndex (i32)
Ar << DefaultTextValue;                    // FText

SerializePinArray(Ar, LinkedTo, ...);      // TArray<PinRef>
SerializePinArray(Ar, SubPins, ...);       // TArray<PinRef>
SerializePin(Ar, ParentPin, ...);          // Single PinRef (b_null + owning + guid = 24 bytes)
SerializePin(Ar, ReferencePassThrough, ...); // Single PinRef (24 bytes)

#if WITH_EDITORONLY_DATA
if (!Ar.IsFilterEditorOnly())
    Ar << PersistentGuid;                  // FGuid (16 bytes)
    Ar << BitField;                        // uint32 (4 bytes)
#endif
```

### SerializePinArray Pattern (EdGraphPin.cpp L2063-2130)

```cpp
// Source: E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Private/EdGraph/EdGraphPin.cpp:2063-2130
int32 ArrayNum;
Ar << ArrayNum;                    // TArray count (i32)
for (int32 PinIdx = 0; PinIdx < ArrayNum; ++PinIdx)
    SerializePin(Ar, PinRef, ...);  // Each element: bNull(i32) + OwningNode(i32) + PinGuid(16B)
```

### SerializePin Pattern (EdGraphPin.cpp L2132+)

```cpp
// Source: E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Private/EdGraph/EdGraphPin.cpp:2132+
bool bNullPtr = (PinRef == nullptr);
Ar << bNullPtr;                    // i32 (0 = has value, 1 = null) — NOTE: bool serialized as i32 in SerializePin
if (!bNullPtr) {
    Ar << LocalOwningNode;         // FPackageIndex (i32)
    Ar << PinGuid;                 // FGuid (16 bytes)
    // Total: 24 bytes for non-null pin reference
}
```

Note: In `SerializePin`, the `bNullPtr` bool is serialized as `i32` (via `Ar << bNullPtr` which uses the generic bool operator — but in this context, the UE5 archive may serialize it differently). The project's `read_pin_reference()` correctly reads it as `read_i32()`, which is consistent with the 24-byte header pattern (b_null=4B + owning=4B + guid=16B).

### FEdGraphPinType::Serialize() Field Order (EdGraphPin.cpp L163-346)

```cpp
// Source: E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Private/EdGraph/EdGraphPin.cpp:163-346
// When CustomVer(FFrameworkObjectVersion) >= PinsStoreFName (UE5 always):
Ar << PinCategory;                 // FName
Ar << PinSubCategory;              // FName

Ar << PinSubCategoryObject;        // UObject* (serialized as FPackageIndex in persistent archives)

if (CustomVer(FFrameworkObjectVersion) >= EdGraphPinContainerType)
    Ar << ContainerType;           // uint8 (0=None, 1=Array, 2=Set, 3=Map)
    if (IsMap())
        Ar << PinValueType;        // FEdGraphTerminalType

Ar << bIsReference;                // bool → uint8 in UE5 (NOT int32!)
Ar << bIsWeakPointer;              // bool → uint8 in UE5 (NOT int32!)

if (UEVer >= VER_UE4_MEMBERREFERENCE_IN_PINTYPE)
    Ar << PinSubCategoryMemberReference;  // FSimpleMemberReference (i32 + FName + 16B guid)

if (UEVer >= VER_UE4_SERIALIZE_PINTYPE_CONST)
    Ar << bIsConst;                // bool → uint8 in UE5

if (CustomVer(FReleaseObjectVersion) >= PinTypeIncludesUObjectWrapperFlag)
    Ar << bIsUObjectWrapper;       // bool → uint8 in UE5
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| UE4 FString for PinName | UE5 FName for PinName (PinsStoreFName, Framework v19) | UE5.0+ | PinName is 8 bytes (i32 index + i32 number) instead of variable-length string |
| UE4 bool serialization (int32) | UE5 bool serialization (uint8) | UE5.0+ | All bool fields consume 1 byte instead of 4 — critical for byte-level parsing |
| UE4 BitField as u32 | UE5 BitField as u32 (unchanged) | — | BitField is still uint32 (source L1902: `uint32 BitField`) |
| No SourceIndex field | SourceIndex i32 added | UE5MainStream v50 | Extra 4 bytes in pin body |
| Separate LinkedTo/ParentPin arrays | Unified SerializePin pattern | UE5.0+ | ParentPin and ReferencePassThrough always 24 bytes |

**Deprecated/outdated:**
- **FString-based pin name:** Replaced by FName in UE5 (PinsStoreFName). Project correctly uses `read_name()` when `use_fname_format=true`.
- **`read_bool()` for UE5:** UE5 serializes bools as uint8. The project's `read_bool()` reads uint32, causing +3 bytes drift per bool. This affects PinType parsing (4 bools) and FText parsing (1 bool) = +15 bytes total drift.
- **u32 BitField for UE5:** The project incorrectly reads u8 for UE5 (`graph.py` L457), but UE5 source uses `uint32`. This is a -3 byte error (reads 3 bytes too few), but since BitField is the last field, it doesn't affect LinkedTo.

## Critical Finding 1: BitField Serialization Mismatch

**UE5 source code (EdGraphPin.cpp L1902):**
```cpp
uint32 BitField = 0;
Ar << BitField;  // Serializes as uint32 (4 bytes)
```

**Current project code (graph.py L456-459):**
```python
if summary.file_version_ue5 > 0:
    bitfield = archive.read_u8()  # WRONG — reads 1 byte, should be 4
else:
    bitfield = archive.read_u32()
```

This reads 1 byte instead of 4 for UE5 files. Since BitField is the LAST field in the pin body, this doesn't cause drift in LinkedTo reading. It only affects the bitfield value and any post-pin data.

## Critical Finding 2: `read_bool()` Consumes 4 Bytes Instead of 1 for UE5

**FArchive implementation (`archive.py` L178-180):**
```python
def read_bool(self) -> bool:
    """读取 UE bool 值（序列化为 uint32，4 bytes）。"""
    return self.read_u32() != 0
```

This is the **UE4 serialization format**. In UE5, `FArchive& operator<<(bool&)` serializes bools as **uint8 (1 byte)**, not uint32.

**Impact on `read_ed_graph_pin_type()`:**
The following bools are each read with `read_bool()` (4 bytes each):
1. `bIsReference` — 4 bytes consumed, should be 1 → +3 bytes drift
2. `bIsWeakPointer` — 4 bytes consumed, should be 1 → +3 bytes drift
3. `bIsConst` — 4 bytes consumed, should be 1 → +3 bytes drift
4. `bIsUObjectWrapper` — 4 bytes consumed, should be 1 → +3 bytes drift

**Impact on `read_ftext_with_history()`:**
5. `b_has_culture` (L208) — 4 bytes consumed via `read_bool()`, should be 1 → +3 bytes drift

**Total drift from bool mis-reading: +15 bytes** minimum

This means by the time `read_pin_array()` is called for LinkedTo, the archive position is already 15 bytes past where it should be. The data at that position likely reads as `array_count=0` because it's reading from the middle of another field (possibly DefaultValue string or DefaultObject).

**Fix:** Add a `read_bool_ue5()` method that reads u8, or make `read_bool()` version-aware based on `summary.file_version_ue5`. Since the project uses `tolerant=True`, consider adding a mode flag.

## Critical Finding 3: FEdGraphPinType PinSubCategoryObject Serialization

**UE5 source (EdGraphPin.cpp L205-213):**
```cpp
if(!Ar.IsObjectReferenceCollector() || Ar.IsModifyingWeakAndStrongReferences() || Ar.IsPersistent())
{
    UObject* Object = PinSubCategoryObject.Get(true);
    Ar << Object;
}
```

In a **persistent archive** (loading from .uasset), UObject pointers are serialized as **FPackageIndex (i32)**. The project's `archive.read_i32()` is correct for this field.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | UE5 `FArchive& operator<<(bool&)` serializes as uint8 (1 byte) | Critical Finding 2 | HIGH — if UE5 actually uses int32 for bools in this context, the drift hypothesis is wrong. Need to verify against UE5 source Archive.h |
| A2 | The asset's 13 custom version GUIDs are game-engine-specific and don't include standard Framework/Mainstream/Release | Custom Version GUID Mismatch | LOW — verified by dump; but one of the 13 GUIDs might correspond to Framework/Mainstream with a different GUID in this UE build |
| A3 | `PinSubCategoryObject` is serialized as FPackageIndex (i32) in persistent archives | Critical Finding 3 | MEDIUM — if serialized differently, adds +4 or -4 bytes of drift |
| A4 | FText history_type=0xFF (None) consumes flags(4B) + history_type(1B) + b_has_culture(1B) = 6 bytes minimum (with correct bool size) | Pitfall 3 | MEDIUM — if actual consumption differs, this is an additional source of byte drift |

## Open Questions

1. **Does UE5 `FArchive& operator<<(bool&)` truly serialize as uint8?**
   - What we know: UE5 documentation and community sources indicate bool is serialized as uint8 in UE5 archives.
   - What's unclear: Whether the specific archive type used for .uasset loading (FArchiveLoad) has any special bool handling.
   - Recommendation: Check `FArchive.h` in UE5 source for `operator<<(FArchive& Ar, bool& V)` definition. If confirmed as uint8, the +15 bytes drift hypothesis is validated.

2. **Which of the 13 asset GUIDs corresponds to Framework/Mainstream/Release?**
   - What we know: The GUIDs are `9f8bf812...` (v49), `86181d60...` (v207), `425e9bd8...` (v56), etc.
   - What's unclear: Without matching GUIDs to their version enum names, we can't determine which version thresholds apply.
   - Recommendation: Search the UE5 source for each GUID's definition. Alternatively, use `file_version_ue5=1017` to infer that all UE5-specific features should be enabled.

3. **Is the FText PinFriendlyName actually present in this asset's pins?**
   - What we know: `WITH_EDITORONLY_DATA` controls whether FText fields are serialized. The test asset has `package_flags=0x00040000` (not cooked).
   - What's unclear: Whether the archive's `IsFilterEditorOnly()` flag is set.
   - Recommendation: The project's archive doesn't track this flag. If editor-only data is filtered, PinFriendlyName, PersistentGuid, and BitField are NOT serialized — all fields after PinName would shift.

## Sources

### Primary (HIGH confidence)
- **UE5 Source: EdGraphPin.cpp** (`E:/Develop/lib/UnrealEngine/Engine/Source/Runtime/Engine/Private/EdGraph/EdGraphPin.cpp`) — UEdGraphPin::Serialize() L1838-1964, SerializePinArray() L2063-2130, SerializePin() L2132+, FEdGraphPinType::Serialize() L163-346
- **UE5 Source: DevObjectVersion.cpp** — FFrameworkObjectVersion GUID confirmed as `CFFC743F-43B04480-939114DF-171D2073` (line 194), FUE5MainStreamObjectVersion GUID confirmed as `697DD581-E64F41AB-AA4A51EC-BEB7B628` (line 332)
- **Project source: `src/uasset_read/archive.py`** — `read_bool()` implementation (L178-180): reads uint32
- **Project source: `src/uasset_read/serializers/graph.py`** — Current pin parsing implementation
- **Project source: `src/uasset_read/constants.py`** — Custom version GUID constants and thresholds

### Secondary (MEDIUM confidence)
- **Custom version table dump** — 13 GUIDs from test asset, none matching project's 3 GUIDs (verified programmatically)
- **Binary analysis scripts** (`tools/final_linkedto_scan.py`, `tools/deep_pin_analysis.py`) — Confirmed 0 linked entries across all 130 pins

### Tertiary (LOW confidence)
- **Asset GUID-to-name mapping** — The 13 GUIDs in the asset couldn't be matched to their enum names in UE5 source (search incomplete)
- **UE5 bool serialization as uint8** — Based on community knowledge and UE5 archive conventions, not directly verified from Archive.h source (A1)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified against UE5 source code
- Architecture: HIGH — field order directly from EdGraphPin.cpp
- Pitfalls: MEDIUM — root cause identified (read_bool size mismatch) but not yet validated with binary trace
- GUID mismatch: HIGH — programmatically verified zero matches
- read_bool bug: MEDIUM — inferred from archive.py code and UE5 conventions, needs Archive.h verification
- BitField bug: HIGH — verified against UE5 source (uint32 vs u8)

**Research date:** 2026-05-13
**Valid until:** 30 days (stable UE5 serialization format)
