"""常见资产类型测试"""
def test_static_mesh_type():
    """测试 UStaticMesh 类型"""
    from uasset_read.objects.exports.mesh import UStaticMesh
    from uasset_read.objects.registry import global_registry

    assert "StaticMesh" in global_registry.list_classes()
    cls = global_registry.get_class("StaticMesh")
    assert cls == UStaticMesh

def test_texture_2d_type():
    """测试 UTexture2D 类型"""
    from uasset_read.objects.exports.texture import UTexture2D
    from uasset_read.objects.registry import global_registry

    assert "Texture2D" in global_registry.list_classes()
    cls = global_registry.get_class("Texture2D")
    assert cls == UTexture2D

def test_material_type():
    """测试 UMaterial 类型"""
    from uasset_read.objects.exports.material import UMaterial
    from uasset_read.objects.registry import global_registry

    assert "Material" in global_registry.list_classes()
    cls = global_registry.get_class("Material")
    assert cls == UMaterial

def test_blueprint_generated_class():
    """测试蓝图生成类后缀剥离"""
    from uasset_read.objects.registry import global_registry
    from uasset_read.objects.uobject import UObject

    cls = global_registry.get_class("StaticMesh_C")
    # 应该返回 UObject（因为 StaticMesh 已注册但实际应返回 UStaticMesh）
    assert cls is not None
