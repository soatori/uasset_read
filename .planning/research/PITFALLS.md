# Domain Pitfalls

**Domain:** Binary file parsing for Unreal Engine .uasset format
**Researched:** 2026-04-27

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

### Pitfall 1: Endianness Detection and Byte Swapping

**What goes wrong:** Parser assumes native endianness (usually little-endian on Windows) without checking the package magic tag. Files saved on different-endian platforms will have corrupted data.

**Why it happens:** UE uses two magic tags to detect endianness:
- `PACKAGE_FILE_TAG = 0x9E2A83C1` (correct endianness)
- `PACKAGE_FILE_TAG_SWAPPED = 0xC1832A9E` (swapped endianness)

The swapped tag indicates the file was saved on a platform with different byte order. From PackageFileSummary.cpp:
```cpp
if (Sum.Tag == PACKAGE_FILE_TAG_SWAPPED)
{
    Sum.Tag = PACKAGE_FILE_TAG;
    if (BaseArchive.ForceByteSwapping())
        BaseArchive.SetByteSwapping(false);
    else
        BaseArchive.SetByteSwapping(true);
}
```

**Consequences:** All multi-byte values (int32, int64, float, etc.) are read incorrectly. Name indices, offsets, sizes, and all structured data become garbage values. Parser will crash or produce nonsense.

**Prevention:**
1. Read the first 4 bytes as uint32
2. Check against both PACKAGE_FILE_TAG and PACKAGE_FILE_TAG_SWAPPED
3. If matches swapped, enable byte swapping for all subsequent reads
4. Use Python's `struct.unpack` with explicit byte order prefixes: `<` for little-endian, `>` for big-endian

**Detection:** If first 4 bytes are neither 0x9E2A83C1 nor 0xC1832A9E, file is not a valid uasset. If offsets/counts are negative or absurdly large after reading summary, byte swapping may be wrong.

**Phase:** Phase 1 (Format Parsing) must address this immediately.

---

### Pitfall 2: Version Handling - Too Old, Too New, or Unversioned

**What goes wrong:** Parser fails to handle three version scenarios:
1. **Too old** - Package from ancient UE version that parser cannot load
2. **Too new** - Package from newer UE version with format changes parser doesn't know
3. **Unversioned** - Cooked packages saved without version numbers

**Why it happens:** UE has complex versioning:
- `EUnrealEngineObjectUE4Version` (oldest loadable: 214, latest: 522+)
- `EUnrealEngineObjectUE5Version` (starts at 1000, latest: ~1000+23)
- `FCustomVersionContainer` with GUID-based custom versions for subsystems
- Legacy file version field (-2 to -9 indicates modern format)

From PackageFileSummary.cpp, the legacy file version indicates format changes:
```cpp
// -2: enum-based custom versions
// -3: guid-based custom versions  
// -4: removal of UE3 version
// -5: replacement of UE3 version writing
// -6: optimizations to custom versions
// -7: texture allocation info removed
// -8: UE5 version added to summary
// -9: contractual change in early exits
```

**Consequences:** Parser may:
- Crash on unknown property types or format changes
- Misinterpret offsets for new fields that don't exist in older versions
- Skip critical data when unversioned packages assume current engine format

**Prevention:**
1. Read LegacyFileVersion, FileVersionUE4, FileVersionUE5, FileVersionLicenseeUE
2. Check `IsFileVersionTooOld()` and `IsFileVersionTooNew()` before proceeding
3. For unversioned packages (`bUnversioned = true`), use current/latest format assumptions
4. Maintain a version compatibility matrix - know which versions your parser supports
5. Gracefully fail with clear error message when version is unsupported

**Detection:** Early exit from summary parsing. Negative/zero version numbers for unversioned. Custom versions array has unknown GUIDs.

**Phase:** Phase 1 (Format Parsing). Parser needs version-aware serialization logic throughout.

---

### Pitfall 3: BulkData Flags and Payload Locations

**What goes wrong:** Parser incorrectly reads BulkData because it doesn't handle the many flag combinations that affect where and how payload data is stored.

**Why it happens:** BulkData has numerous flags from BulkData.cpp:
```cpp
BULKDATA_PayloadAtEndOfFile       // Data at end of file, offset relative to BulkDataStartOffset
BULKDATA_SerializeCompressedZLIB  // Compressed with ZLIB
BULKDATA_ForceInlinePayload       // Data embedded inline (small data)
BULKDATA_PayloadInSeparateFile    // Data in separate .ubulk file
BULKDATA_OptionalPayload          // Optional data, may not exist
BULKDATA_MemoryMappedPayload      // Memory-mapped for streaming
BULKDATA_Size64Bit                // Size uses 64-bit instead of 32-bit
BULKDATA_DuplicateNonOptionalPayload // Has duplicate offset for fallback
```

The serialization changes based on flags:
```cpp
if (UNLIKELY(BulkMeta.Flags & BULKDATA_Size64Bit))
{
    Ar << BulkMeta.ElementCount;  // 64-bit
    Ar << BulkMeta.SizeOnDisk;    // 64-bit  
    Ar << BulkMeta.Offset;        // 64-bit
}
else
{
    SerializeAsInt32(Ar, BulkMeta.ElementCount);  // 32-bit
    SerializeAsInt32(Ar, BulkMeta.SizeOnDisk);    // 32-bit
    Ar << BulkMeta.Offset;                        // Still 64-bit in some cases
}
```

**Consequences:** 
- Offset interpreted incorrectly -> data read from wrong location
- Size mismatch -> buffer overflow or truncated read
- Compression not detected -> raw garbage data
- Separate file not handled -> data missing

**Prevention:**
1. Always check BULKDATA_Size64Bit before reading size/offset
2. Check BULKDATA_PayloadInSeparateFile and load from .ubulk if needed
3. Check compression flags and decompress accordingly
4. Handle BULKDATA_DuplicateNonOptionalPayload for fallback data
5. Payloads at end of file (BULKDATA_PayloadAtEndOfFile) use offset from BulkDataStartOffset

**Detection:** BulkData read returns wrong size. Seeking to offset fails. File too small for claimed payload size.

**Phase:** Phase 1 (Format Parsing). BulkData handling is fundamental for any non-trivial asset.

---

### Pitfall 4: FName Index vs String Confusion

**What goes wrong:** Parser treats FName as a string when it's actually an index into a name table, or vice versa. This leads to incorrect name resolution.

**Why it happens:** FName serialization depends on context:
- In packages: FName is serialized as **index + number** into the package's NameMap
- In BulkData: FName can be serialized as **string** (from BulkDataReader.h)
- FMappedName has type bits (Package, Container, Global) that affect resolution

From MappedName.h:
```cpp
class FMappedName
{
    static constexpr uint32 IndexBits = 30u;  // 30 bits for index
    static constexpr uint32 TypeMask = ~IndexMask;  // 2 bits for type
    
    enum class EType { Package, Container, Global };
    
    uint32 Index;  // Contains both index (30 bits) and type (2 bits)
    uint32 Number; // Name number (for numbered names like "Material_0")
};
```

**Consequences:**
- Names appear as garbage strings or wrong names
- Object references fail because names don't match
- Parser can't identify property types, class names, or object names
- Blueprint node types misidentified

**Prevention:**
1. **First**, deserialize the NameMap from NameOffset/NameCount in summary
2. **Then**, read FNames as index+number pairs
3. Resolve index to string from NameMap
4. Handle numbered names (Number != 0) by appending suffix
5. Check FMappedName type bits for global/package/container resolution

**Detection:** Names appear as empty strings or integers. Object class names are wrong. Can't find expected blueprint node types.

**Phase:** Phase 1 (Format Parsing). NameMap must be loaded before any FName resolution.

---

### Pitfall 5: Offset Arithmetic and Relative vs Absolute Positions

**What goes wrong:** Parser mixes up absolute file offsets and relative offsets, leading to seeking to wrong positions.

**Why it happens:** UE uses different offset types:
- NameOffset, ExportOffset, ImportOffset: **absolute** file positions
- BulkData Offset: **relative** to BulkDataStartOffset when PayloadAtEndOfFile
- Some offsets are relative to TotalHeaderSize
- Trailer offsets read backwards from file end

From PackageFileSummary structure:
```cpp
int32 NameOffset;      // Absolute position in file
int32 ExportOffset;    // Absolute position in file  
int32 ImportOffset;    // Absolute position in file
int64 BulkDataStartOffset;  // Base for bulk data offsets
```

**Consequences:** Parser reads wrong data. Seeking to "offset" gives garbage. Off-by-header-size errors propagate through entire parse.

**Prevention:**
1. Document each offset type (absolute vs relative) before using
2. Add header size when needed: `absolute_pos = relative_offset + TotalHeaderSize`
3. Use BulkDataStartOffset as base for PayloadAtEndOfFile
4. For trailer, seek backwards from file end

**Detection:** Seeking to offset produces wrong data type (names where exports expected). Parser crashes on seek past file end.

**Phase:** Phase 1 (Format Parsing). Clear offset handling is foundational.

---

### Pitfall 6: Unversioned Property Serialization

**What goes wrong:** Parser tries to read property tags for unversioned packages, but unversioned packages use a completely different serialization scheme.

**Why it happens:** UE has two property serialization modes:
1. **Versioned**: Properties serialized with FPropertyTag containing name, type, array index, size, GUID
2. **Unversioned**: Properties serialized in a fixed schema-based order, no tags, uses bitmask to indicate presence

From UnversionedPropertySerialization.cpp:
```cpp
// Unversioned uses a schema-based approach
// Properties serialized in declaration order
// Presence indicated by bitmask, not tags
// No type info in stream - must know class layout
```

Unversioned packages are common in cooked/shipped games. The `bUnversioned` flag in PackageFileSummary indicates this mode.

**Consequences:**
- Parser reads garbage trying to interpret bitmask as property tag
- Can't deserialize any properties from cooked packages
- Blueprint data completely inaccessible

**Prevention:**
1. Check `bUnversioned` flag from summary
2. If unversioned, use schema-based serialization (requires knowing class layout)
3. This requires access to the class definition ( UClass/UStruct property chain)
4. For a standalone parser, this is a **major limitation** - may need to fall back to partial parsing

**Detection:** Property tag has invalid type name. Array index absurd. Size negative or too large.

**Phase:** Phase 1 or Phase 2 depending on approach. Unversioned support requires class type knowledge.

---

### Pitfall 7: PropertyTag Evolution Across Versions

**What goes wrong:** Parser uses old PropertyTag format assumptions for newer packages, missing new fields that affect parsing.

**Why it happens:** PropertyTag format evolved significantly:
- Early UE4: Just name, type, array index, size
- Later UE4: Added HasPropertyGuid, PropertyGuid
- UE5: Added HasPropertyExtensions, complete type name, overridable info

From PropertyTag.cpp:
```cpp
enum class EPropertyTagFlags : uint8
{
    HasArrayIndex              = 0x01,
    HasPropertyGuid            = 0x02,
    HasPropertyExtensions      = 0x04,
    HasBinaryOrNativeSerialize = 0x08,
    BoolTrue                   = 0x10,
    SkippedSerialize           = 0x20,
};
```

Newer versions also use `FPropertyTypeName` for complete type information instead of just type FName.

**Consequences:**
- Properties with GUIDs not identified correctly
- Extension data skipped, causing offset misalignment
- Complex types (maps, sets, nested structs) misparsed
- Blueprint property values wrong or missing

**Prevention:**
1. Check UE version to determine PropertyTag format
2. Parse flags byte to determine which fields are present
3. Handle extensions (EPropertyTagExtension) for overridable info
4. Use FPropertyTypeName for complete type info in newer versions

**Detection:** Property size doesn't match expected. Next property starts at wrong offset. Unknown property type names.

**Phase:** Phase 1 (Format Parsing). Property parsing is core to any asset reading.

---

### Pitfall 8: Package Trailer and Payload TOC (UE5+)

**What goes wrong:** Parser ignores UE5's package trailer structure, missing payload TOC and data resources.

**Why it happens:** UE5 added a trailer at the end of packages:
```cpp
// From PackageTrailer.h documentation:
// [Footer]
// Footer allows loading trailer in reverse, contains PACKAGE_FILE_TAG
//
// Trailer contains:
// - Tag (uint64) - should match FFooter::FooterTag
// - TrailerLength (uint64) - total trailer size
// - PackageTag (uint32) - PACKAGE_FILE_TAG
// - Summary offsets
// - Payload TOC entries
// - Data resource references
```

New fields in PackageFileSummary (UE5+):
```cpp
int64 PayloadTocOffset;      // Payload table of contents
int32 DataResourceOffset;    // Data resource location
int32 NamesReferencedFromExportDataCount; // Names used in export data
```

**Consequences:**
- Payload TOC data inaccessible
- Data resources not found
- Some export data references unresolved
- Package validation fails

**Prevention:**
1. Check UE5 version >= PACKAGE_SAVED_HASH for trailer presence
2. Read trailer backwards from file end if needed
3. Handle PayloadTocOffset and DataResourceOffset fields
4. Package validation should check trailing PACKAGE_FILE_TAG

**Detection:** Payload TOC data not found. Data resource references unresolved. Package ends without PACKAGE_FILE_TAG.

**Phase:** Phase 1 (Format Parsing). UE5-specific handling.

---

## Moderate Pitfalls

### Pitfall 1: Reading Entire File vs Streaming

**What goes wrong:** Parser reads entire .uasset file into memory before parsing, causing memory issues with large assets.

**Why it happens:** Large assets (textures, meshes) can be hundreds of MB. Reading all at once:
- Wastes memory (Python overhead for bytes objects)
- Slow startup for large files
- Can crash on memory limits

**Prevention:**
1. Use file handle with seek/read instead of loading all bytes
2. Read header first, then only needed sections
3. For bulk data, use streaming reads or skip if not needed
4. Set reasonable file size limits upfront

**Detection:** Memory usage spikes on large files. Parsing takes too long before any output.

**Phase:** Phase 1.

---

### Pitfall 2: Python struct.unpack Alignment and Padding

**What goes wrong:** Parser assumes struct.unpack byte sizes match C++ struct sizes, missing alignment/padding differences.

**Why it happens:** 
- C++ structs have alignment padding (e.g., int64 after int32 has 4-byte pad)
- Python struct doesn't add padding by default
- UE serialization may or may not include padding depending on version

**Prevention:**
1. Don't use struct.unpack for complex structs - parse field by field
2. For each field, calculate expected position accounting for UE's alignment
3. Use explicit byte counts, not struct size assumptions

**Detection:** Field values shifted. Reading at offset gives wrong field.

**Phase:** Phase 1.

---

### Pitfall 3: String Encoding (ANSICHAR vs WIDECHAR vs UTF8)

**What goes wrong:** Parser uses wrong encoding for strings, getting garbage or Unicode errors.

**Why it happens:** UE strings use multiple encodings:
- FName entries: Stored as UTF-8 in modern versions, older versions used TCHAR
- FString: TCHAR-based (UTF-16 on Windows, UTF-8 on some platforms)
- ANSICHAR paths: ASCII for file paths
- Serialized strings: Depends on archive context

**Prevention:**
1. For FName entries, try UTF-8 first, fall back to platform TCHAR
2. For FString serialization, check archive's text format
3. Handle null-terminated strings correctly
4. Account for LengthPrefix on serialized strings

**Detection:** Strings have garbage characters. Unicode decode errors. Names don't match expected.

**Phase:** Phase 1.

---

### Pitfall 4: FObjectImport/FObjectExport Structure

**What goes wrong:** Parser misreads import/export map entries due to version-dependent fields.

**Why it happens:** Import/Export structures evolved:
- FObjectImport: ClassPackage, ClassName, OuterIndex, ObjectName (package index for UE5+)
- FObjectExport: ClassIndex, SuperIndex, OuterIndex, ObjectName, ObjectFlags, SerialSize, SerialOffset
  - UE5 removed PackageGuid, added SerialSize/SerialOffset script offset, added bIsInherited

From ObjectResource.h:
```cpp
class FPackageIndex
{
    int32 Index;  // >0 = export (Index-1), <0 = import (-Index-1), 0 = null
    
    bool IsImport() const { return Index < 0; }
    bool IsExport() const { return Index > 0; }
    int32 ToImport() const { return -Index - 1; }
    int32 ToExport() const { return Index - 1; }
};
```

**Prevention:**
1. Parse FPackageIndex correctly (signed encoding for import/export)
2. Check UE version for export structure fields
3. Script serialization offset added in SCRIPT_SERIALIZATION_OFFSET version
4. bIsInherited added in TRACK_OBJECT_EXPORT_IS_INHERITED version

**Detection:** Import/export indices out of range. Object references to wrong classes.

**Phase:** Phase 1.

---

### Pitfall 5: Missing Error Handling for Corrupted Data

**What goes wrong:** Parser crashes or produces garbage when file is partially corrupted or truncated.

**Why it happens:** Real-world files can have:
- Truncated data (file incomplete)
- Corrupted sections (disk errors)
- Mismatched sizes (serialization bugs during save)
- Invalid offsets (old format corruption)

**Prevention:**
1. Validate file size before reading offsets
2. Check offset < file_size before seeking
3. Check count * element_size < remaining_data
4. Use try/except around binary reads
5. Return partial results with error flags, don't crash

**Detection:** Seeking past file end. Reading returns fewer bytes than expected. Struct.unpack raises exception.

**Phase:** Phase 1.

---

### Pitfall 6: Blueprint Graph Parsing Complexity

**What goes wrong:** Parser attempts to fully parse blueprint graphs (nodes, pins, connections) but the format is extremely complex and undocumented.

**Why it happens:** Blueprint graphs involve:
- UK2Node subclasses with type-specific serialization
- EdGraphPin with complex references
- Connections stored as pin-to-pin references
- Ubergraph pages, function graphs, macro graphs
- Each node type has unique property layout

This is **not documented** by Epic. Third-party parsers like FModel struggle with this constantly.

**Prevention:**
1. Accept that full blueprint graph parsing may be impossible without engine integration
2. Focus on extractable metadata: class name, parent class, exposed properties, functions
3. Parse what you can, flag what you can't
4. Consider using UE Python API for full parsing if available

**Detection:** Node properties are empty or wrong. Pin connections unresolved. Graph structure incomplete.

**Phase:** Phase 2. May require re-scoping if full graph parsing proves impractical.

---

## Minor Pitfalls

### Pitfall 1: File Extension Confusion (.uasset vs .umap)

**What goes wrong:** Parser assumes all .uasset files have same format, but .umap files (level packages) have additional structures.

**Why it happens:** .umap files are also packages but contain:
- Level info (ULevel)
- World tile info (for world partition)
- Additional streaming level references

**Prevention:** Check package name or package flags for level-specific handling.

**Phase:** Phase 1.

---

### Pitfall 2: Generations Array Not Handled

**What goes wrong:** Parser ignores Generations array in summary, missing historical version data.

**Why it happens:** Generations track previous saves of the package. Useful for:
- Determining which objects existed in older versions
- Migration compatibility

**Prevention:** Parse GenerationCount and Generations array after package flags. Usually not critical for reading current data.

**Phase:** Phase 1.

---

### Pitfall 3: Package Flags Not Considered

**What goes wrong:** Parser ignores PackageFlags that indicate special package states.

**Why it happens:** PackageFlags include:
- PKG_Cooked - Package is cooked (editor-only data stripped)
- PKG_FilterEditorOnly - Editor-only data excluded
- PKG_PlayInEditor - PIE package
- PKG_UnversionedProperties - Uses unversioned serialization

These affect what data is present.

**Prevention:** Parse and check PackageFlags. Adjust parsing behavior for cooked packages.

**Phase:** Phase 1.

---

### Pitfall 4: SoftObjectPath List (UE5+)

**What goes wrong:** Parser ignores soft object path references list.

**Why it happens:** UE5 added SoftObjectPathsCount/SoftObjectPathsOffset for fast remapping of soft references.

**Prevention:** Parse if version >= ADD_SOFTOBJECTPATH_LIST. Useful for dependency tracking.

**Phase:** Phase 1.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| **Format Parsing** | Endianness, Version, Offsets, BulkData, FName | Comprehensive header parsing with version-aware logic |
| **Blueprint Extraction** | PropertyTag evolution, Graph complexity | Focus on metadata extraction, accept graph parsing limitations |
| **Output Formatting** | Missing data handling | Graceful degradation, partial results with flags |
| **Performance** | Whole-file loading | Stream-based reading, lazy section loading |

---

## UE-Specific Format Quirks

### Quirk 1: Name Table Must Be Loaded First

FNames throughout the package reference indices into the name table. **Must deserialize NameMap before any other FName-dependent data.**

Order: Summary -> NameMap (at NameOffset) -> ImportMap/ExportMap -> Exports

### Quirk 2: Package Index Signed Encoding

FPackageIndex uses signed encoding:
- Positive (1+): Export index (subtract 1)
- Negative (-1-): Import index (negate and subtract 1)  
- Zero: Null reference

### Quirk 3: PayloadAtEndOfFile BulkData

When BULKDATA_PayloadAtEndOfFile flag is set, the offset is **relative to BulkDataStartOffset**, not absolute file position.

### Quirk 4: Custom Version GUIDs

Custom versions use GUIDs as keys, not enums. Parser must maintain GUID->version mapping for known subsystems.

### Quirk 5: Unversioned Package Assumptions

Unversioned packages have zero version numbers but assume current engine format. Parser must use "latest known" format when bUnversioned is true.

### Quirk 6: Trailer Backwards Reading

UE5 packages have a trailer that can be read backwards from file end for validation and payload discovery.

---

## Sources

- UE 5.7 Source: `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Private/UObject/PackageFileSummary.cpp` (Package summary serialization, version handling)
- UE 5.7 Source: `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Private/Serialization/BulkData.cpp` (BulkData flags, payload handling)
- UE 5.7 Source: `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Private/UObject/PropertyTag.cpp` (Property tag evolution, flags)
- UE 5.7 Source: `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/Core/Public/UObject/ObjectVersion.h` (Version constants, UE4/UE5 versions)
- UE 5.7 Source: `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/Core/Public/Serialization/CustomVersion.h` (Custom version system)
- UE 5.7 Source: `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/Core/Public/Serialization/MappedName.h` (FName index structure)
- UE 5.7 Source: `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Private/Serialization/UnversionedPropertySerialization.cpp` (Unversioned schema)
- UE 5.7 Source: `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectResource.h` (Import/Export structures)
- UE 5.7 Source: `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Private/UObject/LinkerLoad.cpp` (Async loading, dependency maps)

**Confidence: HIGH** - All findings verified directly from UE 5.7 source code.