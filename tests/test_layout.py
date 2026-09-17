from tests.fixtures import sample_path
from uasset_read.layout import PackageLayoutDetector
from uasset_read.sources import CompositeSource, MemorySource


def test_loose_sample_selects_legacy_reader():
    source = CompositeSource.from_package(sample_path("StackOBot_BP_Drone.uasset"))
    layout = PackageLayoutDetector().detect(source)
    assert layout.kind == "legacy"
    assert layout.detection_reason == "validated_legacy"


def test_reader_selection_does_not_use_ue_major_version_only():
    # Bytes that look nothing like PACKAGE_FILE_TAG and are not a Zen header.
    layout = PackageLayoutDetector().detect(MemorySource(b"NOT_A_PACKAGE!!!!"))
    assert layout.kind == "unknown"
    assert layout.detection_reason == "unknown"
