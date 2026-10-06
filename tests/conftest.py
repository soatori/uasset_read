"""Collection budget: the sample-first baseline may not grow past ITEM_BUDGET.

Spec: docs/superpowers/specs/2026-09-28-sample-first-test-baseline-design.md
Budget 100 -> 111 on 2026-10-06 by user ruling (A5 VersionContext contract-test
expansion): 111 is the measured final value, not headroom.
No fixtures live here — the baseline is driven by real samples in
tests/test_samples.py; temporary probes belong to untracked temp/.
"""

from __future__ import annotations

import pytest

ITEM_BUDGET = 111


def pytest_collection_modifyitems(session: pytest.Session, config: pytest.Config, items: list[pytest.Item]) -> None:
    if len(items) > ITEM_BUDGET:
        raise pytest.UsageError(
            f"collected {len(items)} items, sample-first budget is {ITEM_BUDGET}; "
            "fold checks into sample-backed aggregates or move probes to temp/"
        )
