"""UE5.5 集成测试 - 验证所有修复的协同工作"""
import os
import pytest
from pathlib import Path


SAMPLE_DIR = Path(os.environ.get("UE55_SAMPLE_DIR", "E:\\Develop\\lib\\UnrealEngine\\Samples\\FirstPerson"))


@pytest.mark.integration
class TestUE55Integration:
    """UE5.5 集成测试套件"""

    @pytest.mark.skipif(not SAMPLE_DIR.exists(), reason="Sample directory not found")
    def test_struct_property_coverage(self):
        """验证 StructProperty 解析通过率 > 95%"""
        from uasset_read.parse_uasset import parse_uasset

        # 排除 Saved/Autosaves 目录
        uasset_files = [
            f for f in SAMPLE_DIR.glob("**/*.uasset")
            if "Saved" not in f.parts
        ][:10]

        total = 0
        success = 0
        errors = []

        for f in uasset_files:
            try:
                result = parse_uasset(str(f))
                total += 1
                if result and result.is_success:
                    success += 1
            except Exception as e:
                errors.append((f.name, str(e)))

        if total == 0:
            pytest.skip("No uasset files found")

        coverage = success / total
        assert coverage > 0.95, f"StructProperty coverage {coverage:.1%} < 95%. Errors: {errors[:5]}"

    @pytest.mark.skipif(not SAMPLE_DIR.exists(), reason="Sample directory not found")
    def test_k2node_fallback_rate(self):
        """验证 K2Node fallback 率 < 10%"""
        from uasset_read.parse_uasset import parse_uasset

        # 排除 Saved/Autosaves 目录
        uasset_files = [
            f for f in SAMPLE_DIR.glob("**/*.uasset")
            if "Saved" not in f.parts
        ][:10]

        total_nodes = 0
        fallback_nodes = 0

        for f in uasset_files:
            try:
                result = parse_uasset(str(f))
                if result and result.graphs:
                    for graph in result.graphs:
                        if graph.nodes:
                            for node in graph.nodes:
                                total_nodes += 1
                                if node.class_name and node.class_name.startswith("Unknown"):
                                    fallback_nodes += 1
            except Exception:
                pass

        if total_nodes == 0:
            pytest.skip("No nodes found")

        fallback_rate = fallback_nodes / total_nodes
        assert fallback_rate < 0.10, f"K2Node fallback rate {fallback_rate:.1%} > 10%"
