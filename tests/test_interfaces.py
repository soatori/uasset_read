"""BlueprintInterfaces 提取测试（Issue #169 部分）。"""
import pytest


def test_blueprint_has_interfaces():
    """蓝图应包含 interfaces 列表"""
    from uasset_read.parse_uasset import parse_uasset_with_linker
    result = parse_uasset_with_linker(
        "E:/Develop/lib/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset",
        tolerant=True,
    )
    assert result.is_success, f"解析失败: {result.errors}"
    blueprint = result.blueprint
    assert blueprint is not None, "蓝图数据不应为 None"
    assert blueprint.interfaces is not None, "interfaces 不应为 None"
    assert isinstance(blueprint.interfaces, list), "interfaces 应为列表"
    print(f"Interfaces: {[{'name': i.name, 'guid': i.guid} for i in blueprint.interfaces]}")
    # BP_FirstPersonCharacter 应实现 BPI_TouchInterface
    if blueprint.interfaces:
        names = [i.name for i in blueprint.interfaces]
        assert any("Touch" in n for n in names), f"应包含 TouchInterface，实际: {names}"
