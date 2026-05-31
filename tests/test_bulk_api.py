"""Bulk Data 公共 API 测试"""
def test_bulk_data_import():
    """测试 Bulk Data 模块可导入"""
    from uasset_read import FBulkDataHeader, BulkDataFlags
    assert FBulkDataHeader is not None
    assert BulkDataFlags is not None
