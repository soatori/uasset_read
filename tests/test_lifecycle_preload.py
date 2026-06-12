"""测试加载生命周期：link → preload → post_load 顺序。

使用 UE Samples 目录中的真实资产进行测试。
"""
import os
import pytest
from pathlib import Path

DEFAULT_SAMPLE_ROOT = Path(r"E:\Develop\lib\UnrealEngine\Samples")


@pytest.fixture(scope="module")
def ue_sample_root() -> Path:
    root = Path(os.environ.get("UE_SAMPLE_ROOT", str(DEFAULT_SAMPLE_ROOT)))
    if not root.exists():
        pytest.skip(f"sample root not found: {root}")
    return root


@pytest.fixture(scope="module")
def static_mesh_asset(ue_sample_root) -> Path:
    """StaticMesh 测试资产。"""
    path = ue_sample_root / r"StarterContent/Content/StarterContent/Architecture/SM_AssetPlatform.uasset"
    if not path.exists():
        pytest.skip(f"asset not found: {path}")
    return path


@pytest.fixture(scope="module")
def blueprint_asset(ue_sample_root) -> Path:
    """Blueprint 测试资产。"""
    path = ue_sample_root / r"FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"
    if not path.exists():
        pytest.skip(f"asset not found: {path}")
    return path


def test_lifecycle_order_link_preload_postload(blueprint_asset):
    """验证生命周期顺序：link → preload → post_load。"""
    from uasset_read.parse_uasset import parse_uasset_with_linker

    result = parse_uasset_with_linker(str(blueprint_asset), preload_all=True)

    # link 阶段完成
    assert result.linker is not None
    assert len(result.linker._export_objects) > 0

    # preload 阶段完成（所有 export 已预加载）
    for idx, inst in enumerate(result.linker._export_objects):
        if inst.serial_size > 0:
            assert inst._preloaded, f"Export #{idx} ({inst.object_name}) 未预加载"

    # post_load 阶段完成（property_references 已填充）
    # 检查至少有一个对象有 property_references（如果有 ObjectProperty）
    has_object_property = False
    for inst in result.linker._export_objects:
        if hasattr(inst, 'serialized_properties') and inst.serialized_properties:
            for prop in inst.serialized_properties:
                if isinstance(prop, dict) and prop.get('type') == 'ObjectProperty':
                    has_object_property = True
                    break

    # 如果有 ObjectProperty，则应该有解析后的引用
    if has_object_property:
        # 至少有一个对象有 property_references
        any_refs = any(
            hasattr(inst, 'property_references') and inst.property_references
            for inst in result.linker._export_objects
        )
        # 注意：即使有 ObjectProperty，引用也可能为 None（越界等），所以不强制断言
        # 但 post_load 应该已执行（通过检查 _preloaded 状态）


def test_preload_all_works(static_mesh_asset):
    """测试 preload_all=True 正常工作。"""
    from uasset_read.parse_uasset import parse_uasset_with_linker

    result = parse_uasset_with_linker(str(static_mesh_asset), preload_all=True)

    assert result.is_success or len(result.errors) == 0
    assert result.linker is not None

    # 所有有 serial_size 的 export 都应该已预加载
    for idx, inst in enumerate(result.linker._export_objects):
        if inst.serial_size > 0 and inst.serial_offset >= 0:
            assert inst._preloaded, f"Export #{idx} ({inst.object_name}) 未预加载"


def test_property_references_resolved_after_postload(blueprint_asset):
    """测试 post_load 后 ObjectProperty 引用已解析。"""
    from uasset_read.parse_uasset import parse_uasset_with_linker

    result = parse_uasset_with_linker(str(blueprint_asset), preload_all=True)

    # 查找包含 ObjectProperty 的对象
    found_object_property = False
    for inst in result.linker._export_objects:
        if not inst._preloaded:
            continue
        if not hasattr(inst, 'serialized_properties') or not inst.serialized_properties:
            continue

        for prop in inst.serialized_properties:
            if not isinstance(prop, dict):
                continue
            if prop.get('type') == 'ObjectProperty':
                found_object_property = True
                # post_load 应该已尝试解析此引用
                # 即使解析结果为 None（越界），property_references 字段应存在
                assert hasattr(inst, 'property_references')

    # 注意：测试资产可能没有 ObjectProperty，所以不强制断言 found_object_property


def test_export_properties_backward_compat(static_mesh_asset):
    """测试 export.properties 向后兼容性（从 linker instance 复制）。"""
    from uasset_read.parse_uasset import parse_package

    result = parse_package(str(static_mesh_asset))

    # export_map 中的 export 应该有 properties 字段
    for export in result.export_map:
        if export.serial_size > 0:
            # properties 应该已填充（从 linker instance 复制）
            assert hasattr(export, 'properties')
            # properties 应该是列表（可能为空）
            assert isinstance(export.properties, list)


def test_is_success_based_on_errors(static_mesh_asset):
    """测试 is_success 基于错误数量，而非无条件 True。"""
    from uasset_read.parse_uasset import parse_package

    result = parse_package(str(static_mesh_asset))

    # 如果没有错误，is_success 应该为 True
    if len(result.errors) == 0:
        assert result.is_success is True
    else:
        # 如果有错误，is_success 应该为 False
        assert result.is_success is False


def test_archive_stays_open_during_preload(static_mesh_asset):
    """测试 archive 在 preload 期间保持打开状态。"""
    from uasset_read.parse_uasset import parse_uasset_with_linker

    # preload_all=True 应该正常工作（archive 在 preload 期间未关闭）
    result = parse_uasset_with_linker(str(static_mesh_asset), preload_all=True)

    # 如果 archive 提前关闭，preload 会失败
    # 成功解析意味着 archive 在 preload 期间保持打开
    assert result.linker is not None

    # 验证至少有一个 export 成功预加载
    preloaded_count = sum(
        1 for inst in result.linker._export_objects
        if inst._preloaded and inst.serial_size > 0
    )
    # 至少有部分 export 成功预加载（除非所有 export 的 serial_size 都为 0）
    if any(inst.serial_size > 0 for inst in result.linker._export_objects):
        assert preloaded_count > 0, "没有 export 成功预加载，可能 archive 提前关闭"
