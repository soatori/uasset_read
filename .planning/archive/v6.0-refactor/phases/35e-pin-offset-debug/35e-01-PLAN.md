---
phase: "35e"
plan: "01"
type: "execute"
wave: 1
depends_on: []
files_modified:
  - "tools/binary_trace_pin.py"
autonomous: true
requirements:
  - "35e-REQ-01"
  - "35e-REQ-02"
must_haves:
  truths:
    - "Binaere Trace kann DefaultTextValue als FText (nicht FString) verfolgen"
    - "Binaere Trace erfasst fehlende FEdGraphPinType Felder (bIsUObjectWrapper, bSerializeAsSinglePrecisionFloat)"
    - "Trace-Report zeigt beseitigte Abweichung pro Feld an"
    - "Rueckwaerts-Kompatibilitaet fuer UE4-Assets bleibt erhalten"
  artifacts:
    - path: "tools/binary_trace_pin.py"
      provides: "Erweiterte Feld-fuer-Feld Binaerverfolgung"
      min_lines: 700
  key_links:
    - from: "tools/binary_trace_pin.py"
      to: "src/uasset_read/serializers/graph.py"
      via: "read_ue_graph_pin Aufruf"
      pattern: "trace_pin_body|_read_ftext_fstring"
---

<objective>
Erweiterung des binaeren Trace-Tools `tools/binary_trace_pin.py` fuer exhaustive Feld-fuer-Feld Verifikation der UE5 Pin-Serialisierung.

Zweck: Nach Rueckwaerts-Analyse der UE5 C++ Quelle (EdGraphPin.cpp L1838-1876) und Identifikation der drei echten 4-Byte-Abweichungsursachen (DefaultTextValue FString statt FText, fehlendes bIsUObjectWrapper, fehlendes bSerializeAsSinglePrecisionFloat) muss das Diagnosewerkzeug in der Lage sein, ALLE drei reparaturbeduerftigen Stellen prazise zu verfolgen.

Ausgabe: Erweiterter Binaer-Trace, der DefaultTextValue als FText (flags + history_type + body) und die fehlenden FEdGraphPinType-Felder korrekt trace-t.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/35e-pin-offset-debug/35e-RESEARCH.md
@.planning/phases/35e-pin-offset-debug/35e-CONTEXT.md
@tools/binary_trace_pin.py
@src/uasset_read/serializers/graph.py

## Kernbefund (aus RESEARCH.md)

D1: FEdGraphPinType `bIsUObjectWrapper` — SKIP (release_version=0 < 10, GUID mismatch) +1B
D2: FEdGraphPinType `bSerializeAsSinglePrecisionFloat` — vollstaendig nicht implementiert +1B
D3: DefaultTextValue `_read_ftext_fstring()` statt vollstaendigem FText — +2B bis +13B

Kombiniert mit D1(1)+D2(1)+D3(None FText: 6-4=2) = +4 Bytes exakt.

<interfaces>
Aus tools/binary_trace_pin.py:
```python
# Kernfunktion: trace_pin_body() — verfolgt jedes Feld
# Hilfsfunktionen: trace_field(), trace_fname(), trace_ftext_flags(),
#   trace_ftext_history_type(), trace_ftext_body(), trace_fstring(),
#   trace_i32(), trace_pin_type(), trace_linkedto_array()
```
Aus src/uasset_read/serializers/graph.py:
```python
def _read_ftext_fstring(archive: FArchive) -> str:
    """Liest FText als vereinfachtes FString (FALSCH fuer DefaultTextValue)."""
    
def read_ed_graph_pin_type(archive, name_map, summary) -> FEdGraphPinType:
    """Fehlt bSerializeAsSinglePrecisionFloat + bIsUObjectWrapper fallback."""
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: DefaultTextValue FText-Tracing in trace_pin_body() ersetzen</name>
  <read_first>
    tools/binary_trace_pin.py (Zeilen 411-470, Funktion trace_pin_body())
    src/uasset_read/serializers/graph.py (Zeilen 417-423, DefaultTextValue _read_ftext_fstring)
    35e-RESEARCH.md (Architecture Patterns Abschnitt "Pin Body")
  </read_first>
  <files>tools/binary_trace_pin.py</files>
  <action>
    In `trace_pin_body()` (ca. Zeile 463-465) die DefaultTextValue-Trace ersetzen:

    AKTUELL:
    ```python
    # 10. DefaultTextValue (FString — UE5 simple format)  <-- FALSCH
    traces.append(trace_fstring(archive, "DefaultTextValue"))
    ```

    ERSETZEN MIT:
    ```python
    # 10. DefaultTextValue (FText — NICHT FString!)
    # UE5 C++: Ar << DefaultTextValue;  (EdGraphPin.cpp L1876)
    # FText: flags(i32,4B) + history_type(u8,1B) + body(variable)
    dtv_before = archive.tell()
    dtv_flags = archive.read_i32()
    dtv_after_flags = archive.tell()
    traces.append({
        "field": "DefaultTextValue.flags",
        "before": dtv_before,
        "after": dtv_after_flags,
        "consumed": 4,
        "expected": 4,
        "delta": 0,
        "value": f"0x{dtv_flags:08X}",
        "success": True,
    })
    dtv_ht_before = archive.tell()
    dtv_history_type = archive.read_u8()
    dtv_after_ht = archive.tell()
    traces.append({
        "field": "DefaultTextValue.history_type",
        "before": dtv_ht_before,
        "after": dtv_after_ht,
        "consumed": 1,
        "expected": 1,
        "delta": 0,
        "value": dtv_history_type,
        "success": True,
    })
    # FText body entsprechend history_type verfolgen
    from uasset_read.serializers.graph import read_ftext_with_history
    body_before = archive.tell()
    try:
        dtv_value, dtv_consumed = read_ftext_with_history(
            archive, dtv_history_type,
            tolerant=True,
            ue5_mode=(summary.file_version_ue5 > 0)
        )
        body_after = archive.tell()
        traces.append({
            "field": "DefaultTextValue.body",
            "before": body_before,
            "after": body_after,
            "consumed": body_after - body_before,
            "expected": "variable",
            "delta": "N/A",
            "value": f"history_type={dtv_history_type}, consumed={body_after - body_before}",
            "success": True,
        })
    except Exception as e:
        traces.append({
            "field": "DefaultTextValue.body",
            "before": body_before,
            "after": archive.tell(),
            "consumed": archive.tell() - body_before,
            "expected": "variable",
            "delta": "N/A",
            "value": f"ERROR: {e}",
            "success": False,
        })
    ```

    Zusaetzlich: Import von `read_ftext_with_history` am Anfang der Datei hinzufuegen (im Block der anderen graph.py imports). Nutze:
    ```python
    from uasset_read.serializers.graph import read_ftext_with_history
    ```

    WICHTIG: Verwende `ue5_mode=(summary.file_version_ue5 > 0)` fuer die korrekte b_has_culture bool Grosse.
  </action>
  <acceptance_criteria>
    - `grep -n "DefaultTextValue.flags" tools/binary_trace_pin.py` findet mindestens 1 Treffer
    - `grep -n "DefaultTextValue.history_type" tools/binary_trace_pin.py` findet mindestens 1 Treffer
    - `grep -n "DefaultTextValue.body" tools/binary_trace_pin.py` findet mindestens 1 Treffer
    - `grep -n "read_ftext_with_history" tools/binary_trace_pin.py` findet mindestens 1 Treffer (Import + Aufruf)
    - Kein `trace_fstring(archive, "DefaultTextValue")` mehr in trace_pin_body
  </acceptance_criteria>
  <verify>
    <automated>python -c "import ast; ast.parse(open('tools/binary_trace_pin.py').read()); print('Syntax OK')"</automated>
  </verify>
  <done>
    DefaultTextValue wird im Trace als FText (flags + history_type + body) verfolgt, nicht als einfaches FString.
  </done>
</task>

<task type="auto">
  <name>Task 2: Fehlende FEdGraphPinType Felder in trace_pin_type() hinzufuegen</name>
  <read_first>
    tools/binary_trace_pin.py (Zeilen 344-351, trace_pin_type() bIsUObjectWrapper)
    src/uasset_read/constants.py (Zeilen 120-122, CustomVersion GUIDs)
    35e-RESEARCH.md (D1, D2 im Abschnitt "Aktueller Code vs C++ Quellcode")
  </read_first>
  <files>tools/binary_trace_pin.py</files>
  <action>
    In `trace_pin_type()` (Funktion die FEdGraphPinType trace-t) zwei Ergaenzungen vornehmen:

    **A) bIsUObjectWrapper mit file_version_ue5 Fallback (D1):**
    Ersetze den aktuellen Block (ca. Zeilen 344-351):
    ```python
    # bIsUObjectWrapper (version dependent)
    release_version = summary.get_custom_version(FRELEASE_OBJECT_VERSION_GUID, 0)
    if release_version >= FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER:
        if summary.file_version_ue5 > 0:
            traces.append(trace_field(archive, "PinType.bIsUObjectWrapper", 1, lambda: archive.read_u8()))
        else:
            traces.append(trace_field(archive, "PinType.bIsUObjectWrapper", 4, lambda: archive.read_bool()))
    ```

    ERSETZE MIT:
    ```python
    # bIsUObjectWrapper (version dependent, +1 Byte Abweichung Quelle D1)
    # C++: if Ar.CustomVer(FReleaseObjectVersion::GUID) >= PinTypeIncludesUObjectWrapperFlag
    # Fallback: ue5_version > 0 bedeutet immer ReleaseObjectVersion >= 10
    if release_version >= FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER or summary.file_version_ue5 > 0:
        if summary.file_version_ue5 > 0:
            traces.append(trace_field(archive, "PinType.bIsUObjectWrapper", 1, lambda: archive.read_u8()))
        else:
            traces.append(trace_field(archive, "PinType.bIsUObjectWrapper", 4, lambda: archive.read_bool()))
    else:
        traces.append({
            "field": "PinType.bIsUObjectWrapper",
            "before": 0,
            "after": 0,
            "consumed": 0,
            "expected": 0,
            "delta": 0,
            "value": "SKIPPED (release_version=0, no ue5 fallback)",
            "success": True,
        })
    ```

    **B) bSerializeAsSinglePrecisionFloat hinzufuegen (D2):**
    DIREKT NACH dem bIsUObjectWrapper Block (innerhalb der `use_custom_serialization`-Sektion, vor `return traces`):
    ```python
    # bSerializeAsSinglePrecisionFloat (fehlendes Feld, +1 Byte Abweichung Quelle D2)
    # C++: WITH_EDITOR && FUE5ReleaseStreamObjectVersion >= SerializeFloatPinDefaultValuesAsSinglePrecision
    # Wir lesen das Feld immer bei UE5 Assets (WITH_EDITOR Daten sind vorhanden fuer Entwicklungs-Builds)
    if summary.file_version_ue5 > 0:
        traces.append(trace_field(archive, "PinType.bSerializeAsSinglePrecisionFloat", 1, lambda: archive.read_u8()))
    ```

    **C) In der default-reflection Sektion (nicht use_custom_serialization):**
    Nach dem FlagsByte Trace (Zeilen 281-294) ebenso bSerializeAsSinglePrecisionFloat hinzufuegen:
    ```python
    if summary.file_version_ue5 > 0:
        traces.append(trace_field(archive, "PinType.bSerializeAsSinglePrecisionFloat", 1, lambda: archive.read_u8()))
    ```
  </acceptance_criteria>
    - `grep -c "summary.file_version_ue5 > 0" tools/binary_trace_pin.py` erhoeht sich um min. 2 Vorkommen
    - `grep -n "bSerializeAsSinglePrecisionFloat" tools/binary_trace_pin.py` findet min. 1 Treffer
    - `grep -n "BIsUObjectWrapper.*fallback\|release_version.*ue5_version.*or" tools/binary_trace_pin.py` ist vorhanden
  </acceptance_criteria>
  <verify>
    <automated>python -c "import ast; ast.parse(open('tools/binary_trace_pin.py').read()); print('Syntax OK')"</automated>
  </verify>
  <done>
    trace_pin_type() erfasst bIsUObjectWrapper mit file_version_ue5 Fallback sowie bSerializeAsSinglePrecisionFloat.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries
| Boundary | Description |
|----------|-------------|
| binary_trace_pin.py -> FArchive | Das Tool liest aus einer FArchive-Instanz, die bereits validierte .uasset-Dateien oeffnet. Kein neues Sicherheitsrisiko. |

## STRIDE Threat Register
| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-35e-01 | EoP | binary_trace_pin.py | accept | Nur Diagnosewerkzeug, keine Produktionsaenderungen. Aendert keine geparsten Daten. |
</threat_model>

<verification>
1. Syntax-Check: `python -c "import ast; ast.parse(open('tools/binary_trace_pin.py').read()); print('Syntax OK')"` muss OK sein
2. Import-Check: `python -c "import sys; sys.path.insert(0,'src'); exec(open('tools/binary_trace_pin.py').read())"` muss ohne ImportError laufen
3. Trace-Run: `python tools/binary_trace_pin.py --asset "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset" --node-export-idx 40 --pin-index 0` muss mit DefaultTextValue.flags/history_type/body Zeilen ausgeben
</verification>

<success_criteria>
- `python tools/binary_trace_pin.py --asset <asset> --node-export-idx 40 --pin-index 0` laeuft ohne Fehler
- Ausgabe enthaelt "DefaultTextValue.flags", "DefaultTextValue.history_type", "DefaultTextValue.body"
- Ausgabe enthaelt "PinType.bIsUObjectWrapper" mit consumed=1 oder "SKIPPED"
- Ausgabe enthaelt "PinType.bSerializeAsSinglePrecisionFloat" mit consumed=1
- Keine Syntax/Import-Fehler
</success_criteria>

<output>
Nach Abschluss: `.planning/phases/35e-pin-offset-debug/35e-01-SUMMARY.md`
</output>
