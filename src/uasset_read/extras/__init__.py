"""可选高级功能模块

使用方式：
    from uasset_read.extras.graph import extract_blueprint_graphs
    from uasset_read.extras.kismet import decompile_uasset
    from uasset_read.extras.cpp_gen import extract_cpp_class_skeleton
    from uasset_read.extras.blueprint import extract_blueprint_metadata

当前为占位实现，实际模块仍在原位置。
"""


def __getattr__(name):
    """延迟加载 extras 子模块"""
    if name == "graph":
        from uasset_read import graph
        return graph
    elif name == "kismet":
        from uasset_read import kismet
        return kismet
    elif name == "cpp_gen":
        from uasset_read import cpp_gen
        return cpp_gen
    elif name == "blueprint":
        from uasset_read import blueprint
        return blueprint
    raise AttributeError(f"module 'uasset_read.extras' has no attribute {name!r}")


__all__ = ["graph", "kismet", "cpp_gen", "blueprint"]
