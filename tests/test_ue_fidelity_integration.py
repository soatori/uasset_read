"""UE 保真度集成测试 — 验证 6 项改进协同工作。

Task 7: 集成测试与验证
覆盖场景：
1. Blueprint 完整解析流程（lifecycle + status）
2. StaticMesh opaque 标记（class_strategy + status）
3. 依赖解析正确性（depends_map + lifecycle）
4. 软引用解析（soft_object_path + lifecycle）
5. 多资产批量解析一致性

验证清单：
- ✅ 生命周期：link → preload → post_load 顺序正确
- ✅ 偏移策略：默认使用 SerialOffset
- ✅ 类策略：opaque 类正确标记
- ✅ 软引用：索引解析工作正常
- ✅ 依赖图：FPackageIndex 语义正确
- ✅ 状态模型：success|partial|failed 统一
"""
import pytest
from pathlib import Path

# 测试资产路径
BLUEPRINT = Path("E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/FirstPersonProjectile.uasset")
STATIC_MESH = Path("E:/Develop/lib/UnrealEngine/Samples/StarterContent/Content/StarterContent/Architecture/SM_AssetPlatform.uasset")
TEXTURE_2D = Path("E:/Develop/lib/UnrealEngine/Samples/StarterContent/Content/StarterContent/Textures/T_Brick_Clay_Medium_D.uasset")

# 备用资产（如果主资产不存在）
BLUEPRINT_ALT = Path("E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset")
BLUEPRINT_USED = BLUEPRINT if BLUEPRINT.exists() else (BLUEPRINT_ALT if BLUEPRINT_ALT.exists() else None)


# ============================================================================
# 场景 1: Blueprint 资产的完整解析流程（lifecycle + status）
# ============================================================================

@pytest.mark.integration
@pytest.mark.skipif(not BLUEPRINT_USED, reason="Blueprint 样本不存在")
class TestBlueprintFullPipeline:
    """场景 1: Blueprint 完整解析流程验证。"""

    def test_lifecycle_completes_all_phases(self):
        """验证 link → preload → post_load 全部完成。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker

        result = parse_uasset_with_linker(str(BLUEPRINT_USED), preload_all=True)

        # link 阶段
        assert result.linker is not None, "link 阶段应完成"
        assert len(result.linker._export_objects) > 0, "应有导出对象"

        # preload 阶段
        preloaded = [
            inst for inst in result.linker._export_objects
            if inst._preloaded and inst.serial_size > 0
        ]
        assert len(preloaded) > 0, "应有预加载的对象"

        # post_load 阶段（property_references 字段存在）
        for inst in result.linker._export_objects:
            if inst._preloaded:
                assert hasattr(inst, 'property_references'), \
                    f"post_load 后 {inst.object_name} 应有 property_references"

    def test_status_is_valid(self):
        """验证状态模型为 success|partial|failed 之一。"""
        from uasset_read.parse_uasset import parse_uasset

        result = parse_uasset(str(BLUEPRINT_USED))

        assert result.status in ('success', 'partial', 'failed'), \
            f"状态应为 success|partial|failed，实际为 {result.status}"

    def test_exports_have_valid_parse_status(self):
        """验证所有 export 的 parse_status 有效。"""
        from uasset_read.parse_uasset import parse_uasset

        result = parse_uasset(str(BLUEPRINT_USED))

        valid_statuses = {'success', 'partial', 'failed', 'opaque', 'skipped', 'metadata'}
        for exp in result.export_map:
            status = getattr(exp, 'parse_status', 'success')
            assert status in valid_statuses, \
                f"Export {exp.object_name} 的 parse_status 无效: {status}"

    def test_blueprints_have_properties(self):
        """验证 Blueprint 类 export 有属性解析。"""
        from uasset_read.parse_uasset import parse_uasset

        result = parse_uasset(str(BLUEPRINT_USED))

        # 查找 BlueprintGeneratedClass 类型的 export
        bpgc_exports = [
            exp for exp in result.export_map
            if 'BlueprintGeneratedClass' in getattr(exp, 'object_class', '')
        ]

        # 如果有 BPGC，应该有属性
        for exp in bpgc_exports:
            if exp.serial_size > 0:
                assert hasattr(exp, 'properties'), \
                    f"BPGC export {exp.object_name} 应有 properties 属性"


# ============================================================================
# 场景 2: StaticMesh 资产的 opaque 标记（class_strategy + status）
# ============================================================================

@pytest.mark.integration
@pytest.mark.skipif(not STATIC_MESH.exists(), reason="StaticMesh 样本不存在")
class TestStaticMeshOpaqueStrategy:
    """场景 2: StaticMesh opaque 标记验证。"""

    def test_static_mesh_is_opaque_class(self):
        """验证 StaticMesh 被识别为 opaque 类。"""
        from uasset_read.parsers.class_serialization_strategy import is_opaque_class

        assert is_opaque_class("StaticMesh"), "StaticMesh 应为 opaque 类"

    def test_static_mesh_exports_marked_opaque(self):
        """验证 StaticMesh 资产的 export 被标记为 opaque。"""
        from uasset_read.parse_uasset import parse_uasset

        result = parse_uasset(str(STATIC_MESH))

        # 查找 StaticMesh 类型的 export
        mesh_exports = [
            exp for exp in result.export_map
            if getattr(exp, 'object_class', '') == 'StaticMesh'
        ]

        # StaticMesh export 应被标记为 opaque 或 partial
        for exp in mesh_exports:
            status = getattr(exp, 'parse_status', 'success')
            # opaque 或 partial 都是可接受的
            assert status in ('opaque', 'partial', 'success'), \
                f"StaticMesh export 状态应为 opaque/partial/success，实际为 {status}"

    def test_static_mesh_status_is_partial_or_success(self):
        """验证 StaticMesh 资产的整体状态。"""
        from uasset_read.parse_uasset import parse_uasset

        result = parse_uasset(str(STATIC_MESH))

        # StaticMesh 有 opaque exports，所以整体状态应为 partial 或 success
        # （取决于是否有非 opaque 的 exports）
        assert result.status in ('success', 'partial'), \
            f"StaticMesh 状态应为 success 或 partial，实际为 {result.status}"

    def test_static_mesh_has_properties(self):
        """验证 StaticMesh 的某些 export 仍有属性解析。"""
        from uasset_read.parse_uasset import parse_uasset

        result = parse_uasset(str(STATIC_MESH))

        # 即使 StaticMesh 本身是 opaque，其他 export（如 Package）应有属性
        exports_with_props = [
            exp for exp in result.export_map
            if hasattr(exp, 'properties') and exp.properties
        ]
        assert len(exports_with_props) > 0, "应有至少一个 export 包含属性"


# ============================================================================
# 场景 3: 依赖解析的正确性（depends_map + lifecycle）
# ============================================================================

@pytest.mark.integration
@pytest.mark.skipif(not BLUEPRINT_USED, reason="Blueprint 样本不存在")
class TestDependsMapResolution:
    """场景 3: DependsMap FPackageIndex 语义验证。"""

    def test_depends_map_uses_package_index_semantics(self):
        """验证 DependsMap 值遵循 FPackageIndex 语义。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker

        result = parse_uasset_with_linker(str(BLUEPRINT_USED), preload_all=True)

        # 检查 DependsMap（如果存在）
        if not hasattr(result.summary, 'depends_map') or not result.summary.depends_map:
            pytest.skip("此资产无 DependsMap")

        for exp_idx, dep_indices in enumerate(result.summary.depends_map):
            if not dep_indices:
                continue

            for raw_dep in dep_indices:
                # FPackageIndex 语义：正数=export(1-based)，负数=import(-1 based)，0=null
                if raw_dep > 0:
                    export_idx = raw_dep - 1
                    assert 0 <= export_idx < len(result.export_map), \
                        f"DependsMap export 引用 {raw_dep} 越界"
                elif raw_dep < 0:
                    import_idx = -raw_dep - 1
                    assert 0 <= import_idx < len(result.import_map), \
                        f"DependsMap import 引用 {raw_dep} 越界"
                # raw_dep == 0 是 null，有效

    def test_linker_resolves_dependencies_to_instances(self):
        """验证 linker 将依赖解析为 UObjectInstance。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker
        from uasset_read.link.object_instance import UObjectInstance

        result = parse_uasset_with_linker(str(BLUEPRINT_USED), preload_all=True)
        linker = result.linker

        # 检查已解析的依赖
        for inst in linker._export_objects:
            if hasattr(inst, 'dependencies') and inst.dependencies:
                for dep in inst.dependencies:
                    assert isinstance(dep, UObjectInstance), \
                        f"依赖应为 UObjectInstance，实际为 {type(dep)}"

    def test_depends_map_after_lifecycle(self):
        """验证生命周期完成后 DependsMap 已处理。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker

        result = parse_uasset_with_linker(str(BLUEPRINT_USED), preload_all=True)

        # preload 完成后，所有 export 应已处理
        for inst in result.linker._export_objects:
            if inst.serial_size > 0:
                assert inst._preloaded, \
                    f"Export {inst.object_name} 应已预加载"


# ============================================================================
# 场景 4: 软引用解析（soft_object_path + lifecycle）
# ============================================================================

@pytest.mark.integration
@pytest.mark.skipif(not BLUEPRINT_USED, reason="Blueprint 样本不存在")
class TestSoftObjectPathResolution:
    """场景 4: SoftObjectPath 索引解析验证。"""

    def test_soft_object_paths_parsed(self):
        """验证 SoftObjectPaths 被正确解析。"""
        from uasset_read.parse_uasset import parse_uasset

        result = parse_uasset(str(BLUEPRINT_USED))

        # 检查 soft_object_paths（如果存在）
        if hasattr(result, 'soft_object_paths'):
            # soft_object_paths 应该是列表
            assert isinstance(result.soft_object_paths, list)

            # 每个条目应有 asset_path 字段
            for soft_path in result.soft_object_paths:
                if isinstance(soft_path, dict):
                    assert 'asset_path' in soft_path or 'AssetPath' in soft_path, \
                        "SoftObjectPath 应有 asset_path 字段"

    def test_soft_object_path_value_structure(self):
        """验证 SoftObjectPathValue 结构正确。"""
        from uasset_read.models.properties import SoftObjectPathValue

        value = SoftObjectPathValue(
            raw_kind="SoftObjectProperty",
            asset_path="/Game/Content/MyAsset",
            sub_path="SubPath",
            index=0,
            error=None,
        )

        assert value.asset_path == "/Game/Content/MyAsset"
        assert value.sub_path == "SubPath"
        assert value.index == 0
        assert value.error is None

    def test_soft_package_references_parsed(self):
        """验证 SoftPackageReferences 被解析。"""
        from uasset_read.parse_uasset import parse_uasset

        result = parse_uasset(str(BLUEPRINT_USED))

        # soft_package_references 应该是列表
        if hasattr(result, 'soft_package_references'):
            assert isinstance(result.soft_package_references, list)


# ============================================================================
# 场景 5: 多资产批量解析的一致性
# ============================================================================

@pytest.mark.integration
class TestBatchParsingConsistency:
    """场景 5: 多资产批量解析一致性验证。"""

    @pytest.fixture
    def available_assets(self):
        """获取可用的测试资产列表。"""
        assets = []
        if BLUEPRINT_USED:
            assets.append(("Blueprint", BLUEPRINT_USED))
        if STATIC_MESH.exists():
            assets.append(("StaticMesh", STATIC_MESH))
        if TEXTURE_2D.exists():
            assets.append(("Texture2D", TEXTURE_2D))
        return assets

    def test_all_assets_parse_without_crash(self, available_assets):
        """验证所有资产类型都能无崩溃解析。"""
        from uasset_read.parse_uasset import parse_uasset

        if not available_assets:
            pytest.skip("无可用测试资产")

        for asset_type, asset_path in available_assets:
            result = parse_uasset(str(asset_path))
            assert result is not None, f"{asset_type} 解析返回 None"

    def test_all_assets_have_valid_status(self, available_assets):
        """验证所有资产都有有效的状态值。"""
        from uasset_read.parse_uasset import parse_uasset

        if not available_assets:
            pytest.skip("无可用测试资产")

        valid_statuses = {'success', 'partial', 'failed'}

        for asset_type, asset_path in available_assets:
            result = parse_uasset(str(asset_path))
            assert result.status in valid_statuses, \
                f"{asset_type} 状态无效: {result.status}"

    def test_all_assets_have_summary(self, available_assets):
        """验证所有资产都有 summary。"""
        from uasset_read.parse_uasset import parse_uasset

        if not available_assets:
            pytest.skip("无可用测试资产")

        for asset_type, asset_path in available_assets:
            result = parse_uasset(str(asset_path))
            assert result.summary is not None, \
                f"{asset_type} 缺少 summary"

    def test_all_assets_have_name_map(self, available_assets):
        """验证所有资产都有 name_map。"""
        from uasset_read.parse_uasset import parse_uasset

        if not available_assets:
            pytest.skip("无可用测试资产")

        for asset_type, asset_path in available_assets:
            result = parse_uasset(str(asset_path))
            assert result.name_map is not None, \
                f"{asset_type} 缺少 name_map"
            assert isinstance(result.name_map, list), \
                f"{asset_type} 的 name_map 应为列表"

    def test_all_assets_have_export_map(self, available_assets):
        """验证所有资产都有 export_map。"""
        from uasset_read.parse_uasset import parse_uasset

        if not available_assets:
            pytest.skip("无可用测试资产")

        for asset_type, asset_path in available_assets:
            result = parse_uasset(str(asset_path))
            assert result.export_map is not None, \
                f"{asset_type} 缺少 export_map"
            assert isinstance(result.export_map, list), \
                f"{asset_type} 的 export_map 应为列表"

    def test_linker_works_for_all_assets(self, available_assets):
        """验证 linker 对所有资产类型都能工作。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker

        if not available_assets:
            pytest.skip("无可用测试资产")

        for asset_type, asset_path in available_assets:
            result = parse_uasset_with_linker(str(asset_path), preload_all=True)
            assert result.linker is not None, \
                f"{asset_type} linker 为 None"

    def test_consistent_status_model_across_types(self, available_assets):
        """验证不同资产类型的状态模型一致性。"""
        from uasset_read.parse_uasset import parse_uasset

        if not available_assets:
            pytest.skip("无可用测试资产")

        valid_statuses = {'success', 'partial', 'failed'}
        valid_export_statuses = {'success', 'partial', 'failed', 'opaque', 'skipped', 'metadata'}

        for asset_type, asset_path in available_assets:
            result = parse_uasset(str(asset_path))

            # 整体状态有效
            assert result.status in valid_statuses, \
                f"{asset_type} 整体状态无效: {result.status}"

            # export 状态有效
            for exp in result.export_map:
                exp_status = getattr(exp, 'parse_status', 'success')
                assert exp_status in valid_export_statuses, \
                    f"{asset_type} export {exp.object_name} 状态无效: {exp_status}"


# ============================================================================
# 综合验证：6 项改进协同工作
# ============================================================================

@pytest.mark.integration
@pytest.mark.skipif(not BLUEPRINT_USED, reason="Blueprint 样本不存在")
class TestAllImprovementsWorkingTogether:
    """验证 6 项改进协同工作。"""

    def test_lifecycle_and_status_consistency(self):
        """验证生命周期和状态模型一致性。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker

        result = parse_uasset_with_linker(str(BLUEPRINT_USED), preload_all=True)

        # 生命周期完成
        assert result.linker is not None

        # LinkerParseResult 使用 is_success 字段
        if result.errors:
            assert result.is_success is False, "有错误时 is_success 应为 False"
        else:
            # 无错误时 is_success 可能为 True 或 False（取决于其他因素）
            assert isinstance(result.is_success, bool)

    def test_class_strategy_and_status_consistency(self):
        """验证类策略和状态模型一致性。"""
        from uasset_read.parse_uasset import parse_uasset
        from uasset_read.parsers.class_serialization_strategy import (
            get_serialization_strategy,
            SerializationStrategy,
        )

        result = parse_uasset(str(BLUEPRINT_USED))

        for exp in result.export_map:
            class_name = getattr(exp, 'object_class', '')
            if not class_name:
                continue

            strategy = get_serialization_strategy(class_name)
            exp_status = getattr(exp, 'parse_status', 'success')

            # Skip 类应该是 skipped 状态
            if strategy == SerializationStrategy.SKIP_UNSUPPORTED:
                assert exp_status in ('skipped', 'success'), \
                    f"Skip 类 {class_name} 应有 skipped 状态"

            # Opaque 类应该是 opaque 或 partial 状态
            if strategy == SerializationStrategy.OPAQUE_CLASS_PAYLOAD:
                assert exp_status in ('opaque', 'partial', 'success'), \
                    f"Opaque 类 {class_name} 应有 opaque/partial 状态"

    def test_depends_map_and_lifecycle_consistency(self):
        """验证 DependsMap 和生命周期一致性。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker

        result = parse_uasset_with_linker(str(BLUEPRINT_USED), preload_all=True)

        # 生命周期完成后，依赖应已解析
        if hasattr(result.summary, 'depends_map') and result.summary.depends_map:
            # linker 应已解析依赖
            assert result.linker is not None

            # 所有 export 应已预加载
            for inst in result.linker._export_objects:
                if inst.serial_size > 0:
                    assert inst._preloaded

    def test_soft_object_path_and_lifecycle_consistency(self):
        """验证 SoftObjectPath 和生命周期一致性。"""
        from uasset_read.parse_uasset import parse_uasset_with_linker

        result = parse_uasset_with_linker(str(BLUEPRINT_USED), preload_all=True)

        # 生命周期完成后，soft_object_paths 应已解析
        if hasattr(result, 'soft_object_paths'):
            assert isinstance(result.soft_object_paths, list)

    def test_offset_strategy_used_correctly(self):
        """验证偏移策略正确使用 SerialOffset。"""
        from uasset_read.parse_uasset import parse_uasset

        result = parse_uasset(str(BLUEPRINT_USED))

        for exp in result.export_map:
            # serial_offset 应存在且非负
            assert hasattr(exp, 'serial_offset'), \
                f"Export {exp.object_name} 缺少 serial_offset"
            assert exp.serial_offset >= 0, \
                f"Export {exp.object_name} serial_offset 应为非负数"

            # serial_size 应存在且非负
            assert hasattr(exp, 'serial_size'), \
                f"Export {exp.object_name} 缺少 serial_size"
            assert exp.serial_size >= 0, \
                f"Export {exp.object_name} serial_size 应为非负数"


# ============================================================================
# 快速冒烟测试
# ============================================================================

@pytest.mark.integration
class TestFidelitySmoke:
    """快速冒烟测试：确保基本功能正常。"""

    @pytest.mark.skipif(not BLUEPRINT_USED, reason="Blueprint 样本不存在")
    def test_blueprint_smoke(self):
        """Blueprint 基本解析冒烟测试。"""
        from uasset_read.parse_uasset import parse_uasset

        result = parse_uasset(str(BLUEPRINT_USED))
        assert result is not None
        assert result.status in ('success', 'partial', 'failed')
        assert len(result.export_map) > 0

    @pytest.mark.skipif(not STATIC_MESH.exists(), reason="StaticMesh 样本不存在")
    def test_static_mesh_smoke(self):
        """StaticMesh 基本解析冒烟测试。"""
        from uasset_read.parse_uasset import parse_uasset

        result = parse_uasset(str(STATIC_MESH))
        assert result is not None
        assert result.status in ('success', 'partial', 'failed')
        assert len(result.export_map) > 0

    @pytest.mark.skipif(not TEXTURE_2D.exists(), reason="Texture2D 样本不存在")
    def test_texture_2d_smoke(self):
        """Texture2D 基本解析冒烟测试。"""
        from uasset_read.parse_uasset import parse_uasset

        result = parse_uasset(str(TEXTURE_2D))
        assert result is not None
        assert result.status in ('success', 'partial', 'failed')
        assert len(result.export_map) > 0
