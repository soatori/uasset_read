"""pytest 全局配置 — 提供大资产门控、测试后内存释放。"""
from __future__ import annotations

import gc

import pytest


# ---------------------------------------------------------------------------
# --include-large 选项
# ---------------------------------------------------------------------------

def pytest_addoption(parser: pytest.Parser) -> None:
    """注册 --include-large 命令行选项。"""
    parser.addoption(
        "--include-large",
        action="store_true",
        default=False,
        help="Include tests marked with @pytest.mark.large (assets > 100 MB)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """未传 --include-large 时，跳过 @pytest.mark.large 标记的测试。"""
    if config.getoption("--include-large"):
        return
    skip_large = pytest.mark.skip(
        reason="large asset test (pass --include-large to enable)"
    )
    for item in items:
        if "large" in item.iter_markers():
            item.add_marker(skip_large)


# ---------------------------------------------------------------------------
# 测试后内存释放
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _gc_after_heavy_test(request: pytest.FixtureRequest):
    """integration / acceptance 测试结束后强制 GC，防止堆无限增长。

    单元测试不涉及资产加载，跳过 GC 以保持速度。
    """
    yield
    markers = {m.name for m in request.node.iter_markers()}
    if markers & {"integration", "acceptance"}:
        gc.collect()
