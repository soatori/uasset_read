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
No fixtures live here — the baseline is driven by real samples in
tests/test_samples.py; temporary probes belong to untracked temp/.
"""

from __future__ import annotations

import pytest

ITEM_BUDGET = 158


def pytest_collection_modifyitems(session: pytest.Session, config: pytest.Config, items: list[pytest.Item]) -> None:
    if len(items) > ITEM_BUDGET:
        raise pytest.UsageError(
            f"collected {len(items)} items, sample-first budget is {ITEM_BUDGET}; "
            "fold checks into sample-backed aggregates or move probes to temp/"
        )
