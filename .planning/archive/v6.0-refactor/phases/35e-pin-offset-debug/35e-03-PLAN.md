---
phase: "35e"
plan: "03"
type: "execute"
wave: 3
depends_on:
  - "35e-02"
files_modified:
  - "src/uasset_read/serializers/graph.py"
autonomous: true
requirements:
  - "35e-REQ-03"
  - "35e-REQ-04"
must_haves:
  truths:
    - "bSerializeAsSinglePrecisionFloat wird in read_ed_graph_pin_type() korrekt gelesen (+1 Byte)"
    - "Nach allen 3 Fixes (D1+D2+D3) ist linked_to_raw fuer mindestens einen Pin nicht-leer"
    - "Die kombinierten 3 Fixes korrigieren gemeinsam die 4-Byte-Abweichung (1+1+2=4 fuer None history_type)"
    - "execution_flows und data_flows sind nach dem Fix nicht-leer"
    - "Rueckwaerts-Kompatibilitaet bleibt erhalten"
  artifacts:
    - path: "src/uasset_read/serializers/graph.py"
      provides: "Vollstaendige Pin-Serialisierung mit allen 3 Fixes"
      min_lines: 5
  key_links:
    - from: "read_ed_graph_pin_type()"
      to: "FUE5RELEASESTREAM_VERSION_SERIALIZE_FLOAT_PIN_DEFAULTS_AS_SINGLE_PRECISION"
      via: "bSerializeAsSinglePrecisionFloat"
      pattern: "bSerializeAsSinglePrecisionFloat"
---

<objective>
Fix 3 (P2): bSerializeAsSinglePrecisionFloat Feld in read_ed_graph_pin_type() hinzufuegen.
Dies ist der letzte der 3 Fixes (D1+D2+D3 aus RESEARCH.md). Nach diesem Fix sollten linked_to_raw, execution_flows und data_flows korrekt funktionieren.

Zweck: Vervollstaendigung der 4-Byte-Abweichungs-Korrektur.
- D1 (bIsUObjectWrapper, Plan 02): +1 Byte
- D2 (bSerializeAsSinglePrecisionFloat, dieser Plan): +1 Byte
- D3 (DefaultTextValue FText, Plan 02): +2 bis +13 Bytes (None: +2)
- Kombiniert: +4 Bytes (fuer None history_type)

Ausgabe: Vollstaendig korrigierte Pin-Serialisierung mit nicht-leerem linked_to_raw.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/35e-pin-offset-debug/35e-RESEARCH.md
@.planning/phases/35e-pin-offset-debug/35e-CONTEXT.md
@src/uasset_read/serializers/graph.py
@.planning/phases/35e-pin-offset-debug/35e-02-SUMMARY.md (nach Plan 02)

## UE5 C++ Source (EdGraphPin.cpp L327-343)

```cpp
#if WITH_EDITOR
    bool bSerializeAsSinglePrecisionFloatBool = bSerializeAsSinglePrecisionFloat;

    if (Ar.CustomVer(FUE5ReleaseStreamObjectVersion::GUID) >= FUE5ReleaseStreamObjectVersion::SerializeFloatPinDefaultValuesAsSinglePrecision)
    {
        Ar << bSerializeAsSinglePrecisionFloatBool;
    }
    else
    {
        if (OldPinCategory == TEXT("float"))
        {
            bSerializeAsSinglePrecisionFloatBool = true;
        }
    }

    bSerializeAsSinglePrecisionFloat = bSerializeAsSinglePrecisionFloatBool;
#endif
```

## Aktuelle Code-Stelle (graph.py Zeilen 132-138)

```python
# bIsUObjectWrapper (version dependent)
if release_version >= FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER:
    pin_type.is_uobject_wrapper = archive.read_bool_ue5() if summary.file_version_ue5 > 0 else archive.read_bool()
else:
    pin_type.is_uobject_wrapper = False
```

Nach Plan 02 wird dies korrigiert zu:
```python
# bIsUObjectWrapper (version dependent, +1 Byte Abweichung Quelle D1)
if release_version >= FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER or summary.file_version_ue5 > 0:
    pin_type.is_uobject_wrapper = archive.read_bool_ue5() if summary.file_version_ue5 > 0 else archive.read_bool()
else:
    pin_type.is_uobject_wrapper = False
```

DIREKT DANACH muss bSerializeAsSinglePrecisionFloat hinzugefuegt werden (vor `return pin_type`).
</context>

<tasks>

<task type="auto">
  <name>Task 1: bSerializeAsSinglePrecisionFloat in read_ed_graph_pin_type() hinzufuegen</name>
  <read_first>
    src/uasset_read/serializers/graph.py (Zeilen 130-138, nach bIsUObjectWrapper im custom_serialization Zweig)
    src/uasset_read/serializers/graph.py (Zeilen 56-78, default reflection Zweig)
    src/uasset_read/constants.py (neue GUID und Threshold aus Plan 02)
    35e-RESEARCH.md (Quelle D2)
  </read_first>
  <files>src/uasset_read/serializers/graph.py</files>
  <action>
    **A) Im custom-serialization Zweig (use_custom_serialization=True):**

    Fuege NACH dem bIsUObjectWrapper Block (nach dem `pin_type.is_uobject_wrapper = False` else-Zweig und VOR dem `return pin_type`) ein:

    ```python
    # bSerializeAsSinglePrecisionFloat (fehlendes Feld, +1 Byte Abweichung Quelle D2)
    # C++: WITH_EDITOR && FUE5ReleaseStreamObjectVersion >= SerializeFloatPinDefaultValuesAsSinglePrecision
    # UE5 Assets aus Entwicklungs-Builds enthalten dieses Feld immer (WITH_EDITOR=true)
    if summary.file_version_ue5 > 0:
        _b_single_prec = archive.read_u8()
        pin_type.b_serialize_as_single_precision_float = bool(_b_single_prec)
    ```

    Dazu muss in `FEdGraphPinType` (models/core.py) das Feld existieren. Ueberpruefe ob es bereits existiert.
    Wenn nicht, muss es hinzugefuegt werden.

    **B) Im default-reflection Zweig (use_custom_serialization=False, Zeilen 57-77):**

    Nach dem FlagsByte-Block (Zeilen 72-77, nach `pin_type.is_uobject_wrapper = (flags_byte & 0x20) != 0` und VOR dem `return pin_type`):

    ```python
    # bSerializeAsSinglePrecisionFloat (optional, 1 Byte)
    # Im default-reflection Modus gibt es kein separates Feld dafuer —
    # es wird entweder im FlagsByte codiert oder nicht vorhanden
    # Daher hier nichts hinzufuegen (der FlagsByte-Block deckt alles ab)
    ```

    AKTUELL: Der default-reflection Zweig (nicht use_custom_serialization) endet nach dem Setzen von `pin_type.is_uobject_wrapper`. Der `return pin_type` steht danach. Da der FlagsByte bereits 8 Bits enthaelt (bIsArray_DEPRECATED + bIsReference + bIsConst + bIsWeakPointer + bIsUObjectWrapper = 5 Bits plus 3 reservierte), und bSerializeAsSinglePrecisionFloat in diesem Modus nicht im FlagsByte enthalten ist (es gibt kein Bit dafuer im default-reflection Format), ist hier KEINE Aenderung noetig. Der default-reflection Modus wird ohnehin nur fuer sehr alte UE5 Assets (vor FrameworkObjectVersion >= 15/19) verwendet.

    **C) FEdGraphPinType Feld hinzufuegen (falls nicht vorhanden):**

    Suche in `src/uasset_read/models/core.py` nach der Klasse `FEdGraphPinType`. Pruefe ob `b_serialize_as_single_precision_float` existiert. Wenn nicht, fuege es mit Default-Wert `False` hinzu, in der Naehe der anderen bool Felder (is_uobject_wrapper, etc.).

    Das Feld muss ein optionaler bool sein, der default auf `False` steht, z.B.:
    ```python
    b_serialize_as_single_precision_float: bool = False
    ```
  </action>
  <acceptance_criteria>
    - `grep -n "b_serialize_as_single_precision_float\|bSerializeAsSinglePrecisionFloat" src/uasset_read/serializers/graph.py` findet die neue read_u8() Logik
    - `grep -n "b_serialize_as_single_precision_float" src/uasset_read/models/core.py` findet das Feld (falls nicht vorher schon vorhanden)
    - Der Code hat `summary.file_version_ue5 > 0` Guard (nur UE5)
  </acceptance_criteria>
  <verify>
    <automated>python -c "import ast; ast.parse(open('src/uasset_read/serializers/graph.py').read()); print('graph.py Syntax OK')"</automated>
  </verify>
  <done>
    bSerializeAsSinglePrecisionFloat wird in read_ed_graph_pin_type() gelesen, FEdGraphPinType hat das Feld.
  </done>
</task>

<task type="auto">
  <name>Task 2: Verify linked_to_raw, execution_flows, data_flows sind nicht-leer</name>
  <read_first>
    tools/binary_trace_pin.py (erweitert in Plan 01)
    35e-RESEARCH.md (Abschnitt "Validierungsmethoden")
  </read_first>
  <files>tools/binary_trace_pin.py</files>
  <action>
    Fuehre Diagnose-Kommando aus, um zu verifizieren dass alle 3 Fixes gemeinsam wirken:

    ```bash
    python -c "
    import sys
    sys.path.insert(0, 'src')
    from uasset_read import parse_uasset, format_json_full

    asset_path = 'E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset'
    result = parse_uasset(asset_path)

    # 1. linked_to_raw Check
    total_pins = 0
    pins_with_links = 0
    for g in result.graphs:
        for n in g.nodes:
            for pin in n.pins:
                total_pins += 1
                links = getattr(pin, 'linked_to_raw', [])
                if links and len(links) > 0:
                    pins_with_links += 1

    print(f'linked_to_raw: {pins_with_links}/{total_pins} pins have connections')

    # 2. execution_flows Check
    json_out = format_json_full(result)
    for g in json_out.get('blueprint', {}).get('graphs', []):
        gname = g.get('graph_name', '')
        eflows = g.get('execution_flows', [])
        dflows = g.get('data_flows', [])
        if eflows:
            print(f'{gname}: execution_flows={len(eflows)}')
        if dflows:
            print(f'{gname}: data_flows={len(dflows)}')

    # 3. Gesamtergebnis
    if pins_with_links > 0:
        print('RESULT: linked_to_raw FIXED')
    else:
        print('RESULT: linked_to_raw STILL EMPTY — additional debugging needed')
    "
    ```

    WICHTIG: DISE VERIFIKATION LAEUFT AUTOMATISCH. Der Task ist erfolgreich wenn mindestens einer der folgenden Checks wahr ist:
    - `pins_with_links > 0` (linked_to_raw enthaelt Verbindungen) ODER
    - Das Diagnose-Skript meldet validen Grund warum es noch leer ist
    
    Dokumentiere das Ergebnis in der SUMMARY-Datei. Bei "STILL EMPTY" analysiere zusaetzlich mit dem Binary Trace Tool:
    ```
    python tools/binary_trace_pin.py --asset "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset" --node-export-idx 40 --pin-index 0
    ```

    Speichere das Diagnoseergebnis fuer den SUMMARY-Output.
  </action>
  <acceptance_criteria>
    - Diagnose-Kommando laeuft ohne Exception
    - Ausgabe enthaelt "linked_to_raw:" gefolgt von einer Zahl > 0 (FIXED) ODER beschreibt warum noch leer
    - Keine neuen Exception/Warning in der Ausgabe
  </acceptance_criteria>
  <verify>
    <automated>MISSING — Wave 0 (Plan 01) hat binary_trace_pin.py als Diagnose-Tool erstellt. Die linked_to_raw Verifikation erfolgt durch das python -c Kommando oben.</automated>
  </verify>
  <done>
    linked_to_raw nicht-leer bestaetigt ODER dokumentiert warum noch leer.
    Alle 3 Fixes (D1+D2+D3) funktionieren korrekt.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries
| Boundary | Description |
|----------|-------------|
| read_ed_graph_pin_type() -> FArchive | Liest zusaetzliches 1-Byte-Feld. Positioniert die folgenden Lesevorgaenge korrekt. |

## STRIDE Threat Register
| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-35e-04 | DoS | read_ed_graph_pin_type() bSerializeAsSinglePrecisionFloat | accept | Ein zusaetzlicher read_u8 kann keinen DoS ausloesen. Guard durch `file_version_ue5 > 0`. |
</threat_model>

<verification>
1. Syntax: `python -c "import ast; ast.parse(open('src/uasset_read/serializers/graph.py').read()); print('Syntax OK')"`
2. Import: `python -c "import sys; sys.path.insert(0,'src'); from uasset_read.serializers.graph import read_ue_graph_pin; print('Import OK')"`
3. Diagnose: Fuehre Task 2 Skript aus, bestaetige linked_to_raw > 0
4. Regressions-Check: `python tests/test_ue5_pin_integration.py -v` (aktuelle Tests, vor Plan 04)
</verification>

<success_criteria>
- linked_to_raw nicht-leer (mindestens 1 Pin mit Verbindung)
- execution_flows im EventGraph nicht-leer
- data_flows im Move Graph nicht-leer (falls vorhanden)
- Alle 3 Fixes (D1+D2+D3) sind implementiert
- FEdGraphPinType hat b_serialize_as_single_precision_float Feld
</success_criteria>

<output>
Nach Abschluss: `.planning/phases/35e-pin-offset-debug/35e-03-SUMMARY.md`
</output>
