"""
DependsMap 异常数量防护测试 (#336, #451)。
验证畸形的 DependsMap 数据不会导致解析中断，而是优雅跳过异常条目。
验证无效 PackageIndex 值被检测并通过 warnings 通知调用方。
"""
import struct
import pytest
from uasset_read.archive import ByteArchive
from uasset_read.serializers.package_summary import read_depends_map, PackageFileSummary
from uasset_read.models.status import _result_status


# depends_offset must be > 0 (function entry check), but ByteArchive seeks there
# so data starts at offset=1, first byte is padding
_PADDING = b'\x00'


def _make_summary(
    export_count: int,
    depends_offset: int = 1,
    import_count: int = 0,
) -> PackageFileSummary:
    """Create a minimal PackageFileSummary for testing."""
    summary = PackageFileSummary.__new__(PackageFileSummary)
    summary.depends_offset = depends_offset
    summary.export_count = export_count
    summary.import_count = import_count
    return summary


def _i32_le(value: int) -> bytes:
    """将 int32 编码为小端字节序列。"""
    return struct.pack('<i', value)


def test_depends_map_abnormal_count():
    """DependsMap abnormal count (>10000) should skip entry, return empty list, emit warning."""
    # dep_count = 100000 (exceeds 10000 limit)
    data = _PADDING + _i32_le(100000)

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=1)

    warnings = []
    result = read_depends_map(archive, summary, warnings=warnings)
    assert result == [[]], "Abnormal count entry should be skipped, returning empty list"
    assert len(warnings) == 1, "Should emit a warning for skipped entries"
    assert "1/1 entries skipped" in warnings[0]


def test_depends_map_negative_count():
    """DependsMap negative count should skip entry and emit warning."""
    data = _PADDING + _i32_le(-1)

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=1)

    warnings = []
    result = read_depends_map(archive, summary, warnings=warnings)
    assert result == [[]], "Negative count entry should be skipped, returning empty list"
    assert len(warnings) == 1, "Should emit a warning for skipped entries"
    assert "1/1 entries skipped" in warnings[0]


def test_depends_map_boundary_count():
    """DependsMap boundary count (exactly 10000) should parse normally."""
    # dep_count = 10000, followed by 10000 i32 dependency values (all 0)
    dep_count_bytes = _i32_le(10000)
    deps_bytes = _i32_le(0) * 10000
    data = _PADDING + dep_count_bytes + deps_bytes

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=1)

    warnings = []
    result = read_depends_map(archive, summary, warnings=warnings)
    assert len(result) == 1
    assert len(result[0]) == 10000
    assert warnings == [], "No warnings for valid boundary count"


def test_depends_map_mixed_normal_and_abnormal():
    """Mixed normal and abnormal entries: only skip the abnormal ones, emit warning."""
    # export_count = 3
    # entry 0: dep_count = 2 (normal) -> two deps 0, 0
    # entry 1: dep_count = 50000 (abnormal) -> skip
    # entry 2: dep_count = 1 (normal) -> one dep 0
    data = (
        _PADDING
        + _i32_le(2)       # dep_count = 2
        + _i32_le(0) * 2   # 2 deps
        + _i32_le(50000)   # dep_count = 50000 (abnormal)
        + _i32_le(1)       # dep_count = 1
        + _i32_le(0)       # 1 dep
    )

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=3)

    warnings = []
    result = read_depends_map(archive, summary, warnings=warnings)
    assert len(result) == 3, "Should return 3 entries"
    assert len(result[0]) == 2, "Entry 0 should have 2 dependencies"
    assert result[1] == [], "Entry 1 (abnormal) should be skipped"
    assert len(result[2]) == 1, "Entry 2 should have 1 dependency"
    assert len(warnings) == 1, "Should emit warning for the 1 skipped entry"
    assert "1/3 entries skipped" in warnings[0]


def test_depends_map_empty():
    """DependsMap with no data returns empty list."""
    summary = _make_summary(export_count=0, depends_offset=0)

    result = read_depends_map(ByteArchive(b''), summary)
    assert result == []


def test_depends_map_zero_offset():
    """DependsMap offset=0 returns empty list."""
    summary = _make_summary(export_count=5, depends_offset=0)
    result = read_depends_map(ByteArchive(b'\x00' * 100), summary)
    assert result == []


# ============================================================================
# #451 — Invalid PackageIndex coverage tests
# ============================================================================

def test_depends_map_invalid_import_index():
    """PackageIndex referencing non-existent import triggers warning."""
    # 1 export, 0 imports. Entry 0: dep_count=1, pkg_index=5 (import 5 does not exist)
    data = (
        _PADDING
        + _i32_le(1)    # dep_count = 1
        + _i32_le(5)    # pkg_index = 5 (import ref, but import_count=0)
    )

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=1, import_count=0)

    warnings = []
    result = read_depends_map(archive, summary, warnings=warnings)
    assert len(result) == 1
    assert result[0] == [5], "Index value is preserved even if invalid"
    assert len(warnings) == 1, "Should emit warning for out-of-range import index"
    assert "PackageIndex" in warnings[0]


def test_depends_map_invalid_export_index():
    """PackageIndex referencing non-existent export triggers warning."""
    # 1 export, 0 imports. Entry 0: dep_count=1, pkg_index=-5 (export 4 does not exist)
    data = (
        _PADDING
        + _i32_le(1)     # dep_count = 1
        + _i32_le(-5)    # pkg_index = -5 (export ref, but export_count=1)
    )

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=1, import_count=0)

    warnings = []
    result = read_depends_map(archive, summary, warnings=warnings)
    assert len(result) == 1
    assert result[0] == [-5], "Index value is preserved even if invalid"
    assert len(warnings) == 1, "Should emit warning for out-of-range export index"
    assert "PackageIndex" in warnings[0]


def test_depends_map_valid_indices_no_warning():
    """Valid PackageIndex values (0, in-range import, in-range export) produce no warning."""
    # 1 export, 2 imports. Entry 0: dep_count=4, values: 0, 1, -1
    data = (
        _PADDING
        + _i32_le(3)     # dep_count = 3
        + _i32_le(0)     # null (always valid)
        + _i32_le(1)     # import 0 (valid: 1 <= import_count=2)
        + _i32_le(-1)    # export 0 (valid: 1 <= export_count=1)
    )

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=1, import_count=2)

    warnings = []
    result = read_depends_map(archive, summary, warnings=warnings)
    assert result == [[0, 1, -1]]
    assert warnings == [], "No warnings for valid PackageIndex values"


def test_depends_map_multiple_invalid_indices():
    """Multiple invalid indices in a single entry produce a single aggregated warning."""
    # 1 export, 1 import. Entry 0: dep_count=2, values: 10 (invalid import), -10 (invalid export)
    data = (
        _PADDING
        + _i32_le(2)     # dep_count = 2
        + _i32_le(10)    # pkg_index = 10 (import ref, but import_count=1)
        + _i32_le(-10)   # pkg_index = -10 (export ref, but export_count=1)
    )

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=1, import_count=1)

    warnings = []
    result = read_depends_map(archive, summary, warnings=warnings)
    assert result == [[10, -10]]
    assert len(warnings) == 1, "Should emit one aggregated warning for multiple invalid indices"
    assert "2 PackageIndex" in warnings[0]


def test_depends_map_mixed_skipped_and_invalid():
    """Skipped entries (bad count) and invalid indices produce separate warnings."""
    # export_count = 2
    # entry 0: dep_count = 50000 (abnormal, skipped)
    # entry 1: dep_count = 1, pkg_index = 99 (invalid import, import_count=0)
    data = (
        _PADDING
        + _i32_le(50000)  # dep_count = 50000 (abnormal)
        + _i32_le(1)      # dep_count = 1
        + _i32_le(99)     # pkg_index = 99 (invalid import)
    )

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=2, import_count=0)

    warnings = []
    result = read_depends_map(archive, summary, warnings=warnings)
    assert result == [[], [99]]
    assert len(warnings) == 2, "Should emit 2 warnings: one for skip, one for invalid index"
    assert "1/2 entries skipped" in warnings[0]
    assert "PackageIndex" in warnings[1]


def test_depends_map_no_warnings_param():
    """When warnings parameter is not passed, no error occurs (backward compatible)."""
    data = (
        _PADDING
        + _i32_le(1)     # dep_count = 1
        + _i32_le(99)    # invalid import index
    )

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=1, import_count=0)

    # No warnings param — should not crash
    result = read_depends_map(archive, summary)
    assert result == [[99]]


# ---------------------------------------------------------------------------
# _result_status integration (#451)
# ---------------------------------------------------------------------------

class TestResultStatusDependsMap:
    """Verify _result_status returns 'partial' when DependsMap warnings are present."""

    def _fake_result(self, warnings: list[str]):
        class FakeResult:
            is_success = True
            errors = []
            metadata = {}
            diagnostics = []
            decompiled_functions = []
            summary = None
            name_map = None
            import_map = None
            export_map = None
        r = FakeResult()
        r.warnings = warnings
        return r

    def test_depends_map_skip_warning_triggers_partial(self):
        """'DependsMap: N/M entries skipped' warning must yield 'partial' status."""
        result = self._fake_result([
            "DependsMap: 1/3 entries skipped (abnormal dep_count=50000)"
        ])
        assert _result_status(result) == "partial"

    def test_depends_map_package_index_warning_triggers_partial(self):
        """'DependsMap: PackageIndex ...' warning must yield 'partial' status."""
        result = self._fake_result([
            "DependsMap: 2 PackageIndex values out of range"
        ])
        assert _result_status(result) == "partial"

    def test_depends_map_mixed_warnings_triggers_partial(self):
        """Multiple DependsMap warnings must still yield 'partial' status."""
        result = self._fake_result([
            "DependsMap: 1/2 entries skipped",
            "DependsMap: 1 PackageIndex value out of range",
        ])
        assert _result_status(result) == "partial"

    def test_no_depends_map_warning_stays_success(self):
        """Unrelated warnings must not trigger partial for DependsMap."""
        result = self._fake_result(["Some unrelated warning"])
        assert _result_status(result) == "success"
