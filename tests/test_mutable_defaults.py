"""可变默认参数检测测试。"""
import inspect
import pytest
from uasset_read.graph import flow_builder


class TestNoMutableDefaults:
    """验证 flow_builder 中无可变默认参数。"""

    def _get_functions_with_mutable_defaults(self, module):
        """扫描模块中所有函数的可变默认参数。"""
        issues = []
        for name, obj in inspect.getmembers(module, inspect.isfunction):
            sig = inspect.signature(obj)
            for param_name, param in sig.parameters.items():
                if param.default is not inspect.Parameter.empty:
                    if isinstance(param.default, (dict, list, set)):
                        issues.append(f"{name}({param_name}={param.default})")
        return issues

    def test_flow_builder_no_mutable_defaults(self):
        """flow_builder 应无可变默认参数。"""
        issues = self._get_functions_with_mutable_defaults(flow_builder)
        assert len(issues) == 0, (
            f"flow_builder 存在可变默认参数: {issues}"
        )
