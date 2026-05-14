---
phase: "35e"
plan: "02"
type: "execute"
wave: 2
depends_on:
  - "35e-01"
files_modified:
  - "src/uasset_read/serializers/graph.py"
  - "src/uasset_read/constants.py"
autonomous: true
requirements:
  - "35e-REQ-03"
must_haves:
  truths:
    - "DefaultTextValue wird als vollstaendiges FText gelesen (flags + history_type + body), nicht als FString"
    - "bIsUObjectWrapper wird auch dann gelesen wenn release_version=0 ist, sofern file_version_ue5 > 0"
    - "Die kombinierten Aenderungen korrigieren 2-13 Bytes Abweichung"
    - "UE4-Assets bleiben unveraendert (ue5_version > 0 Guard)"
    - "FUE5ReleaseStreamObjectVersion GUID ist in constants.py definiert"
  artifacts:
    - path: "src/uasset_read/serializers/graph.py"
      provides: "DefaultTextValue als FText + bIsUObjectWrapper fallback"
      min_lines: 5
    - path: "src/uasset_read/constants.py"
      provides: "FUE5RELEASESTREAM_OBJECT_VERSION_GUID Definition"
      contains: "FUE5RELEASESTREAM_OBJECT_VERSION_GUID"
  key_links:
    - from: "read_ue_graph_pin()"
      to: "read_ftext_with_history()"
      via: "DefaultTextValue als FText"
      pattern: "read_ftext_with_history.*DefaultTextValue"
---

<objective>
Fix 1 (P0): DefaultTextValue von FString auf vollstaendiges FText aendern.
Fix 2 (P1): bIsUObjectWrapper mit file_version_ue5 > 0 Fallback lesen.
Fix 3 (P4): FUE5ReleaseStreamObjectVersion GUID in constants.py definieren.

Zweck: Korrektur der beiden hauptsaechlichen Quellen der 4-Byte-Abweichung.
- DefaultTextValue FText statt FString: korrigiert +2 bis +13 Bytes (je nach history_type)
- bIsUObjectWrapper Fallback: korrigiert +1 Byte (durch release_version=0 GUID mismatch)

Diese beiden Aenderungen + Plan 03 (bSerializeAsSinglePrecisionFloat) reparieren gemeinsam die 4-Byte-Abweichung.

Ausgabe: Korrigierte graph.py und constants.py.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/35e-pin-offset-debug/35e-RESEARCH.md
@.planning/phases/35e-pin-offset-debug/35e-CONTEXT.md
@src/uasset_read/serializers/graph.py
@src/uasset_read/constants.py
@tools/binary_trace_pin.py (Plan 01 erzeugt)

## UE5 C++ Quellcode Bestaetigung

EdGraphPin.cpp L1838-1876:
```
Ar << OwningNode;        // 1
Ar << PinId;             // 2
Ar << PinName;           // 3 (FName)
Ar << PinFriendlyName;   // 4 (FText, EditorOnly)
Ar << SourceIndex;       // 5 (i32, conditional)
Ar << PinToolTip;        // 6 (FString)
Ar << Direction;         // 7 (TEnumAsByte, 1 Byte, KEIN Padding danach)
PinType.Serialize(Ar);   // 8 (FEdGraphPinType)
Ar << DefaultValue;      // 9 (FString)
Ar << AutoDefaultValue;  // 10 (FString)
Ar << DefaultObject;     // 11 (FPackageIndex, i32)
Ar << DefaultTextValue;  // 12 (FText, NICHT FString!)
```

EdGraphPin.cpp L278-343 (FEdGraphPinType::Serialize):
```
Ar << bIsUObjectWrapperBool;   // if ReleaseObjectVersion >= 10
Ar << bSerializeAsSinglePrecisionFloatBool;  // if UE5ReleaseStreamVersion >= 36 + WITH_EDITOR
```

## Aktuelle Code-Stelle (graph.py Zeilen 417-423)

```python
# 12. DefaultTextValue (FText) — UE5 中使用简单 FString 格式（非 FText-with-history）
try:
    _read_ftext_fstring(archive)
except Exception:
    # 极端容错：如果连 FString 都失败，跳过
    pass
```

DIES IST FALSCH. Der Kommentar sagt "UE5 verwendet einfaches FString" — die C++ Quelle zeigt `Ar << DefaultTextValue;` (DefaultTextValue ist FText, Serialisierung via FText::Serialize, nicht via FString::Serialize).
</context>

<tasks>

<task type="auto">
  <name>Task 1: FUE5ReleaseStreamObjectVersion GUID in constants.py definieren</name>
  <read_first>
    src/uasset_read/constants.py (Zeilen 120-142, CustomVersion GUIDs + Thresholds)
  </read_first>
  <files>src/uasset_read/constants.py</files>
  <action>
    Fuege nach Zeile 122 (ende der existierenden 3 GUID-Definitionen) eine vierte GUID hinzu:

    ```python
    FUE5RELEASESTREAM_OBJECT_VERSION_GUID = "D89B5E42-24BD4D46-8412ACA8-DF641779"
    ```

    Fuege nach Zeile 141 (ende der FRELEASE_VERSION_* threshold definition) einen neuen Threshold hinzu:

    ```python
    # ============================================================================
    # FUE5ReleaseStreamObjectVersion Thresholds
    # ============================================================================
    
    FUE5RELEASESTREAM_VERSION_SERIALIZE_FLOAT_PIN_DEFAULTS_AS_SINGLE_PRECISION = 36
    ```

    Achte darauf dass das Format (Kommentar-Blocks, Leerzeilen) zum bestehenden Stil passt.
  </action>
  <acceptance_criteria>
    - `grep -n "FUE5RELEASESTREAM_OBJECT_VERSION_GUID" src/uasset_read/constants.py` findet genau 1 Definition
    - `grep -n "FUE5RELEASESTREAM_VERSION_SERIALIZE_FLOAT_PIN_DEFAULTS_AS_SINGLE_PRECISION" src/uasset_read/constants.py` findet genau 1 Definition mit Wert 36
  </acceptance_criteria>
  <verify>
    <automated>python -c "import ast; ast.parse(open('src/uasset_read/constants.py').read()); print('Syntax OK')"</automated>
  </verify>
  <done>
    FUE5RELEASESTREAM_OBJECT_VERSION_GUID + Threshold in constants.py definiert.
  </done>
</task>

<task type="auto">
  <name>Task 2: bIsUObjectWrapper mit file_version_ue5 Fallback in read_ed_graph_pin_type()</name>
  <read_first>
    src/uasset_read/serializers/graph.py (Zeilen 38-138, read_ed_graph_pin_type())
    src/uasset_read/constants.py (neue GUID + Threshold aus Task 1)
    35e-RESEARCH.md (D1, D2 im Abschnitt "Differenzliste")
  </read_first>
  <files>src/uasset_read/serializers/graph.py</files>
  <action>
    In `read_ed_graph_pin_type()` im custom-serialization Zweig (use_custom_serialization=True):

    Aendere den bIsUObjectWrapper Block (ca. Zeilen 132-136):
    ```python
    # bIsUObjectWrapper (version dependent, +1 Byte Abweichung Quelle D1)
    # C++: if Ar.CustomVer(FReleaseObjectVersion::GUID) >= PinTypeIncludesUObjectWrapperFlag
    # Fallback: UE5 Assets haben immer ReleaseObjectVersion >= 10, auch wenn GUID nicht in custom version table
    if release_version >= FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER or summary.file_version_ue5 > 0:
        pin_type.is_uobject_wrapper = archive.read_bool_ue5() if summary.file_version_ue5 > 0 else archive.read_bool()
    else:
        pin_type.is_uobject_wrapper = False
    ```

    WICHTIG: Der Import von `FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER` existiert bereits in Zeile 23.

    Gleichzeitig den Import von `FUE5RELEASESTREAM_OBJECT_VERSION_GUID` und `FUE5RELEASESTREAM_VERSION_SERIALIZE_FLOAT_PIN_DEFAULTS_AS_SINGLE_PRECISION` in der Importzeile (Zeilen 17-24) hinzufuegen:
    
    Aendere Zeile 23-24:
    ```python
    # ALT:
        FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX,
        FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER,
    
    # NEU:
        FUE5_MAINSTREAM_VERSION_ED_GRAPH_PIN_SOURCE_INDEX,
        FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER,
        FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
        FUE5RELEASESTREAM_VERSION_SERIALIZE_FLOAT_PIN_DEFAULTS_AS_SINGLE_PRECISION,
    ```
  </action>
  <acceptance_criteria>
    - `grep -n "release_version.*ue5_version.*or\|file_version_ue5 > 0" src/uasset_read/serializers/graph.py | grep -i "is_uobject_wrapper"` findet den Fallback
    - `grep -n "FUE5RELEASESTREAM_OBJECT_VERSION_GUID" src/uasset_read/serializers/graph.py` findet den Import
    - `grep -n "FUE5RELEASESTREAM_VERSION_SERIALIZE_FLOAT_PIN_DEFAULTS_AS_SINGLE_PRECISION" src/uasset_read/serializers/graph.py` findet den Import
  </acceptance_criteria>
  <verify>
    <automated>python -c "import ast; ast.parse(open('src/uasset_read/serializers/graph.py').read()); print('Syntax OK')"</automated>
  </verify>
  <done>
    bIsUObjectWrapper wird mit file_version_ue5 Fallback korrekt gelesen.
  </done>
</task>

<task type="auto">
  <name>Task 3: DefaultTextValue von FString auf vollstaendiges FText aendern</name>
  <read_first>
    src/uasset_read/serializers/graph.py (Zeilen 329-499, read_ue_graph_pin())
    35e-RESEARCH.md (D3 im Abschnitt "Differenzliste")
    src/uasset_read/serializers/graph.py (Zeilen 188-266, read_ftext_with_history())
  </read_first>
  <files>src/uasset_read/serializers/graph.py</files>
  <action>
    In `read_ue_graph_pin()` den Block fuer DefaultTextValue (ca. Zeilen 416-423) ersetzen:

    AKTUELL:
    ```python
    # 12. DefaultTextValue (FText) — UE5 中使用简单 FString 格式（非 FText-with-history）
    try:
        _read_ftext_fstring(archive)
    except Exception:
        # 极端容错：如果连 FString 都失败，跳过
        pass
    ```

    ERSETZEN MIT:
    ```python
    # 12. DefaultTextValue (FText) — NICHT FString!
    # UE5 C++: Ar << DefaultTextValue; (EdGraphPin.cpp L1876)
    # FText Serialisierung: flags(i32,4B) + history_type(u8,1B) + body(variable)
    # Siehe read_ftext_with_history() fuer history_type Verarbeitung
    try:
        _dtv_flags = archive.read_i32()
        _dtv_history = archive.read_u8()
        _dtv_value, _dtv_consumed = read_ftext_with_history(
            archive, _dtv_history,
            tolerant=True,
            ue5_mode=(summary.file_version_ue5 > 0)
        )
    except Exception:
        # Extrem tolerant: Falls FText-Lesen fehlschlaegt, DefaultTextValue ignorieren
        pass
    ```

    WICHTIG: `read_ftext_with_history` ist bereits im selben Modul (graph.py) definiert, kein zusaetzlicher Import noetig.
    Der Funktionsrueckgabewert `_dtv_value` wird aktuell nicht verwendet (das alte FString-Ergebnis wurde auch ignoriert).
    Das ist intentional — der Fokus liegt auf korrektem Konsum der Bytes, nicht auf dem Wert.
  </action>
  <acceptance_criteria>
    - `grep -n "read_ftext_with_history" src/uasset_read/serializers/graph.py` zeigt den neuen Aufruf (mehrfach: einer fuer PinFriendlyName, einer fuer DefaultTextValue)
    - `grep -n "_read_ftext_fstring.*DefaultTextValue\|DefaultTextValue.*_read_ftext_fstring" src/uasset_read/serializers/graph.py` findet KEINEN Treffer mehr
    - `grep -n "DefaultTextValue.*FString\|DefaultTextValue.*简单" src/uasset_read/serializers/graph.py` findet keine falschen Kommentare mehr
  </acceptance_criteria>
  <verify>
    <automated>python -c "import ast; ast.parse(open('src/uasset_read/serializers/graph.py').read()); print('Syntax OK')"</automated>
  </verify>
  <done>
    DefaultTextValue wird als vollstaendiges FText (flags + history_type + body) gelesen.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries
| Boundary | Description |
|----------|-------------|
| graph.py -> FArchive | Serialisiert Daten aus .uasset Dateien. Die gelesenen Bytes bestimmen nachfolgende Feldpositionen. |

## STRIDE Threat Register
| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-35e-02 | DoS | read_ue_graph_pin() DefaultTextValue | mitigate | try/except mit tolerant=True verhindert Absturz bei unerwarteten FText-Daten |
| T-35e-03 | DoS | read_ed_graph_pin_type() bIsUObjectWrapper | accept | Ein zusaetzlicher Byte-Lesevorgang kann nicht zu OOM fuehren |
</threat_model>

<verification>
1. Syntax-Check beider Dateien: `python -c "import ast; ast.parse(open('src/uasset_read/serializers/graph.py').read()); print('Syntax OK'); ast.parse(open('src/uasset_read/constants.py').read()); print('Constants OK')"`
2. Modul-Import: `python -c "import sys; sys.path.insert(0,'src'); from uasset_read.serializers.graph import read_ue_graph_pin, read_ed_graph_pin_type; print('Import OK')"`
3. Parse-Test: `python -c "import sys; sys.path.insert(0,'src'); from uasset_read import parse_uasset; r = parse_uasset('E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset'); print('Parse OK, graphs:', len(r.graphs))"` — darf nicht crashen
</verification>

<success_criteria>
- Syntax OK fuer graph.py und constants.py
- Modul-Import ohne Fehler
- Parse des BP_FirstPersonCharacter.uasset ohne Exception (trotz noch fehlendem bSerializeAsSinglePrecisionFloat in Plan 03)
- UE4-Assets parsen weiterhin korrekt
- linked_to_raw ist nach dieser Aenderung allein noch NICHT unbedingt nicht-leer (benoetigt Plan 03)
</success_criteria>

<output>
Nach Abschluss: `.planning/phases/35e-pin-offset-debug/35e-02-SUMMARY.md`
</output>
