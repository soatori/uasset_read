"""Collection budget: the sample-first baseline may not grow past ITEM_BUDGET.

Spec: docs/superpowers/specs/2026-09-28-sample-first-test-baseline-design.md
Budget 100 -> 111 on 2026-10-06 by user ruling (A5 VersionContext contract-test
expansion): 111 is the measured final value, not headroom.
Budget 111 -> 112 on 2026-10-20 (dead-name sweep guard, plan Task 6): 112 is the measured final value, not headroom.
Budget 112 -> 125 on 2026-10-22 (issue #651 synthetic Pak index reader, 13
mechanics tests in tests/test_pak_reader.py; no real .pak fixture exists, so
these stay synthetic and honestly named).
Budget 152 -> 153 on 2026-10-24 (issue #662 UE4 graph carrier): the 68th manifest sample
adds one parametrized parse item; 153 is the measured final value, not headroom.
Budget 153 -> 158 on 2026-10-24 (issue #662 UE 5.8.2 user fixtures): the 69th-73rd
manifest samples add five parametrized parse items; 158 is the measured final value,
not headroom.
Budget 158 -> 161 on 2026-10-26 (issue #656 UE5.3 graph partial carrier): the 74th
manifest sample adds one parametrized parse item, plus two sample-backed tests
(Helm VariableSet pins, UE5.3 1009 partial carrier); 161 is the measured final
value, not headroom.
Budget 161 -> 162 on 2026-10-27 (audit P0 fix 1, switch-value jump regression): 162 is the measured final value, not headroom.
Budget 162 -> 163 on 2026-10-27 (audit P0 fix 2, kismet tolerant opaque-tail recovery): 163 is the measured final value, not headroom.
Budget 163 -> 164 on 2026-10-27 (audit P0 fix 3, container recursion depth): 164 is the measured final value, not headroom.
Budget 164 -> 165 on 2026-10-27 (audit P0 fix 4, interface-ref bounds): 165 is the measured final value, not headroom.
Budget 165 -> 166 on 2026-10-27 (audit P0 fix 5, LWC Matrix/TwoVectors precision): 166 is the measured final value, not headroom.
Budget 166 -> 167 on 2026-10-27 (audit P0 fix 6, tagged FText history 0xFF): 167 is the measured final value, not headroom.
Budget 167 -> 168 on 2026-10-27 (audit P0 fix 7, fstring padding-zone seek gating): 168 is the measured final value, not headroom.
Budget 168 -> 169 on 2026-10-27 (audit P0 fix 8, table-tail keeps property bag): 169 is the measured final value, not headroom.
Budget 169 -> 170 on 2026-10-27 (audit P0 fix 9, node pin export bounds): 170 is the measured final value, not headroom.
Budget 170 -> 171 on 2026-10-27 (audit P0 fix 10, utoc directory-graph guards): 171 is the measured final value, not headroom.
Budget 171 -> 172 on 2026-10-28 (audit cleanup Task 3, payload descriptor kind evidence): 172 is the measured final value, not headroom.
Budget 172 -> 173 on 2026-11-06 (untrusted-read Task 2, BulkData tail heuristic deleted): 173 is the measured final value, not headroom.
Budget 173 -> 174 on 2026-11-12 (untrusted-read Task 3, one bad header field keeps the parsed tables): 174 is the measured final value, not headroom.
Budget 174 -> 175 on 2026-11-12 (untrusted-read Task 4, property values bounded to PropertyTag size): 175 is the measured final value, not headroom.
Budget 175 -> 176 on 2026-11-12 (untrusted-read Task 5, oversized PropertyTag size keeps earlier properties): 176 is the measured final value, not headroom.
Budget 176 -> 177 on 2026-11-12 (untrusted-read Task 6, FString bounds respect the export window): 177 is the measured final value, not headroom.
Budget 177 -> 178 on 2026-11-12 (untrusted-read Task 7, null pin slot consumes only its flag): 178 is the measured final value, not headroom.
Budget 178 -> 179 on 2026-11-12 (untrusted-read Task 8, failed graphs never claim decoded): 179 is the measured final value, not headroom.
Budget 179 -> 180 on 2026-11-12 (untrusted-read Task 9, nonexistent package index stays unresolved): 180 is the measured final value, not headroom.
Budget 180 -> 181 on 2026-11-12 (untrusted-read Task 10, out-of-range script name not reported verified): 181 is the measured final value, not headroom.
Budget 181 -> 182 on 2026-11-12 (untrusted-read Task 11, property-layer failures stay diagnosed): 182 is the measured final value, not headroom.
Budget 182 -> 183 on 2026-11-12 (untrusted-read Task 12, collection counts bounded by declared payload): 183 is the measured final value, not headroom.
Budget 183 -> 184 on 2026-11-12 (untrusted-read Task 13, agent boundary wraps memory-limit failures): 184 is the measured final value, not headroom.
Budget 184 -> 186 on 2026-11-15 (#672, stalled collection tails preserved as opaque sibling entries): 186 is the measured final value, not headroom.
Budget 186 -> 189 on 2026-11-18 (blueprint C++ translation data gaps Task 1, pin
container/object/reference types projected: three sample-backed tests).
189 is the measured final value, not headroom.
Budget 189 -> 192 on 2026-11-18 (blueprint C++ translation data gaps Task 2,
function-entry linkage and CFG/exec-chain attribution: three sample-backed
tests). 192 is the measured final value, not headroom.
Budget 192 -> 195 on 2026-11-18 (blueprint C++ translation data gaps Task 3, UFunction FunctionFlags decoded into FunctionDeclaration.flags: three sample-backed tests).
195 is the measured final value, not headroom.
Budget 195 -> 198 on 2026-11-18 (blueprint C++ translation data gaps Task 4, member replication projected and VariableDefinition.cpp_type derived: three sample-backed tests).
198 is the measured final value, not headroom.
Budget 198 -> 199 on 2026-11-18 (blueprint C++ translation data gaps Task 5, dispatcher records resolved from DelegateReference: one sample-backed test).
199 is the measured final value, not headroom.
Budget 199 -> 201 on 2026-11-18 (blueprint C++ translation data gaps Task 6, SCS attach tree projected onto components: two sample-backed tests).
201 is the measured final value, not headroom.
Budget 201 -> 202 on 2026-11-18 (blueprint C++ translation data gaps Task 7, no Python repr in functions[].reads/writes: one sample-backed test).
202 is the measured final value, not headroom.
Budget 202 -> 207 on 2026-11-18 (blueprint C++ translation data gaps final-review fix pass (C1/I1/I2/I4/I5): five sample-backed tests).
207 is the measured final value, not headroom.
Budget 207 -> 208 on 2026-11-18 (blueprint C++ translation data gaps deferred-minor pass: one sample-backed test).
208 is the measured final value, not headroom.
Budget 208 -> 209 on 2026-11-19 (review follow-up on #674: undetermined cpp_type is
explicit through a structured diagnostic, one sample-backed test).
209 is the measured final value, not headroom.
No fixtures live here — the baseline is driven by real samples in
tests/test_samples.py; temporary probes belong to untracked temp/.
"""

from __future__ import annotations

import pytest

ITEM_BUDGET = 209


def pytest_collection_modifyitems(session: pytest.Session, config: pytest.Config, items: list[pytest.Item]) -> None:
    if len(items) > ITEM_BUDGET:
        raise pytest.UsageError(
            f"collected {len(items)} items, sample-first budget is {ITEM_BUDGET}; "
            "fold checks into sample-backed aggregates or move probes to temp/"
        )
