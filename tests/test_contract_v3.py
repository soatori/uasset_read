from tests.fixtures import parse_sample
from uasset_read.projection import project_document


def test_rebuilt_document_declares_v3_and_package_first():
    document = parse_sample("StackOBot_BP_Drone.uasset", depth="package")
    output = project_document(document, depth="package")
    assert output["format_version"] == "3.0"
    assert isinstance(output["projections"], list)
    assert isinstance(output["sidecars"], list)
    assert document.objects
    assert all(obj.id.startswith(("export:", "import:")) for obj in document.objects)


def test_stackobot_package_counts_match_manifest():
    document = parse_sample("StackOBot_BP_Drone.uasset", depth="package")
    assert len(document.objects) == 31
    assert document.package.export_count == 31
