"""UObject 类型体系公共 API 测试"""
def test_uobject_import():
    """测试 UObject 可导入"""
    from uasset_read import UObject, ObjectTypeRegistry
    assert UObject is not None
    assert ObjectTypeRegistry is not None

def test_asset_types_import():
    """测试资产类型可导入"""
    from uasset_read import UStaticMesh, UTexture2D, UMaterial
    assert UStaticMesh is not None
    assert UTexture2D is not None
    assert UMaterial is not None
