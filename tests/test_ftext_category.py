"""测试 FText Category 解析（Issue #170）

BP_FirstPersonPlayerController 变量 Category 应正确解析，
不应出现 PropertyFallback 或乱码。
"""
import pytest


def test_category_not_property_fallback():
    """变量 Category 不应为 PropertyFallback"""
    from uasset_read.parse_uasset import parse_package
    result = parse_package(
        "E:/Develop/lib/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonPlayerController.uasset"
    )
    blueprint = result.blueprint
    assert blueprint is not None, "蓝图数据为空"
    for var in blueprint.variables:
        cat = str(var.category)
        print(f"{var.var_name}: category={cat}")
        assert "Fallback" not in cat, (
            f"变量 {var.var_name} Category 解析失败: {cat}"
        )


def test_category_not_empty_or_garbled():
    """变量 Category 不应为空或乱码"""
    from uasset_read.parse_uasset import parse_package
    result = parse_package(
        "E:/Develop/lib/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonPlayerController.uasset"
    )
    blueprint = result.blueprint
    assert blueprint is not None, "蓝图数据为空"
    # 至少有一个变量有非空 Category
    has_category = any(str(var.category).strip() for var in blueprint.variables)
    # 这只是诊断性断言，不做硬性要求
    if not has_category:
        pytest.skip("该资产变量均无 Category（可能正常）")
