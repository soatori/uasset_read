"""
BoxSphereBounds 解析验证测试（Issue #175）。

UE5 中 FBoxSphereBounds UPROPERTY 结构体没有 STRUCT_SerializeNative 标志，
因此始终使用 tagged 格式（PropertyTags 序列化每个字段），而非紧凑二进制格式。

三种变体：
- FBoxSphereBounds3f = TBoxSphereBounds<float, float>  — 28 bytes（紧凑格式）
- FBoxSphereBounds3d = TBoxSphereBounds<double, double> — 56 bytes（紧凑格式）
- FCompactBoxSphereBounds3d = TBoxSphereBounds<double, float> — 40 bytes（紧凑格式）
- FBoxSphereBounds = TBoxSphereBounds<double, float>（UE5 LWC）— tagged 格式（通过 UPROPERTY）

FBoxSphereBounds（UPROPERTY 版本）始终使用 tagged 格式，因为
TBoxSphereBoundsStructOpsTypeTraits 没有设置 WithSerialize 标志。
"""
import os
import pytest

SAMPLES_DIR = "E:/Develop/lib/Samples"
CHAIR_PATH = os.path.join(
    SAMPLES_DIR, "StarterContent", "Content", "StarterContent", "Props", "SM_Chair.uasset"
)


def _find_sample_with_bounds():
    """搜索包含 BoxSphereBounds 属性的样本文件。"""
    from uasset_read.parse_uasset import parse_package

    for root, _dirs, files in os.walk(SAMPLES_DIR):
        for fname in files:
            if not fname.endswith(".uasset"):
                continue
            fpath = os.path.join(root, fname).replace("\\", "/")
            try:
                result = parse_package(fpath, tolerant=True)
                linker = result.linker
                for inst in linker._export_objects:
                    if not inst._preloaded:
                        continue
                    if not hasattr(inst, "serialized_properties") or not inst.serialized_properties:
                        continue
                    for prop in inst.serialized_properties:
                        if "Bounds" in prop.name and hasattr(prop.value, "struct_type"):
                            if prop.value.struct_type == "BoxSphereBounds":
                                return fpath, prop
            except Exception:
                continue
    return None, None


@pytest.mark.integration
class TestBoxSphereBoundsParsing:
    """BoxSphereBounds 解析验证。"""

    def test_box_sphere_bounds_parsed(self):
        """验证 SM_Chair 中的 BoxSphereBounds 能正确解析。"""
        if not os.path.exists(CHAIR_PATH):
            pytest.skip(f"样本文件不存在: {CHAIR_PATH}")

        from uasset_read.parse_uasset import parse_package

        result = parse_package(CHAIR_PATH, tolerant=True)
        linker = result.linker

        found = False
        for inst in linker._export_objects:
            if not inst._preloaded:
                continue
            if not hasattr(inst, "serialized_properties") or not inst.serialized_properties:
                continue
            for prop in inst.serialized_properties:
                if "Bounds" in prop.name and hasattr(prop.value, "struct_type"):
                    if prop.value.struct_type == "BoxSphereBounds":
                        found = True
                        sv = prop.value
                        # 验证结构体被正确解析
                        assert sv.parse_status == "parsed", (
                            f"BoxSphereBounds parse_status 应为 parsed, 实际: {sv.parse_status}"
                        )
                        # 验证包含必要字段
                        assert "Origin" in sv.fields, "缺少 Origin 字段"
                        assert "BoxExtent" in sv.fields, "缺少 BoxExtent 字段"
                        assert "SphereRadius" in sv.fields, "缺少 SphereRadius 字段"

                        origin = sv.fields["Origin"]
                        box_extent = sv.fields["BoxExtent"]
                        sphere_radius = sv.fields["SphereRadius"]

                        # 验证 Origin 和 BoxExtent 是 StructValue（Vector 类型）
                        assert hasattr(origin, "fields"), "Origin 应为 StructValue"
                        assert hasattr(box_extent, "fields"), "BoxExtent 应为 StructValue"

                        # 验证数值合理性（Chair 的 bounds）
                        assert origin.fields["X"] != 0 or origin.fields["Y"] != 0 or origin.fields["Z"] != 0, (
                            "Origin 不应全为零"
                        )
                        assert box_extent.fields["X"] > 0, "BoxExtent.X 应大于 0"
                        assert box_extent.fields["Y"] > 0, "BoxExtent.Y 应大于 0"
                        assert box_extent.fields["Z"] > 0, "BoxExtent.Z 应大于 0"
                        assert sphere_radius > 0, "SphereRadius 应大于 0"

        assert found, "未在 SM_Chair 中找到 BoxSphereBounds 属性"

    def test_box_sphere_bounds_no_warning(self):
        """验证 BoxSphereBounds 解析不产生 '不匹配' 警告。"""
        if not os.path.exists(CHAIR_PATH):
            pytest.skip(f"样本文件不存在: {CHAIR_PATH}")

        import logging
        from uasset_read.parse_uasset import parse_package

        handler = logging.handlers if hasattr(logging, "handlers") else None
        # 捕获 property_types 模块的 WARNING
        logger = logging.getLogger("uasset_read.parsers.property_types")

        class WarningCapture(logging.Handler):
            def __init__(self):
                super().__init__()
                self.warnings = []

            def emit(self, record):
                if record.levelno >= logging.WARNING:
                    self.warnings.append(record.getMessage())

        capture = WarningCapture()
        logger.addHandler(capture)
        try:
            result = parse_package(CHAIR_PATH, tolerant=True)
        finally:
            logger.removeHandler(capture)

        # 检查没有 BoxSphereBounds 相关的警告
        bounds_warnings = [w for w in capture.warnings if "BoxSphereBounds" in w]
        assert len(bounds_warnings) == 0, (
            f"BoxSphereBounds 解析不应产生警告, 实际警告: {bounds_warnings}"
        )

    def test_box_sphere_bounds_tagged_format(self):
        """验证 BoxSphereBounds 在 tagged 格式下（tag.size != 28/56）也能正确解析。"""
        if not os.path.exists(CHAIR_PATH):
            pytest.skip(f"样本文件不存在: {CHAIR_PATH}")

        from uasset_read.parse_uasset import parse_package
        from uasset_read.parsers.property_types import _LWC_TYPE_MAP

        result = parse_package(CHAIR_PATH, tolerant=True)
        linker = result.linker

        for inst in linker._export_objects:
            if not inst._preloaded:
                continue
            if not hasattr(inst, "serialized_properties") or not inst.serialized_properties:
                continue
            for prop in inst.serialized_properties:
                if "Bounds" in prop.name and hasattr(prop.value, "struct_type"):
                    if prop.value.struct_type == "BoxSphereBounds":
                        sv = prop.value
                        float_size, double_size = _LWC_TYPE_MAP["BoxSphereBounds"]
                        # tagged 格式：raw_size 不匹配紧凑格式
                        if sv.raw_size not in (float_size, double_size):
                            # tagged 格式下仍能正确解析
                            assert sv.parse_status == "parsed", (
                                f"tagged 格式 BoxSphereBounds parse_status 应为 parsed, "
                                f"实际: {sv.parse_status}, raw_size: {sv.raw_size}"
                            )
                            assert len(sv.fields) >= 3, (
                                f"tagged 格式 BoxSphereBounds 应有 >= 3 个字段, "
                                f"实际: {list(sv.fields.keys())}"
                            )
