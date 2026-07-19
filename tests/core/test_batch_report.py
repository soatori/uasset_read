"""BatchResult partial 追踪字段测试。"""
from uasset_read.core import BatchResult


def test_batch_result_has_partial_fields():
    """BatchResult 应包含 partial 和 partial_reasons 字段。"""
    result = BatchResult()
    assert hasattr(result, "partial")
    assert hasattr(result, "partial_reasons")
    assert result.partial == []
    assert result.partial_reasons == {}


def test_batch_result_tracks_partial_files():
    """BatchResult 应能追踪 partial 文件及原因。"""
    result = BatchResult()
    result.total = 5
    result.success = ["file1.uasset", "file2.uasset"]
    result.partial = ["file3.uasset", "file4.uasset", "file5.uasset"]
    result.partial_reasons = {
        "opaque": ["file3.uasset"],
        "partial_metadata": ["file4.uasset", "file5.uasset"],
    }
    assert len(result.partial) == 3
    assert "opaque" in result.partial_reasons
    assert len(result.partial_reasons["partial_metadata"]) == 2


def test_batch_result_backward_compatible():
    """BatchResult 应保持向后兼容 — 旧字段不受影响。"""
    result = BatchResult(total=3)
    result.success = ["a.uasset", "b.uasset"]
    result.skipped = [("c.uasset", "too large")]
    result.failed = [("d.uasset", "Error", "traceback")]
    # partial 字段默认为空，不影响旧逻辑
    assert result.partial == []
    assert result.partial_reasons == {}
    assert result.total == 3
    assert len(result.success) == 2
    assert len(result.skipped) == 1
    assert len(result.failed) == 1
