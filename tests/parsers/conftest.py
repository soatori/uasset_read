"""parsers/ 测试共享基础设施"""
from types import SimpleNamespace


class FakeProperty:
    """模拟属性对象"""
    def __init__(self, name: str, value):
        self.name = name
        self.value = value


class FakeExport:
    """模拟 export 对象"""
    def __init__(self, properties=None):
        if isinstance(properties, dict):
            self.properties = [FakeProperty(k, v) for k, v in properties.items()]
        elif isinstance(properties, list):
            self.properties = properties
        else:
            self.properties = []
        self.custom_data = {}


class FakeContext:
    """模拟解析上下文"""
    def __init__(self):
        self.warnings = []
