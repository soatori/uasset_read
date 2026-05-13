---
phase: "35e"
plan: "04"
type: "execute"
wave: 4
depends_on:
  - "35e-03"
files_modified:
  - "tests/test_ue5_pin_integration.py"
  - "tests/test_ue5_pin_offset_verification.py"
autonomous: true
requirements:
  - "35e-REQ-04"
must_haves:
  truths:
    - "Integrationstest test_pins_have_linked_to_raw PASS (linked_to_raw nicht-leer)"
    - "Integrationstest test_execution_flows_not_empty PASS"
    - "Integrationstest test_data_flows_not_empty PASS"
    - "Integrationstest test_connections_not_empty PASS"
    - "Vollstaendiger Verifikationstest fuer alle 3 Fixes existiert"
    - "Gesamte Test-Suite: 0 neue Fehler (keine Regression)"
  artifacts:
    - path: "tests/test_ue5_pin_offset_verification.py"
      provides: "Integrationstest der 3 Fixes fuer 4-Byte-Abweichung"
      min_lines: 50
  key_links:
    - from: "test_ue5_pin_offset_verification.py"
      to: "uasset_read.parse_uasset"
      via: "Test-Aufruf"
      pattern: "parse_uasset.*TEST_ASSET"
---

<objective>
Integrationstests und vollstaendige Regression nach Anwendung der 3 Fixes (D1+D2+D3).

Zweck: Sicherstellen dass die kombinierten Fixes in den Plaenen 02 und 03 linked_to_raw, execution_flows und data_flows korrekt lesen, und dass keine Regression fuer bestehende Funktionalitaet auftritt.

Ausgabe: 
1. Neue Verifikationstest-Datei `tests/test_ue5_pin_offset_verification.py` mit Tests fuer alle 3 Fixes
2. Aktualisierter Integrationstest in `tests/test_ue5_pin_integration.py` (falls noetig)
3. `pytest tests/` laeuft ohne Regression
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/35e-pin-offset-debug/35e-RESEARCH.md
@.planning/phases/35e-pin-offset-debug/35e-03-SUMMARY.md (nach Plan 03)
@tests/test_ue5_pin_integration.py
@src/uasset_read/serializers/graph.py

## Aktuelle Tests (vor Plan 04)

`tests/test_ue5_pin_integration.py` enthaelt:
1. `test_asset_parses_successfully` — Parse-check (PASS)
2. `test_eventgraph_has_nodes_with_pins` — Node/Pin Zaehlung (PASS)
3. `test_pins_have_linked_to_raw` — **Erwartet FAIL vor Fix** (PASS nach Fix)
4. `test_execution_flows_not_empty` — **Erwartet FAIL vor Fix** (PASS nach Fix)
5. `test_data_flows_not_empty` — **Erwartet FAIL vor Fix** (PASS nach Fix)
6. `test_connections_not_empty` — **Erwartet FAIL vor Fix** (PASS nach Fix)

## 3 Fixes (D1+D2+D3) die getestet werden muessen

| Fix | Datei | Typ | Bytes |
|-----|-------|-----|-------|
| D1: bIsUObjectWrapper fallback | graph.py | bool read | +1 |
| D2: bSerializeAsSinglePrecisionFloat | graph.py | bool read | +1 |
| D3: DefaultTextValue FString→FText | graph.py | FText read | +2~+13 |
| **Total** | | | **+4 (None FText)** |
</context>

<tasks>

<task type="auto">
  <name>Task 1: Erstelle test_ue5_pin_offset_verification.py mit 3 Fix Verifikation</name>
  <read_first>
    src/uasset_read/serializers/graph.py (read_ue_graph_pin, read_ed_graph_pin_type, read_ftext_with_history)
    src/uasset_read/models/core.py (FEdGraphPinType, UEdGraphPin)
    tests/test_ue5_pin_integration.py (bestehende Teststruktur)
    35e-RESEARCH.md (Abschnitt "Validierungsmethoden")
  </read_first>
  <files>tests/test_ue5_pin_offset_verification.py</files>
  <action>
    Erstelle eine neue Testdatei `tests/test_ue5_pin_offset_verification.py` mit den folgenden Test-Klassen:

    ```python
    """Verification tests for Phase 35e 4-byte offset fixes.
    
    Tests D1 (bIsUObjectWrapper fallback), D2 (bSerializeAsSinglePrecisionFloat),
    and D3 (DefaultTextValue FString→FText) from RESEARCH.md.
    
    These 3 fixes collectively correct the 4-byte drift that caused
    linked_to_raw to be empty for all pins.
    """
    import pytest
    from uasset_read import parse_uasset, format_json_full
    
    TEST_ASSET = "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"
    
    
    @pytest.mark.skipif(not __import__('os').path.exists(TEST_ASSET), reason="Test asset not found")
    class TestDefaultTextValueFText:
        """Verify D3: DefaultTextValue is read as FText, not FString."""
    
        def test_parse_does_not_crash(self):
            """Parsing the asset does not crash after FText fix."""
            result = parse_uasset(TEST_ASSET)
            assert result is not None
    
        def test_pins_have_expected_structure(self):
            """Pins after FText fix have expected attributes."""
            result = parse_uasset(TEST_ASSET)
            event_graph = None
            for g in result.graphs:
                if g.graph_name == "EventGraph":
                    event_graph = g
                    break
            assert event_graph is not None
            assert len(event_graph.nodes) > 0
            # Mindestens ein Pin existiert
            total_pins = sum(len(n.pins) for n in event_graph.nodes)
            assert total_pins > 0
    
    
    @pytest.mark.skipif(not __import__('os').path.exists(TEST_ASSET), reason="Test asset not found")
    class TestFEdGraphPinTypeFields:
        """Verify D1 + D2: bIsUObjectWrapper and bSerializeAsSinglePrecisionFloat."""
    
        def test_pin_type_has_uobject_wrapper(self):
            """FEdGraphPinType has b_serialize_as_single_precision_float field."""
            from uasset_read.models.core import FEdGraphPinType
            assert hasattr(FEdGraphPinType, 'b_serialize_as_single_precision_float'), \
                "Missing b_serialize_as_single_precision_float field"
    
        def test_pin_type_parses_without_drift(self):
            """Parsing pins produces reasonable PinType values (no drift)."""
            result = parse_uasset(TEST_ASSET)
            event_graph = None
            for g in result.graphs:
                if g.graph_name == "EventGraph":
                    event_graph = g
                    break
            assert event_graph is not None
            # Verify pin_type values are reasonable (not garbage)
            for node in event_graph.nodes:
                for pin in node.pins:
                    if pin.pin_type:
                        assert pin.pin_type.pin_category is None or isinstance(pin.pin_type.pin_category, (str, type(None)))
                        assert isinstance(pin.pin_type.container_type, int)
                        assert pin.pin_type.container_type in (0, 1, 2, 3)
    
    
    @pytest.mark.skipif(not __import__('os').path.exists(TEST_ASSET), reason="Test asset not found")
    class TestLinkedToNonEmpty:
        """Verify linked_to_raw is non-empty after all 3 fixes."""
    
        def test_at_least_one_pin_has_linked_to_raw(self):
            """At least one pin has non-empty linked_to_raw."""
            result = parse_uasset(TEST_ASSET)
            total_pins = 0
            pins_with_links = 0
            for g in result.graphs:
                for n in g.nodes:
                    for pin in n.pins:
                        total_pins += 1
                        links = getattr(pin, 'linked_to_raw', [])
                        if links and len(links) > 0:
                            pins_with_links += 1
            assert total_pins > 0, "No pins found in any graph"
            assert pins_with_links > 0, \
                f"None of {total_pins} pins have linked_to_raw entries (4-byte drift still present)"
    
        def test_linked_to_raw_has_expected_structure(self):
            """linked_to_raw entries contain owning_node and pin_guid."""
            result = parse_uasset(TEST_ASSET)
            found_with_structure = False
            for g in result.graphs:
                for n in g.nodes:
                    for pin in n.pins:
                        links = getattr(pin, 'linked_to_raw', [])
                        for link in links:
                            assert 'owning_node' in link, f"Missing owning_node in link: {link}"
                            assert 'pin_guid' in link, f"Missing pin_guid in link: {link}"
                            found_with_structure = True
            assert found_with_structure, "No linked_to_raw entries with expected structure"
    
        def test_linked_to_count_reasonable(self):
            """Total linked_to_raw entries is reasonable (>0 and <1000)."""
            result = parse_uasset(TEST_ASSET)
            total_links = 0
            for g in result.graphs:
                for n in g.nodes:
                    for pin in n.pins:
                        links = getattr(pin, 'linked_to_raw', [])
                        total_links += len(links)
            assert 0 < total_links < 1000, \
                f"linked_to_raw total {total_links} is out of reasonable range"
    
        def test_execution_flows_not_empty(self):
            """execution_flows is non-empty in EventGraph."""
            result = parse_uasset(TEST_ASSET)
            json_output = format_json_full(result)
            event_graph = None
            graphs = json_output.get("blueprint", {}).get("graphs", [])
            for g in graphs:
                if g.get("graph_name") == "EventGraph":
                    event_graph = g
                    break
            assert event_graph is not None, "EventGraph not found in JSON"
            execution_flows = event_graph.get("execution_flows", [])
            assert len(execution_flows) > 0, "execution_flows is empty after fix"
    
        def test_data_flows_not_empty(self):
            """data_flows is non-empty in Move graph or any graph."""
            result = parse_uasset(TEST_ASSET)
            json_output = format_json_full(result)
            graphs = json_output.get("blueprint", {}).get("graphs", [])
            any_data_flows = False
            for g in graphs:
                data_flows = g.get("data_flows", [])
                if len(data_flows) > 0:
                    any_data_flows = True
                    break
            assert any_data_flows, "No graph has data_flows after fix"
    
        def test_connections_not_empty(self):
            """connections list is non-empty (source -> target pin connections)."""
            result = parse_uasset(TEST_ASSET)
            json_output = format_json_full(result)
            graphs = json_output.get("blueprint", {}).get("graphs", [])
            any_connections = False
            for g in graphs:
                connections = g.get("connections", [])
                if len(connections) > 0:
                    any_connections = True
                    break
            assert any_connections, "No graph has connections after fix"
    
    
    @pytest.mark.skipif(not __import__('os').path.exists(TEST_ASSET), reason="Test asset not found")
    class TestRegression:
        """Ensure no regression after fixes."""
    
        def test_asset_parses_without_errors(self):
            """Asset parses without errors."""
            result = parse_uasset(TEST_ASSET)
            assert result is not None
            assert len(result.graphs) > 0
    
        def test_eventgraph_has_reasonable_nodes(self):
            """EventGraph has between 1 and 100 nodes."""
            result = parse_uasset(TEST_ASSET)
            event_graph = None
            for g in result.graphs:
                if g.graph_name == "EventGraph":
                    event_graph = g
                    break
            assert event_graph is not None
            assert 1 <= len(event_graph.nodes) <= 100, \
                f"Unexpected node count: {len(event_graph.nodes)}"
    
        def test_existing_ue5_tests_still_pass(self):
            """Existing integration tests still pass."""
            from tests.test_ue5_pin_integration import TestUE5PinIntegration
            # Run each test manually
            for test_name in dir(TestUE5PinIntegration):
                if test_name.startswith('test_'):
                    test_method = getattr(TestUE5PinIntegration(test_name), test_name)
                    # Skip if pytest.mark.skipif decorator
                    test_method()
    ```

    WICHTIG: Die Datei muss korrekte pytest-Struktur haben. Alle Tests verwenden `@pytest.mark.skipif` fuer das Asset.
    Der Import von `test_ue5_pin_integration` in `test_existing_ue5_tests_still_pass` funktioniert nur wenn das Modul importierbar ist.
    Alternativ kann dieser Test auch die Logik duplizieren statt zu importieren.

    Die Test-Klasse `TestLinkedToNonEmpty` ist die kritischste — sie verifiziert dass linked_to_raw nach allen 3 Fixes nicht-leer ist.
  </action>
  <acceptance_criteria>
    - Datei existiert: `tests/test_ue5_pin_offset_verification.py`
    - Datei enthaelt `class TestDefaultTextValueFText`
    - Datei enthaelt `class TestFEdGraphPinTypeFields`
    - Datei enthaelt `class TestLinkedToNonEmpty`
    - Datei enthaelt `class TestRegression`
    - `grep -c "assert.*>" tests/test_ue5_pin_offset_verification.py` >= 10 (genuegend Assertions)
    - `grep -c "linked_to_raw" tests/test_ue5_pin_offset_verification.py` >= 5
  </acceptance_criteria>
  <verify>
    <automated>python -m pytest tests/test_ue5_pin_offset_verification.py -v --tb=short 2>&1 | tail -20</automated>
  </verify>
  <done>
    Neue Verifikationstest-Datei existiert mit Tests fuer alle 3 Fixes.
    linked_to_raw, execution_flows, data_flows Tests sind enthalten.
  </done>
</task>

<task type="auto">
  <name>Task 2: Vollstaendige Regression mit pytest tests/ ausfuehren</name>
  <read_first>
    tests/test_ue5_pin_integration.py (bestehende Tests, nach Fix sollten ALLE passen)
    35e-RESEARCH.md (Abschnitt "Validierung")
  </read_first>
  <files>tests/test_ue5_pin_integration.py</files>
  <action>
    Fuehre die vollstaendige Regression aus:

    ```bash
    python -m pytest tests/ -v --tb=short 2>&1
    ```

    WICHTIG: Falls die bestehenden Integrationstests in `test_ue5_pin_integration.py` bereits auf PASS erwarten nach den Fixes,
    koennen sie unveraendert bleiben. Pruefe ob `test_pins_have_linked_to_raw` in der Datei jetzt PASS ist.

    **Falls `test_pins_have_linked_to_raw` immer noch FAIL:** Das bedeutet dass trotz aller 3 Fixes noch immer
    eine Abweichung besteht. Dann dokumentiere das Ergebnis und analysiere mit dem Binary Trace Tool.

    **Falls `test_pins_have_linked_to_raw` jetzt PASS:** Herzlichen Glueckwunsch! Die 4-Byte-Abweichung wurde erfolgreich behoben.

    Sammele die Ergebnisse:
    - Anzahl PASSED
    - Anzahl FAILED (mit Liste der fehlgeschlagenen Tests)
    - Anzahl SKIPPED
    - Alle neuen Tests aus `test_ue5_pin_offset_verification.py` Ergebnisse

    KEINE Aenderungen an `test_ue5_pin_integration.py` sind normalerweise noetig. Nur wenn ein Test durch die Fixes
    unerwartet bricht, dokumentiere und repariere.
  </action>
  <acceptance_criteria>
    - `python -m pytest tests/ --tb=short -q` meldet 0 failed (oder dokumentierte, bekannte Fehler)
    - `python -m pytest tests/test_ue5_pin_offset_verification.py -v --tb=short` meldet 0 failed
    - Alle Test-Ergebnisse sind im SUMMARY dokumentiert
  </acceptance_criteria>
  <verify>
    <automated>python -m pytest tests/ -v --tb=short -q 2>&1 | tail -10</automated>
  </verify>
  <done>
    Vollstaendige Regression abgeschlossen, 0 neue Fehler.
    linked_to_raw-Tests PASS.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries
| Boundary | Description |
|----------|-------------|
| Tests -> parse_uasset | Tests rufen die Produktions-API auf. Kein neues Sicherheitsrisiko. |

## STRIDE Threat Register
| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-35e-05 | DoS | test_ue5_pin_offset_verification.py | accept | Nur Testcode. Keine Produktionsaenderungen. Nicht in Produktion eingesetzt. |
</threat_model>

<verification>
1. `python -m pytest tests/test_ue5_pin_offset_verification.py -v --tb=short` — ALLE Tests muessen PASS
2. `python -m pytest tests/test_ue5_pin_integration.py -v --tb=short` — ALLE Tests muessen PASS (inkl. linked_to_raw, execution_flows, data_flows)
3. `python -m pytest tests/ -v --tb=short -q` — 0 failed (oder dokumentierte Ausnahmen)
</verification>

<success_criteria>
- `test_ue5_pin_offset_verification.py`: 12+ Tests alle PASS
- `test_ue5_pin_integration.py`: 6 Tests alle PASS
- `pytest tests/`: 0 failed (keine Regression)
- linked_to_raw: >0 Pins mit Verbindungen
- execution_flows: Nicht-leer in EventGraph
- data_flows: Nicht-leer in mindestens einem Graph
</success_criteria>

<output>
Nach Abschluss: `.planning/phases/35e-pin-offset-debug/35e-04-SUMMARY.md`
</output>
