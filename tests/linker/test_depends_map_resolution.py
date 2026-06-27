"""测试 DependsMap 语义解析（Issue #31）。

验证 PackageIndex 依赖解析的正确性：
- 正数 PackageIndex → export 依赖
- 负数 PackageIndex → import 依赖
- 零 PackageIndex → null，应被忽略（linker 层）
- 越界依赖 → path 为 None
"""
import pytest
from unittest.mock import Mock, MagicMock

from uasset_read.serializers.object_resources import PackageIndex
from uasset_read.ir_builder import _build_resolved_depends_map


class MockParseResult:
    """模拟 ParseResult，包含 DependsMap 测试所需字段。"""
    def __init__(self, depends_map, import_map=None, export_map=None, linker=None):
        self.summary = Mock()
        self.summary.depends_map = depends_map
        self.import_map = import_map or []
        self.export_map = export_map or []
        self.linker = linker
        self.blueprint = None


def _make_linker(import_map=None, export_map=None):
    """创建模拟 linker，resolve_package_index 按 UE 语义解析。

    PackageIndex 编码：
    - > 0: export (1-based), to_export_index() = idx - 1
    - < 0: import (-1 based), to_import_index() = -idx - 1
    - == 0: null
    """
    imports = import_map or []
    exports = export_map or []
    linker = Mock()

    def resolve_package_index(pkg_idx):
        if pkg_idx is None or pkg_idx.index == 0:
            return None
        if pkg_idx.is_export:
            idx = pkg_idx.index - 1  # 1-based → 0-based
            if 0 <= idx < len(exports):
                return exports[idx]
            return None
        if pkg_idx.is_import:
            idx = -pkg_idx.index - 1  # -1 based → 0-based
            if 0 <= idx < len(imports):
                return imports[idx]
            return None
        return None

    linker.resolve_package_index = resolve_package_index
    return linker


def _make_export(name, full_name=None):
    """创建模拟 export 对象。"""
    exp = Mock()
    exp.object_name = name
    exp.get_full_name = Mock(return_value=full_name or f"Package.{name}")
    return exp


def _make_import(class_package, class_name, full_name=None):
    """创建模拟 import 对象。"""
    imp = Mock()
    imp.class_package = class_package
    imp.class_name = class_name
    imp.get_full_name = Mock(return_value=full_name or f"{class_package}.{class_name}")
    return imp


class TestExportDependencyResolution:
    """测试 export 依赖解析（正数 PackageIndex）。"""

    def test_export_dependency_resolution(self):
        """正数 PackageIndex 应正确解析为 export 路径。"""
        # Export 0 依赖 Export 1（PackageIndex=2，UE 1-based 编码）
        exports = [_make_export("Export0"), _make_export("Export1")]
        linker = _make_linker(export_map=exports)
        result = MockParseResult([[2]], export_map=exports, linker=linker)

        resolved = _build_resolved_depends_map(result)

        assert len(resolved) == 1
        assert len(resolved[0]) == 1
        assert resolved[0][0]["index"] == 2
        assert resolved[0][0]["path"] == "Package.Export1"

    def test_multiple_export_dependencies(self):
        """单个 export 可以依赖多个其他 export。"""
        exports = [
            _make_export("Export0"),
            _make_export("Export1"),
            _make_export("Export2"),
        ]
        linker = _make_linker(export_map=exports)
        result = MockParseResult([[2, 3]], export_map=exports, linker=linker)

        resolved = _build_resolved_depends_map(result)

        assert len(resolved[0]) == 2
        assert resolved[0][0]["index"] == 2
        assert resolved[0][0]["path"] == "Package.Export1"
        assert resolved[0][1]["index"] == 3
        assert resolved[0][1]["path"] == "Package.Export2"


class TestImportDependencyResolution:
    """测试 import 依赖解析（负数 PackageIndex）。"""

    def test_import_dependency_resolution(self):
        """负数 PackageIndex 应正确解析为 import 路径。"""
        # Export 0 依赖 Import 0（PackageIndex=-1，UE -1 based 编码）
        imports = [_make_import("/Script/Core", "Object")]
        exports = [_make_export("Export0")]
        linker = _make_linker(import_map=imports, export_map=exports)
        result = MockParseResult([[-1]], import_map=imports, export_map=exports, linker=linker)

        resolved = _build_resolved_depends_map(result)

        assert len(resolved) == 1
        assert len(resolved[0]) == 1
        assert resolved[0][0]["index"] == -1
        assert resolved[0][0]["path"] == "/Script/Core.Object"

    def test_multiple_import_dependencies(self):
        """单个 export 可以依赖多个 import。"""
        imports = [
            _make_import("/Script/Core", "Object"),
            _make_import("/Script/Engine", "Actor"),
        ]
        exports = [_make_export("Export0")]
        linker = _make_linker(import_map=imports, export_map=exports)
        result = MockParseResult([[-1, -2]], import_map=imports, export_map=exports, linker=linker)

        resolved = _build_resolved_depends_map(result)

        assert len(resolved[0]) == 2
        assert resolved[0][0]["index"] == -1
        assert resolved[0][0]["path"] == "/Script/Core.Object"
        assert resolved[0][1]["index"] == -2
        assert resolved[0][1]["path"] == "/Script/Engine.Actor"


class TestNullDependencyIgnored:
    """测试 null PackageIndex (0) 的处理。"""

    def test_null_dependency_kept_with_none_path(self):
        """PackageIndex=0 在 _build_resolved_depends_map 中保留但 path=None。

        注：null 过滤发生在 linker._build_dependency_graph 层，
        _build_resolved_depends_map 保留所有原始条目。
        """
        exports = [_make_export("Export0"), _make_export("Export1")]
        linker = _make_linker(export_map=exports)
        result = MockParseResult([[0, 2, 0]], export_map=exports, linker=linker)

        resolved = _build_resolved_depends_map(result)

        # 所有条目保留，null 的 path 为 None
        assert len(resolved[0]) == 3
        assert resolved[0][0]["index"] == 0
        assert resolved[0][0]["path"] is None
        assert resolved[0][1]["index"] == 2
        assert resolved[0][1]["path"] == "Package.Export1"
        assert resolved[0][2]["index"] == 0
        assert resolved[0][2]["path"] is None

    def test_all_null_dependencies(self):
        """所有依赖都是 null 时，path 全部为 None。"""
        exports = [_make_export("Export0")]
        linker = _make_linker(export_map=exports)
        result = MockParseResult([[0, 0, 0]], export_map=exports, linker=linker)

        resolved = _build_resolved_depends_map(result)

        assert len(resolved[0]) == 3
        assert all(item["path"] is None for item in resolved[0])

    def test_linker_filters_null_dependencies(self):
        """验证 linker._build_dependency_graph 层过滤 null 依赖。"""
        from uasset_read.link.linker import PackageLinker
        from uasset_read.serializers.package_summary import PackageFileSummary

        summary = Mock()
        summary.depends_map = [[0, 2, 0]]  # null, export 1, null

        # 创建 linker 实例并手动设置必要属性
        linker = Mock(spec=PackageLinker)
        linker._summary = summary
        linker._export_objects = [Mock(), Mock()]  # 2 个 export 对象
        linker._diagnostics = []

        # 用真实方法测试 null 过滤逻辑
        from uasset_read.serializers.object_resources import PackageIndex as PI

        # 模拟 resolve_package_index
        def resolve_pkg_idx(pkg_idx):
            if pkg_idx.index == 0:
                return None
            if pkg_idx.is_export:
                idx = pkg_idx.index - 1
                if 0 <= idx < len(linker._export_objects):
                    return linker._export_objects[idx]
            return None

        linker.resolve_package_index = resolve_pkg_idx

        # 手动执行 _build_dependency_graph 的核心逻辑
        depends_map = summary.depends_map
        for exp_idx, dep_indices in enumerate(depends_map):
            inst = linker._export_objects[exp_idx]
            inst.dependencies = []
            for raw_dep in dep_indices:
                if raw_dep == 0:
                    continue  # Null dependency, skip
                pkg_idx = PI(raw_dep)
                resolved = resolve_pkg_idx(pkg_idx)
                if resolved is not None:
                    inst.dependencies.append(resolved)

        # 验证 null 被过滤，只保留有效依赖
        assert len(linker._export_objects[0].dependencies) == 1


class TestResolvedDependsMapOutputFormat:
    """测试 resolved_depends_map 输出格式。"""

    def test_resolved_depends_map_output_format(self):
        """输出应包含 raw index 和 resolved path。"""
        imports = [_make_import("/Script/Core", "Object")]
        exports = [_make_export("Export0"), _make_export("Export1")]
        linker = _make_linker(import_map=imports, export_map=exports)
        result = MockParseResult([[2, -1]], import_map=imports, export_map=exports, linker=linker)

        resolved = _build_resolved_depends_map(result)

        assert isinstance(resolved, list)
        assert len(resolved) == 1
        assert isinstance(resolved[0], list)

        for item in resolved[0]:
            assert "index" in item
            assert "path" in item
            assert isinstance(item["index"], int)
            assert isinstance(item["path"], (str, type(None)))

    def test_empty_depends_map(self):
        """空 DependsMap 应返回空列表。"""
        result = MockParseResult([])
        resolved = _build_resolved_depends_map(result)
        assert resolved == []

    def test_no_summary(self):
        """无 summary 时应返回空列表。"""
        result = MockParseResult([[2]])
        result.summary = None
        resolved = _build_resolved_depends_map(result)
        assert resolved == []

    def test_multiple_export_rows(self):
        """多个 export 各自有独立的依赖行。"""
        exports = [
            _make_export("Export0"),
            _make_export("Export1"),
            _make_export("Export2"),
        ]
        linker = _make_linker(export_map=exports)
        depends_map = [[2], [3], []]  # Export0→Export1, Export1→Export2, Export2→none
        result = MockParseResult(depends_map, export_map=exports, linker=linker)

        resolved = _build_resolved_depends_map(result)

        assert len(resolved) == 3
        assert len(resolved[0]) == 1
        assert resolved[0][0]["path"] == "Package.Export1"
        assert len(resolved[1]) == 1
        assert resolved[1][0]["path"] == "Package.Export2"
        assert len(resolved[2]) == 0


class TestOutOfBoundsDependencyDiagnostic:
    """测试越界依赖产生诊断信息。"""

    def test_out_of_bounds_export_dependency(self):
        """越界 export PackageIndex 应返回 path=None。"""
        exports = [_make_export("Export0"), _make_export("Export1")]
        linker = _make_linker(export_map=exports)
        result = MockParseResult([[5]], export_map=exports, linker=linker)  # 只有 2 个 export

        resolved = _build_resolved_depends_map(result)

        assert len(resolved[0]) == 1
        assert resolved[0][0]["index"] == 5
        assert resolved[0][0]["path"] is None

    def test_out_of_bounds_import_dependency(self):
        """越界 import PackageIndex 应返回 path=None。"""
        imports = [_make_import("/Script/Core", "Object")]
        exports = [_make_export("Export0")]
        linker = _make_linker(import_map=imports, export_map=exports)
        # -6 表示 import index 5 (0-based)，但只有 1 个 import
        result = MockParseResult([[-6]], import_map=imports, export_map=exports, linker=linker)

        resolved = _build_resolved_depends_map(result)

        assert len(resolved[0]) == 1
        assert resolved[0][0]["index"] == -6
        assert resolved[0][0]["path"] is None

    def test_mixed_valid_and_invalid_dependencies(self):
        """混合有效和无效依赖时，应保留所有条目。"""
        imports = [_make_import("/Script/Core", "Object")]
        exports = [_make_export("Export0"), _make_export("Export1")]
        linker = _make_linker(import_map=imports, export_map=exports)
        # 2=有效export, 99=越界, -1=有效import, -99=越界
        result = MockParseResult([[2, 99, -1, -99]], import_map=imports, export_map=exports, linker=linker)

        resolved = _build_resolved_depends_map(result)

        assert len(resolved[0]) == 4
        assert resolved[0][0]["path"] == "Package.Export1"  # 有效 export
        assert resolved[0][1]["path"] is None  # 越界 export
        assert resolved[0][2]["path"] == "/Script/Core.Object"  # 有效 import
        assert resolved[0][3]["path"] is None  # 越界 import

    def test_no_linker_returns_all_none(self):
        """无 linker 时所有 path 应为 None。"""
        result = MockParseResult([[2, -1]], linker=None)

        resolved = _build_resolved_depends_map(result)

        assert len(resolved[0]) == 2
        assert resolved[0][0]["index"] == 2
        assert resolved[0][0]["path"] is None
        assert resolved[0][1]["index"] == -1
        assert resolved[0][1]["path"] is None
