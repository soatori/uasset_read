"""测试 extras 模块导入"""
import pytest


def test_extras_graph_import():
    """可通过 extras 路径导入 graph"""
    from uasset_read.extras import graph
    assert hasattr(graph, "extract_blueprint_graphs")


def test_extras_kismet_import():
    """可通过 extras 路径导入 kismet"""
    from uasset_read.extras import kismet
    assert hasattr(kismet, "decompile_uasset")


def test_extras_cpp_gen_import():
    """可通过 extras 路径导入 cpp_gen"""
    from uasset_read.extras import cpp_gen
    assert hasattr(cpp_gen, "extract_cpp_class_skeleton")


def test_extras_blueprint_import():
    """可通过 extras 路径导入 blueprint"""
    from uasset_read.extras import blueprint
    assert hasattr(blueprint, "extract_blueprint_metadata")


def test_original_path_still_works():
    """原路径仍可访问（向后兼容）"""
    from uasset_read.graph import extract_blueprint_graphs
    from uasset_read.kismet import decompile_uasset
    from uasset_read.cpp_gen import extract_cpp_class_skeleton
    from uasset_read.blueprint import extract_blueprint_metadata
    assert callable(extract_blueprint_graphs)
    assert callable(decompile_uasset)
    assert callable(extract_cpp_class_skeleton)
    assert callable(extract_blueprint_metadata)


def test_extras_invalid_attribute():
    """访问不存在的属性应抛出 AttributeError"""
    import uasset_read.extras as extras
    with pytest.raises(AttributeError):
        extras.nonexistent
