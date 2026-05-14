---
phase: 35b
plan: 05
type: execute
wave: 3
depends_on:
  - 35b-01
  - 35b-02
  - 35b-03
files_modified:
  - tests/test_phase21_verification.py
  - tests/test_ue5_pin_integration.py
autonomous: true
requirements:
  - TEST-01
  - TEST-02

must_haves:
  truths:
    - "pin.linked_to_raw is non-empty for pins that have connections in BP_FirstPersonCharacter.uasset"
    - "execution_flows contains IA_Jump -> Jump -> StopJumping chain in EventGraph"
    - "data_flows contains ActionValue_X/Y connections in Move graph"
    - "All existing tests pass (397+ passed, 0 failed)"
  artifacts:
    - path: "tests/test_ue5_pin_integration.py"
      provides: "Integration tests for linked_to_raw, execution_flows, data_flows"
      exports: ["TestUE5PinIntegration"]
    - path: "tests/test_phase21_verification.py"
      provides: "Previously skipped Phase 21 tests unskipped and passing"
      exports: ["TestExecutionFlow", "TestDataFlow"]
  key_links:
    - from: "tests/test_ue5_pin_integration.py"
      to: "src/uasset_read/serializers/graph.py"
      via: "parse_uasset -> read_ue_graph_pin -> read_pin_array -> linked_to_raw populated"
      pattern: "linked_to_raw"
    - from: "tests/test_phase21_verification.py"
      to: "src/uasset_read/graph/flow_builder.py"
      via: "build_execution_flows / build_data_flows use linked_to_raw"
      pattern: "execution_flows|data_flows"
---

<objective>
Integration tests: verify linked_to_raw, execution_flows, and data_flows all work correctly after bool serialization fixes.

Purpose: The bool serialization fixes (35b-01, 35b-02, 35b-03) should resolve the empty pin.linked_to_raw issue. This plan creates integration tests to verify the end-to-end pipeline works: correct pin parsing -> connection resolution -> execution flow tracing -> data flow extraction. Additionally, unskips previously-skipped Phase 21 tests that were blocked by this issue.

Output: Integration tests confirming linked_to_raw non-empty, execution_flows and data_flows populated, Phase 21 tests unskipped and passing.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/35b-pin-connection-debug/35b-RESEARCH.md
@tests/test_phase21_verification.py
@src/uasset_read/graph/flow_builder.py

<interfaces>
<!-- Key types the integration tests will use: -->
<!-- UEdGraphPin.linked_to_raw: List[dict] with {"owning_node": str, "pin_guid": str} -->
<!-- ParseResult.graphs: List[UEdGraph] each with nodes -> pins -->
<!-- graphs_summary: contains execution_flows, data_flows, connections arrays -->

<!-- test_phase21_verification.py currently has skipped tests: -->
<!-- L100: @pytest.skip on test_jump_started_flow -->
<!-- L134: @pytest.skip on test_jump_completed_flow -->
<!-- L193: @pytest.skip on test_actionvalue_x_to_right -->
<!-- L291: @pytest.skip on test_function_reference_member_name -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create integration tests for linked_to_raw, execution_flows, data_flows</name>
  <files>tests/test_ue5_pin_integration.py</files>
  <behavior>
    - Test: BP_FirstPersonCharacter.uasset parses successfully with no errors
    - Test: EventGraph has nodes with non-empty linked_to_raw on their output pins
    - Test: execution_flows in EventGraph is non-empty and contains Jump or StopJumping function calls
    - Test: data_flows in Move graph is non-empty
    - Test: connections list has entries (source -> target pin connections)
    - Test: At least one pin has linked_to_raw length > 0
  </behavior>
  <action>Create integration tests that:
1. Parse BP_FirstPersonCharacter.uasset using parse_uasset()
2. Verify parse success and graphs exist
3. Check that EventGraph nodes have pins with linked_to_raw entries (the key fix verification)
4. Verify execution_flows is non-empty in EventGraph
5. Verify data_flows is non-empty in Move graph
6. Verify connections list has entries

Use format_json_full() to get the JSON output for flow/connection verification. Also directly inspect ParseResult.graphs for linked_to_raw on pins.</action>
  <verify>
    <automated>python -m pytest tests/test_ue5_pin_integration.py -v -x</automated>
  </verify>
  <done>Integration tests pass, confirming linked_to_raw non-empty, execution_flows/data_flows populated</done>
</task>

<task type="auto">
  <name>Task 2: Unskip Phase 21 tests that were blocked by empty linked_to_raw</name>
  <files>tests/test_phase21_verification.py</files>
  <action>Remove the `@pytest.mark.skip(...)` decorators from the following tests in test_phase21_verification.py (keeping the `@pytest.mark.skipif(not os.path.exists(...))` decorators):

1. L100: `@pytest.mark.skip(reason="Phase 34: graph parsing functional issue -- flow verification")` on test_jump_started_flow
2. L134: `@pytest.mark.skip(reason="Phase 34: graph parsing functional issue -- flow verification")` on test_jump_completed_flow
3. L193: `@pytest.mark.skip(reason="Phase 34: graph parsing functional issue -- data flow verification")` on test_actionvalue_x_to_right
4. L291: `@pytest.mark.skip(reason="Phase 34: graph parsing functional issue -- node property verification")` on test_function_reference_member_name

After removing skips, run the tests to verify they pass with the bool serialization fixes in place. If any test still fails, investigate and fix -- do NOT re-skip.</action>
  <verify>
    <automated>python -m pytest tests/test_phase21_verification.py -v --tb=short -k "test_jump_started_flow or test_jump_completed_flow or test_actionvalue_x_to_right or test_function_reference_member_name"</automated>
  </verify>
  <done>Previously skipped Phase 21 tests are unskipped and passing</done>
</task>

<task type="auto">
  <name>Task 3: Full test suite regression check</name>
  <files>tests/</files>
  <action>Run the complete test suite to verify no regressions:

```bash
python -m pytest tests/ --tb=short -x
```

Expected: 397+ passed, 0 failed. The skipped count may decrease as Phase 21 tests are unskipped.

This is the final gate -- if any test fails, the fixes must be re-examined before the phase can be considered complete.</action>
  <verify>
    <automated>python -m pytest tests/ --tb=short -x</automated>
  </verify>
  <done>Full test suite passes with 397+ passed, 0 failed</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Test asset -> integration tests | BP_FirstPersonCharacter.uasset is external; test must handle parse failures gracefully |
| Integration results -> phase completion | False positives would incorrectly mark the phase as complete |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-35b-12 | Integrity | test_ue5_pin_integration.py | mitigate | Direct assertions on linked_to_raw length > 0; no mocking of pin parsing |
| T-35b-13 | Denial of Service | Full test suite | accept | pytest -x flag stops on first failure; existing test infrastructure handles timeouts |
| T-35b-14 | Tampering | Unskipped Phase 21 tests | mitigate | Tests assert on actual parse results; no test data modification |
</threat_model>

<verification>
- tests/test_ue5_pin_integration.py passes (6 tests)
- Phase 21 tests unskipped and passing (4 tests)
- Full test suite: `python -m pytest tests/ --tb=short -x` returns 397+ passed, 0 failed
- linked_to_raw non-empty on BP_FirstPersonCharacter.uasset pins
- execution_flows contains Jump/StopJumping function calls
- data_flows contains connections in Move graph
- Binary trace tool (35b-04) confirms zero drift on pin body parsing
</verification>

<success_criteria>
- Integration tests confirm linked_to_raw non-empty on EventGraph pins
- execution_flows in EventGraph contains IA_Jump -> Jump -> StopJumping chain
- data_flows in Move graph contains ActionValue_X/Y connections
- All Phase 21 tests unskipped and passing
- Full test suite: 397+ passed, 0 failed
- Binary trace tool reports zero byte drift
</success_criteria>

<output>
After completion, create `.planning/phases/35b-pin-connection-debug/35b-05-SUMMARY.md`
</output>
