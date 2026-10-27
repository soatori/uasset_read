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
No fixtures live here — the baseline is driven by real samples in
tests/test_samples.py; temporary probes belong to untracked temp/.
"""

from __future__ import annotations

import pytest

ITEM_BUDGET = 168


def pytest_collection_modifyitems(session: pytest.Session, config: pytest.Config, items: list[pytest.Item]) -> None:
    if len(items) > ITEM_BUDGET:
        raise pytest.UsageError(
            f"collected {len(items)} items, sample-first budget is {ITEM_BUDGET}; "
            "fold checks into sample-backed aggregates or move probes to temp/"
        )
