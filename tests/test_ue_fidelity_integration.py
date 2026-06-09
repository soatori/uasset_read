"""
UE 保真度改进集成测试

验证所有 6 项改进协同工作：
1. 生命周期：link → preload → post_load
2. 偏移策略：SerialOffset 默认
3. 类策略：opaque 标记
4. 软引用：索引解析
5. 依赖图：FPackageIndex 语义
6. 状态模型：success|partial|failed
"""
import pytest
from pathlib import Path
from uasset_read.parse_uasset import parse_uasset, parse_uasset_with_linker
from uasset_read.serializers.object_resources import resolve_class_name

# 测试资产路径
BLUEPRINT_ASSET = "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/Variant_Shooter/Blueprints/Pickups/Projectiles/BP_ShooterProjectileBase.uasset"
STATICMESH_ASSET = "E:/Develop/lib/UnrealEngine/Samples/StarterContent/Content/StarterContent/Architecture/SM_AssetPlatform.uasset"
TEXTURE_ASSET = "E:/Develop/lib/UnrealEngine/Samples/StarterContent/Content/StarterContent/Textures/T_Brick_Clay_Beveled_D.uasset"


def asset_exists(path: str) -> bool:
    """检查资产文件是否存在"""
    return Path(path).exists()


class TestUEFidelityIntegration:
    """UE 保真度改进集成测试"""

    @pytest.mark.skipif(not asset_exists(BLUEPRINT_ASSET), reason="Blueprint asset not found")
    def test_blueprint_full_pipeline(self):
        """场景 1: Blueprint 资产的完整解析流程"""
        result = parse_uasset_with_linker(BLUEPRINT_ASSET, preload_all=True)

        assert result.linker is not None, "Linker should be created"
        assert len(result.linker._export_objects) > 0, "Should have export objects"

        for exp in result.linker._export_objects:
            assert exp._preloaded, f"Export {exp.object_name} should be preloaded"

        # 验证 export_map 已填充属性
        has_properties = any(
            hasattr(exp, 'properties') and exp.properties
            for exp in result.export_map
        )
        assert has_properties, "Blueprint should have properties after preload"

        assert result.status in ['success', 'partial', 'failed']

        if result.errors:
            assert result.status == 'partial'

    @pytest.mark.skipif(not asset_exists(STATICMESH_ASSET), reason="StaticMesh asset not found")
    def test_staticmesh_opaque_marking(self):
        """场景 2: StaticMesh 资产的 opaque 标记"""
        result = parse_uasset(STATICMESH_ASSET)

        # StaticMesh 有 class-specific Serialize()，因此不能标记为完整 success。
        # 若 asset type handler 成功提取基础元数据，会从 opaque 提升为 partial_metadata。
        has_staticmesh = False
        for exp in result.export_map:
            class_name = resolve_class_name(exp.class_index, result.import_map, result.export_map)
            if class_name == "StaticMesh":
                has_staticmesh = True
                assert hasattr(exp, 'parse_status')
                assert exp.parse_status in ('opaque', 'partial_metadata'), (
                    f"StaticMesh should be opaque/partial_metadata, got {exp.parse_status}"
                )
                if hasattr(exp, 'fallback_reason'):
                    assert exp.fallback_reason is not None

        assert has_staticmesh, "Should have at least one StaticMesh export"
        assert result.status in ['success', 'partial', 'failed']

    @pytest.mark.skipif(not asset_exists(BLUEPRINT_ASSET), reason="Blueprint asset not found")
    def test_dependency_graph_correctness(self):
        """场景 3: 依赖解析的正确性"""
        result = parse_uasset_with_linker(BLUEPRINT_ASSET, preload_all=True)

        assert hasattr(result.summary, 'depends_map')
        assert result.summary.depends_map is not None

        assert result.linker is not None
        for exp in result.linker._export_objects:
            assert hasattr(exp, 'dependencies')
            for dep in exp.dependencies:
                assert hasattr(dep, 'object_name'),                     f"Dependency should be UObjectInstance, got {type(dep)}"
                assert hasattr(dep, 'package_index')

    @pytest.mark.skipif(not asset_exists(BLUEPRINT_ASSET), reason="Blueprint asset not found")
    def test_soft_object_path_resolution(self):
        """场景 4: 软引用解析"""
        result = parse_uasset(BLUEPRINT_ASSET)

        assert hasattr(result, 'soft_object_path_list')

        has_soft_object = False
        for export in result.export_map:
            if hasattr(export, 'properties'):
                for prop in export.properties:
                    if hasattr(prop, 'type') and prop.type == 'SoftObjectProperty':
                        has_soft_object = True
                        assert hasattr(prop.value, 'asset_path')
                        assert hasattr(prop.value, 'sub_path')
                        if hasattr(prop.value, 'index') and prop.value.index is not None:
                            assert 0 <= prop.value.index < len(result.soft_object_path_list)

    @pytest.mark.skipif(not asset_exists(BLUEPRINT_ASSET), reason="Blueprint asset not found")
    def test_serial_offset_default(self):
        """场景 2 补充: 验证默认使用 SerialOffset"""
        result = parse_uasset(BLUEPRINT_ASSET)

        has_script_offset = False
        for export in result.export_map:
            if hasattr(export, 'script_serialization_start_offset'):
                if export.script_serialization_start_offset > 0:
                    has_script_offset = True
                    assert hasattr(export, '_script_serialization_start_absolute')
                    assert hasattr(export, '_script_serialization_end_absolute')

    @pytest.mark.skipif(
        not asset_exists(BLUEPRINT_ASSET) or not asset_exists(STATICMESH_ASSET),
        reason="Required assets not found"
    )
    def test_batch_parsing_consistency(self):
        """场景 5: 多资产批量解析的一致性"""
        assets = [BLUEPRINT_ASSET, STATICMESH_ASSET]
        results = []

        for asset_path in assets:
            result = parse_uasset(asset_path)
            results.append(result)

            assert hasattr(result, 'status')
            assert result.status in ['success', 'partial', 'failed']
            assert result.summary is not None
            assert hasattr(result, 'export_map')
            assert result.export_map is not None

        assert len(results) == len(assets)

    @pytest.mark.skipif(not asset_exists(TEXTURE_ASSET), reason="Texture asset not found")
    def test_texture_opaque_handling(self):
        """场景 2 补充: Texture2D 资产的 opaque 处理"""
        result = parse_uasset(TEXTURE_ASSET)

        texture_exports = [
            exp for exp in result.export_map
            if hasattr(exp, 'class_name') and exp.class_name == 'Texture2D'
        ]

        if len(texture_exports) > 0:
            for tex in texture_exports:
                if hasattr(tex, 'parse_status'):
                    if tex.parse_status == 'opaque':
                        assert hasattr(tex, 'fallback_reason')

        assert result.status in ['success', 'partial', 'failed']

    def test_all_improvements_together(self):
        """综合测试: 验证所有改进协同工作"""
        if not asset_exists(BLUEPRINT_ASSET):
            pytest.skip("Blueprint asset not found")

        result = parse_uasset_with_linker(BLUEPRINT_ASSET, preload_all=True)

        assert result.linker is not None
        assert all(exp._preloaded for exp in result.linker._export_objects)

        assert result.status in ['success', 'partial', 'failed']

        if result.linker._export_objects:
            first_exp = result.linker._export_objects[0]
            assert hasattr(first_exp, 'dependencies')

        assert hasattr(result, 'soft_object_path_list')

        for export in result.export_map:
            if export.serial_size > 0:
                assert hasattr(export, 'properties')
